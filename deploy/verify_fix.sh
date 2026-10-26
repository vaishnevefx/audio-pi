#!/usr/bin/env bash
B=http://127.0.0.1:8080
PID=$(systemctl show -p MainPID --value audio-portal)
fdcount(){ sudo -n ls /proc/$PID/fd 2>/dev/null | wc -l; }
echo "PID=$PID  initial FDs=$(fdcount)"

for i in $(seq 1 25); do
  J=/tmp/jx.txt; rm -f "$J"
  curl -s -c "$J" "$B/login" >/dev/null
  curl -s -b "$J" -c "$J" -o /dev/null \
    --data-urlencode "username=changemaker" --data-urlencode "password=vOyiPnpEGsd8r5C9" "$B/login"
  curl -s -b "$J" -o /dev/null "$B/api/status"
  rm -f "$J"
done
echo "after 25 login+status cycles FDs=$(fdcount)"
sleep 12
echo "after ~2 scheduler ticks     FDs=$(fdcount)"

echo "--- login checks (expect 302) ---"
chk(){ J=/tmp/jc.txt; rm -f "$J"; curl -s -c "$J" "$B/login" >/dev/null;
  c=$(curl -s -b "$J" -c "$J" -o /dev/null -w '%{http_code}' \
    --data-urlencode "username=$1" --data-urlencode "password=$2" "$B/login");
  echo "$1 login=$c"; rm -f "$J"; }
chk changemaker vOyiPnpEGsd8r5C9
chk admin El0vwUbgSA-oMRZj
echo DONE
