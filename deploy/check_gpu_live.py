import os, time, subprocess
import display

def cpu(pid):
    f = open(f"/proc/{pid}/stat").read().split()
    return (int(f[13]) + int(f[14])) / os.sysconf("SC_CLK_TCK")

mpv = int(subprocess.run(["pgrep", "-x", "mpv"], capture_output=True, text=True).stdout.split()[0])
svc = int(subprocess.run(["systemctl", "show", "-p", "MainPID", "--value", "audio-portal"],
                         capture_output=True, text=True).stdout.strip())
p = display.get_prop("path")
print("showing our still image:", isinstance(p, str) and "/screen/screen_" in p)
a = (display.get_prop("video-pan-x"), display.get_prop("video-pan-y"))
c0 = (cpu(mpv), cpu(svc)); t0 = time.time(); time.sleep(20); dt = time.time() - t0
b = (display.get_prop("video-pan-x"), display.get_prop("video-pan-y"))
c1 = (cpu(mpv), cpu(svc))
print("pan before:", a, "after 20s:", b, "(moved:", a != b, ")")
print(f"mpv CPU: {(c1[0]-c0[0])/dt*100:.1f}%   portal service CPU: {(c1[1]-c0[1])/dt*100:.1f}%  (of one core)")
print("renderer:", display.get_prop("current-vo"), "| dropped:", display.get_prop("frame-drop-count"))
