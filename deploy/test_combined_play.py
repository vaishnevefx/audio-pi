import time, db, player
with db.get_conn() as c:
    vid = dict(c.execute("select * from audio_files where id=9").fetchone())
    aud = dict(c.execute("select * from audio_files where id=8").fetchone())
print("video:", vid["title"], "(kind", vid["kind"] + ") | audio:", aud["title"], "(kind", aud["kind"] + ")")
ok, msg = player.play_schedule(video_row=vid, audio_row=aud, mute_video_audio=True,
                               total_seconds=8, loop=True, trigger="ComboTest")
print("start:", ok, msg)
time.sleep(11)
print("final status:", player.status())
with db.get_conn() as c:
    for r in c.execute("select title,trigger,status,detail from play_log order by id desc limit 2").fetchall():
        print("log:", dict(r))
