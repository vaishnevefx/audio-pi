#!/usr/bin/env bash
B=http://127.0.0.1:8080
J=/tmp/aj.txt
rm -f "$J"
curl -s -c "$J" "$B/login" >/dev/null
echo -n "admin login (expect 302): "
curl -s -b "$J" -c "$J" -o /dev/null -w "%{http_code}\n" \
  --data-urlencode "username=admin" --data-urlencode "password=El0vwUbgSA-oMRZj" "$B/login"
echo -n "authed dashboard (expect 200): "
curl -s -b "$J" -o /dev/null -w "%{http_code}\n" "$B/"
rm -f "$J"
echo DONE
