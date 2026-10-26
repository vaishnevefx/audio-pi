"""Playback engine.

A playback can run a VIDEO stream (mpv -> TV via DRM) and/or an AUDIO stream
(ffmpeg | aplay -> soundbar) at the same time:

  * video only                -> mpv plays the video with its own audio
  * audio only                -> ffmpeg | aplay
  * video + audio, muted      -> mpv video (silent) + audio track on the soundbar  (default)
  * video + audio, not muted  -> mpv video with its own audio (audio track ignored)

Timed sessions loop and are bounded by a timer. Only one playback runs at a time.
"""
import os
import threading
import time
import subprocess

import config
import db
import display

_lock = threading.Lock()
_state = {
    "playing": False,
    "transient": False,
    "title": None,
    "trigger": None,
    "started_at": None,
    "ends_at": None,
    "log_id": None,
    "token": 0,
    "procs": [],
}

AFMT = "aformat=sample_rates=48000:channel_layouts=stereo"


def _master_mute():
    master = int(db.get_setting("master_volume", "100") or 100)
    muted = db.get_setting("muted", "0") == "1"
    return master, muted


def status():
    if not _lock.acquire(timeout=1.0):
        return {"playing": False, "title": None, "trigger": None,
                "started_at": None, "ends_at": None}
    try:
        playing = _state["playing"] and not _state["transient"]
        return {
            "playing": playing,
            "title": _state["title"] if playing else None,
            "trigger": _state["trigger"] if playing else None,
            "started_at": _state["started_at"] if playing else None,
            "ends_at": _state["ends_at"] if playing else None,
        }
    finally:
        _lock.release()


# ---------------- command builders ----------------
def _file_ffmpeg_args(path, volume, preroll, loop):
    vol = max(0.0, min(2.0, volume / 100.0))
    args = ["ffmpeg", "-loglevel", "error", "-nostdin"]
    use_pre = preroll and preroll > 0
    if use_pre:
        args += ["-f", "lavfi", "-i",
                 f"sine=frequency=90:duration={preroll}:sample_rate=48000"]
    if loop:
        args += ["-stream_loop", "-1"]
    args += ["-i", path]
    if use_pre:
        filt = (f"[0:a]{AFMT},volume=0.02[w];"
                f"[1:a]{AFMT},volume={vol:.3f}[m];"
                f"[w][m]concat=n=2:v=0:a=1[out]")
    else:
        filt = f"[0:a]{AFMT},volume={vol:.3f}[out]"
    args += ["-filter_complex", filt, "-map", "[out]", "-f", "wav", "-"]
    return args


def _tone_ffmpeg_args(volume, freq=880, dur=0.5, wake=0.6):
    vol = max(0.0, min(2.0, volume / 100.0))
    args = ["ffmpeg", "-loglevel", "error", "-nostdin",
            "-f", "lavfi", "-i", f"sine=frequency=110:duration={wake}:sample_rate=48000",
            "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={dur}:sample_rate=48000"]
    filt = (f"[0:a]{AFMT},volume=0.02[w];"
            f"[1:a]{AFMT},volume={vol:.3f}[b];"
            f"[w][b]concat=n=2:v=0:a=1[out]")
    args += ["-filter_complex", filt, "-map", "[out]", "-f", "wav", "-"]
    return args


# ---------------- process builders (return started process-like list) ----------------
def _audio_pipe(ff_args, device):
    ffmpeg = subprocess.Popen(ff_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    aplay = subprocess.Popen(["aplay", "-q", "-D", device],
                             stdin=ffmpeg.stdout, stderr=subprocess.PIPE)
    ffmpeg.stdout.close()
    return [ffmpeg, aplay]


def _video_job(path, volume, mute_audio, loop):
    """Video plays inside the persistent display mpv (see display.py)."""
    return [display.start_video(path, volume, mute_audio, loop)]


def _read(stream):
    try:
        return (stream.read() or b"").decode("utf-8", "ignore")
    except Exception:
        return ""


# ---------------- lifecycle ----------------
def _run_general(token, builders, log_id):
    status_str, detail = "done", ""
    try:
        procs = []
        for b in builders:
            procs.extend(b())
        with _lock:
            _state["procs"] = procs
        for p in procs:
            p.wait()
        with _lock:
            stopped = _state["token"] != token
        if stopped:
            status_str = "stopped"
        elif any(p.returncode not in (0, None) for p in procs):
            status_str = "error"
            detail = " ".join(_read(p.stderr) for p in procs if p.stderr).strip()[:500]
    except Exception as e:
        status_str, detail = "error", str(e)[:500]
    finally:
        _finish(token, status_str, detail, log_id)


def _finish(token, status_str, detail, log_id):
    with _lock:
        if _state["token"] != token:
            return
        _state.update(playing=False, transient=False, title=None, trigger=None,
                      started_at=None, ends_at=None, log_id=None, procs=[])
    _log_end(log_id, status_str, detail)


def _log_end(log_id, status_str, detail=None):
    if not log_id:
        return
    try:
        with db.get_conn() as conn:
            conn.execute(
                "UPDATE play_log SET ended_at=?, status=?, detail=? WHERE id=? AND ended_at IS NULL",
                (int(time.time()), status_str, detail or None, log_id))
    except Exception:
        pass


def _kill_current_locked():
    for p in _state.get("procs", []):
        try:
            p.terminate()
        except Exception:
            pass
    deadline = time.time() + 3
    for p in _state.get("procs", []):
        try:
            p.wait(timeout=max(0.1, deadline - time.time()))
        except Exception:
            try:
                p.kill()
            except Exception:
                pass


def stop():
    with _lock:
        _state["token"] += 1
        _kill_current_locked()
        log_id = _state["log_id"]
        _state.update(playing=False, transient=False, title=None, trigger=None,
                      started_at=None, ends_at=None, log_id=None, procs=[])
    _log_end(log_id, "stopped")


def _end_window(token):
    with _lock:
        if _state["token"] != token or not _state["playing"]:
            return
        _state["token"] += 1
        _kill_current_locked()
        log_id = _state["log_id"]
        _state.update(playing=False, transient=False, title=None, trigger=None,
                      started_at=None, ends_at=None, log_id=None, procs=[])
    _log_end(log_id, "done")


def _start(builders, title, trigger, total_seconds,
           schedule_id=None, audio_id=None, log=True, transient=False):
    now = int(time.time())
    with _lock:
        prev_log = _state["log_id"]
        _state["token"] += 1
        _kill_current_locked()
        token = _state["token"]
        log_id = None
        if log:
            with db.get_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO play_log(title, trigger, schedule_id, audio_id, started_at, status) "
                    "VALUES(?,?,?,?,?, 'playing')",
                    (title, trigger, schedule_id, audio_id, now))
                log_id = cur.lastrowid
        _state.update(playing=True, transient=transient, title=title, trigger=trigger,
                      started_at=now,
                      ends_at=(now + total_seconds) if total_seconds else None,
                      log_id=log_id, procs=[])
        t = threading.Thread(target=_run_general, args=(token, builders, log_id), daemon=True)
        t.start()
    _log_end(prev_log, "stopped")  # close a session we interrupted
    if total_seconds:
        threading.Timer(total_seconds, _end_window, args=(token,)).start()
    return token


# ---------------- public API ----------------
def _exists(media_row):
    return media_row and os.path.exists(os.path.join(config.AUDIO_DIR, media_row["filename"]))


def play_schedule(video_row=None, audio_row=None, mute_video_audio=True,
                  volume=None, total_seconds=None, loop=None,
                  trigger="Manual", schedule_id=None):
    """Play a video (TV) and/or an audio track (soundbar) together."""
    has_v = _exists(video_row)
    has_a = _exists(audio_row)
    if not has_v and not has_a:
        return False, "No playable media."
    if volume is None:
        volume = int(db.get_setting("default_volume", config.DEFAULTS["default_volume"]))
    if loop is None:
        loop = bool(total_seconds)
    master, muted = _master_mute()
    effective = 0 if muted else max(0, min(100, round(volume * master / 100.0)))
    preroll = int(db.get_setting("preroll_seconds", config.DEFAULTS["preroll_seconds"]))
    device = db.get_setting("audio_device", config.DEFAULTS["audio_device"])

    # the soundbar plays the audio track when one is chosen and either muting the
    # video's audio or there's no video at all
    play_audio_track = has_a and (mute_video_audio or not has_v)
    builders = []
    titles = []

    if has_v:
        vpath = os.path.join(config.AUDIO_DIR, video_row["filename"])
        mpv_silent = play_audio_track            # drop the video's audio when the audio track carries sound
        builders.append(lambda p=vpath, v=effective, m=mpv_silent, l=loop: _video_job(p, v, m, l))
        titles.append(video_row["title"])

    if play_audio_track:
        apath = os.path.join(config.AUDIO_DIR, audio_row["filename"])
        ff = _file_ffmpeg_args(apath, effective, preroll, loop)
        builders.append(lambda a=ff, d=device: _audio_pipe(a, d))
        titles.append(audio_row["title"])

    title = " + ".join(dict.fromkeys(titles))  # de-dupe, keep order
    primary_id = (video_row or audio_row)["id"]
    _start(builders, title, trigger, total_seconds,
           schedule_id=schedule_id, audio_id=primary_id)
    return True, ("Playing video on the TV." if has_v else "Playing.")


def play_media(media_row, trigger="Manual", schedule_id=None,
               volume=None, total_seconds=None, loop=None, video=False):
    """Single-item play (library test / play-now)."""
    kind = media_row["kind"] if "kind" in media_row.keys() else "audio"
    if bool(video) and kind == "video":
        return play_schedule(video_row=media_row, audio_row=None,
                             volume=volume, total_seconds=total_seconds, loop=loop,
                             trigger=trigger, schedule_id=schedule_id)
    return play_schedule(video_row=None, audio_row=media_row,
                         volume=volume, total_seconds=total_seconds, loop=loop,
                         trigger=trigger, schedule_id=schedule_id)


def play_feedback_tone(level=None):
    master, muted = _master_mute()
    if muted:
        return False, "Muted."
    if level is None:
        level = master
    level = max(0, min(100, int(level)))
    device = db.get_setting("audio_device", config.DEFAULTS["audio_device"])
    ff = _tone_ffmpeg_args(level)
    _start([lambda: _audio_pipe(ff, device)],
           "Volume preview", "Volume", None, log=False, transient=True)
    return True, "tone"
