#!/usr/bin/env python3
"""
chromebook-gestured.py — Chromebook 触控板手势守护进程
======================================================
监听触控板的多指滑动手势，触发桌面切换等操作。

手势映射：
  三指左滑 → 切换到下一个工作区
  三指右滑 → 切换到上一个工作区
  三指上滑 → 显示桌面
  三指下滑 → 还原窗口

依赖：wmctrl, dunst (dunstify), xfwm4
"""

import subprocess
import os
import sys
import signal
import select
import struct
import time
import glob

SWIPE_THRESHOLD = 300
SWIPE_TIME_MAX = 0.8
DEBOUNCE = 1.0

last_action_time = 0
WORKSPACE_OSD_ID = 2001
DESKTOP_OSD_ID = 2002


def find_user():
    for line in open('/etc/passwd'):
        parts = line.strip().split(':')
        if len(parts) >= 7 and int(parts[2]) >= 1000 and int(parts[2]) < 65534:
            if parts[6] in ['/bin/bash', '/bin/zsh', '/usr/bin/zsh']:
                return int(parts[2]), parts[0], parts[5]
    return 1000, 'cc', '/home/cc'


def find_touchpad():
    for dev_path in sorted(glob.glob('/dev/input/event*')):
        try:
            event_num = dev_path.replace('/dev/input/event', '')
            with open(f'/sys/class/input/event{event_num}/device/name', 'r') as f:
                name = f.read().strip()
            if 'touchpad' in name.lower() or 'elan' in name.lower():
                return dev_path, name
        except:
            pass
    return None, None


def get_env():
    uid, username, home = find_user()
    return {
        'DISPLAY': ':0',
        'DBUS_SESSION_BUS_ADDRESS': f'unix:path=/run/user/{uid}/bus',
        'XAUTHORITY': f'{home}/.Xauthority',
        'HOME': home,
        'USER': username,
        'PATH': '/usr/local/bin:/usr/bin:/bin',
    }


def run_cmd(args):
    global last_action_time
    now = time.time()
    if now - last_action_time < DEBOUNCE:
        return
    last_action_time = now
    try:
        subprocess.Popen(
            args, env=get_env(),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp
        )
    except Exception as e:
        print(f"cmd error: {e}", file=sys.stderr)


def show_osd(label, osd_id):
    uid, username, home = find_user()
    try:
        env_str = f'DISPLAY=:0 DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/{uid}/bus XAUTHORITY={home}/.Xauthority'
        subprocess.Popen(
            f'sudo -u {username} {env_str} dunstify -r {osd_id} -u normal "{label}" ""',
            shell=True,
            executable='/bin/bash',
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            preexec_fn=os.setpgrp
        )
    except:
        pass


def get_current_workspace():
    env = get_env()
    try:
        out = subprocess.check_output(
            ['wmctrl', '-d'], env=env,
            stderr=subprocess.DEVNULL, timeout=5
        ).decode()
        desktops = [l for l in out.strip().split('\n') if l]
        for i, d in enumerate(desktops):
            if '*' in d:
                return i, len(desktops)
    except:
        pass
    return 0, 2


def switch_workspace(direction):
    env = get_env()
    try:
        out = subprocess.check_output(
            ['wmctrl', '-d'], env=env,
            stderr=subprocess.DEVNULL, timeout=5
        ).decode()
        desktops = [l for l in out.strip().split('\n') if l]
        for i, d in enumerate(desktops):
            if '*' in d:
                current = i
                if direction == 'next':
                    target = current + 1 if current + 1 < len(desktops) else current
                else:
                    target = current - 1 if current > 0 else current
                if target != current:
                    run_cmd(['wmctrl', '-s', str(target)])
                    time.sleep(0.1)
                    _, total = get_current_workspace()
                    show_osd(f"工作区 {target + 1}/{total}", WORKSPACE_OSD_ID)
                break
    except Exception as e:
        print(f"wmctrl error: {e}", file=sys.stderr)


def is_desktop_shown():
    env = get_env()
    try:
        out = subprocess.check_output(
            ['xprop', '-root', '_NET_SHOWING_DESKTOP'], env=env,
            stderr=subprocess.DEVNULL, timeout=5
        ).decode()
        return ' = 1' in out
    except:
        return False


def show_desktop():
    run_cmd(['wmctrl', '-k', 'on'])
    show_osd("显示桌面", DESKTOP_OSD_ID)


def restore_desktop():
    run_cmd(['wmctrl', '-k', 'off'])
    show_osd("还原窗口", DESKTOP_OSD_ID)


def main():
    dev_path, dev_name = find_touchpad()
    if not dev_path:
        print("No touchpad found", file=sys.stderr)
        sys.exit(1)

    print(f"Watching {dev_path} ({dev_name})", file=sys.stderr)

    try:
        fd = os.open(dev_path, os.O_RDONLY)
    except Exception as e:
        print(f"Cannot open {dev_path}: {e}", file=sys.stderr)
        sys.exit(1)

    def cleanup(signum, frame):
        try:
            os.close(fd)
        except:
            pass
        sys.exit(0)

    signal.signal(signal.SIGTERM, cleanup)
    signal.signal(signal.SIGINT, cleanup)

    fmt = 'llHHi'
    size = struct.calcsize(fmt)

    EV_ABS = 0x03
    EV_SYN = 0x00

    ABS_MT_SLOT = 0x2f
    ABS_MT_TRACKING_ID = 0x39
    ABS_MT_POSITION_X = 0x35
    ABS_MT_POSITION_Y = 0x36
    SYN_REPORT = 0

    fingers = {}
    active_slots = {}
    current_slot = 0
    finger_count = 0
    swipe_start = {}
    swipe_active = False

    poll = select.poll()
    poll.register(fd, select.POLLIN)

    while True:
        try:
            events = poll.poll(1000)
            for fd_num, event in events:
                if not (event & select.POLLIN):
                    continue
                data = os.read(fd_num, size)
                if not data:
                    continue
                tv_sec, tv_usec, type_, code, value = struct.unpack(fmt, data)

                if type_ == EV_ABS and code == ABS_MT_SLOT:
                    current_slot = value

                elif type_ == EV_ABS and code == ABS_MT_TRACKING_ID:
                    if value >= 0:
                        active_slots[current_slot] = value
                    else:
                        active_slots.pop(current_slot, None)
                    finger_count = len(active_slots)

                elif type_ == EV_ABS and code == ABS_MT_POSITION_X:
                    if current_slot not in fingers:
                        fingers[current_slot] = {}
                    fingers[current_slot]['x'] = value
                    if finger_count >= 3 and current_slot not in swipe_start:
                        swipe_start[current_slot] = {
                            'x': value,
                            'y': fingers[current_slot].get('y', 0),
                            'time': time.time()
                        }

                elif type_ == EV_ABS and code == ABS_MT_POSITION_Y:
                    if current_slot not in fingers:
                        fingers[current_slot] = {}
                    fingers[current_slot]['y'] = value
                    if finger_count >= 3 and current_slot not in swipe_start:
                        swipe_start[current_slot] = {
                            'x': fingers[current_slot].get('x', 0),
                            'y': value,
                            'time': time.time()
                        }

                elif type_ == EV_SYN and code == SYN_REPORT:
                    if finger_count >= 3 and len(swipe_start) >= 3:
                        swipe_active = True

                    if finger_count == 0 and swipe_active and len(swipe_start) >= 2:
                        now = time.time()
                        dx_total = 0
                        dy_total = 0
                        t_valid = True
                        for slot, start in swipe_start.items():
                            if slot in fingers:
                                dx_total += fingers[slot].get('x', start['x']) - start['x']
                                dy_total += fingers[slot].get('y', start['y']) - start['y']
                                if now - start['time'] > SWIPE_TIME_MAX:
                                    t_valid = False
                            else:
                                t_valid = False

                        n = len(swipe_start)
                        dx_avg = dx_total / n if n > 0 else 0
                        dy_avg = dy_total / n if n > 0 else 0

                        if t_valid:
                            if abs(dx_avg) > abs(dy_avg) and abs(dx_avg) > SWIPE_THRESHOLD:
                                if dx_avg > 0:
                                    print("Swipe RIGHT (prev workspace)", file=sys.stderr)
                                    switch_workspace('prev')
                                else:
                                    print("Swipe LEFT (next workspace)", file=sys.stderr)
                                    switch_workspace('next')
                            elif abs(dy_avg) > abs(dx_avg) and abs(dy_avg) > SWIPE_THRESHOLD:
                                if dy_avg < 0:
                                    print("Swipe UP (show desktop)", file=sys.stderr)
                                    show_desktop()
                                else:
                                    print("Swipe DOWN (restore desktop)", file=sys.stderr)
                                    restore_desktop()

                        swipe_start = {}
                        swipe_active = False
                        fingers = {}

                    if finger_count == 0:
                        swipe_start = {}
                        swipe_active = False
                        fingers = {}

        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            time.sleep(0.1)


if __name__ == '__main__':
    main()
