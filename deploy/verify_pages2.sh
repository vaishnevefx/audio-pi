#!/usr/bin/env bash
B=http://127.0.0.1:8080
J=/tmp/pj.txt
PW=$(cat /home/ubuntu/audio-portal/data/INITIAL_ADMIN_PASSWORD.txt 2>/dev/null)
rm -f "$J"; curl -s -c "$J" "$B/login" >/dev/null
code=$(curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}' \
  --data-urlencode "username=changemaker" --data-urlencode "password=$PW" "$B/login")
if [ "$code" != "302" ]; then
  code=$(curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}' \
    --data-urlencode "username=admin" --data-urlencode "password=El0vwUbgSA-oMRZj" "$B/login")
fi
echo "login: $code"
for p in / /schedules /library /youtube /settings /api/status; do
  out=$(curl -s -b "$J" -o /tmp/pg.html -w '%{http_code}' "$B$p")
  err=$(grep -ciE "Internal Server Error|Traceback|jinja2|BuildError|UndefinedError" /tmp/pg.html || true)
  echo "$p -> HTTP $out  errors:$err"
done
rm -f "$J" /tmp/pg.html
echo DONE
