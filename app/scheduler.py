"""Background scheduler: fires schedules at their local start time on enabled days.

Dependency-free: a daemon thread wakes every few seconds, compares the current
local time (in the configured timezone) against each enabled schedule, and starts
playback once per matching minute.
"""
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import config
import db
import player

TICK_SECONDS = 5
_fired = set()          # keys of (schedule_id, 'YYYY-MM-DD', 'HH:MM') already fired
_thread = None
_stop = threading.Event()


def _tz():
    name = db.get_setting("timezone", config.DEFAULTS["timezone"])
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("UTC")


def _enabled_schedules():
    with db.get_conn() as conn:
        return conn.execute(
            "SELECT s.*, "
            "a.filename AS audio_filename, a.title AS audio_title, a.kind AS audio_kind, "
            "v.filename AS video_filename, v.title AS video_title "
            "FROM schedules s "
            "LEFT JOIN audio_files a ON a.id = s.audio_id "
            "LEFT JOIN audio_files v ON v.id = s.video_id "
            "WHERE s.enabled = 1"
        ).fetchall()


def _days_set(days_str):
    out = set()
    for part in (days_str or "").split(","):
        part = part.strip()
        if part.isdigit():
            out.add(int(part))
    return out


def _tick():
    now = datetime.now(_tz())
    hhmm = now.strftime("%H:%M")
    today = now.strftime("%Y-%m-%d")
    iso_dow = now.isoweekday()  # Mon=1 .. Sun=7

    for s in _enabled_schedules():
        if s["start_time"] != hhmm:
            continue
        if iso_dow not in _days_set(s["days"]):
            continue
        key = (s["id"], today, hhmm)
        if key in _fired:
            continue
        _fired.add(key)

        video_row = None
        if s["video_id"] and s["video_filename"]:
            video_row = {"id": s["video_id"], "title": s["video_title"],
                         "filename": s["video_filename"], "kind": "video"}
        audio_row = None
        if s["audio_id"] and s["audio_filename"]:
            audio_row = {"id": s["audio_id"], "title": s["audio_title"],
                         "filename": s["audio_filename"], "kind": s["audio_kind"] or "audio"}
        if not video_row and not audio_row:
            _log_skip(s, "No media assigned")
            continue

        player.play_schedule(
            video_row=video_row,
            audio_row=audio_row,
            mute_video_audio=bool(s["mute_video_audio"]),
            volume=s["volume"],
            total_seconds=s["duration_seconds"],
            loop=bool(s["loop"]),
            trigger=s["name"],
            schedule_id=s["id"],
        )


def _log_skip(s, reason):
    try:
        with db.get_conn() as conn:
            conn.execute(
                "INSERT INTO play_log(title, trigger, schedule_id, started_at, ended_at, status, detail) "
                "VALUES(?,?,?,?,?, 'error', ?)",
                (s["name"], s["name"], s["id"], int(time.time()), int(time.time()), reason),
            )
    except Exception:
        pass


def _prune_fired(now):
    # keep only today's keys
    today = now.strftime("%Y-%m-%d")
    stale = {k for k in _fired if k[1] != today}
    _fired.difference_update(stale)


def _loop():
    while not _stop.is_set():
        try:
            _tick()
            _prune_fired(datetime.now(_tz()))
        except Exception:
            pass
        _stop.wait(TICK_SECONDS)


def next_runs(limit=8):
    """Compute the next fire datetime for each enabled, assigned schedule."""
    tz = _tz()
    now = datetime.now(tz)
    runs = []
    for s in _enabled_schedules():
        days = _days_set(s["days"])
        if not days:
            continue
        try:
            hh, mm = [int(x) for x in s["start_time"].split(":")]
        except Exception:
            continue
        for ahead in range(0, 8):
            cand = (now + timedelta(days=ahead)).replace(
                hour=hh, minute=mm, second=0, microsecond=0)
            if cand.isoweekday() in days and cand > now:
                runs.append({
                    "name": s["name"],
                    "when": cand,
                    "assigned": bool(s["audio_id"] or s["video_id"]),
                    "audio_title": s["video_title"] if s["video_id"] else s["audio_title"],
                })
                break
    runs.sort(key=lambda r: r["when"])
    return runs[:limit]


def start():
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, daemon=True, name="scheduler")
    _thread.start()
