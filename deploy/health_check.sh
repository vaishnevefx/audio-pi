#!/usr/bin/env bash
PY=/home/ubuntu/audio-portal/venv/bin/python
echo "=== services ==="
for s in audio-portal pi-timesync.timer pi-free-console pi-mtu; do
  echo "  $s: active=$(systemctl is-active $s 2>/dev/null) enabled=$(systemctl is-enabled $s 2>/dev/null)"
done
echo "=== wlan0 mtu ==="; ip -o link show wlan0 | grep -o 'mtu [0-9]*'
echo "=== time ==="; date '+%F %T %Z'; tail -1 /var/log/pi-timesync.log 2>/dev/null
echo "=== settings ==="
$PY -c "import db; print(' device=',db.get_setting('audio_device'),'| master=',db.get_setting('master_volume'),'| muted=',db.get_setting('muted'),'| defvol=',db.get_setting('default_volume'))"
echo "=== recent play_log ==="
$PY -c "import db; c=db._connect(); [print('  ',dict(r)) for r in c.execute('select id,title,trigger,status,detail from play_log order by id desc limit 6').fetchall()]; c.close()"
echo "=== DRM / HDMI state ==="
echo "  status=$(cat /sys/class/drm/card1-HDMI-A-1/status 2>/dev/null) enabled=$(cat /sys/class/drm/card1-HDMI-A-1/enabled 2>/dev/null) dpms=$(cat /sys/class/drm/card1-HDMI-A-1/dpms 2>/dev/null)"
echo "  fbcon bind=$(cat /sys/class/vtconsole/vtcon1/bind 2>/dev/null)"
echo "=== aplay cards ==="; aplay -l 2>/dev/null | grep -i 'card 0\|card 1'
echo
echo "=== TEST A: audio-only (aplay, 440Hz 3s) ==="
ffmpeg -loglevel error -f lavfi -i "sine=frequency=440:duration=3" -af volume=0.6 -f wav - | aplay -q -D plughw:CARD=vc4hdmi0,DEV=0
echo "  aplay rc $?"
sleep 1
echo "=== TEST B: audio (660Hz 3s) + black-screen HDMI keepalive ==="
ffmpeg -loglevel error -y -f lavfi -i color=c=black:s=1920x1080 -frames:v 1 /tmp/black.png
mpv --no-config --really-quiet --vo=drm --drm-device=/dev/dri/card1 --drm-connector=HDMI-A-1 \
  --drm-mode=1920x1080 --no-audio --image-display-duration=inf --loop-file=inf /tmp/black.png &
MPVPID=$!
sleep 1
ffmpeg -loglevel error -f lavfi -i "sine=frequency=660:duration=3" -af volume=0.6 -f wav - | aplay -q -D plughw:CARD=vc4hdmi0,DEV=0
echo "  aplay2 rc $?"
kill $MPVPID 2>/dev/null
echo DONE
