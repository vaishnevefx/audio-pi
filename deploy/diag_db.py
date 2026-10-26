import db
print("device=", db.get_setting("audio_device"))
print("master=", db.get_setting("master_volume"),
      "muted=", db.get_setting("muted"),
      "defvol=", db.get_setting("default_volume"))
c = db._connect()
for r in c.execute("select id,title,trigger,status,detail from play_log order by id desc limit 8").fetchall():
    print("LOG", dict(r))
c.close()
