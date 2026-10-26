#!/usr/bin/env bash
# Robust offline-friendly time sync for a network that blocks NTP:
#   - htpdate sets the clock from HTTP Date headers (port 80, no TLS/cert dependency)
#   - fake-hwclock + RTC write-back keep time sane across reboots/power loss
set -e

echo "[1/6] Installing fake-hwclock + htpdate..."
sudo -n DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=300 install -y fake-hwclock htpdate >/tmp/time_apt.log 2>&1 || true

echo "[2/6] Disabling internet chrony (cannot reach NTP on this network)..."
sudo -n systemctl disable --now chrony 2>/dev/null || true
sudo -n systemctl disable --now chronyd 2>/dev/null || true

echo "[3/6] Installing /usr/local/bin/pi-timesync.sh..."
sudo -n tee /usr/local/bin/pi-timesync.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
# Set clock from HTTP Date headers, then persist to hardware RTC + disk.
SERVERS="http://www.google.com http://connectivitycheck.gstatic.com/generate_204 http://www.msftconnecttest.com/connecttest.txt"
/usr/sbin/htpdate -s -t $SERVERS >/var/log/pi-timesync.log 2>&1
/usr/sbin/hwclock -w 2>/dev/null || true
command -v fake-hwclock >/dev/null 2>&1 && fake-hwclock save 2>/dev/null || true
EOF
sudo -n chmod +x /usr/local/bin/pi-timesync.sh

echo "[4/6] Installing systemd service + timer..."
sudo -n tee /etc/systemd/system/pi-timesync.service >/dev/null <<'EOF'
[Unit]
Description=Sync clock over HTTP (htpdate) and persist to RTC
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/pi-timesync.sh
EOF
sudo -n tee /etc/systemd/system/pi-timesync.timer >/dev/null <<'EOF'
[Unit]
Description=Periodic HTTP time sync
[Timer]
OnBootSec=20
OnUnitActiveSec=30min
Persistent=true
[Install]
WantedBy=timers.target
EOF

echo "[5/6] Enabling + running..."
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now pi-timesync.timer
sudo -n systemctl start pi-timesync.service
sleep 2

echo "[6/6] Status:"
echo -n "timer enabled: "; systemctl is-enabled pi-timesync.timer
echo -n "timer active:  "; systemctl is-active pi-timesync.timer
echo -n "fake-hwclock:  "; systemctl is-enabled fake-hwclock 2>/dev/null || echo "n/a"
echo -n "chrony:        "; systemctl is-active chrony 2>/dev/null || echo "inactive"
echo "last sync log:"; tail -4 /var/log/pi-timesync.log 2>/dev/null
echo -n "system time:   "; date "+%F %T %Z"
echo -n "rtc time:      "; sudo -n hwclock -r 2>/dev/null || echo "n/a"
echo "SETUP_TIME_DONE"
