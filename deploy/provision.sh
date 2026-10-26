#!/usr/bin/env bash
# Provisions system + python dependencies for the Pi Audio Portal.
# Safe to re-run (idempotent).
set -euo pipefail

APP_DIR=/home/ubuntu/audio-portal
DATA_DIR="$APP_DIR/data"
AUDIO_DIR="$DATA_DIR/audio"

echo "[1/5] Installing apt packages (venv, pip, ffmpeg, alsa-utils)..."
sudo -n apt-get -o DPkg::Lock::Timeout=300 update -y
sudo -n DEBIAN_FRONTEND=noninteractive apt-get -o DPkg::Lock::Timeout=300 install -y \
    python3-venv python3-pip ffmpeg alsa-utils

echo "[2/5] Creating directories..."
mkdir -p "$AUDIO_DIR"

echo "[3/5] Creating virtualenv..."
if [ ! -x "$APP_DIR/venv/bin/python" ]; then
    python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" install --upgrade pip wheel

echo "[4/5] Installing python deps (flask, waitress, yt-dlp)..."
"$APP_DIR/venv/bin/pip" install --upgrade flask waitress yt-dlp

echo "[5/5] Versions:"
"$APP_DIR/venv/bin/python" -c "import flask, waitress; print('flask', flask.__version__)"
"$APP_DIR/venv/bin/yt-dlp" --version
echo "PROVISION_DONE"
