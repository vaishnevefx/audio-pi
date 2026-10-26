import secrets, time, db

username = "admin"
if db.get_user(username):
    print("ALREADY_EXISTS", username)
else:
    pw = secrets.token_urlsafe(12)
    pw_hash, pw_salt = db.hash_password(pw)
    with db.get_conn() as c:
        c.execute(
            "INSERT INTO users(username, pw_hash, pw_salt, created_at) VALUES(?,?,?,?)",
            (username, pw_hash, pw_salt, int(time.time())))
    print("CREATED", username, "PASSWORD:", pw)

print("all users:", [dict(r) for r in db.get_conn().execute(
    "select id, username from users").fetchall()])
