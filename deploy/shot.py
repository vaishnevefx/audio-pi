import time, display
time.sleep(1)
print("props: idle-active=", display.get_prop("idle-active"), "osc=", display.get_prop("osc"))
print(display.ipc(["screenshot-to-file", "/tmp/tv.png", "window"]))
