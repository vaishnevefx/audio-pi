#!/usr/bin/env bash
B=http://127.0.0.1:8080
J=/tmp/cj2.txt
PWF=/home/ubuntu/audio-portal/data/INITIAL_ADMIN_PASSWORD.txt
if [ ! -f "$PWF" ]; then echo "initial password file gone (changed?) - skipping authed tests"; exit 0; fi
PW=$(cat "$PWF")
rm -f "$J"
curl -s -c "$J" "$B/login" >/dev/null
echo -n "login: "; curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}\n' \
  --data-urlencode "username=admin" --data-urlencode "password=$PW" "$B/login"
CSRF=$(curl -s -b "$J" "$B/" | grep -oE 'name="csrf" content="[^"]+"' | sed 's/.*content="//; s/"$//')
echo "csrf: ${CSRF:0:8}..."
echo
echo "=== /api/status (new fields) ==="
curl -s -b "$J" "$B/api/status" | python3 -c 'import sys,json; d=json.load(sys.stdin); print({k:d.get(k) for k in ("server_epoch","timezone","master_volume","muted","playing")})'
echo
echo "=== dashboard has volume card + clock? ==="
P=$(curl -s -b "$J" "$B/")
echo "vol-range hits: $(echo "$P" | grep -c vol-range) | dev-clock hits: $(echo "$P" | grep -c dev-clock)"
echo
echo "=== /volume/set value=75 (silent) ==="
curl -s -b "$J" -H "X-CSRF: $CSRF" -H "X-Requested-With: fetch" --data "value=75&tone=0" "$B/volume/set"; echo
echo -n "persisted master_volume: "
curl -s -b "$J" "$B/api/status" | python3 -c 'import sys,json; print(json.load(sys.stdin)["master_volume"])'
echo
echo "=== AUDIBLE: one beep at 60% ==="
curl -s -b "$J" -H "X-CSRF: $CSRF" -H "X-Requested-With: fetch" --data "value=60&tone=1" "$B/volume/set"; echo
sleep 2
echo "=== restore master=100 (silent) ==="
curl -s -b "$J" -H "X-CSRF: $CSRF" -H "X-Requested-With: fetch" --data "value=100&tone=0" "$B/volume/set"; echo
rm -f "$J"
echo DONE
