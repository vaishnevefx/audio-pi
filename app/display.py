"""Persistent TV display.

One long-lived mpv owns the HDMI output through the Pi's GPU (vo=gpu, DRM context).
Between sessions it shows a minimal "floating" screen: a dim block of text on black
that drifts slowly around and bounces off the edges (DVD-logo style), so no pixel
stays lit -> no burn-in.

How it stays cheap and smooth: the block is rendered ONCE as a still image (only
re-rendered when its text changes, e.g. once a minute) and the GPU slides that image
around via mpv's video-pan properties, updated ~30x/second. CPU use is a few percent.

Videos are loaded into the same mpv (loadfile / stop over mpv's JSON IPC socket).
"""
import atexit
import json
import os
import socket
import subprocess
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import config
import db

SOCK = os.path.join(config.DATA_DIR, "mpv.sock")
LOG = os.path.join(config.DATA_DIR, "mpv.log")
TEXT_DIR = os.path.join(config.DATA_DIR, "screen")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
W, H = 1920, 1080

VY_RATIO = 11 / 18                      # vertical speed relative to horizontal (covers the screen)
_cfg_cache = {"at": 0.0, "v": None}


def _cfg():
    """Admin-editable display settings (Settings page), cached for a few seconds."""
    now = time.time()
    if _cfg_cache["v"] is None or now - _cfg_cache["at"] > 3:
        def num(key, default, lo, hi):
            try:
                return max(lo, min(hi, int(db.get_setting(key, str(default)))))
            except (TypeError, ValueError):
                return default
        _cfg_cache["v"] = {
            "speed": num("display_speed", 18, 2, 120),
            "hz": num("display_hz", 30, 10, 60),
            "night": db.get_setting("night_mode", "1") == "1",
            "night_start": num("night_start", 22, 0, 23),
            "night_end": num("night_end", 7, 0, 23),
        }
        _cfg_cache["at"] = now
    return _cfg_cache["v"]


def _is_night(hour):
    c = _cfg()
    if not c["night"] or c["night_start"] == c["night_end"]:
        return False
    s, e = c["night_start"], c["night_end"]
    return (hour >= s or hour < e) if s > e else (s <= hour < e)

# dim greys (hex RGB for drawtext)
C_MAIN = "0x8d949e"
C_SUB = "0x6b727c"
C_FAINT = "0x4a505a"
C_ACCENT = "0x4f9d86"

# (file, fontsize, colour, y offset from screen centre) -- block is centred in the image
IDLE_LAYOUT = [("clock.txt", 150, C_MAIN, -130),
               ("date.txt", 30, C_SUB, 60),
               ("next.txt", 22, C_FAINT, 115)]
PLAYING_LAYOUT = [("pl_label.txt", 24, C_ACCENT, -110),
                  ("pl_title.txt", 46, C_MAIN, -60),
                  ("pl_sub.txt", 28, C_SUB, 20),
                  ("pl_left.txt", 26, C_FAINT, 70),
                  ("pl_bar.txt", 24, C_ACCENT, 115)]
# how far (fraction of the image) the centred block may travel and still stay on screen
PAN_LIMITS = {"idle": (0.32, 0.34), "playing": (0.23, 0.33)}

_proc = None
_proc_lock = threading.Lock()
_ipc_lock = threading.Lock()
_video_lock = threading.Lock()
_video_gen = 0
_video_active = False
_started = False
_quit = threading.Event()
_cur_mode = "unset"                      # None | "idle" | "playing" | "unset"
_shown_version = None
_last_check = 0.0
_png_n = 0
_written = {}
_next_cache = {"at": 0.0, "val": None}
_state_fn = None


# ---------------- mpv process ----------------
def _mpv_args():
    drm_dev = db.get_setting("drm_device", config.DEFAULTS["drm_device"])
    connector = db.get_setting("drm_connector", config.DEFAULTS["drm_connector"])
    mode = db.get_setting("drm_mode", config.DEFAULTS["drm_mode"])
    device = db.get_setting("audio_device", config.DEFAULTS["audio_device"])
    args = ["mpv", "--no-config", "--really-quiet", "--input-terminal=no",
            "--idle=yes", "--force-window=yes", "--fs", "--keep-open=no",
            "--osc=no", "--no-osd-bar", "--no-input-default-bindings", "--no-input-cursor",
            "--vo=gpu", "--gpu-context=drm", "--background-color=#000000",
            "--image-display-duration=inf",
            f"--drm-device={drm_dev}", f"--drm-connector={connector}",
            f"--audio-device=alsa/{device}", f"--input-ipc-server={SOCK}",
            f"--log-file={LOG}"]
    if mode:
        args.append(f"--drm-mode={mode}")
    return args


def _launch():
    global _proc, _cur_mode, _shown_version
    try:
        os.remove(SOCK)
    except OSError:
        pass
    _proc = subprocess.Popen(_mpv_args(), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    _cur_mode, _shown_version = "unset", None   # force the screen to be loaded again
    for _ in range(50):
        if os.path.exists(SOCK) or _proc.poll() is not None:
            break
        time.sleep(0.1)


def _watchdog():
    while not _quit.is_set():
        try:
            with _proc_lock:
                if _proc is None or _proc.poll() is not None:
                    _launch()
        except Exception:
            pass
        _quit.wait(3)


def restart():
    """Restart mpv (e.g. after changing the DRM / audio device settings)."""
    with _proc_lock:
        if _proc and _proc.poll() is None:
            _proc.terminate()


def _shutdown():
    _quit.set()
    try:
        if _proc and _proc.poll() is None:
            _proc.terminate()
    except Exception:
        pass


# ---------------- IPC ----------------
def ipc(command, timeout=2.0):
    """Send one command to mpv; return the reply dict (or None)."""
    with _ipc_lock:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(timeout)
        try:
            s.connect(SOCK)
            s.sendall(json.dumps({"command": command}).encode() + b"\n")
            buf = b""
            deadline = time.time() + timeout
            while time.time() < deadline:
                chunk = s.recv(65536)
                if not chunk:
                    return None
                buf += chunk
                *lines, buf = buf.split(b"\n")
                for line in lines:
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if "error" in obj:
                        return obj
            return None
        except Exception:
            return None
        finally:
            s.close()


def get_prop(name):
    r = ipc(["get_property", name])
    if r and r.get("error") == "success":
        return r.get("data")
    return None


# ---------------- video ----------------
class VideoJob:
    """Process-like handle so the player can wait on / stop a video."""
    stderr = None

    def __init__(self, path, volume, mute_audio, loop):
        global _video_gen, _video_active
        self.path = path
        self.returncode = None
        self._term = False
        with _video_lock:
            _video_gen += 1
            self.gen = _video_gen
            _video_active = True           # stops the floating-motion thread
        ipc(["set_property", "video-pan-x", 0])
        ipc(["set_property", "video-pan-y", 0])
        opts = [f"volume={max(0, min(100, int(volume)))}",
                "loop-file=" + ("inf" if loop else "no"),
                "video-pan-x=0", "video-pan-y=0"]
        if mute_audio:
            opts.append("aid=no")
        ipc(["loadfile", path, "replace", -1, ",".join(opts)])

    def wait(self, timeout=None):
        deadline = None if timeout is None else time.time() + timeout
        seen = False
        t0 = time.time()
        while True:
            if self._term:
                break
            cur = get_prop("path")
            if cur == self.path:
                seen = True
            elif seen:
                break                      # finished, or replaced
            elif time.time() - t0 > 10:
                self.returncode = 1        # never loaded
                break
            if deadline is not None and time.time() > deadline:
                raise subprocess.TimeoutExpired("video", timeout)
            time.sleep(0.5)
        self._release()
        if self.returncode is None:
            self.returncode = 0
        return self.returncode

    def _release(self):
        global _video_active, _cur_mode
        with _video_lock:
            if self.gen == _video_gen:
                _video_active = False
                _cur_mode = "unset"        # bring the floating screen back

    def terminate(self):
        self._term = True
        with _video_lock:
            current = self.gen == _video_gen
        if current:
            ipc(["stop"])

    kill = terminate


def start_video(path, volume, mute_audio, loop):
    return VideoJob(path, volume, mute_audio, loop)


# ---------------- floating screens ----------------
def _tz():
    try:
        return ZoneInfo(db.get_setting("timezone", config.DEFAULTS["timezone"]))
    except Exception:
        return ZoneInfo("UTC")


def _trim(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _write(name, content):
    """Atomically update a text file used when rendering the screen image."""
    content = content if content.strip() else " "
    if _written.get(name) == content:
        return
    os.makedirs(TEXT_DIR, exist_ok=True)
    path = os.path.join(TEXT_DIR, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)
    _written[name] = content


def _layout(mode):
    return IDLE_LAYOUT if mode == "idle" else PLAYING_LAYOUT


def _render(mode):
    """Render the (centred) text block for `mode` onto a black 1920x1080 PNG."""
    global _png_n
    chain = ",".join(
        f"drawtext=fontfile={FONT}:textfile={os.path.join(TEXT_DIR, fname)}:expansion=none"
        f":fontsize={fs}:fontcolor={col}:x=(w-text_w)/2:y=(h/2)+({off})"
        for fname, fs, col, off in _layout(mode))
    tmp = os.path.join(TEXT_DIR, "render.png")
    _png_n ^= 1                              # alternate names so mpv always reloads
    final = os.path.join(TEXT_DIR, f"screen_{_png_n}.png")
    try:
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
             f"color=c=black:s={W}x{H}", "-vf", chain, "-frames:v", "1", tmp],
            check=True, timeout=20, stdin=subprocess.DEVNULL)
        os.replace(tmp, final)
        return final
    except Exception:
        return None


def _default_state():
    import player
    import scheduler
    st = dict(player.status())
    now = time.time()
    if now - _next_cache["at"] > 30:
        try:
            runs = scheduler.next_runs(limit=1)
            _next_cache["val"] = runs[0] if runs else None
        except Exception:
            _next_cache["val"] = None
        _next_cache["at"] = now
    st["next"] = _next_cache["val"]
    return st


def _update_idle_files(now, st):
    _write("clock.txt", now.strftime("%H:%M"))
    _write("date.txt", now.strftime("%a  ·  %d %b").upper())
    nxt = st.get("next")
    if nxt:
        when = nxt["when"]
        stamp = when.strftime("%H:%M") if when.date() == now.date() else when.strftime("%a %H:%M")
        _write("next.txt", f"NEXT  ›  {stamp}  ·  {_trim(nxt['name'], 34).upper()}")
    else:
        _write("next.txt", " ")


def _update_playing_files(st):
    _write("pl_label.txt", "NOW PLAYING")
    _write("pl_title.txt", _trim(st.get("title"), 38))
    _write("pl_sub.txt", _trim(st.get("trigger"), 40))
    ends, started = st.get("ends_at"), st.get("started_at")
    if ends and started and ends > started:
        left = max(0.0, ends - time.time())
        mins = int(left // 60)
        _write("pl_left.txt", f"{mins} min left" if mins >= 1 else "less than a minute left")
        frac = min(1.0, max(0.0, (time.time() - started) / (ends - started)))
        n = int(round(frac * 32))
        _write("pl_bar.txt", "━" * n + "─" * (32 - n))
    else:
        _write("pl_left.txt", " ")
        _write("pl_bar.txt", " ")


def _wanted_mode(st, now):
    if st.get("playing"):
        return "playing" if db.get_setting("playing_screen", "1") == "1" else None
    if db.get_setting("idle_screen", "1") != "1":
        return None
    if _is_night(now.hour):
        return None                        # night: pure black
    return "idle"


def _tick_ui():
    global _cur_mode, _shown_version, _last_check
    if not os.path.exists(SOCK) or _video_active:
        return
    st = (_state_fn or _default_state)()
    now = datetime.now(_tz())
    mode = _wanted_mode(st, now)

    if mode == "idle":
        _update_idle_files(now, st)
    elif mode == "playing":
        _update_playing_files(st)
    version = tuple(_written.get(f[0]) for f in _layout(mode)) if mode else None

    need = mode != _cur_mode or version != _shown_version
    if not need and mode and time.time() - _last_check > 15:
        _last_check = time.time()
        path = get_prop("path")
        need = not (isinstance(path, str) and path.startswith(TEXT_DIR))   # mpv lost it
    if not need:
        return

    if mode is None:
        with _video_lock:
            if _video_active:
                return
            ipc(["stop"])                  # plain black
    else:
        png = _render(mode)
        if not png:
            return                         # retry next tick
        with _video_lock:                  # never replace a video that just started
            if _video_active:
                return
            ipc(["loadfile", png, "replace", -1, "aid=no"])
    _cur_mode, _shown_version = mode, version


def _ui_loop():
    while not _quit.is_set():
        try:
            _tick_ui()
        except Exception:
            pass
        _quit.wait(1.0)


# ---------------- smooth motion (GPU pan) ----------------
def _tri(x, a):
    """Triangle wave bouncing between -a and +a."""
    p = x % (4 * a)
    return p - a if p < 2 * a else 3 * a - p


def _motion_loop():
    sock = None

    def close():
        nonlocal sock
        if sock:
            try:
                sock.close()
            except Exception:
                pass
        sock = None

    phx, phy, last = 0.0, 0.1, time.time()   # continuous phase: speed changes never jump
    while not _quit.is_set():
        mode = _cur_mode
        if mode in PAN_LIMITS and not _video_active and os.path.exists(SOCK):
            try:
                if sock is None:
                    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    sock.connect(SOCK)
                    sock.setblocking(False)
                ax, ay = PAN_LIMITS[mode]
                c = _cfg()
                t = time.time()
                dt, last = min(t - last, 0.5), t
                phx += dt * c["speed"] / W
                phy += dt * c["speed"] * VY_RATIO / H
                px, py = _tri(phx, ax), _tri(phy, ay)
                for name, val in (("video-pan-x", px), ("video-pan-y", py)):
                    sock.sendall((json.dumps({"command": ["set_property", name, val]}) + "\n").encode())
                try:
                    while sock.recv(65536):         # discard replies/events
                        pass
                except BlockingIOError:
                    pass
            except Exception:
                close()
            _quit.wait(1.0 / _cfg()["hz"])
        else:
            close()
            last = time.time()
            _quit.wait(0.5)
    close()


def start(state_fn=None):
    global _started, _state_fn
    if _started:
        return
    _started = True
    _state_fn = state_fn
    os.makedirs(TEXT_DIR, exist_ok=True)
    for name in [f[0] for f in IDLE_LAYOUT + PLAYING_LAYOUT]:
        _write(name, " ")
    atexit.register(_shutdown)
    threading.Thread(target=_watchdog, daemon=True, name="display-watchdog").start()
    threading.Thread(target=_ui_loop, daemon=True, name="display-ui").start()
    threading.Thread(target=_motion_loop, daemon=True, name="display-motion").start()
