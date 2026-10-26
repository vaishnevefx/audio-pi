#!/usr/bin/env bash
B=http://127.0.0.1:8080
getset() { cd /home/ubuntu/audio-portal && ./venv/bin/python -c "import db;print(db.get_setting('default_volume'))"; }
login() {
  local u="$1" p="$2" J="$3"; rm -f "$J"; curl -s -c "$J" "$B/login" >/dev/null
  curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}' \
    --data-urlencode "username=$u" --data-urlencode "password=$p" "$B/login"
}
post_audio() {
  local J="$1" vol="$2"
  local CSRF=$(curl -s -b "$J" "$B/" | grep -oE 'name="csrf" content="[^"]+"' | sed 's/.*content="//; s/"$//')
  curl -s -b "$J" -H "X-CSRF: $CSRF" -o /dev/null \
    --data-urlencode "form=audio" --data-urlencode "audio_device=plughw:CARD=vc4hdmi0,DEV=0" \
    --data-urlencode "default_volume=$vol" --data-urlencode "preroll_seconds=2" \
    --data-urlencode "timezone=Asia/Kolkata" --data-urlencode "drm_device=/dev/dri/card1" \
    --data-urlencode "drm_connector=HDMI-A-1" --data-urlencode "drm_mode=1920x1080" "$B/settings"
}
CPW=$(cat /home/ubuntu/audio-portal/data/INITIAL_ADMIN_PASSWORD.txt 2>/dev/null)
AJ=/tmp/adm.txt; CJ=/tmp/chm.txt
echo "admin login:       $(login admin El0vwUbgSA-oMRZj $AJ)"
echo "changemaker login: $(login changemaker "$CPW" $CJ)"
echo "baseline default_volume: $(getset)"
echo "admin sees system settings:       $(curl -s -b $AJ "$B/settings" | grep -c 'name="audio_device"')"
echo "changemaker sees system settings: $(curl -s -b $CJ "$B/settings" | grep -c 'name="audio_device"')"
echo "admin sets default_volume=55...";      post_audio $AJ 55; echo "  -> $(getset)"
echo "changemaker tries default_volume=99..."; post_audio $CJ 99; echo "  -> $(getset)  (should still be 55)"
echo "admin restores default_volume=80...";   post_audio $AJ 80; echo "  -> $(getset)"
rm -f $AJ $CJ
echo DONE
