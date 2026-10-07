import os
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
from werkzeug.security import check_password_hash

from db import get_db

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")

    def current_user():
        uid = session.get("user_id")
        if not uid:
            return None
        conn = get_db()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT user_id, name, email, role FROM users WHERE user_id=%s", (uid,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        return user

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard"))
        return redirect(url_for("login"))

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            conn = get_db()
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM users WHERE email=%s", (email,))
            user = cur.fetchone()
            cur.close()
            conn.close()
            if user and check_password_hash(user["password_hash"], password):
                session["user_id"] = user["user_id"]
                return redirect(url_for("dashboard"))
            flash("Invalid email or password")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        user = current_user()
        messages = {
            "admin": "Admin dashboard",
            "teacher": "Teacher dashboard",
            "student": "Student dashboard",
        }
        return render_template("dashboard.html", user=user, message=messages.get(user["role"], ""))

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
