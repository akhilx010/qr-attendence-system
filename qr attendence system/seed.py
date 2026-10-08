import os
from werkzeug.security import generate_password_hash
from db import get_db

ADMIN_NAME = os.getenv("ADMIN_NAME", "Admin")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

conn = get_db()
cur = conn.cursor()
cur.execute("SELECT user_id FROM users WHERE email=%s", (ADMIN_EMAIL,))
if cur.fetchone():
    print("Admin already exists.")
else:
    cur.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s,%s,%s,'admin')",
        (ADMIN_NAME, ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD)),
    )
    conn.commit()
    print(f"Admin created: {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
cur.close()
conn.close()
