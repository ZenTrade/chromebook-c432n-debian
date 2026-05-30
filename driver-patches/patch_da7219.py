#!/usr/bin/env python3
"""
patch_da7219.py — 为内核源码 sof_da7219.c 添加 BXT (Apollo Lake) 支持
========================================================================

用法：
    1. 确保 Chromebook 上已有内核源码：
       /root/linux-src/usr/src/linux-source-6.12/sound/soc/intel/boards/sof_da7219.c
    2. 在 Chromebook 上运行：python3 patch_da7219.py
    3. 或从 Windows 远程运行：python upload_patch.py（会自动上传并执行本脚本）

功能：对 sof_da7219.c 做以下 4 处修改，使 SOF 机器驱动能匹配 BXT 平台：

  修改 1: 在 SOF_DA7219_MCLK_EN (BIT(3)) 之后添加 SOF_DA7219_BXT_BOARD (BIT(4))
          这是 BXT 板子的 quirk 标识位

  修改 2: 在 JSL_LINK_ORDER 之后添加 BXT_LINK_ORDER
          定义 BXT 的 DAI link 创建顺序：AMP(SPK) → CODEC(HP) → DMIC01 → HDMI

  修改 3: 在 audio_probe() 的 JSL 处理分支之后添加 BXT 处理分支
          设置 dmic_be_num=1, link_order_overwrite=BXT_LINK_ORDER,
          当 amp_type=CODEC_MAX98357A 时设置 card_name="bxtda7219max"

  修改 4: 在 board_ids[] 的空终止符之前添加 BXT 条目
          .name = "bxt_da7219_mx98357a"
          .driver_data = SOF_DA7219_BXT_BOARD | SOF_SSP_PORT_CODEC(1) | SOF_SSP_PORT_AMP(5)

SSP 端口映射（来自 NHLT 表 ssp_mask=0x22）：
  - SSP1: DA7219 耳机 codec (SOF_SSP_PORT_CODEC(1))
  - SSP5: MAX98357A 扬声器 amp (SOF_SSP_PORT_AMP(5))

注意：
  - 本脚本使用基于行内容的模式匹配，而非字符串替换，以避免 tab/空格差异问题
  - 修改前会保留 .orig 备份（由 Python open() 覆盖写入，建议先手动备份）
  - 修改后打印所有包含 BXT/bxt 的行以供验证
"""

SRC = '/root/linux-src/usr/src/linux-source-6.12/sound/soc/intel/boards/sof_da7219.c'

with open(SRC, 'r') as f:
    lines = f.readlines()

new_lines = []
i = 0
while i < len(lines):
    line = lines[i]

    # 1. After SOF_DA7219_MCLK_EN line, add SOF_DA7219_BXT_BOARD
    if '#define SOF_DA7219_MCLK_EN' in line and 'BIT(3)' in line:
        new_lines.append(line)
        new_lines.append('#define SOF_DA7219_BXT_BOARD\t\t\tBIT(4)\n')
        i += 1
        continue

    # 2. After JSL_LINK_ORDER closing paren, add BXT_LINK_ORDER
    if line.strip() == 'SOF_LINK_NONE)' and i > 0:
        for j in range(max(0, i-10), i):
            if 'JSL_LINK_ORDER' in lines[j]:
                new_lines.append(line)
                new_lines.append('\n')
                new_lines.append('#define BXT_LINK_ORDER\tSOF_LINK_ORDER(SOF_LINK_AMP,\t\t\\\n')
                new_lines.append('\t\t\t\t\tSOF_LINK_CODEC,\t\t\\\n')
                new_lines.append('\t\t\t\t\tSOF_LINK_DMIC01,\t\t\\\n')
                new_lines.append('\t\t\t\t\tSOF_LINK_IDISP_HDMI,\t\\\n')
                new_lines.append('\t\t\t\t\tSOF_LINK_NONE,\t\t\\\n')
                new_lines.append('\t\t\t\t\tSOF_LINK_NONE,\t\t\\\n')
                new_lines.append('\t\t\t\t\tSOF_LINK_NONE)\n')
                i += 1
                break
        else:
            new_lines.append(line)
            i += 1
        continue

    # 3. Replace JSL board block closing brace with } else if BXT block
    if (line.strip() == '}' and i + 2 < len(lines) and
        'SOF_DA7219_MCLK_EN' in lines[i + 2]):
        new_lines.append('\t} else if (board_quirk & SOF_DA7219_BXT_BOARD) {\n')
        new_lines.append('\t\t/* dmic16k not support */\n')
        new_lines.append('\t\tctx->dmic_be_num = 1;\n')
        new_lines.append('\t\t/* overwrite the DAI link order for BXT boards */\n')
        new_lines.append('\t\tctx->link_order_overwrite = BXT_LINK_ORDER;\n')
        new_lines.append('\t\t/* backward-compatible with existing devices */\n')
        new_lines.append('\t\tswitch (ctx->amp_type) {\n')
        new_lines.append('\t\tcase CODEC_MAX98357A:\n')
        new_lines.append('\t\t\tcard_name = devm_kstrdup(&pdev->dev, "bxtda7219max",\n')
        new_lines.append('\t\t\t\t\t\t GFP_KERNEL);\n')
        new_lines.append('\t\t\tif (!card_name)\n')
        new_lines.append('\t\t\t\treturn -ENOMEM;\n')
        new_lines.append('\t\t\tcard_da7219.name = card_name;\n')
        new_lines.append('\t\t\tbreak;\n')
        new_lines.append('\t\tdefault:\n')
        new_lines.append('\t\t\tbreak;\n')
        new_lines.append('\t\t}\n')
        new_lines.append('\t}\n')
        i += 1
        continue

    # 4. Before the empty terminator entry in board_ids[], add BXT entry
    #    SSP1 = DA7219 (headset codec), SSP5 = MAX98357A (speaker amp)
    if line.strip() == '{ }' and i + 2 < len(lines) and 'MODULE_DEVICE_TABLE' in lines[i + 2]:
        new_lines.append('\t{\n')
        new_lines.append('\t\t.name = "bxt_da7219_mx98357a",\n')
        new_lines.append('\t\t.driver_data = (kernel_ulong_t)(SOF_DA7219_BXT_BOARD |\n')
        new_lines.append('\t\t\t\t\tSOF_SSP_PORT_CODEC(1) |\n')
        new_lines.append('\t\t\t\t\tSOF_SSP_PORT_AMP(5)),\n')
        new_lines.append('\t},\n')
        new_lines.append(line)
        i += 1
        continue

    new_lines.append(line)
    i += 1

with open(SRC, 'w') as f:
    f.writelines(new_lines)

print('Modification complete!')

with open(SRC, 'r') as f:
    content = f.read()

for i, line in enumerate(content.split('\n'), 1):
    if any(kw in line for kw in ['BXT', 'bxt_da7219_mx98357a']):
        print(f'L{i}: {line}')
