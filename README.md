# Pi Audio Portal

A professional, persistent audio and video appliance designed for Raspberry Pi 5. The Pi Audio Portal provides a centralized system for scheduling audio and video content to be played through an HDMI-connected soundbar and TV, featuring a custom administrative web dashboard for seamless management.

## 🚀 Features

- **Scheduled Playback**: Precise scheduling of audio and video sessions with support for specific days of the week, custom durations, and looping.
- **Dynamic Floating Screen**: A custom-built, burn-in resistant "idle" screen featuring dim, drifting text (clock, date, and next session) that bounces across the display using GPU-accelerated panning.
- **Web Dashboard**: A secure, login-gated portal for managing the media library, configuring schedules, and adjusting system settings.
- **YouTube Integration**: Integrated `yt-dlp` support to download audio or video directly from YouTube into the appliance library.
- **Hardware Optimized**: 
  - Optimized for Raspberry Pi 5 on Ubuntu.
  - Direct DRM/KMS output for low-overhead video rendering via `mpv`.
  - Custom HDMI wake pre-roll to ensure a seamless start for scheduled content.
  - Robust time synchronization via HTTP (`htpdate`) for networks with blocked NTP ports.

## 🛠️ Technical Architecture

- **Backend**: Python 3.14 / Flask / Waitress.
- **Database**: SQLite (WAL mode) for reliable session and media tracking.
- **Playback Engine**: 
  - **Audio**: `ffmpeg` pipeline → `aplay`.
  - **Video**: `mpv` using GPU DRM context for maximum performance and stability.
- **Deployment**: Managed via `systemd` for high availability and automatic recovery.

## 📦 Installation & Setup

### Prerequisites
- Raspberry Pi 5
- Ubuntu (aarch64)
- HDMI display/soundbar

### Quick Start
1. Clone the repository:
   ```bash
   git clone https://github.com/vaishnevefx/audio-pi.git
   cd audio-pi
   ```
2. Run the provisioning script:
   ```bash
   sudo bash deploy/provision.sh
   ```
3. Access the portal at `http://<your-pi-ip>:8080`.

## ⚙️ Configuration
System settings are available via the Web Portal under the **Settings** tab, allowing administrators to configure:
- ALSA audio device and master volume.
- DRM connector and resolution.
- Floating screen speed, refresh rate, and "Night Mode" (black screen) hours for OLED/LCD protection.
- System timezone.

## 🛡️ Security
- Login-gated access for administrators and contributors.
- CSRF protection on all state-changing requests.
- Isolated data directory for media and configuration.
