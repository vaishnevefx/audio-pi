import time, os, youtube, db, config
jid = youtube.start_download("https://www.youtube.com/watch?v=jNQXAC9IVRw")
print("job:", jid)
for _ in range(45):
    j = youtube.get_job(jid)
    print(" ", j["stage"], "-", j.get("message"))
    if j["stage"] in ("done", "error"):
        break
    time.sleep(2)
j = youtube.get_job(jid)
print("FINAL:", j["stage"], j.get("message"))
if j.get("stage") == "done":
    aid = j["audio_id"]
    row = db.get_conn().execute("select * from audio_files where id=?", (aid,)).fetchone()
    print("downloaded file:", row["filename"], "title:", row["title"])
    p = os.path.join(config.AUDIO_DIR, row["filename"])
    print("exists:", os.path.exists(p), "bytes:", os.path.getsize(p) if os.path.exists(p) else 0)
    with db.get_conn() as c:
        c.execute("delete from audio_files where id=?", (aid,))
    try:
        os.remove(p)
    except Exception:
        pass
    print("CLEANED_UP test track")
