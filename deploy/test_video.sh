#!/usr/bin/env bash
echo "=== free the console (stop getty@tty1) ==="
sudo -n systemctl stop getty@tty1
sleep 1
echo "=== generate 12s test video ==="
ffmpeg -loglevel error -y -f lavfi -i testsrc=duration=12:size=1280x720:rate=30 \
  -f lavfi -i "sine=frequency=440:duration=12" \
  -pix_fmt yuv420p -c:v libx264 -preset veryfast -c:a aac -shortest /tmp/testvid.mp4
echo "ffmpeg exit $?  size: $(stat -c %s /tmp/testvid.mp4 2>/dev/null) bytes"
echo "=== play to TV (DRM, card1 HDMI-A-1) + soundbar (ALSA), 10s ==="
sudo -n mpv --no-config --vo=drm --drm-device=/dev/dri/card1 --drm-connector=HDMI-A-1 \
  --audio-device=alsa/plughw:CARD=vc4hdmi0,DEV=0 \
  --length=10 --msg-level=all=v /tmp/testvid.mp4 2>&1 \
  | grep -iE 'drm|vo |audio devi|error|master|connector|opening|fail|resolut|mode' | head -45
echo "=== mpv exit done ==="
rm -f /tmp/testvid.mp4
