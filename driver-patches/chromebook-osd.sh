#!/bin/bash
VOLUME_ID=1001
BRIGHTNESS_ID=1002
VOL_STATE_DIR="/home/cc/.local/state"
VOL_STATE="$VOL_STATE_DIR/chromebook-osd-vol"
VOL_MUTE_STATE="$VOL_STATE_DIR/chromebook-osd-muted"

if [ -z "$PULSE_RUNTIME_PATH" ] && [ -d "/run/user/$(id -u)/pulse" ]; then
    export PULSE_RUNTIME_PATH="/run/user/$(id -u)/pulse"
fi
if [ -z "$DBUS_SESSION_BUS_ADDRESS" ] && [ -S "/run/user/$(id -u)/bus" ]; then
    export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"
fi

if command -v dunstify &>/dev/null; then
    NOTIFY="dunstify"
else
    NOTIFY="notify-send"
fi

show_osd() {
    local value="$1"
    local label="$2"
    local id="$3"

    if [ "$NOTIFY" = "dunstify" ]; then
        dunstify -r "$id" -h int:value:"$value" -u normal "$label" ""
    else
        notify-send -h string:x-canonical-private-synchronous:osd -h int:value:"$value" "$label" "" 2>/dev/null
    fi
}

display_to_actual() {
    local d="$1"
    d=$(printf '%.0f' "$d" 2>/dev/null || echo "$d")
    if [ "${d:-0}" -eq 0 ] 2>/dev/null; then echo "0"; return; fi
    if [ "$d" -le 90 ]; then
        echo "$d" | awk '{printf "%.2f", 1 + ($1 - 1) * 9.0 / 89.0}'
    else
        echo "$d" | awk '{printf "%.1f", 10 + ($1 - 90) * 9.0}'
    fi
}

actual_to_display() {
    local a="$1"
    a=$(printf '%.0f' "$a" 2>/dev/null || echo "$a")
    if [ "${a:-0}" -eq 0 ] 2>/dev/null; then echo "0"; return; fi
    awk -v target="$a" '
    BEGIN {
        for (d=0; d<=100; d++) {
            if (d == 0) actual = 0
            else if (d <= 90) actual = 1 + (d - 1) * 9.0 / 89.0
            else actual = 10 + (d - 90) * 9.0
            if (actual >= target) { printf "%d\n", d; exit }
        }
        print 100
    }'
}

get_display_volume() {
    if [ -f "$VOL_STATE" ]; then cat "$VOL_STATE" 2>/dev/null; return; fi
    local actual
    actual=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | grep -oP '\d+%' | head -1 | tr -d '%')
    if [ -z "$actual" ]; then echo "50"; return; fi
    local disp; disp=$(actual_to_display "$actual"); printf '%.0f' "$disp"
}

save_display_volume() {
    mkdir -p "$VOL_STATE_DIR" 2>/dev/null
    echo "$1" > "$VOL_STATE" 2>/dev/null
}

save_mute_state() {
    mkdir -p "$VOL_STATE_DIR" 2>/dev/null
    echo "$1" > "$VOL_MUTE_STATE" 2>/dev/null
}

get_step() { echo "5"; }

case "$1" in
    volume-up)
        vol=$(get_display_volume); [ -z "$vol" ] && vol=50
        step=$(get_step "$vol"); new_vol=$((vol + step)); [ "$new_vol" -gt 100 ] && new_vol=100
        actual=$(display_to_actual "$new_vol")
        pactl set-sink-volume @DEFAULT_SINK@ "${actual}%" 2>/dev/null
        muted=$(LANG=C pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | grep -oP 'yes|no')
        [ "$muted" = "yes" ] && pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null
        save_display_volume "$new_vol"; save_mute_state "no"
        show_osd "$new_vol" "音量 ${new_vol}%" "$VOLUME_ID" ;;
    volume-down)
        vol=$(get_display_volume); [ -z "$vol" ] && vol=50
        step=$(get_step "$vol"); new_vol=$((vol - step)); [ "$new_vol" -lt 0 ] && new_vol=0
        actual=$(display_to_actual "$new_vol")
        pactl set-sink-volume @DEFAULT_SINK@ "${actual}%" 2>/dev/null
        save_display_volume "$new_vol"; save_mute_state "no"
        show_osd "$new_vol" "音量 ${new_vol}%" "$VOLUME_ID" ;;
    volume-mute)
        pactl set-sink-mute @DEFAULT_SINK@ toggle 2>/dev/null
        sleep 0.1
        muted=$(LANG=C pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null | grep -oP 'yes|no')
        if [ "$muted" = "yes" ]; then
            save_mute_state "yes"
            show_osd "0" "音量 0%" "$VOLUME_ID"
        else
            vol=$(get_display_volume); save_mute_state "no"
            show_osd "${vol:-50}" "音量 ${vol:-50}%" "$VOLUME_ID"
        fi ;;
    volume-restore)
        if [ -f "$VOL_STATE" ]; then
            vol=$(cat "$VOL_STATE" 2>/dev/null)
            if [ -n "$vol" ] && [ "$vol" -ge 0 ] 2>/dev/null && [ "$vol" -le 100 ] 2>/dev/null; then
                actual=$(display_to_actual "$vol")
                pactl set-sink-volume @DEFAULT_SINK@ "${actual}%" 2>/dev/null
                if [ -f "$VOL_MUTE_STATE" ]; then
                    saved_mute=$(cat "$VOL_MUTE_STATE" 2>/dev/null)
                    if [ "$saved_mute" = "yes" ]; then
                        pactl set-sink-mute @DEFAULT_SINK@ 1 2>/dev/null
                    else
                        pactl set-sink-mute @DEFAULT_SINK@ 0 2>/dev/null
                    fi
                fi
            fi
        fi ;;
    brightness-up)
        brightnessctl set 10%+ 2>/dev/null
        bright=$(brightnessctl info 2>/dev/null | grep -oP '\d+%' | tr -d '%')
        show_osd "${bright:-50}" "亮度 ${bright:-50}%" "$BRIGHTNESS_ID" ;;
    brightness-down)
        brightnessctl set 10%- 2>/dev/null
        bright=$(brightnessctl info 2>/dev/null | grep -oP '\d+%' | tr -d '%')
        show_osd "${bright:-50}" "亮度 ${bright:-50}%" "$BRIGHTNESS_ID" ;;
esac
