#!/usr/bin/env bash
# Persist wlan0 MTU=1400 to work around the WiFi path-MTU black hole.
# Two layers: a systemd .link rule (applied at device init) and a boot
# oneshot that re-asserts it after DHCP (in case DHCP pushes 1500).
set -e

IP_BIN=$(command -v ip)
echo "ip binary: $IP_BIN"

echo "[1/3] .link rule..."
sudo -n tee /etc/systemd/network/10-wlan0-mtu.link >/dev/null <<'EOF'
[Match]
OriginalName=wlan0

[Link]
MTUBytes=1400
EOF

echo "[2/3] boot oneshot..."
sudo -n tee /etc/systemd/system/pi-mtu.service >/dev/null <<EOF
[Unit]
Description=Set wlan0 MTU to 1400 (WiFi path-MTU workaround)
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=$IP_BIN link set wlan0 mtu 1400
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

echo "[3/3] enable + apply..."
sudo -n systemctl daemon-reload
sudo -n systemctl enable pi-mtu.service
sudo -n systemctl start pi-mtu.service
sudo -n "$IP_BIN" link set wlan0 mtu 1400
echo -n "mtu now: "; ip -o link show wlan0 | sed -n 's/.*\(mtu [0-9]*\).*/\1/p'
echo -n "service enabled: "; systemctl is-enabled pi-mtu.service
echo -n "service active:  "; systemctl is-active pi-mtu.service
echo "MTU_SETUP_DONE"
