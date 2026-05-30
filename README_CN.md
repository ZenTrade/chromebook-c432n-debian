# ASUS C432N Chromebook — Debian Linux 完整适配方案

让 ASUS C432N Chromebook (Intel N3350 / Apollo Lake) 在 Debian 13 (trixie) + XFCE 上完美运行的全套方案。

[English](README.md)

## 前提条件

**本项目假设你已经完成以下操作：**

1. **使用 [MrChromebox](https://mrchromebox.tech/) 刷写自定义固件** — 这会将 Chrome OS 固件替换为标准 UEFI BIOS，从而可以启动任意操作系统。在 Chrome OS 开发者模式下运行 MrChromebox 固件脚本后再安装 Debian。

2. **安装 Debian 13 (trixie)** — 标准 amd64 安装。本项目不涉及 Chrome OS 转 Debian 的过程，只覆盖安装后的硬件适配。

> ⚠️ **不要与 ChrUbuntu 或 chroot 方案混淆。** 这是在 MrChromebox UEFI 固件上的原生 Debian 安装。

## 硬件信息

| 项目 | 值 |
|------|-----|
| 机型 | ASUS C432N (Coral baseboard) |
| CPU | Intel N3350 (Apollo Lake / BXT) |
| 屏幕 | 14" 1366×768, 实际 DPI ≈ 112 |
| 音频 DSP | Intel SST `[8086:5a98]` |
| 耳机 Codec | DA7219 (SSP1) |
| 扬声器 Amp | MAX98357A (SSP5) |
| 数字麦克风 | DMIC (2ch) |
| 触控板 | Elan Touchpad (多点触控) |
| 蓝牙 | Intel 8087:0a2a (BT 4.2) |
| 系统 | Debian 13 trixie, 内核 6.12+ |
| 驱动栈 | SOF (`snd-sof-pci-intel-apl`) |

## 目录结构

### `driver-patches/` — 驱动补丁（必需）

这些补丁解决 Chromebook 硬件在 Linux 下不工作的问题，是本项目的核心。

| 文件 | 用途 |
|------|------|
| `AUDIO_DRIVER_FIX.md` | 声卡修复完整文档：根因分析、15 个踩坑记录、解决方案 |
| `patch_da7219.py` | 修补内核 `sof_da7219.c`，添加 BXT (Apollo Lake) 支持。修复 MAX98357A 扬声器和 DMIC 不工作的问题。仅使用 Python3 标准库，可直接在 Chromebook 上运行 |
| `parse_nhlt.py` | 解析 ACPI NHLT (Non-HDA Link Table) 音频拓扑表，用于诊断音频路由。仅使用 Python3 标准库 |
| `chromebook-volumed.py` | 音量/亮度键守护进程。直接监听 Intel Virtual Buttons 内核输入设备，绕过 X11 |
| `chromebook-volumed.service` | 音量键守护进程的 systemd 服务文件 |
| `chromebook-osd.sh` | 音量/亮度 OSD 通知脚本。含感知音量曲线（显示 1-90% → 实际 1-10%），统一 5% 步进，纯文字无图标 |
| `chromebook-volume-restore.desktop` | 音量记忆 autostart 文件。开机自动恢复上次关机时的音量和静音状态 |
| `chromebook-gestured.py` | 触控板手势守护进程。直接监听触控板内核输入设备，三指滑动切换工作区/显示桌面 |
| `chromebook-gestured.service` | 手势守护进程的 systemd 服务文件 |
| `dunstrc` | dunst 通知守护进程配置。纯文字、无图标、25% 透明度、统一风格 |
| `policies.json` | Firefox 系统策略。启用 VA-API 硬件视频解码、允许安装扩展 |

**声卡修复根因**：内核模块 `snd_soc_sof_da7219` 的 `MODULE_DEVICE_TABLE` 缺少 `bxt_da7219_mx98357a` 条目。SOF 驱动根据 ACPI 匹配创建名为 `bxt_da7219_mx98357a` 的 platform device，但统一驱动 `sof_da7219.c` 只有 GLK/CML/JSL 条目，没有 BXT 条目。这是上游回归 bug。

**感知音量曲线**：Chromebook 扬声器的有效感知范围是实际 1%-10%（10% 以上人耳无法分辨变化）。OSD 脚本将这个范围校准为显示 1%-90%：

```
显示 0%      → 实际  0%（静音）
显示 1-90%   → 实际 1-10%（扬声器完整感知范围，线性映射）
显示 91-100% → 实际 10-100%（耳机/外接余量）
```

**触控板手势**：

| 手势 | 动作 |
|------|------|
| 三指左滑 | 切换到下一个工作区 |
| 三指右滑 | 切换到上一个工作区 |
| 三指上滑 | 显示桌面 |
| 三指下滑 | 还原窗口 |

---

### `xfce-ui/` — XFCE 界面优化（推荐）

改善 XFCE 桌面的视觉一致性和舒适度。

| 文件 | 用途 |
|------|------|
| `gtk.css` | GTK3 CSS 覆盖。菜单项间距从 26px 提高到 28px（接近 macOS），菜单容器边距增加，pager 工作区指示器在深色面板上可见 |

**部署**：复制到 `~/.config/gtk-3.0/gtk.css`

**其他 UI 优化**（通过 xfconf-query 命令设置，无独立文件）：

```bash
# 字体（Sarasa Gothic SC 在 fontconfig 中的主名称是中文"更纱黑体 SC"）
apt install -y fonts-sarasa-gothic
xfconf-query -c xsettings -p /Gtk/FontName -s "更纱黑体 SC 10"
xfconf-query -c xsettings -p /Gtk/MonospaceFontName -s "Sarasa Fixed SC 10"
xfconf-query -c xsettings -p /Xft/Hinting -s 1
xfconf-query -c xsettings -p /Xft/HintStyle -s "hintslight"

# 合盖待机（绕过 xfce4-power-manager inhibitor 锁）
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/lid-suspend.conf << 'EOF'
[Login]
HandleLidSwitch=suspend
HandleLidSwitchDocked=suspend
LidSwitchIgnoreInhibited=yes
EOF

# Chromebook 键盘映射（Search 键 → Super_L）
cat > /etc/X11/xinit/xinitrc.d/99-chromebook-xmodmap.sh << 'SCRIPT'
#!/bin/bash
xmodmap -e "keycode 133 = Super_L"
SCRIPT
chmod +x /etc/X11/xinit/xinitrc.d/99-chromebook-xmodmap.sh

# PulseAudio 感知音量曲线
echo "flat-volumes = no" >> /etc/pulse/daemon.conf
```

---

### `daily-optimizations/` — 日常使用优化（推荐）

减少系统维护负担，自动保持干净。

| 文件 | 用途 |
|------|------|
| `cleanup-caches.sh` | 关机/重启时自动清理：Firefox 缓存、微信聊天记录、缩略图、GStreamer/Mesa shader 缓存、APT 缓存、日志轮转。保留 cookie 和登录凭证 |
| `cleanup-caches.service` | 清理脚本的 systemd 服务，关机前自动执行 |

**其他日常优化**（通过命令设置，无独立文件）：

```bash
# 日志大小限制（最大 20M，保留 2 周）
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/size-limit.conf << 'EOF'
[Journal]
SystemMaxUse=20M
MaxRetentionSec=2week
EOF

# APT 自动清理（每 7 天清理下载缓存）
cat > /etc/apt/apt.conf.d/99-auto-clean << 'EOF'
APT::Periodic::AutocleanInterval "7";
APT::Periodic::MaxAge "7";
EOF

# 开机速度：禁用不必要的服务
systemctl disable NetworkManager-wait-online.service
systemctl disable ModemManager.service
systemctl disable avahi-daemon.service
systemctl disable cups.service
systemctl disable accounts-daemon.service

# 内核模块黑名单
cat > /etc/modprobe.d/chromebook-optimizations.conf << 'EOF'
blacklist mach_patch
blacklist snd_soc_avs
blacklist snd_soc_avs_da7219
blacklist snd_soc_avs_dmic
blacklist snd_soc_avs_hdaudio
blacklist microcode
blacklist edac_pnd2
blacklist cros_ec_lpcs
blacklist parport_pc
blacklist ppdev
blacklist lp
EOF

# GRUB 内核参数（跳过无用硬件检测）
# 编辑 /etc/default/grub：
# GRUB_CMDLINE_LINUX_DEFAULT="quiet module_blacklist=edac_pnd2 i915.enable_lspcon=0"
# GRUB_TIMEOUT=0
# 然后运行 update-grub
```

---

### `personal-preferences/` — 个人偏好（可选，仅供参考）

这些是作者的个人使用习惯，**并非必需**。其他用户可根据自身需求选择性参考。

| 文件 | 用途 |
|------|------|
| `r.py` | SSH 远程执行工具。连接参数需自行配置。需要 `paramiko`（`pip install paramiko`） |

**其他个人偏好**（无独立文件，仅供参考）：

- 安装 blueman（蓝牙图形管理）、flameshot（截图）、thunar（文件管理器）
- 安装微信/飞书 Linux 版
- 安装 fcitx5 中文输入法
- 安装 WhiteSur 主题 + Papirus 图标
- 卸载不需要的软件包（quodlibet、xsane、system-config-printer 等）
- 设置用户自动登录

## 快速部署

### 1. 修复声卡驱动

```bash
# 在 Chromebook 上，以 root 执行：
python3 driver-patches/patch_da7219.py
# 然后编译并安装模块（详见 AUDIO_DRIVER_FIX.md）
reboot
```

详见 [AUDIO_DRIVER_FIX.md](driver-patches/AUDIO_DRIVER_FIX.md)。

### 2. 部署 OSD 和手势

```bash
cp driver-patches/chromebook-osd.sh /usr/local/bin/ && chmod +x /usr/local/bin/chromebook-osd.sh
cp driver-patches/chromebook-volumed.py /usr/local/bin/ && chmod +x /usr/local/bin/chromebook-volumed.py
cp driver-patches/chromebook-gestured.py /usr/local/bin/ && chmod +x /usr/local/bin/chromebook-gestured.py
cp driver-patches/chromebook-volumed.service /etc/systemd/system/
cp driver-patches/chromebook-gestured.service /etc/systemd/system/
cp driver-patches/chromebook-volume-restore.desktop /home/cc/.config/autostart/
systemctl enable --now chromebook-volumed
systemctl enable --now chromebook-gestured
```

### 3. 部署 dunst 和 UI 配置

```bash
apt install -y dunst
cp driver-patches/dunstrc /etc/dunst/
cp xfce-ui/gtk.css /home/cc/.config/gtk-3.0/
```

### 4. 部署自动清理

```bash
cp daily-optimizations/cleanup-caches.sh /usr/local/bin/ && chmod +x /usr/local/bin/cleanup-caches.sh
cp daily-optimizations/cleanup-caches.service /etc/systemd/system/
systemctl enable cleanup-caches
```

### 5. Firefox VA-API 硬解

```bash
apt install -y intel-media-va-driver mesa-va-drivers
mkdir -p /usr/share/firefox-esr/distribution
cp driver-patches/policies.json /usr/share/firefox-esr/distribution/
```

## License

MIT
