#!/bin/bash
# 合盖待机轮询服务
# ==================
# Chromebook (MrChromebox 固件) 的 lid switch 在非 ChromeOS 固件下
# 不产生硬件中断事件，systemd-logind / xfce4-power-manager / evtest
# 都无法感知合盖动作。此脚本每 2 秒轮询 ACPI lid 状态文件，
# 检测到 closed 时执行待机。
#
# 根因：ChromeOS 设备的 lid switch 由嵌入式控制器 (EC) 管理，
# MrChromebox 固件下 ACPI 事件通路失效。

LID_DEVICE="/proc/acpi/button/lid/LID0/state"
SUSPEND_CMD="systemctl suspend -i"

# 防重复触发：合盖后不再重复发待机指令
last_was_closed=0

if [ ! -f "$LID_DEVICE" ]; then
    echo "错误: 找不到 $LID_DEVICE" >&2
    exit 1
fi

logger -t "lid-watch" "Lid polling service started"

while true; do
    if [ -f "$LID_DEVICE" ]; then
        state=$(awk '{print $2}' "$LID_DEVICE")
        if [ "$state" = "closed" ]; then
            if [ "$last_was_closed" -eq 0 ]; then
                logger -t "lid-watch" "Lid closed, suspending..."
                $SUSPEND_CMD &
                last_was_closed=1
            fi
        else
            last_was_closed=0
        fi
    fi
    sleep 2
done