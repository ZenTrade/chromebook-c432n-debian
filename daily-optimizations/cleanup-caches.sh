#!/bin/bash
# cleanup-caches.sh — 关机/重启时清理缓存和垃圾文件
# 保留 cookie 和登录凭证，只清理占用磁盘的缓存/消息数据

# Firefox 缓存
for cache_dir in /home/*/.cache/mozilla/firefox/*/cache2; do
    [ -d "$cache_dir" ] && rm -rf "$cache_dir" 2>/dev/null
done

# 微信聊天记录和缓存（保留登录凭证）
for wechat_data in /home/*/.local/share/xwechat /home/*/.xwechat; do
    if [ -d "$wechat_data" ]; then
        for msg_dir in "$wechat_data"/*/Msg "$wechat_data"/*/MsgAttach; do
            [ -d "$msg_dir" ] && rm -rf "$msg_dir" 2>/dev/null
        done
        for cache_dir in "$wechat_data"/*/Cache; do
            [ -d "$cache_dir" ] && rm -rf "$cache_dir" 2>/dev/null
        done
    fi
done

# 缩略图缓存
rm -rf /home/*/.cache/thumbnails/* 2>/dev/null

# GStreamer 缓存
rm -rf /home/*/.cache/gstreamer-1.0/* 2>/dev/null

# Mesa shader 缓存
rm -rf /home/*/.cache/mesa_shader_cache_db/* 2>/dev/null

# Fontconfig 缓存（下次启动自动重建）
rm -rf /home/*/.cache/fontconfig/* 2>/dev/null

# APT 缓存
apt-get clean 2>/dev/null

# 日志轮转
journalctl --vacuum-time=2weeks --vacuum-size=20M 2>/dev/null

# 旧日志
find /var/log -name '*.gz' -mtime +7 -delete 2>/dev/null
find /var/log -name '*.old' -mtime +7 -delete 2>/dev/null
find /var/log -name '*.[0-9]' -mtime +7 -delete 2>/dev/null
