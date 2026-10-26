import db
db.init_db()  # ensure video_id / mute_video_audio columns exist

# Move any video that was assigned in the audio slot into the new video slot.
with db.get_conn() as conn:
    conn.execute(
        "UPDATE schedules SET video_id = audio_id, audio_id = NULL "
        "WHERE audio_id IN (SELECT id FROM audio_files WHERE kind='video')")

with db.get_conn() as conn:
    for r in conn.execute(
        "SELECT name, start_time, audio_id, video_id, mute_video_audio, enabled "
        "FROM schedules ORDER BY start_time").fetchall():
        print(dict(r))
