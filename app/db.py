"""SQLite storage: schema, connection helpers, settings, and first-run seeding."""
import os
import sqlite3
import hashlib
import secrets
import subprocess
import time
from contextlib import contextmanager

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    username   TEXT UNIQUE NOT NULL,
    pw_hash    TEXT NOT NULL,
    pw_salt    TEXT NOT NULL,
    is_admin   INTEGER NOT NULL DEFAULT 0,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audio_files (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    filename         TEXT NOT NULL,          -- basename inside data/audio
    duration_seconds REAL,
    kind             TEXT NOT NULL DEFAULT 'audio',   -- audio | video
    source           TEXT NOT NULL DEFAULT 'upload',  -- upload | youtube | builtin
    source_url       TEXT,
    created_at       INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    audio_id         INTEGER,                 -- audio track for the soundbar (NULL = none)
    video_id         INTEGER,                 -- video for the TV (NULL = none)
    start_time       TEXT NOT NULL,           -- 'HH:MM' local time
    duration_seconds INTEGER NOT NULL,        -- how long the session runs
    days             TEXT NOT NULL,           -- ISO weekdays, e.g. '1,2,3,4,5'
    volume           INTEGER NOT NULL DEFAULT 80,
    loop             INTEGER NOT NULL DEFAULT 1,  -- 1 = loop to fill duration
    video            INTEGER NOT NULL DEFAULT 0,  -- legacy flag (unused)
    mute_video_audio INTEGER NOT NULL DEFAULT 1,  -- mute video's own audio when an audio track is set
    enabled          INTEGER NOT NULL DEFAULT 1,
    created_at       INTEGER NOT NULL,
    FOREIGN KEY (audio_id) REFERENCES audio_files(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS play_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT,
    trigger     TEXT,                          -- schedule name | 'Test' | 'Manual'
    schedule_id INTEGER,
    audio_id    INTEGER,
    started_at  INTEGER NOT NULL,
    ended_at    INTEGER,
    status      TEXT NOT NULL DEFAULT 'playing',  -- playing | done | stopped | error
    detail      TEXT
);
"""


def _connect():
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


@contextmanager
def get_conn():
    """Yield a connection, commit on success / rollback on error, ALWAYS close.

    (sqlite3's own `with conn:` commits but never closes — that leaks file
    descriptors until the process hits 'Too many open files'.)
    """
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _add_column_if_missing(conn, table, column, decl):
    cols = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init_db():
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        # migrations for databases created before these columns existed
        _add_column_if_missing(conn, "audio_files", "kind", "TEXT NOT NULL DEFAULT 'audio'")
        _add_column_if_missing(conn, "schedules", "video", "INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, "schedules", "video_id", "INTEGER")
        _add_column_if_missing(conn, "schedules", "mute_video_audio", "INTEGER NOT NULL DEFAULT 1")
        _add_column_if_missing(conn, "users", "is_admin", "INTEGER NOT NULL DEFAULT 0")


# ---------- settings ----------
def get_setting(key, default=None):
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, str(value)),
        )


# ---------- passwords (stdlib scrypt, no native deps) ----------
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt.encode("utf-8"),
        n=2 ** 14, r=8, p=1, dklen=32,
    )
    return digest.hex(), salt


def verify_password(password, pw_hash, pw_salt):
    calc, _ = hash_password(password, pw_salt)
    return secrets.compare_digest(calc, pw_hash)


def get_user(username):
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()


def is_admin(username):
    row = get_user(username)
    return bool(row and row["is_admin"])


def set_user_password(username, password):
    pw_hash, pw_salt = hash_password(password)
    with get_conn() as conn:
        conn.execute("UPDATE users SET pw_hash=?, pw_salt=? WHERE username=?",
                     (pw_hash, pw_salt, username))


# ---------- audio helpers ----------
def _probe_duration(path):
    """Return media duration in seconds via ffprobe, or None."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30,
        )
        return float(out.stdout.strip())
    except Exception:
        return None


def _has_video(path):
    """True only for a real moving-video stream (ignores mp3 cover-art pictures)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v",
             "-show_entries", "stream_disposition=attached_pic",
             "-of", "csv=p=0", path],
            capture_output=True, text=True, timeout=30,
        )
        return any(line.strip() == "0" for line in out.stdout.splitlines())
    except Exception:
        return False


def add_audio(title, filename, source="upload", source_url=None, duration=None, kind=None):
    path = os.path.join(config.AUDIO_DIR, filename)
    if duration is None:
        duration = _probe_duration(path)
    if kind is None:
        kind = "video" if _has_video(path) else "audio"
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO audio_files(title, filename, duration_seconds, kind, source, source_url, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (title, filename, duration, kind, source, source_url, int(time.time())),
        )
        return cur.lastrowid


# ---------- first-run seeding ----------
def ensure_test_tone():
    """Generate a pleasant built-in test tone if it is missing."""
    with get_conn() as conn:
        row = conn.execute("SELECT id FROM audio_files WHERE source='builtin'").fetchone()
    if row:
        return
    fname = "builtin_test_tone.mp3"
    path = os.path.join(config.AUDIO_DIR, fname)
    if not os.path.exists(path):
        try:
            subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", "sine=frequency=528:duration=6",
                 "-af", "tremolo=f=4:d=0.5,volume=0.5",
                 path],
                check=True, timeout=60,
            )
        except Exception:
            return
    add_audio("Built-in Test Tone", fname, source="builtin", duration=6.0)


def ensure_defaults():
    # settings
    for key, val in config.DEFAULTS.items():
        if get_setting(key) is None:
            set_setting(key, val)

    # admin user (generate a random password the first time; write it out once)
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
    if n == 0:
        pw = secrets.token_urlsafe(12)
        pw_hash, pw_salt = hash_password(pw)
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users(username, pw_hash, pw_salt, is_admin, created_at) VALUES(?,?,?,?,?)",
                ("changemaker", pw_hash, pw_salt, 1, int(time.time())),
            )
        with open(config.INITIAL_ADMIN_PW_PATH, "w") as f:
            f.write(pw + "\n")
        os.chmod(config.INITIAL_ADMIN_PW_PATH, 0o600)

    ensure_test_tone()

    # default schedules (only if none exist yet)
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) AS c FROM schedules").fetchone()["c"]
    if n == 0:
        vol = int(get_setting("default_volume", "80"))
        now = int(time.time())
        weekdays = "1,2,3,4,5"
        defaults = [
            ("Focus Time (Morning)",   "10:00", 30 * 60, weekdays, vol, 1),
            ("Focus Time (Afternoon)", "14:00", 30 * 60, weekdays, vol, 1),
            ("Stretching (Morning)",   "10:55", 5 * 60,  weekdays, vol, 1),
            ("Stretching (Afternoon)", "14:55", 5 * 60,  weekdays, vol, 1),
        ]
        with get_conn() as conn:
            for name, start, dur, days, v, loop in defaults:
                conn.execute(
                    "INSERT INTO schedules(name, audio_id, start_time, duration_seconds, days, "
                    "volume, loop, enabled, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                    (name, None, start, dur, days, v, loop, 1, now),
                )


def ensure_seed():
    ensure_defaults()
