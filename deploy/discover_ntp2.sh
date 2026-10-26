#!/usr/bin/env bash
echo "=== upstream DNS servers (often also NTP / domain controllers) ==="
resolvectl status 2>/dev/null | grep -iE 'DNS Servers|Current DNS Server' || true
grep -h nameserver /run/systemd/resolve/resolv.conf /etc/resolv.conf 2>/dev/null | sort -u

echo
echo "=== full test: gateway 10.10.0.1 ==="
sudo -n chronyd -Q -t 5 'server 10.10.0.1 iburst' 2>&1

echo
echo "=== test upstream DNS IPs as NTP servers ==="
DNS=$(grep -h nameserver /run/systemd/resolve/resolv.conf /etc/resolv.conf 2>/dev/null \
      | awk '{print $2}' | grep -vE '^127\.' | sort -u)
echo "dns candidates: ${DNS:-none}"
for ip in $DNS; do
  echo "--- $ip ---"
  sudo -n chronyd -Q -t 4 "server $ip iburst" 2>&1 | grep -iE 'offset|wrong by|No suitable|reachable' || echo "   no NTP response"
done
echo "DONE"
