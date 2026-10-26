"""Static paths and defaults for the Pi Audio Portal."""
import os

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(APP_DIR, "data")
AUDIO_DIR = os.path.join(DATA_DIR, "audio")
DB_PATH = os.path.join(DATA_DIR, "app.db")
SECRET_KEY_PATH = os.path.join(DATA_DIR, "secret_key")
INITIAL_ADMIN_PW_PATH = os.path.join(DATA_DIR, "INITIAL_ADMIN_PASSWORD.txt")

# Web server
HOST = "0.0.0.0"
PORT = 8080

# Defaults (seeded into the settings table; editable in the Settings tab)
DEFAULTS = {
    "audio_device": "plughw:CARD=vc4hdmi0,DEV=0",
    "timezone": "Asia/Kolkata",
    "default_volume": "80",     # 0-100, default level for new schedules / play-now
    "master_volume": "100",     # 0-100, master gain applied to ALL output
    "muted": "0",               # 1 = silence all output
    "preroll_seconds": "2",     # HDMI wake lead-in to avoid clipped starts
    "drm_device": "/dev/dri/card1",   # KMS device driving the HDMI/TV
    "drm_connector": "HDMI-A-1",      # connected HDMI output
    "drm_mode": "1920x1080",          # output mode (TV upscales; smooth on Pi)
    "idle_screen": "1",               # 1 = show the clock on the TV when idle
    "playing_screen": "1",            # 1 = show "now playing" on the TV for audio sessions
    "display_speed": "18",            # floating screen drift speed, pixels per second
    "display_hz": "30",               # floating screen motion updates per second
    "night_mode": "1",                # 1 = idle screen goes fully black at night
    "night_start": "22",              # hour (0-23) the black night screen begins
    "night_end": "7",                 # hour (0-23) it ends
}

# Allowed upload / import extensions
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus"}
ALLOWED_VIDEO_EXT = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"}
ALLOWED_MEDIA_EXT = ALLOWED_AUDIO_EXT | ALLOWED_VIDEO_EXT

os.makedirs(AUDIO_DIR, exist_ok=True)
