#!/usr/bin/env bash
echo "=== what chrony is currently configured to use ==="
grep -rhE '^[[:space:]]*(server|pool)' /etc/chrony/ 2>/dev/null || echo "(none)"

echo
echo "=== default gateway (router) ==="
GW=$(ip route show default | awk '{print $3; exit}')
echo "gateway: ${GW:-none}"

echo
echo "=== DHCP-advertised NTP servers (option 42) ==="
NTPD=$(grep -rhiE '^NTP=' /run/systemd/netif/leases/ 2>/dev/null | sed 's/^NTP=//I' | tr ',' ' ')
echo "from networkd leases: ${NTPD:-none}"
grep -rhiE 'ntp|option.*42' /var/lib/dhcp/ /var/lib/NetworkManager/ 2>/dev/null | head -5

echo
echo "=== domain + name-based candidates ==="
DOM=$(hostname -d 2>/dev/null)
echo "domain: ${DOM:-none}"
for n in ntp time time1 timeserver; do
  [ -n "$DOM" ] && getent hosts "$n.$DOM" 2>/dev/null
  getent hosts "$n" 2>/dev/null
done

echo
echo "=== testing candidate servers (safe one-shot query, no clock change) ==="
CANDS=$(printf '%s %s\n' "$GW" "$NTPD" | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]' | sort -u)
[ -z "$CANDS" ] && echo "(no numeric candidates found)"
for ip in $CANDS; do
  echo "--- $ip ---"
  sudo -n chronyd -Q -t 4 "server $ip iburst" 2>&1 | grep -iE 'offset|System clock|No suitable|reachable|wrong by' || echo "   no response / not an NTP server"
done
echo "DONE"
