import db
db.init_db()  # ensure migration columns (kind, video) exist

existing = None
with db.get_conn() as conn:
    for r in conn.execute("select id, filename from audio_files").fetchall():
        if r["filename"] == "stretch_short.mp4":
            existing = r["id"]

if existing is None:
    vid_id = db.add_audio("Stretching Routine", "stretch_short.mp4",
                          source="youtube",
                          source_url="https://www.youtube.com/shorts/PqUTmd0xdjw")
else:
    vid_id = existing

with db.get_conn() as conn:
    print("video media:", [dict(r) for r in conn.execute(
        "select id, title, kind, duration_seconds from audio_files where id=?",
        (vid_id,)).fetchall()])

with db.get_conn() as conn:
    conn.execute("UPDATE schedules SET audio_id=?, video=1 WHERE name LIKE 'Stretching%'", (vid_id,))

with db.get_conn() as conn:
    print("schedules:", [dict(r) for r in conn.execute(
        "select name, start_time, audio_id, video, enabled from schedules order by start_time"
    ).fetchall()])
