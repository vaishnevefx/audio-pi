#!/usr/bin/env bash
B=http://127.0.0.1:8080; J=/tmp/ds.txt; PY=/home/ubuntu/audio-portal/venv/bin/python
cfg() { (cd /home/ubuntu/audio-portal && $PY -c "import display;print(display._cfg())"); }
rm -f $J; curl -s -c $J $B/login >/dev/null
echo "admin login: $(curl -s -b $J -c $J -o /dev/null -w '%{http_code}' --data-urlencode username=admin --data-urlencode password=El0vwUbgSA-oMRZj $B/login)"
echo "fields on page: $(curl -s -b $J $B/settings | grep -cE 'name="(display_speed|display_hz|night_mode|night_start|night_end)"') of 5"
CSRF=$(curl -s -b $J $B/ | grep -oE 'name="csrf" content="[^"]+"' | sed 's/.*content="//; s/"$//')
save() { curl -s -b $J -H "X-CSRF: $CSRF" -o /dev/null --data-urlencode form=audio --data-urlencode audio_device=plughw:CARD=vc4hdmi0,DEV=0 --data-urlencode default_volume=80 --data-urlencode preroll_seconds=2 --data-urlencode timezone=Asia/Kolkata --data-urlencode drm_device=/dev/dri/card1 --data-urlencode drm_connector=HDMI-A-1 --data-urlencode drm_mode=1920x1080 --data-urlencode idle_screen=on --data-urlencode playing_screen=on "$@" $B/settings; }
MP1=$(pgrep -x mpv)
save --data-urlencode display_speed=30 --data-urlencode display_hz=20 --data-urlencode night_mode=on --data-urlencode night_start=23 --data-urlencode night_end=6
sleep 5
echo "saved (speed 30, 20Hz, night 23-6): $(cfg)"
save --data-urlencode display_speed=18 --data-urlencode display_hz=30 --data-urlencode night_mode=on --data-urlencode night_start=22 --data-urlencode night_end=7
sleep 5
echo "restored: $(cfg)"
echo "mpv restarted by saving? $([ "$MP1" = "$(pgrep -x mpv)" ] && echo no || echo YES)"
echo "night window check: hour 22->$($PY -c 'import sys;sys.path.insert(0,"/home/ubuntu/audio-portal");import display;print(display._is_night(22),display._is_night(3),display._is_night(12))')"
rm -f $J
