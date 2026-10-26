#!/usr/bin/env bash
echo "[1] install mpv..."
sudo -n DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=300 install -y mpv >/tmp/mpv_apt.log 2>&1
echo "apt exit $?"
mpv --version 2>/dev/null | head -1

echo
echo "[2] DRM cards:"
ls -1 /sys/class/drm/ | grep -E '^card[0-9]+$'

echo
echo "[3] connector status (which HDMI has the TV/soundbar):"
for s in /sys/class/drm/card*-*/status; do
  d=$(dirname "$s"); echo "  $(basename "$d"): $(cat "$s")"
done

echo
echo "[4] /dev/dri nodes:"
ls -l /dev/dri/ 2>/dev/null

echo
echo "[5] grant ubuntu video,render groups (for DRM/KMS access):"
id ubuntu
sudo -n usermod -aG video,render ubuntu && echo "  added ubuntu to video,render"

echo
echo "[6] is a getty holding tty1 (console/DRM)?"
systemctl is-active getty@tty1 2>/dev/null || echo "  getty@tty1 not active"
echo "DONE"
