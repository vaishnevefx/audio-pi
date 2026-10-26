#!/usr/bin/env bash
echo "Testing PLAIN (non-NTS) NTP to public servers over UDP 123..."
for s in time.google.com time.cloudflare.com pool.ntp.org 216.239.35.0 162.159.200.123; do
  echo "--- $s ---"
  sudo -n chronyd -Q -t 5 "server $s iburst" 2>&1 \
    | grep -iE 'offset|wrong by|No suitable|Timeout|resolve|unreachable' \
    | sed 's/^/   /' || echo "   (no output)"
done
echo "DONE"
