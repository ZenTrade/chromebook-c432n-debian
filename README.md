# ASUS C432N Chromebook — Debian Linux Complete Adaptation

A complete solution for running Debian 13 (trixie) + XFCE on the ASUS C432N Chromebook (Intel N3350 / Apollo Lake).

[中文文档](README_CN.md)

## Prerequisites

**This project assumes you have already:**

1. **Flashed custom firmware using [MrChromebox](https://mrchromebox.tech/)** — This replaces the Chrome OS firmware with a standard UEFI BIOS, allowing you to boot any OS. Run the MrChromebox firmware script from Chrome OS developer mode before installing Debian.

2. **Installed Debian 13 (trixie)** — A standard amd64 installation. The Chrome OS to Debian conversion is NOT covered here; only the post-install hardware adaptation.

> ⚠️ **Do NOT confuse this with ChrUbuntu or chroot-based solutions.** This is a native Debian installation on MrChromebox UEFI firmware.

## Hardware

| Item | Value |
|------|-------|
| Model | ASUS C432N (Coral baseboard) |
| CPU | Intel N3350 (Apollo Lake / BXT) |
| Display | 14" 1366×768, actual DPI ≈ 112 |
| Audio DSP | Intel SST `[8086:5a98]` |
| Headset Codec | DA7219 (SSP1) |
| Speaker Amp | MAX98357A (SSP5) |
| Digital Mic | DMIC (2ch) |
| Touchpad | Elan Touchpad (multi-touch) |
| Bluetooth | Intel 8087:0a2a (BT 4.2) |
| OS | Debian 13 trixie, kernel 6.12+ |
| Audio driver | SOF (`snd-sof-pci-intel-apl`) |

## Directory Structure

### `driver-patches/` — Driver Patches (Required)

These patches fix Chromebook hardware that doesn't work under Linux. This is the core of the project.

| File | Purpose |
|------|---------|
| `AUDIO_DRIVER_FIX.md` | Complete audio fix documentation: root cause analysis, 15 pitfalls, solution |
| `patch_da7219.py` | Patch kernel `sof_da7219.c` to add BXT (Apollo Lake) support. Fixes MAX98357A speaker and DMIC not working. Uses Python3 standard library only — run directly on Chromebook |
| `parse_nhlt.py` | Parse ACPI NHLT (Non-HDA Link Table) audio topology. Useful for diagnosing audio routing. Uses Python3 standard library only |
| `chromebook-volumed.py` | Volume/brightness key daemon. Listens to Intel Virtual Buttons kernel input device directly, bypassing X11 |
| `chromebook-volumed.service` | systemd service for the volume key daemon |
| `chromebook-osd.sh` | Volume/brightness OSD notification script. Includes perceptual volume curve (display 1-90% → actual 1-10%), 5% step, text-only no icons |
| `chromebook-volume-restore.desktop` | Volume memory autostart file. Restores volume and mute state from last shutdown on login |
| `chromebook-gestured.py` | Touchpad gesture daemon. Listens to touchpad kernel input device directly. Three-finger swipe to switch workspace / show desktop |
| `chromebook-gestured.service` | systemd service for the gesture daemon |
| `dunstrc` | dunst notification daemon config. Text-only, no icons, 25% transparency, unified style |
| `policies.json` | Firefox system policies. Enables VA-API hardware video decoding and extension installation |

**Audio fix root cause:** The kernel module `snd_soc_sof_da7219` is missing the `bxt_da7219_mx98357a` entry in its `MODULE_DEVICE_TABLE`. The SOF driver creates a platform device named `bxt_da7219_mx98357a` based on ACPI matching, but the unified driver `sof_da7219.c` only has GLK/CML/JSL entries — no BXT entry. This is an upstream regression bug.

**Perceptual volume curve:** The Chromebook speaker's effective perceptual range is actual 1%-10% (above 10%, the human ear cannot distinguish changes). The OSD script calibrates this range to display 1%-90%:

```
Display 0%      → Actual  0% (muted)
Display 1-90%   → Actual 1-10% (speaker full perceptual range, linear mapping)
Display 91-100% → Actual 10-100% (headphone/external headroom)
```

**Touchpad gestures:**

| Gesture | Action |
|---------|--------|
| 3-finger swipe left | Switch to next workspace |
| 3-finger swipe right | Switch to previous workspace |
| 3-finger swipe up | Show desktop |
| 3-finger swipe down | Restore windows |

---

### `xfce-ui/` — XFCE UI Optimization (Recommended)

Improves visual consistency and comfort of the XFCE desktop.

| File | Purpose |
|------|---------|
| `gtk.css` | GTK3 CSS overrides. Menu item spacing increased from 26px to 28px (close to macOS), menu container padding increased, pager workspace indicator visible on dark panels |

**Deploy:** Copy to `~/.config/gtk-3.0/gtk.css`

**Other UI optimizations** (set via xfconf-query commands, no separate files):

```bash
# Font (Sarasa Gothic SC's fontconfig primary name is Chinese "更纱黑体 SC")
apt install -y fonts-sarasa-gothic
xfconf-query -c xsettings -p /Gtk/FontName -s "更纱黑体 SC 10"
xfconf-query -c xsettings -p /Gtk/MonospaceFontName -s "Sarasa Fixed SC 10"
xfconf-query -c xsettings -p /Xft/Hinting -s 1
xfconf-query -c xsettings -p /Xft/HintStyle -s "hintslight"

# Lid suspend (bypass xfce4-power-manager inhibitor lock)
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/lid-suspend.conf << 'EOF'
[Login]
HandleLidSwitch=suspend
HandleLidSwitchDocked=suspend
LidSwitchIgnoreInhibited=yes
EOF

# Chromebook keyboard mapping (Search key → Super_L)
cat > /etc/X11/xinit/xinitrc.d/99-chromebook-xmodmap.sh << 'SCRIPT'
#!/bin/bash
xmodmap -e "keycode 133 = Super_L"
SCRIPT
chmod +x /etc/X11/xinit/xinitrc.d/99-chromebook-xmodmap.sh

# PulseAudio perceptual volume curve
echo "flat-volumes = no" >> /etc/pulse/daemon.conf
```

---

### `daily-optimizations/` — Daily Use Optimization (Recommended)

Reduces system maintenance burden, keeps the system clean automatically.

| File | Purpose |
|------|---------|
| `cleanup-caches.sh` | Auto-cleanup on shutdown/reboot: Firefox cache, WeChat chat history, thumbnails, GStreamer/Mesa shader cache, APT cache, journal rotation. Preserves cookies and login credentials |
| `cleanup-caches.service` | systemd service for the cleanup script, runs automatically before shutdown |

**Other daily optimizations** (set via commands, no separate files):

```bash
# Journal size limit (max 20M, keep 2 weeks)
mkdir -p /etc/systemd/journald.conf.d
cat > /etc/systemd/journald.conf.d/size-limit.conf << 'EOF'
[Journal]
SystemMaxUse=20M
MaxRetentionSec=2week
EOF

# APT auto-clean (clean download cache every 7 days)
cat > /etc/apt/apt.conf.d/99-auto-clean << 'EOF'
APT::Periodic::AutocleanInterval "7";
APT::Periodic::MaxAge "7";
EOF

# Boot speed: disable unnecessary services
systemctl disable NetworkManager-wait-online.service
systemctl disable ModemManager.service
systemctl disable avahi-daemon.service
systemctl disable cups.service
systemctl disable accounts-daemon.service

# Kernel module blacklist
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

# GRUB kernel parameters (skip unnecessary hardware detection)
# Edit /etc/default/grub:
# GRUB_CMDLINE_LINUX_DEFAULT="quiet module_blacklist=edac_pnd2 i915.enable_lspcon=0"
# GRUB_TIMEOUT=0
# Then run: update-grub
```

---

### `personal-preferences/` — Personal Preferences (Optional, for Reference Only)

These reflect the author's personal workflow. **They are NOT required.** Other users may selectively reference them based on their own needs.

| File | Purpose |
|------|---------|
| `r.py` | SSH remote execution tool. Connect parameters need to be configured by the user. Requires `paramiko` (`pip install paramiko`) |

**Other personal preferences** (no separate files, for reference only):

- Install blueman (Bluetooth GUI), flameshot (screenshot), thunar (file manager)
- Install WeChat/Feishu Linux version
- Install fcitx5 Chinese input method
- Install WhiteSur theme + Papirus icons
- Remove unused packages (quodlibet, xsane, system-config-printer, etc.)
- Set up auto-login for the primary user

## Quick Deploy

### 1. Fix audio driver

```bash
# On Chromebook, as root:
python3 driver-patches/patch_da7219.py
# Then compile and install the module (see AUDIO_DRIVER_FIX.md for details)
reboot
```

See [AUDIO_DRIVER_FIX.md](driver-patches/AUDIO_DRIVER_FIX.md) for the complete procedure.

### 2. Deploy OSD and gestures

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

### 3. Deploy dunst and UI config

```bash
apt install -y dunst
cp driver-patches/dunstrc /etc/dunst/
cp xfce-ui/gtk.css /home/cc/.config/gtk-3.0/
```

### 4. Deploy auto-cleanup

```bash
cp daily-optimizations/cleanup-caches.sh /usr/local/bin/ && chmod +x /usr/local/bin/cleanup-caches.sh
cp daily-optimizations/cleanup-caches.service /etc/systemd/system/
systemctl enable cleanup-caches
```

### 5. Firefox VA-API hardware decoding

```bash
apt install -y intel-media-va-driver mesa-va-drivers
mkdir -p /usr/share/firefox-esr/distribution
cp driver-patches/policies.json /usr/share/firefox-esr/distribution/
```

## License

MIT
