#!/usr/bin/env bash
sudo -n systemctl stop getty@tty1 2>/dev/null
echo "=== vtconsole bindings ==="
for v in /sys/class/vtconsole/vtcon*; do
  echo "  $v: name='$(cat $v/name 2>/dev/null)' bind=$(cat $v/bind 2>/dev/null)"
done
echo "=== unbind framebuffer console (frees the CRTC) ==="
for v in /sys/class/vtconsole/vtcon*; do
  if cat "$v/name" 2>/dev/null | grep -qi "frame buffer"; then
    echo 0 | sudo -n tee "$v/bind" >/dev/null && echo "  unbound $v"
  fi
done
echo "=== regenerate test video ==="
ffmpeg -loglevel error -y -f lavfi -i testsrc=duration=12:size=1280x720:rate=30 \
  -f lavfi -i "sine=frequency=440:duration=12" \
  -pix_fmt yuv420p -c:v libx264 -preset veryfast -c:a aac -shortest /tmp/testvid.mp4
echo "=== play to TV + soundbar (10s) ==="
sudo -n mpv --no-config --vo=drm --drm-device=/dev/dri/card1 --drm-connector=HDMI-A-1 \
  --audio-device=alsa/plughw:CARD=vc4hdmi0,DEV=0 \
  --length=10 --msg-level=all=status /tmp/testvid.mp4 2>&1 | tail -25
echo "mpv rc ${PIPESTATUS[0]}"
rm -f /tmp/testvid.mp4
