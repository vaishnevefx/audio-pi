#!/usr/bin/env bash
B=http://127.0.0.1:8080
J=/tmp/dj.txt
PY=/home/ubuntu/audio-portal/venv/bin/python
prop() { (cd /home/ubuntu/audio-portal && $PY -c "import display;print(display.get_prop('$1'))"); }
PW=$(cat /home/ubuntu/audio-portal/data/INITIAL_ADMIN_PASSWORD.txt 2>/dev/null)
rm -f "$J"; curl -s -c "$J" "$B/login" >/dev/null
code=$(curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}' --data-urlencode "username=changemaker" --data-urlencode "password=$PW" "$B/login")
[ "$code" != "302" ] && code=$(curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}' --data-urlencode "username=admin" --data-urlencode "password=El0vwUbgSA-oMRZj" "$B/login")
echo "login: $code"
CSRF=$(curl -s -b "$J" "$B/" | grep -oE 'name="csrf" content="[^"]+"' | sed 's/.*content="//; s/"$//')
post() { curl -s -b "$J" -H "X-CSRF: $CSRF" -H "X-Requested-With: fetch" --data "$1" "$B$2"; echo; }
st() { curl -s -b "$J" "$B/api/status" | $PY -c 'import sys,json;d=json.load(sys.stdin);print({k:d.get(k) for k in ("playing","title","remaining")})'; }

echo "== idle: path=$(prop path) idle-active=$(prop idle-active)"
echo "== VIDEO (silent) + AUDIO via play-now not available; plain video test =="
post "audio_id=9&video=1&minutes=1" /play
sleep 4
echo "during video: path=$(prop path)"; st
echo "stopping..."; post "x=1" /stop
sleep 2
echo "after stop: path=$(prop path) idle-active=$(prop idle-active)"; st
echo "== AUDIO ONLY (track 8) =="
post "audio_id=8&minutes=1" /play
sleep 4; st
post "x=1" /stop; sleep 1
echo "== final: idle-active=$(prop idle-active) =="
echo "play_log:"
(cd /home/ubuntu/audio-portal && $PY -c "
import db
with db.get_conn() as c:
    for r in c.execute('select id,title,trigger,status,detail from play_log order by id desc limit 3').fetchall(): print(dict(r))")
rm -f "$J"
echo DONE
