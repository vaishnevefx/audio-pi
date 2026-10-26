import db, scheduler, webapp, youtube, player
db.init_db()
db.ensure_seed()
print("SEED_OK")
for r in db.get_conn().execute(
        "select name,start_time,duration_seconds,days,enabled from schedules").fetchall():
    print(dict(r))
