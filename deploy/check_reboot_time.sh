#!/usr/bin/env bash
echo "=== htpdate over PLAIN HTTP (port 80, no cert dependency) ==="
sudo -n htpdate -d -t http://www.google.com http://www.bing.com 2>&1 \
  | grep -iE '=>|Offset|no timestamp' | tail -8

echo
echo "=== RTC hardware (Pi 5 has one; needs a coin cell to persist power-off) ==="
ls -l /dev/rtc* 2>/dev/null || echo "no /dev/rtc"
echo -n "rtc name: "; cat /sys/class/rtc/rtc0/name 2>/dev/null || echo "n/a"
echo -n "hwclock read: "; sudo -n hwclock -r 2>&1 | head -1

echo
echo "=== fake-hwclock (restores last-known time forward on boot) ==="
(dpkg -l fake-hwclock 2>/dev/null | awk '/^ii/{print "installed "$3}') || true
dpkg -l fake-hwclock >/dev/null 2>&1 || echo "fake-hwclock NOT installed"
ls -l /etc/fake-hwclock.data 2>/dev/null || echo "(no saved timestamp file)"

echo
echo "=== can the Pi reach the laptop 10.10.20.51 at all? ==="
ping -c 2 -W 2 10.10.20.51 >/dev/null 2>&1 && echo "laptop reachable (ping ok)" || echo "laptop NOT reachable by ping"
echo -n "does laptop already answer NTP? "
sudo -n chronyd -Q -t 4 'server 10.10.20.51 iburst' 2>&1 | grep -iE 'offset|wrong by|Timeout|No suitable' | tail -1
echo DONE
