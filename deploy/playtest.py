import time, db, player
row = db.get_conn().execute(
    "select * from audio_files where source='builtin'").fetchone()
print("playing:", dict(row))
ok, msg = player.play_audio(dict(row), trigger="Test", total_seconds=5, loop=True)
print("start:", ok, msg)
time.sleep(9)
print("status after:", player.status())
for r in db.get_conn().execute(
        "select title,trigger,status,detail from play_log order by id desc limit 2"):
    print("log:", dict(r))
