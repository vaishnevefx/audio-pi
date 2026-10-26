#!/usr/bin/env bash
set -e
echo "[1] install updated unit (video,render groups)..."
sed -i 's/\r$//' /home/ubuntu/audio-portal.service
sudo -n cp /home/ubuntu/audio-portal.service /etc/systemd/system/audio-portal.service
rm -f /home/ubuntu/audio-portal.service

echo "[2] mask getty@tty1 (free the console for DRM video)..."
sudo -n systemctl stop getty@tty1 2>/dev/null || true
sudo -n systemctl mask getty@tty1 2>/dev/null || true

echo "[3] boot service to unbind the framebuffer console..."
sudo -n tee /usr/local/bin/pi-free-console.sh >/dev/null <<'EOF'
#!/usr/bin/env bash
for v in /sys/class/vtconsole/vtcon*; do
  if grep -qi "frame buffer" "$v/name" 2>/dev/null; then echo 0 > "$v/bind" 2>/dev/null; fi
done
EOF
sudo -n chmod +x /usr/local/bin/pi-free-console.sh
sudo -n tee /etc/systemd/system/pi-free-console.service >/dev/null <<'EOF'
[Unit]
Description=Unbind framebuffer console so mpv can drive the TV (DRM/KMS)
After=multi-user.target
[Service]
Type=oneshot
ExecStart=/usr/local/bin/pi-free-console.sh
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
EOF

echo "[4] reload + enable + restart..."
sudo -n systemctl daemon-reload
sudo -n systemctl enable --now pi-free-console.service
sudo -n systemctl restart audio-portal
sleep 3
PID=$(systemctl show -p MainPID --value audio-portal)
echo "audio-portal:   $(systemctl is-active audio-portal) (pid $PID)"
echo "service groups: $(grep -i '^Groups:' /proc/$PID/status 2>/dev/null)"
echo "pi-free-console:$(systemctl is-active pi-free-console.service)"
echo "getty@tty1:     $(systemctl is-enabled getty@tty1 2>&1)"
echo "fbcon bind:     $(cat /sys/class/vtconsole/vtcon1/bind 2>/dev/null)"
echo DONE
