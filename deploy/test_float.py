import subprocess, time
from datetime import datetime
import display

now = datetime.now(display._tz())
nxt = {"name": "Focus Time (Afternoon)", "when": now.replace(hour=14, minute=0, second=0)}
display._update_idle_files(now.replace(hour=13, minute=42), {"next": nxt})
t = time.time()
display._update_playing_files({"title": "You Are Solving The Impossible | Interstellar Soundtrack | 1 Hour Study",
                               "trigger": "Focus Time (Morning)", "started_at": t - 600, "ends_at": t + 1200})

for name, url in (("idle", display._idle_url()), ("playing", display._playing_url())):
    graph = url[len("av://lavfi:"):]
    for secs in (1, 30):
        out = f"/tmp/float_{name}_{secs}.png"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", graph,
                        "-t", str(secs), "-update", "1", out], check=True)
        print("rendered", out)
