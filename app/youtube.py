"""YouTube -> MP3/MP4 download tab backend.

Runs yt-dlp in a background thread so long videos don't block the request.
Jobs are tracked in memory and polled by the browser.
"""
import os
import threading
import uuid
import time

import config
import db

_jobs = {}
_jobs_lock = threading.Lock()


def _set(job_id, **kw):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kw)


def get_job(job_id):
    with _jobs_lock:
        j = _jobs.get(job_id)
        return dict(j) if j else None


def _download(job_id, url, kind):
    base = uuid.uuid4().hex
    outtmpl = os.path.join(config.AUDIO_DIR, base + ".%(ext)s")

    def hook(d):
        if d.get("status") == "downloading":
            pct = d.get("_percent_str", "").strip()
            _set(job_id, stage="downloading", message=f"Downloading {pct}".strip())
        elif d.get("status") == "finished":
            _set(job_id, stage="converting", message="Processing...")

    if kind == "video":
        ext = "mp4"
        ydl_opts = {
            "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "noplaylist": True, "quiet": True, "no_warnings": True,
            "nocheckcertificate": True, "progress_hooks": [hook],
        }
    else:
        ext = "mp3"
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "noplaylist": True, "quiet": True, "no_warnings": True,
            "nocheckcertificate": True, "progress_hooks": [hook],
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3", "preferredquality": "192"}],
        }

    final_path = os.path.join(config.AUDIO_DIR, base + "." + ext)
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
        title = (info.get("title") or "YouTube media").strip()
        duration = info.get("duration")

        if os.path.exists(final_path):
            final_name = base + "." + ext
        else:  # fall back to whatever file was produced with this base
            final_name = None
            for fn in os.listdir(config.AUDIO_DIR):
                if fn.startswith(base):
                    final_name = fn
                    break
            if not final_name:
                raise RuntimeError("Download produced no file.")

        media_id = db.add_audio(title, final_name, source="youtube",
                                source_url=url, duration=duration,
                                kind=("video" if kind == "video" else "audio"))
        _set(job_id, stage="done", message="Saved to library.",
             audio_id=media_id, title=title, kind=kind)
    except Exception as e:
        for fn in os.listdir(config.AUDIO_DIR):
            if fn.startswith(base):
                try:
                    os.remove(os.path.join(config.AUDIO_DIR, fn))
                except Exception:
                    pass
        _set(job_id, stage="error", message=str(e)[:400])


def start_download(url, kind="audio"):
    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {"id": job_id, "url": url, "kind": kind, "stage": "starting",
                         "message": "Starting...", "created_at": time.time()}
    t = threading.Thread(target=_download, args=(job_id, url, kind), daemon=True)
    t.start()
    return job_id
