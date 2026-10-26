#!/usr/bin/env bash
echo "=== HTTPS egress (expected open) ==="
curl -sS -o /dev/null -w 'https www.google.com: %{http_code}\n' https://www.google.com || echo "https failed"
echo
echo "=== HTTP port 80 egress ==="
curl -sS -m 8 -o /dev/null -w 'http www.google.com: %{http_code}\n' http://www.google.com || echo "http(80) failed/blocked"
echo
echo "=== install htpdate ==="
sudo -n DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=300 install -y htpdate >/tmp/htp.log 2>&1
echo "apt exit $?  ($(dpkg -l htpdate 2>/dev/null | awk '/^ii/{print $3}'))"
echo
echo "=== htpdate debug query over HTTPS (does NOT change the clock) ==="
sudo -n htpdate -d -t https://www.google.com https://www.cloudflare.com https://www.bing.com 2>&1 | tail -20
echo "DONE"
