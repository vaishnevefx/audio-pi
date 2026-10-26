#!/usr/bin/env bash
F=/boot/firmware/current/cmdline.txt
OPTS="quiet loglevel=0 systemd.show_status=false vt.global_cursor_default=0"
if ! grep -q "loglevel=0" "$F"; then
  sudo -n cp "$F" "$F.bak"
  echo "$(tr -d '\n' < "$F") $OPTS" | sudo -n tee "$F" >/dev/null
fi
echo "cmdline now:"; cat "$F"; echo
unbind() {
  for v in /sys/class/vtconsole/vtcon*; do
    if grep -qi "frame buffer" "$v/name"; then echo 0 | sudo -n tee "$v/bind" >/dev/null; fi
  done
}
unbind
echo "bind before video: $(cat /sys/class/vtconsole/vtcon1/bind)"
timeout 4 mpv --no-config --really-quiet --vo=drm --drm-device=/dev/dri/card1 \
  --drm-connector=HDMI-A-1 --drm-mode=1920x1080 --no-audio --loop-file=inf \
  /home/ubuntu/audio-portal/data/audio/stretch_short.mp4 >/dev/null 2>&1
echo "bind after video: $(cat /sys/class/vtconsole/vtcon1/bind)"
