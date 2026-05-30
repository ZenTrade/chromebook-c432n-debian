#!/usr/bin/env python3
"""
chromebook-volumed.py — Chromebook 音量/亮度守护进程

直接监听内核输入设备（绕过 X11 键绑定），检测音量/亮度键按下事件，
调用 chromebook-osd.sh 来设置音量/亮度并显示 OSD。

自动查找所有输入设备并监听包含目标键事件的设备。
"""

import struct
import subprocess
import os
import sys
import signal
import time
import select
import glob

EV_KEY = 0x01
KEY_MUTE = 113
KEY_VOLUMEDOWN = 114
KEY_VOLUMEUP = 115
KEY_BRIGHTNESSDOWN = 224
KEY_BRIGHTNESSUP = 225

ALL_KEYS = {KEY_MUTE, KEY_VOLUMEDOWN, KEY_VOLUMEUP, KEY_BRIGHTNESSDOWN, KEY_BRIGHTNESSUP}

DEBOUNCE = 0.15

last_press = {}

def find_user():
    for line in open('/etc/passwd'):
        parts = line.strip().split(':')
        if len(parts) >= 7 and int(parts[2]) >= 1000 and int(parts[2]) < 65534:
            if parts[6] in ['/bin/bash', '/bin/zsh', '/usr/bin/zsh']:
                return int(parts[2]), parts[0], parts[5]
    return 1000, 'cc', '/home/cc'

def find_input_devices():
    devices = []
    for dev_path in sorted(glob.glob('/dev/input/event*')):
        name = ''
        try:
            event_num = dev_path.replace('/dev/input/event', '')
            sys_path = f'/sys/class/input/event{event_num}/device/name'
            with open(sys_path, 'r') as f:
                name = f.read().strip()
        except:
            pass

        devices.append({
            'path': dev_path,
            'name': name,
        })

    return devices

def set_volume(action):
    uid, username, home = find_user()
    env = {
        'DISPLAY': ':0',
        'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{uid}/bus',
        'PULSE_RUNTIME_PATH': f'/run/user/{uid}/pulse',
        'XAUTHORITY': f'{home}/.Xauthority',
        'HOME': home,
        'USER': username,
        'PATH': '/usr/local/bin:/usr/bin:/bin',
    }

    try:
        subprocess.Popen(
            ['/usr/local/bin/chromebook-osd.sh', action],
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp
        )
    except Exception as e:
        print(f"Error running OSD script: {e}", file=sys.stderr)

def handle_key(keycode):
    now = time.time()
    if keycode in last_press and now - last_press[keycode] < DEBOUNCE:
        return
    last_press[keycode] = now

    key_name = {113: 'MUTE', 114: 'VOLDOWN', 115: 'VOLUP', 224: 'BRIGHTDOWN', 225: 'BRIGHTUP'}.get(keycode, f'KEY_{keycode}')
    print(f"Key: {key_name}", file=sys.stderr)

    if keycode == KEY_VOLUMEUP:
        set_volume('volume-up')
    elif keycode == KEY_VOLUMEDOWN:
        set_volume('volume-down')
    elif keycode == KEY_MUTE:
        set_volume('volume-mute')
    elif keycode == KEY_BRIGHTNESSUP:
        set_volume('brightness-up')
    elif keycode == KEY_BRIGHTNESSDOWN:
        set_volume('brightness-down')

def main():
    devices = find_input_devices()
    watched = []
    skip_names = {'Lid Switch', 'Sleep Button', 'Power Button', 'PC Speaker',
                  'Elan Touchpad', 'sof-bxtda7219max Headset Jack'}
    for d in devices:
        if d['name'] in skip_names:
            continue
        try:
            fd = os.open(d['path'], os.O_RDONLY)
            watched.append({'fd': fd, 'path': d['path'], 'name': d['name']})
            print(f"Watching {d['path']} ({d['name']})", file=sys.stderr)
        except Exception as e:
            print(f"Cannot open {d['path']}: {e}", file=sys.stderr)

    if not watched:
        print("No input devices found", file=sys.stderr)
        sys.exit(1)

    fmt = 'llHHi'
    size = struct.calcsize(fmt)

    def cleanup(signum, frame):
        for w in watched:
            try:
                os.close(w['fd'])
            except:
                pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    poll = select.poll()
    for w in watched:
        poll.register(w['fd'], select.POLLIN)

    while True:
        try:
            events = poll.poll(1000)
            for fd, event in events:
                if event & select.POLLIN:
                    data = os.read(fd, size)
                    if not data:
                        continue
                    tv_sec, tv_usec, type_, code, value = struct.unpack(fmt, data)
                    if type_ == EV_KEY and value == 1 and code in ALL_KEYS:
                        handle_key(code)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(0.1)

if __name__ == '__main__':
    main()
