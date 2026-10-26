#!/usr/bin/env bash
B=http://127.0.0.1:8080
J=/tmp/cj.txt
PW=$(cat /home/ubuntu/audio-portal/data/INITIAL_ADMIN_PASSWORD.txt)
rm -f "$J"
curl -s -c "$J" "$B/login" > /dev/null
code=$(curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}' \
       --data-urlencode "username=admin" --data-urlencode "password=$PW" "$B/login")
echo "login POST (expect 302): $code"
for p in / /schedules /library /youtube /settings /api/status; do
  out=$(curl -s -b "$J" -o /tmp/page.html -w '%{http_code}' "$B$p")
  err=$(grep -ciE "Internal Server Error|Traceback|jinja2" /tmp/page.html || true)
  echo "$p -> HTTP $out  template_errors:$err"
done
rm -f "$J" /tmp/page.html
echo "DONE"
