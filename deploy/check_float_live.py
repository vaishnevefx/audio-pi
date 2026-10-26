import time, subprocess, display
p1 = display.get_prop("path")
print("path is lavfi stream:", isinstance(p1, str) and p1.startswith("av://lavfi:"))
t1 = display.get_prop("time-pos"); time.sleep(5); t2 = display.get_prop("time-pos")
print("time-pos advance over 5s wall:", None if t1 is None or t2 is None else round(t2 - t1, 2))
print("fps estimate:", display.get_prop("estimated-vf-fps"), "| dropped:", display.get_prop("frame-drop-count"),
      "| decoder drops:", display.get_prop("decoder-frame-drop-count"))
out = subprocess.run(["bash", "-c", "ps -o %cpu,cmd -C mpv | cut -c1-40; uptime"], capture_output=True, text=True).stdout
print(out)
