#!/usr/bin/env bash
URL="https://www.youtube.com/shorts/PqUTmd0xdjw"
OUT=/home/ubuntu/audio-portal/data/audio/stretch_short.mp4
echo "=== free console ==="
sudo -n systemctl stop getty@tty1 2>/dev/null
for v in /sys/class/vtconsole/vtcon*; do
  if cat "$v/name" 2>/dev/null | grep -qi "frame buffer"; then echo 0 | sudo -n tee "$v/bind" >/dev/null; fi
done
echo "=== download short (mp4, <=1080p) ==="
/home/ubuntu/audio-portal/venv/bin/yt-dlp -f "bv*[height<=1080]+ba/b[height<=1080]/b" \
  --merge-output-format mp4 --no-playlist -o "$OUT" "$URL" 2>&1 | tail -5
echo "file: $(ls -la "$OUT" 2>/dev/null | awk '{print $5" bytes"}')"
echo "=== probe ==="
ffprobe -v error -show_entries format=duration:stream=width,height,codec_type \
  -of default=noprint_wrappers=1 "$OUT" 2>/dev/null
echo "=== PLAYING ON TV for ~60s (TV must be on + correct HDMI input) ==="
sudo -n timeout 60 mpv --no-config --vo=drm --drm-device=/dev/dri/card1 --drm-connector=HDMI-A-1 \
  --audio-device=alsa/plughw:CARD=vc4hdmi0,DEV=0 --loop-file=inf \
  --msg-level=all=status "$OUT" 2>&1 | tail -8
echo "done rc ${PIPESTATUS[0]}"
