import db, display
from datetime import datetime
print("now (portal tz):", datetime.now(display._tz()).strftime("%F %T"))
print("idle_screen:", db.get_setting("idle_screen"), "| playing_screen:", db.get_setting("playing_screen"))
print("idle-active:", display.get_prop("idle-active"), "| path:", display.get_prop("path"))
st = display._default_state()
print("player playing:", st.get("playing"), "| video_active:", display._video_active)
txt = display.build_text(st)
print("overlay text is None (black by design):", txt is None)
