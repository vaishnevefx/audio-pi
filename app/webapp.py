"""Flask web portal: login-gated dashboard, schedules, library, YouTube, settings."""
import os
import secrets
import time
from datetime import datetime
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (Flask, request, session, redirect, url_for, render_template,
                   flash, jsonify, send_file, abort)
from werkzeug.utils import secure_filename

import config
import db
import display
import player
import scheduler
import youtube

app = Flask(__name__)


def _load_secret_key():
    if os.path.exists(config.SECRET_KEY_PATH):
        with open(config.SECRET_KEY_PATH) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(config.SECRET_KEY_PATH, "w") as f:
        f.write(key)
    os.chmod(config.SECRET_KEY_PATH, 0o600)
    return key


app.config.update(
    SECRET_KEY=_load_secret_key(),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    MAX_CONTENT_LENGTH=512 * 1024 * 1024,  # 512 MB uploads
)

DAY_NAMES = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


# ---------------- auth / csrf ----------------
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("user"):
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)
    return wrapper


def _is_admin():
    u = session.get("user")
    return bool(u) and db.is_admin(u)


@app.before_request
def _csrf_and_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    if request.method == "POST" and request.endpoint != "login":
        sent = request.form.get("csrf") or request.headers.get("X-CSRF")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Bad CSRF token")


@app.context_processor
def _inject():
    return {
        "csrf_token": session.get("csrf", ""),
        "player_status": player.status(),
        "day_names": DAY_NAMES,
        "current_user": session.get("user"),
        "is_admin": _is_admin(),
    }


# ---------------- jinja filters ----------------
@app.template_filter("dur")
def _dur(seconds):
    if seconds is None:
        return "-"
    seconds = int(round(float(seconds)))
    m, s = divmod(seconds, 60)
    if m and s:
        return f"{m}m {s:02d}s"
    if m:
        return f"{m} min"
    return f"{s}s"


@app.template_filter("localtime")
def _localtime(epoch):
    if not epoch:
        return "-"
    tz = ZoneInfo(db.get_setting("timezone", config.DEFAULTS["timezone"]))
    return datetime.fromtimestamp(epoch, tz).strftime("%d %b, %H:%M:%S")


def _tz():
    return ZoneInfo(db.get_setting("timezone", config.DEFAULTS["timezone"]))


# ---------------- login ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_user(username)
        if user and db.verify_password(password, user["pw_hash"], user["pw_salt"]):
            session.clear()
            session["user"] = username
            session["csrf"] = secrets.token_hex(16)
            nxt = request.args.get("next") or url_for("dashboard")
            return redirect(nxt)
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------- dashboard ----------------
@app.route("/")
@login_required
def dashboard():
    with db.get_conn() as conn:
        recent = conn.execute(
            "SELECT * FROM play_log ORDER BY started_at DESC LIMIT 12").fetchall()
        n_sched = conn.execute(
            "SELECT COUNT(*) c FROM schedules WHERE enabled=1").fetchone()["c"]
        n_audio = conn.execute("SELECT COUNT(*) c FROM audio_files").fetchone()["c"]
    runs = scheduler.next_runs(limit=6)
    now_local = datetime.now(_tz()).strftime("%d %b %Y, %H:%M")
    return render_template("dashboard.html", recent=recent, next_runs=runs,
                           n_sched=n_sched, n_audio=n_audio, now_local=now_local,
                           tz=db.get_setting("timezone"),
                           master_volume=int(db.get_setting("master_volume", "100")),
                           muted=db.get_setting("muted", "0") == "1")


# ---------------- schedules ----------------
def _all_audio():
    with db.get_conn() as conn:
        return conn.execute(
            "SELECT * FROM audio_files ORDER BY created_at DESC").fetchall()


@app.route("/schedules")
@login_required
def schedules():
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT s.*, a.title AS audio_title, v.title AS video_title "
            "FROM schedules s "
            "LEFT JOIN audio_files a ON a.id = s.audio_id "
            "LEFT JOIN audio_files v ON v.id = s.video_id "
            "ORDER BY s.start_time").fetchall()
        media = conn.execute("SELECT * FROM audio_files ORDER BY created_at DESC").fetchall()
    audios = [m for m in media if m["kind"] != "video"]
    videos = [m for m in media if m["kind"] == "video"]
    return render_template("schedules.html", schedules=rows, audios=audios, videos=videos)


@app.route("/schedules/save", methods=["POST"])
@login_required
def schedules_save():
    sid = request.form.get("id")
    name = request.form.get("name", "").strip() or "Session"
    start_time = request.form.get("start_time", "09:00")
    minutes = max(1, int(request.form.get("minutes", "30") or 30))
    audio_id = request.form.get("audio_id") or None
    video_id = request.form.get("video_id") or None
    volume = max(0, min(100, int(request.form.get("volume", "80") or 80)))
    loop = 1 if request.form.get("loop") else 0
    enabled = 1 if request.form.get("enabled") else 0
    mute_video_audio = 1 if request.form.get("mute_video_audio") else 0
    days = ",".join(d for d in request.form.getlist("days") if d.isdigit())
    if not days:
        days = "1,2,3,4,5"
    dur = minutes * 60
    with db.get_conn() as conn:
        if sid:
            conn.execute(
                "UPDATE schedules SET name=?, audio_id=?, video_id=?, start_time=?, "
                "duration_seconds=?, days=?, volume=?, loop=?, mute_video_audio=?, enabled=? "
                "WHERE id=?",
                (name, audio_id, video_id, start_time, dur, days, volume, loop,
                 mute_video_audio, enabled, sid))
            flash(f"Updated “{name}”.", "ok")
        else:
            conn.execute(
                "INSERT INTO schedules(name, audio_id, video_id, start_time, duration_seconds, "
                "days, volume, loop, mute_video_audio, enabled, created_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (name, audio_id, video_id, start_time, dur, days, volume, loop,
                 mute_video_audio, enabled, int(time.time())))
            flash(f"Created “{name}”.", "ok")
    return redirect(url_for("schedules"))


@app.route("/schedules/delete", methods=["POST"])
@login_required
def schedules_delete():
    sid = request.form.get("id")
    with db.get_conn() as conn:
        conn.execute("DELETE FROM schedules WHERE id=?", (sid,))
    flash("Schedule deleted.", "ok")
    return redirect(url_for("schedules"))


@app.route("/schedules/toggle", methods=["POST"])
@login_required
def schedules_toggle():
    sid = request.form.get("id")
    with db.get_conn() as conn:
        conn.execute("UPDATE schedules SET enabled = 1 - enabled WHERE id=?", (sid,))
    return redirect(url_for("schedules"))


# ---------------- library ----------------
@app.route("/library")
@login_required
def library():
    return render_template("library.html", audio=_all_audio())


@app.route("/library/upload", methods=["POST"])
@login_required
def library_upload():
    f = request.files.get("file")
    if not f or not f.filename:
        flash("No file selected.", "error")
        return redirect(url_for("library"))
    ext = os.path.splitext(f.filename)[1].lower()
    if ext not in config.ALLOWED_MEDIA_EXT:
        flash(f"Unsupported file type: {ext}", "error")
        return redirect(url_for("library"))
    title = request.form.get("title", "").strip() or os.path.splitext(
        secure_filename(f.filename))[0]
    stored = f"{int(time.time())}_{secure_filename(f.filename)}"
    f.save(os.path.join(config.AUDIO_DIR, stored))
    db.add_audio(title, stored, source="upload")
    flash(f"Uploaded “{title}”.", "ok")
    return redirect(url_for("library"))


@app.route("/library/rename", methods=["POST"])
@login_required
def library_rename():
    aid = request.form.get("id")
    title = request.form.get("title", "").strip()
    if title:
        with db.get_conn() as conn:
            conn.execute("UPDATE audio_files SET title=? WHERE id=?", (title, aid))
        flash("Renamed.", "ok")
    return redirect(url_for("library"))


@app.route("/library/delete", methods=["POST"])
@login_required
def library_delete():
    aid = request.form.get("id")
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM audio_files WHERE id=?", (aid,)).fetchone()
        if row:
            conn.execute("DELETE FROM audio_files WHERE id=?", (aid,))
            conn.execute("UPDATE schedules SET audio_id=NULL WHERE audio_id=?", (aid,))
    if row:
        try:
            os.remove(os.path.join(config.AUDIO_DIR, row["filename"]))
        except Exception:
            pass
        flash("Deleted.", "ok")
    return redirect(url_for("library"))


@app.route("/audio/<int:aid>")
@login_required
def audio_file(aid):
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM audio_files WHERE id=?", (aid,)).fetchone()
    if not row:
        abort(404)
    path = os.path.join(config.AUDIO_DIR, row["filename"])
    if not os.path.exists(path):
        abort(404)
    return send_file(path, conditional=True)


# ---------------- playback control ----------------
@app.route("/play", methods=["POST"])
@login_required
def play_now():
    aid = request.form.get("audio_id")
    minutes = request.form.get("minutes")
    volume = request.form.get("volume")
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM audio_files WHERE id=?", (aid,)).fetchone()
    if not row:
        return _maybe_json(False, "Media not found.")
    row_d = dict(row)
    total = int(minutes) * 60 if minutes else None
    vol = int(volume) if volume else None
    vparam = request.form.get("video")
    video = (row_d.get("kind") == "video") if vparam is None else (vparam == "1")
    ok, msg = player.play_media(row_d, trigger="Test", volume=vol,
                                total_seconds=total, loop=bool(total), video=video)
    return _maybe_json(ok, msg)


@app.route("/stop", methods=["POST"])
@login_required
def stop_now():
    player.stop()
    return _maybe_json(True, "Stopped.")


def _maybe_json(ok, msg):
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=ok, message=msg)
    flash(msg, "ok" if ok else "error")
    return redirect(request.referrer or url_for("dashboard"))


# ---------------- master volume / mute ----------------
@app.route("/volume/set", methods=["POST"])
@login_required
def volume_set():
    try:
        value = max(0, min(100, int(request.form.get("value", "80"))))
    except ValueError:
        return jsonify(ok=False, message="bad value"), 400
    db.set_setting("master_volume", value)
    tone = request.form.get("tone", "1") == "1"
    muted = db.get_setting("muted", "0") == "1"
    if tone and not muted:
        player.play_feedback_tone(value)
    return jsonify(ok=True, master_volume=value, muted=muted)


@app.route("/volume/mute", methods=["POST"])
@login_required
def volume_mute():
    muted = db.get_setting("muted", "0") == "1"
    muted = not muted
    db.set_setting("muted", "1" if muted else "0")
    if not muted:
        # unmuting: chirp at the current level as confirmation
        player.play_feedback_tone(int(db.get_setting("master_volume", "100")))
    else:
        player.stop()
    return jsonify(ok=True, muted=muted,
                   master_volume=int(db.get_setting("master_volume", "100")))


# ---------------- youtube ----------------
@app.route("/youtube")
@login_required
def youtube_page():
    return render_template("youtube.html")


@app.route("/youtube/download", methods=["POST"])
@login_required
def youtube_download():
    url = (request.form.get("url") or request.json.get("url", "")).strip()
    if not url.startswith(("http://", "https://")):
        return jsonify(ok=False, message="Enter a valid URL."), 400
    kind = "video" if request.form.get("kind") == "video" else "audio"
    job_id = youtube.start_download(url, kind=kind)
    return jsonify(ok=True, job_id=job_id)


@app.route("/youtube/status/<job_id>")
@login_required
def youtube_status(job_id):
    job = youtube.get_job(job_id)
    if not job:
        return jsonify(ok=False, message="Unknown job"), 404
    return jsonify(ok=True, **job)


# ---------------- settings ----------------
@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        form = request.form.get("form")
        if form == "password":
            cur = request.form.get("current", "")
            new = request.form.get("new", "")
            confirm = request.form.get("confirm", "")
            user = db.get_user(session["user"])
            if not db.verify_password(cur, user["pw_hash"], user["pw_salt"]):
                flash("Current password is incorrect.", "error")
            elif len(new) < 6:
                flash("New password must be at least 6 characters.", "error")
            elif new != confirm:
                flash("New passwords do not match.", "error")
            else:
                db.set_user_password(session["user"], new)
                # remove the one-time initial password file if present
                try:
                    os.remove(config.INITIAL_ADMIN_PW_PATH)
                except Exception:
                    pass
                flash("Password changed.", "ok")
        elif form == "audio":
            if not _is_admin():
                flash("Only an admin can change system settings.", "error")
                return redirect(url_for("settings"))
            old_out = tuple(db.get_setting(k) for k in
                            ("audio_device", "drm_device", "drm_connector", "drm_mode"))
            db.set_setting("audio_device", request.form.get("audio_device", "").strip())
            db.set_setting("default_volume",
                           max(0, min(100, int(request.form.get("default_volume", "80") or 80))))
            db.set_setting("preroll_seconds",
                           max(0, min(10, int(request.form.get("preroll_seconds", "2") or 2))))
            db.set_setting("timezone", request.form.get("timezone", "").strip() or "Asia/Kolkata")
            db.set_setting("drm_device", request.form.get("drm_device", "").strip()
                           or config.DEFAULTS["drm_device"])
            db.set_setting("drm_connector", request.form.get("drm_connector", "").strip()
                           or config.DEFAULTS["drm_connector"])
            db.set_setting("drm_mode", request.form.get("drm_mode", "").strip())
            db.set_setting("idle_screen", "1" if request.form.get("idle_screen") else "0")
            db.set_setting("playing_screen", "1" if request.form.get("playing_screen") else "0")
            def _num(key, default, lo, hi):
                try:
                    return max(lo, min(hi, int(request.form.get(key, default) or default)))
                except ValueError:
                    return default
            db.set_setting("display_speed", _num("display_speed", 18, 2, 120))
            db.set_setting("display_hz", _num("display_hz", 30, 10, 60))
            db.set_setting("night_mode", "1" if request.form.get("night_mode") else "0")
            db.set_setting("night_start", _num("night_start", 22, 0, 23))
            db.set_setting("night_end", _num("night_end", 7, 0, 23))
            new_out = tuple(db.get_setting(k) for k in
                            ("audio_device", "drm_device", "drm_connector", "drm_mode"))
            if new_out != old_out:
                display.restart()   # re-open the TV output with the new device/mode
            flash("Settings saved.", "ok")
        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        audio_device=db.get_setting("audio_device", config.DEFAULTS["audio_device"]),
        default_volume=db.get_setting("default_volume", config.DEFAULTS["default_volume"]),
        preroll_seconds=db.get_setting("preroll_seconds", config.DEFAULTS["preroll_seconds"]),
        timezone=db.get_setting("timezone", config.DEFAULTS["timezone"]),
        drm_device=db.get_setting("drm_device", config.DEFAULTS["drm_device"]),
        drm_connector=db.get_setting("drm_connector", config.DEFAULTS["drm_connector"]),
        drm_mode=db.get_setting("drm_mode", config.DEFAULTS["drm_mode"]),
        idle_screen=db.get_setting("idle_screen", "1") == "1",
        playing_screen=db.get_setting("playing_screen", "1") == "1",
        display_speed=db.get_setting("display_speed", config.DEFAULTS["display_speed"]),
        display_hz=db.get_setting("display_hz", config.DEFAULTS["display_hz"]),
        night_mode=db.get_setting("night_mode", "1") == "1",
        night_start=db.get_setting("night_start", config.DEFAULTS["night_start"]),
        night_end=db.get_setting("night_end", config.DEFAULTS["night_end"]),
    )


# ---------------- live status api ----------------
@app.route("/api/status")
@login_required
def api_status():
    st = player.status()
    runs = []
    for r in scheduler.next_runs(limit=5):
        runs.append({
            "name": r["name"],
            "when": r["when"].strftime("%a %H:%M"),
            "assigned": r["assigned"],
            "audio_title": r["audio_title"],
        })
    now = None
    if st["ends_at"]:
        now = max(0, int(st["ends_at"] - time.time()))
    return jsonify(playing=st["playing"], title=st["title"], trigger=st["trigger"],
                   remaining=now, next_runs=runs,
                   server_epoch=int(time.time()),
                   timezone=db.get_setting("timezone", config.DEFAULTS["timezone"]),
                   master_volume=int(db.get_setting("master_volume", "100")),
                   muted=db.get_setting("muted", "0") == "1")
