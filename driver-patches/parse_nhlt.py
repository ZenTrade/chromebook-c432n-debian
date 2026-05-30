#!/usr/bin/env python3
"""
parse_nhlt.py — NHLT (Non-HDA Link Table) 二进制解析工具
=========================================================

用法：
    1. 从 Chromebook 读取 NHLT 表：
       python r.py "cat /sys/firmware/acpi/tables/NHLT" > tmp/nhlt.bin
    2. 运行解析：
       python parse_nhlt.py

功能：解析 ACPI NHLT 表，列出所有音频端点信息：
  - link_type: HDA/DSP/SSP/PDM/DMIC/SoundWire
  - direction: Playback/Capture
  - vendor_id / device_id: codec 标识
  - format: 通道数、采样率、位深

用途：调试音频驱动时确认 SSP 端口映射。
      例如 ASUS C432N 的 NHLT 显示 ssp_mask=0x22 (SSP1+SSP5)，
      对应 DA7219 在 SSP1、MAX98357A 在 SSP5。

输入文件：tmp/nhlt.bin（相对于脚本所在目录）
"""

import struct
import os

local_path = os.path.join(os.path.dirname(__file__), "tmp", "nhlt.bin")
data = open(local_path, 'rb').read()
print(f"NHLT total size: {len(data)} bytes")

print(f"\nFirst 80 bytes hex:")
for i in range(0, min(80, len(data)), 16):
    hex_str = ' '.join(f'{data[j]:02x}' for j in range(i, min(i+16, len(data))))
    ascii_str = ''.join(chr(data[j]) if 0x20 <= data[j] <= 0x7e else '.' for j in range(i, min(i+16, len(data))))
    print(f"  {i:04x}: {hex_str:<48s}  {ascii_str}")

ACPI_HEADER_SIZE = 36
print(f"\nByte at offset {ACPI_HEADER_SIZE} (endpoint_count): 0x{data[ACPI_HEADER_SIZE]:02x} = {data[ACPI_HEADER_SIZE]}")

ep_count = data[ACPI_HEADER_SIZE]
off = ACPI_HEADER_SIZE + 1

print(f"\nFirst endpoint starts at offset {off}")
print(f"Raw bytes at offset {off}:")
for i in range(off, min(off + 80, len(data)), 16):
    hex_str = ' '.join(f'{data[j]:02x}' for j in range(i, min(i+16, len(data))))
    ascii_str = ''.join(chr(data[j]) if 0x20 <= data[j] <= 0x7e else '.' for j in range(i, min(i+16, len(data))))
    print(f"  {i:04x}: {hex_str:<48s}  {ascii_str}")

desc_len = struct.unpack_from('<I', data, off)[0]
print(f"\nFirst endpoint length: {desc_len} (0x{desc_len:x})")
print(f"  link_type (off+4): {data[off+4]}")
print(f"  instance_id (off+5): {data[off+5]}")
print(f"  vendor_id (off+6): 0x{struct.unpack_from('<H', data, off+6)[0]:04x}")
print(f"  device_id (off+8): 0x{struct.unpack_from('<H', data, off+8)[0]:04x}")

types = {0: 'HDA', 1: 'DSP', 2: 'SSP', 3: 'PDM', 4: 'SoundWire', 5: 'DMIC'}
dirs = {0: 'Render/Playback', 1: 'Capture', 2: 'Loopback'}

for i in range(ep_count):
    if off + 4 > len(data):
        break
    desc_len = struct.unpack_from('<I', data, off)[0]
    if off + desc_len > len(data) or desc_len < 20:
        print(f"\n  Endpoint {i}: BAD len={desc_len} at offset {off}")
        break

    link_type = data[off + 4]
    instance_id = data[off + 5]
    vendor_id = struct.unpack_from('<H', data, off + 6)[0]
    device_id = struct.unpack_from('<H', data, off + 8)[0]
    revision_id = struct.unpack_from('<H', data, off + 10)[0]
    subsystem_id = struct.unpack_from('<I', data, off + 12)[0]
    device_type = data[off + 16]
    direction = data[off + 17]
    virtual_bus_id = data[off + 18]
    hw_config = struct.unpack_from('<I', data, off + 19)[0]

    print(f"\n  Endpoint {i}: len={desc_len} type={types.get(link_type, f'?{link_type}')} "
          f"dir={dirs.get(direction, f'?{direction}')} instance={instance_id}")
    print(f"    vendor=0x{vendor_id:04x} device=0x{device_id:04x} rev={revision_id}")
    print(f"    subsystem=0x{subsystem_id:08x} devtype={device_type} vbus={virtual_bus_id} hw=0x{hw_config:08x}")

    fmt_off = off + 23
    if fmt_off + 4 <= off + desc_len:
        fmt_count = struct.unpack_from('<I', data, fmt_off)[0]
        fmt_off += 4
        print(f"    fmt_count={fmt_count} (at offset {off+23})")

        if fmt_count > 0 and fmt_count < 20:
            for j in range(fmt_count):
                if fmt_off + 18 > off + desc_len:
                    break
                wFormat = struct.unpack_from('<H', data, fmt_off)[0]
                nChannels = struct.unpack_from('<H', data, fmt_off + 2)[0]
                nSamplesPerSec = struct.unpack_from('<I', data, fmt_off + 4)[0]
                nBitsPerSample = struct.unpack_from('<H', data, fmt_off + 14)[0]
                cbSize = struct.unpack_from('<H', data, fmt_off + 16)[0]
                print(f"    Format {j}: ch={nChannels} rate={nSamplesPerSec} bits={nBitsPerSample} cbSize={cbSize}")
                fmt_off += 18 + cbSize
    else:
        print(f"    No fmt section (desc too short)")

    off += desc_len

print(f"\nTotal parsed: {off} bytes (of {len(data)})")
