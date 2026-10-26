#!/usr/bin/env bash
B=http://127.0.0.1:8080
J=/tmp/vj.txt
login() {
  rm -f "$J"; curl -s -c "$J" "$B/login" >/dev/null
  curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}' \
    --data-urlencode "username=$1" --data-urlencode "password=$2" "$B/login"
}
PW=$(cat /home/ubuntu/audio-portal/data/INITIAL_ADMIN_PASSWORD.txt 2>/dev/null)
code=$(login changemaker "$PW")
echo "login changemaker(initial pw): $code"
if [ "$code" != "302" ]; then
  code=$(login admin "El0vwUbgSA-oMRZj")
  echo "login admin(backup): $code"
fi
CSRF=$(curl -s -b "$J" "$B/" | grep -oE 'name="csrf" content="[^"]+"' | sed 's/.*content="//; s/"$//')
echo "triggering: stretching video, 1-minute looped window, via the service..."
curl -s -b "$J" -H "X-CSRF: $CSRF" -H "X-Requested-With: fetch" \
  --data "audio_id=9&video=1&minutes=1" "$B/play"; echo
sleep 2
echo "player status:"; curl -s -b "$J" "$B/api/status" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print({k:d.get(k) for k in ("playing","title","trigger","remaining")})'
rm -f "$J"
echo DONE
