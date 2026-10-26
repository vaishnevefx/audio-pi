import db
with db.get_conn() as c:
    c.execute("UPDATE users SET username='changemaker' WHERE username='admin'")
rows = [dict(r) for r in db.get_conn().execute(
        "select id, username from users").fetchall()]
print("users:", rows)
