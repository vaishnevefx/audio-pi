import db
db.init_db()  # ensure is_admin column exists
with db.get_conn() as conn:
    conn.execute("UPDATE users SET is_admin=1 WHERE username='admin'")
    conn.execute("UPDATE users SET is_admin=0 WHERE username='changemaker'")
with db.get_conn() as conn:
    print([dict(r) for r in conn.execute(
        "select username, is_admin from users order by id").fetchall()])
