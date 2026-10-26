#!/usr/bin/env bash
B=http://127.0.0.1:8080; J=/tmp/tj.txt; PY=/home/ubuntu/audio-portal/venv/bin/python
getv() { (cd /home/ubuntu/audio-portal && $PY -c "import db;print(db.get_setting('$1'))"); }
rm -f $J; curl -s -c $J $B/login >/dev/null
echo "admin login: $(curl -s -b $J -c $J -o /dev/null -w '%{http_code}' --data-urlencode username=admin --data-urlencode password=El0vwUbgSA-oMRZj $B/login)"
echo "settings page shows toggles: $(curl -s -b $J $B/settings | grep -c 'name="idle_screen"')"
CSRF=$(curl -s -b $J $B/ | grep -oE 'name="csrf" content="[^"]+"' | sed 's/.*content="//; s/"$//')
save() { curl -s -b $J -H "X-CSRF: $CSRF" -o /dev/null --data-urlencode form=audio --data-urlencode audio_device=plughw:CARD=vc4hdmi0,DEV=0 --data-urlencode default_volume=80 --data-urlencode preroll_seconds=2 --data-urlencode timezone=Asia/Kolkata --data-urlencode drm_device=/dev/dri/card1 --data-urlencode drm_connector=HDMI-A-1 --data-urlencode drm_mode=1920x1080 "$@" $B/settings; }
save --data-urlencode playing_screen=on          # idle box unticked
echo "idle off -> idle_screen=$(getv idle_screen) playing_screen=$(getv playing_screen)"
sleep 8
save --data-urlencode idle_screen=on --data-urlencode playing_screen=on
echo "restored -> idle_screen=$(getv idle_screen) playing_screen=$(getv playing_screen)"
rm -f $J
