#!/usr/bin/env bash
sudo -n systemctl stop getty@tty1 2>/dev/null
for v in /sys/class/vtconsole/vtcon*; do
  if grep -qi "frame buffer" "$v/name" 2>/dev/null; then echo 0 | sudo -n tee "$v/bind" >/dev/null; fi
done
echo "=== start separate AUDIO (tone) on the soundbar ==="
( ffmpeg -loglevel error -f lavfi -i "sine=frequency=440:duration=9" -af "volume=0.6" -f wav - \
  | aplay -q -D plughw:CARD=vc4hdmi0,DEV=0 ) 2>/tmp/aplay.err &
APID=$!
echo "=== start SILENT VIDEO on the TV (mpv --no-audio) ==="
timeout 9 mpv --no-config --really-quiet --vo=drm --drm-device=/dev/dri/card1 \
  --drm-connector=HDMI-A-1 --drm-mode=1920x1080 --no-audio --loop-file=inf \
  /home/ubuntu/audio-portal/data/audio/stretch_short.mp4
echo "mpv rc $? (124=timeout=ok)"
wait $APID 2>/dev/null
echo "aplay rc $?"
echo "aplay stderr: $(cat /tmp/aplay.err 2>/dev/null)"
echo DONE
