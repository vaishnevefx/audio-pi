#!/usr/bin/env bash
sudo -n systemctl stop getty@tty1 2>/dev/null
for v in /sys/class/vtconsole/vtcon*; do
  if cat "$v/name" 2>/dev/null | grep -qi "frame buffer"; then echo 0 | sudo -n tee "$v/bind" >/dev/null; fi
done
echo "=== available modes on HDMI-A-1 ==="
head -12 /sys/class/drm/card1-HDMI-A-1/modes
echo "=== id (expect video + render groups) ==="
id
echo "=== NON-ROOT mpv, 1080p, loop+length=8s, volume=70 ==="
mpv --no-config --vo=drm --drm-device=/dev/dri/card1 --drm-connector=HDMI-A-1 --drm-mode=1920x1080 \
  --audio-device=alsa/plughw:CARD=vc4hdmi0,DEV=0 --volume=70 \
  --loop-file=inf --length=8 --msg-level=all=status \
  /home/ubuntu/audio-portal/data/audio/stretch_short.mp4 2>&1 | tail -16
echo "rc ${PIPESTATUS[0]}"
