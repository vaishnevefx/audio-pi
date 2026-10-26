import subprocess, time
from datetime import datetime
import display

print("idle-active:", display.get_prop("idle-active"), "| path:", display.get_prop("path"))

now = datetime.now(display._tz())
nxt = {"name": "Focus Time (Afternoon)", "when": now.replace(hour=14, minute=0, second=0)}
idle = display.build_text({"playing": False, "next": nxt}, now.replace(hour=13, minute=42))
t = time.time()
playing = display.build_text({"playing": True, "title": "You Are Solving The Impossible | Interstellar Soundtrack | 1 Hour Study",
                              "trigger": "Focus Time (Morning)", "started_at": t - 600, "ends_at": t + 1200}, now)

for name, text in (("idle", idle), ("playing", playing)):
    r = display.ipc(["osd-overlay", 1, "ass-events", text, display.W, display.H])
    print(name, "overlay reply:", r)
    ass = ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\n\n"
           "[V4+ Styles]\nFormat: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n"
           "Style: Default,DejaVu Sans,40,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1\n\n"
           "[Events]\nFormat: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n")
    for line in text.split("\n"):
        ass += "Dialogue: 0,0:00:00.00,0:00:10.00,Default,,0,0,0,," + line + "\n"
    open(f"/tmp/{name}.ass", "w").write(ass)
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=black:s=1920x1080",
                    "-vf", f"ass=/tmp/{name}.ass", "-frames:v", "1", f"/tmp/{name}.png"])
print("clear:", display.ipc(["osd-overlay", 1, "none", "", display.W, display.H]))
