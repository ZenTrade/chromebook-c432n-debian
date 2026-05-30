# ASUS C432N Chromebook (Apollo Lake) — Debian 13 扬声器驱动修复

## 硬件信息

| 项目 | 值 |
|------|-----|
| 机型 | ASUS C432N (Coral baseboard) |
| CPU | Intel N3350 (Apollo Lake / BXT) |
| 音频 DSP | Intel SST `[8086:5a98]` |
| 耳机 Codec | DA7219，挂载在 SSP1 |
| 扬声器 Amp | MAX98357A，挂载在 SSP5 |
| 数字麦克风 | DMIC (2ch) |
| 系统 | Debian 13 trixie, 内核 `6.12.90+deb13-amd64` |
| 驱动栈 | SOF (`snd-sof-pci-intel-apl`) |

## 根因

内核模块 `snd_soc_sof_da7219` 的 `MODULE_DEVICE_TABLE(platform, board_ids[])` 缺少 `bxt_da7219_mx98357a` 条目。

SOF 驱动在 ACPI 匹配阶段会根据 `soc-acpi-intel-bxt-match.c` 创建名为 `bxt_da7219_mx98357a` 的 platform device，
但 `sof_da7219.c` 的 `board_ids[]` 中只有 GLK/CML/JSL 条目，没有 BXT 条目，
导致 platform device 找不到 driver，扬声器（MAX98357A）和 DMIC 无法工作。

这是上游回归 bug：旧的独立驱动 `bxt_da7219_max98357a.c` 被移除后，BXT 支持未迁移到新的统一驱动 `sof_da7219.c`。

---

## 踩过的坑（按严重程度排序）

### 坑 1：xz 压缩模块内核解压失败（`decompression failed with status 6`）

**现象**：用 `xz -9` 压缩的 `.ko.xz` 模块，`modinfo` 能读取，但内核加载时报 `decompression failed with status 6`。

**原因**：Debian 内核的 xz 解码器可能对某些 xz 压缩参数不兼容。`xz -9` 使用了内核解码器不支持的 LZMA2 参数。

**解决**：直接安装未压缩的 `.ko` 文件，不压缩。内核会自动识别未压缩的模块。

### 坑 2：vermagic 不匹配

**现象**：编译出的模块 vermagic 是 `6.12.90 SMP preempt...`，缺少 `+deb13-amd64` 后缀。

**原因**：`include/generated/utsrelease.h` 在 `make modules_prepare` 时就已生成，之后修改 `.config` 中的 `CONFIG_LOCALVERSION` 不会自动更新。

**解决**：修改 `.config` 后，手动覆盖 `include/generated/utsrelease.h`，然后重新编译模块。

### 坑 3：SSP 端口映射错误

**现象**：模块加载成功但 topology 加载失败，`ASoC: failed to load widget SSP1.OUT`。

**原因**：最初根据 ACPI 描述将 DA7219 配置在 SSP2，但 NHLT 表显示 `ssp_mask=0x22`（bit1=SSP1, bit5=SSP5），实际硬件是 SSP1+SSP5。

**解决**：将 `SOF_SSP_PORT_CODEC(2)` 改为 `SOF_SSP_PORT_CODEC(1)`。**NHLT 永远比 ACPI 更可信。**

### 坑 4：PulseAudio `default-sink` 指向不存在的 sink

**现象**：PulseAudio sink 存在且状态正常，但 `paplay` 报 `流错误：无此实体`，Firefox 无声。

**原因**：`/etc/pulse/client.conf.d/chromebook.conf` 设置了 `default-sink = headset`，这是之前 ChromeOS 时代的配置，指向一个不存在的 sink。PulseAudio 尝试将流路由到不存在的 sink，导致失败。

**解决**：修改 `chromebook.conf`，将 `default-sink` 指向正确的 ALSA sink 名称。

### 坑 5：PulseAudio 自动切回 off profile

**现象**：手动 `set-card-profile 0 output:stereo-fallback` 后，PulseAudio 过一会自动切回 `off`。

**原因**：`module-switch-on-port-available` 检测到扬声器端口 "not available"（因为 `Line Out Jack` 检测为 off），自动将 profile 切回 `off`。

**解决**：在用户级 `default.pa` 中 `unload-module module-switch-on-port-available`。

### 坑 6：apt/dpkg 被锁

**现象**：backports 内核安装进程 (PID 2104) 长时间占用 dpkg 锁，无法 `apt install`。

**解决**：手动下载 `.deb` 包，用 `dpkg-deb -x` 提取到本地目录（如 `/root/local-prefix/`），绕过 dpkg。

### 坑 7：编译依赖缺失（libssl-dev, libelf-dev, flex, bison, m4）

**现象**：`make modules_prepare` 依次报错缺少 openssl 头文件、objtool 编译失败等。

**解决**：手动下载 `.deb` 包并提取。注意多架构头文件（如 `opensslconf.h` 在 `x86_64-linux-gnu/openssl/` 下）需要复制到 `/usr/include/openssl/`。objtool 可以从 `/lib/modules/$(uname -r)/build/tools/objtool/` 直接复制。

### 坑 8：`module.lds` 缺失

**现象**：编译模块时 `scripts/module.lds` 不存在。

**解决**：从 `scripts/module.lds.S` 手动预处理生成：
```bash
gcc -E -P -D__KERNEL__ -I./include -I./arch/x86/include ... -o scripts/module.lds scripts/module.lds.S
```

### 坑 9：运行时 rmmod snd_* 模块导致 D 状态死锁（⚠️ 致命）

**现象**：`rmmod snd_sof_pci_intel_apl` 或 `rmmod snd_soc_acpi_intel_match` 后，PulseAudio 和 Xorg 进入 D 状态（不可中断睡眠），`kill -9` 无效，`systemctl restart lightdm` 也卡住，系统无法正常关机或重启。

**原因**：SOF 驱动在 probe 时会注册 DMA 传输、固件加载等内核资源。PulseAudio 持有 `/dev/snd/*` 文件描述符，Xorg 通过 PulseAudio 间接依赖音频子系统。rmmod 时内核尝试释放这些资源，但进程仍在使用，导致死锁。D 状态进程无法被信号杀死，只能重启。

**解决**：**永远不要在运行时 rmmod 任何 snd_* 模块。** 所有音频驱动的修改必须通过编译替换 `.ko` 文件 + reboot 完成。如果系统已卡死，唯一恢复方式是 `echo b > /proc/sysrq-trigger`（需先 `echo 1 > /proc/sys/kernel/sysrq`）或长按电源键强制关机。

### 坑 10：内存补丁路线全线失败（⚠️ 浪费大量时间）

**现象**：尝试了多种运行时修改内核内存的方法，全部失败：

| 方法 | 失败原因 |
|------|----------|
| `ioremap_cache` 修改 NHLT 物理内存 | 修改后 `acpi_get_table` 仍返回原始大小，SOF 驱动读不到修改 |
| `kprobe` 钩取未导出内核函数 | `register_kprobe` 返回 `-ENOENT`，未导出符号无法通过 kprobe 获取 |
| `__symbol_get` 获取 machine table 符号 | 部分数据符号无法通过此方式获取 |
| 修改 machine table `drv_name` 指针（bxt→glk） | 写入成功，但 `glk_da7219_def` 驱动的 DAI link 用 SSP1，而 topology `sof-apl-da7219.tplg` 引用 SSP5，导致 `ASoC: failed to add widget SSP5.OUT` (-22) |
| 修改 machine table `id` 字段（bxt→glk） | 写入成功，但需要卸载重载 `snd_soc_acpi_intel_match` 才能生效，触发坑 9 的 D 状态死锁 |
| `modprobe install` hook 自动执行补丁 | hook 脚本内调用 `modprobe snd_soc_acpi_intel_match`，触发 hook 自身，形成无限递归 |
| `find_ptr.ko` 扫描内核内存 | KASLR 导致每次重启后模块地址变化，硬编码地址在新启动后失效 |

**结论**：运行时内存补丁在这条路线上不可行。正确做法是从源码编译替换模块。

### 坑 11：ACPI CPIO override 导致内核 panic

**现象**：将修改后的 NHLT 表打包为 `acpi_override.cpio`，通过 GRUB 的 `acpi_tbl_override=1` 加载，启动时 kernel panic：`VFS: Unable to mount root fs on unknown-block(0,0)`。

**原因**：initrd 中的 ACPI 表覆盖机制与 Debian 的 initramfs 格式不兼容，导致内核无法正确解析后续的 initrd 内容，找不到根文件系统。

**解决**：不要使用 ACPI CPIO override。如果必须修改 ACPI 表，考虑编译自定义内核或使用 DSDT override（但后者同样有风险）。

### 坑 12：dbus-x11 缺失导致桌面登录失败

**现象**：LightDM 登录界面输入密码后弹出错误"未能与设置服务器联系"、"执行子进程 dbus-launch 失败（没有那个文件或目录）"，关闭错误提示后鼠标光标消失，键盘无反应。

**原因**：`dbus-launch` 命令由 `dbus-x11` 包提供，Debian 13 默认不安装此包。XFCE 会话启动依赖 `dbus-launch`，缺失时整个桌面会话无法初始化。

**解决**：
```bash
apt install dbus-x11
systemctl restart lightdm
```

### 坑 13：GLK 驱动与 APL topology 的 SSP 不匹配

**现象**：将 machine table `drv_name` 从 `bxt_da7219_mx98357a` 改为 `glk_da7219_def` 后，驱动成功绑定，但 topology 加载失败：`ASoC: failed to add widget SSP5.OUT`，错误码 -22 (EINVAL)。

**原因**：
- `sof-apl-da7219.tplg`（APL 平台 topology）定义了 SSP5 用于扬声器（MAX98357A）
- `glk_da7219_def` 驱动的 DAI link 定义扬声器在 SSP1
- 两者 SSP 编号不一致，topology 中的 SSP5 widget 在驱动中找不到对应的 DAI link

**关键对比**：

| 驱动 | 耳机 SSP | 扬声器 SSP | 对应 topology |
|------|----------|-----------|---------------|
| `bxt_da7219_mx98357a`（缺失，上游原版） | SSP2 | SSP5 | `sof-apl-da7219.tplg` |
| `bxt_da7219_mx98357a`（缺失，本机修正版） | SSP1 | SSP5 | `sof-apl-da7219.tplg` |
| `glk_da7219_def`（存在） | SSP1 | SSP1 | `sof-glk-da7219.tplg` |

> ⚠️ 上游原版 `bxt_da7219_mx98357a` 驱动将 DA7219 配置在 SSP2，但本机 NHLT 表显示 `ssp_mask=0x22`（SSP1+SSP5），DA7219 实际在 SSP1。编译时需将 `SOF_SSP_PORT_CODEC` 从 2 改为 1（见坑 3）。

**结论**：不能简单地将 BXT 的 `drv_name` 指向 GLK 驱动，因为 GLK 驱动的扬声器在 SSP1，而本机扬声器在 SSP5。必须在 `sof_da7219.c` 中新增 BXT 专用条目，指定 SSP1（耳机）+ SSP5（扬声器）。

### 坑 14：KASLR 使硬编码内核地址在重启后失效

**现象**：在当前启动中通过 `find_ptr.ko` 扫描到 `bxt_da7219_mx98357a` 字符串地址为 `0xffffffffc101d8f7`，重启后同一地址读取到的是无关数据。

**原因**：KASLR (Kernel Address Space Layout Randomization) 在每次启动时随机化内核模块的加载地址。`/proc/modules` 中显示的地址每次都不同。

**教训**：任何依赖硬编码内核地址的方案都不具备跨重启的持久性。这也进一步印证了坑 10 的结论——内存补丁路线不可行。

### 坑 15：speaker-test 进程卡入 D 状态

**现象**：运行 `speaker-test` 测试扬声器时，如果底层驱动有问题，speaker-test 进程会进入 D 状态，无法 `kill -9`，也无法正常关机。

**原因**：speaker-test 打开了 ALSA PCM 设备，当驱动层出现死锁或资源未释放时，进程在内核态等待 I/O，进入不可中断睡眠。

**解决**：避免在驱动不稳定时运行 speaker-test。如果已卡死，用 `echo b > /proc/sysrq-trigger` 强制重启。

---

## 成功部署步骤（从零开始）

### 前提

- Debian 13 trixie 已安装，内核 `6.12.90+deb13-amd64`
- SSH 连接可用（本工作区用 `r.py` 通过 paramiko 远程连接 Chromebook）
- 有 root 权限

### 步骤 1：安装编译依赖

```bash
apt install -y build-essential bc bison flex libelf-dev libssl-dev \
  dwarves zstd kmod cpio rsync linux-headers-$(uname -r)
```

如果 apt 被锁，手动下载 `.deb` 并提取到 `/root/local-prefix/`。

### 步骤 2：获取内核源码

```bash
mkdir -p /root/linux-src && cd /root/linux-src
apt source linux
# 校验源码版本与 uname -r 一致
head -5 linux-6.12.*/Makefile
```

### 步骤 3：配置内核

```bash
cd /root/linux-src/usr/src/linux-source-6.12/
cp /boot/config-$(uname -r) .config

# 设置 LOCALVERSION 使 vermagic 匹配
# 在 .config 中找到 CONFIG_LOCALVERSION="" 改为 CONFIG_LOCALVERSION="+deb13-amd64"

make olddefconfig
make modules_prepare
```

### 步骤 4：打补丁

运行 `patch_da7219.py`（在 Chromebook 上执行），对 `sof_da7219.c` 添加 4 处修改：
1. `SOF_DA7219_BXT_BOARD BIT(4)` 宏定义
2. `BXT_LINK_ORDER` (AMP→CODEC→DMIC01→HDMI)
3. `audio_probe()` 中的 BXT 处理分支
4. `board_ids[]` 中的 `bxt_da7219_mx98357a` 条目

### 步骤 5：编译模块

```bash
cd /root/linux-src/usr/src/linux-source-6.12/
make M=sound/soc/intel/boards/ modules
```

验证：
```bash
modinfo sound/soc/intel/boards/snd-soc-sof_da7219.ko | grep -E 'vermagic|alias:bxt'
# 应输出：
# vermagic:       6.12.90+deb13-amd64 SMP preempt mod_unload modversions
# alias:          platform:bxt_da7219_mx98357a
```

### 步骤 6：安装模块

```bash
# 备份旧模块
TS=$(date +%s)
mkdir -p ~/audio-backup/$TS
cp /lib/modules/$(uname -r)/kernel/sound/soc/intel/boards/snd-soc-sof_da7219.ko.* ~/audio-backup/$TS/

# 安装新模块（未压缩）
cp sound/soc/intel/boards/snd-soc-sof_da7219.ko \
   /lib/modules/$(uname -r)/kernel/sound/soc/intel/boards/

depmod -a
update-initramfs -u
```

### 步骤 7：配置 PulseAudio

运行 `deploy_audio.py`（从 Windows 远程执行），自动完成：
1. 创建 UCM 配置文件
2. 修复 `/etc/pulse/client.conf.d/chromebook.conf`
3. 创建用户级 `default.pa`（卸载 `module-switch-on-port-available`）
4. 创建 systemd 服务自动激活 card profile

### 步骤 8：Reboot 验证

```bash
uname -r                          # 6.12.90+deb13-amd64
aplay -l                          # 应列出 Speakers / Headset / HDMI
speaker-test -D plughw:CARD=sofbxtda7219max,DEV=0 -c 2 -t wav -l 1
pactl list sinks short            # 应有 alsa_output...stereo-fallback
pactl list sink-inputs short      # Firefox 播放时应有音频流
```

---

## 一键部署（推荐）

如果 Chromebook 已准备好内核源码和编译依赖，可以直接从 Windows 运行：

```powershell
python deploy_audio.py
```

此脚本自动完成步骤 4-8（打补丁→编译→安装→UCM→PulseAudio→systemd→reboot→验证）。

---

## Chromebook 桌面配置（新系统安装后）

音频驱动修复完成后，还需要配置 Chromebook 的桌面环境：

```bash
# 1. 键盘和 XFCE 基础配置
bash setup_keyboard_theme.sh

# 2. 安装 WhiteSur macOS 风格主题
bash setup_themes.sh

# 3. Firefox 硬件加速
cp firefox_user.js ~/.mozilla/firefox/<profile>/.default/user.js
```

---

## 文件清单

### 核心文件（音频驱动修复）

| 文件 | 用途 |
|------|------|
| `deploy_audio.py` | **一键部署脚本**：从 Windows 远程完成步骤 4-7 的所有操作 |
| `r.py` | SSH 远程执行工具：`python r.py "command"` |
| `patch_da7219.py` | 内核源码补丁：为 sof_da7219.c 添加 BXT 支持（4 处修改） |
| `upload_patch.py` | 上传并执行 patch_da7219.py（仅补丁，不编译；完整部署用 deploy_audio.py） |
| `parse_nhlt.py` | NHLT 表解析工具：调试时用于确认 SSP 端口映射 |
| `AUDIO_DRIVER_FIX.md` | 本文档：工作成果、踩坑记录、部署步骤 |

### Chromebook 桌面配置

| 文件 | 用途 |
|------|------|
| `chromebook-init.sh` | XFCE 桌面初始化脚本（主题、快捷键、音频重启），登录时自动执行 |
| `chromebook-osd.sh` | 音量/亮度 OSD 通知脚本，由 XFCE 快捷键调用 |
| `chromebook-keys.sh` | Chromebook 顶行按键 xmodmap 映射（F1-F10 → 多媒体键） |
| `setup_keyboard_theme.sh` | 键盘和 XFCE 一键配置脚本（新系统首次配置） |
| `setup_themes.sh` | WhiteSur macOS 风格主题安装脚本（从 GitHub 下载） |
| `firefox_user.js` | Firefox VA-API 硬件加速配置（复制到 profile 目录） |
| `firefox-vaapi-config.md` | Firefox VAAPI 配置详细说明 |

### 备选方案参考（未使用，保留供参考）

| 目录/文件 | 说明 |
|-----------|------|
| `snd_soc_avs_max98357a/` | 路线3 (driver_override) 的 AVS out-of-tree 驱动，未使用 |
| `nhlt_patcher/` | 调试阶段的 NHLT 表补丁工具集（9 个内核模块），未使用 |

### 第三方主题资源

| 目录 | 说明 |
|------|------|
| `WhiteSur-gtk-theme/` | WhiteSur GTK 主题源码（也可从 GitHub 下载） |
| `WhiteSur-icon-theme/` | WhiteSur 图标主题源码（也可从 GitHub 下载） |
| `WhiteSur-cursors/` | WhiteSur 光标主题源码（也可从 GitHub 下载） |

---

## Chromebook 上的关键部署文件

以下是成功部署后 Chromebook 上的文件，重装系统后需要重新创建：

| 路径 | 用途 |
|------|------|
| `/lib/modules/6.12.90+deb13-amd64/kernel/sound/soc/intel/boards/snd-soc-sof_da7219.ko` | 编译后的模块（未压缩，勿用 xz 压缩！） |
| `/usr/share/alsa/ucm2/Intel/sof-bxtda7219max/` | UCM 配置（sof-bxtda7219max.conf, HiFi.conf, Hdmi.conf） |
| `/usr/share/alsa/ucm2/conf.d/sof-bxtda7219max/sof-bxtda7219max.conf` | UCM 注册文件 |
| `/etc/pulse/client.conf.d/chromebook.conf` | PulseAudio 默认 sink/source 配置 |
| `/home/cc/.config/pulse/default.pa` | 用户级 PA 配置（卸载 module-switch-on-port-available） |
| `/etc/systemd/system/bxt-audio-profile-lightdm.service` | 开机自动激活 card profile |
| `/usr/local/bin/chromebook-init.sh` | XFCE 桌面初始化脚本 |
| `/usr/local/bin/chromebook-osd.sh` | 音量/亮度 OSD 脚本 |
| `/home/cc/.Xmodmap` | Chromebook 键盘映射 |
