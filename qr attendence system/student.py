from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from datetime import datetime

from db import get_db

student_bp = Blueprint("student", __name__, url_prefix="/student")


def require_student():
    return session.get("role") == "student"


def _rows(query, params=()):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close(); conn.close()
    return rows


@student_bp.route("/")
def index():
    if not require_student():
        return redirect(url_for("login"))
    uid = session["user_id"]
    student = _rows("SELECT * FROM students WHERE user_id=%s", (uid,))
    history = []
    percentage = 0
    if student:
        history = _rows(
            "SELECT a.scan_time, a.status, s.date, s.start_time, s.end_time, c.class_name FROM attendance a JOIN sessions s ON a.session_id=s.session_id JOIN classes c ON s.class_id=c.class_id WHERE a.student_id=%s ORDER BY s.date DESC",
            (student[0]["student_id"],))
        eligible = _rows(
            "SELECT COUNT(*) AS n FROM sessions WHERE class_id=%s AND date <= CURDATE()",
            (student[0]["class_id"],))[0]["n"]
        attended = _rows(
            "SELECT COUNT(*) AS n FROM attendance a JOIN sessions s ON a.session_id=s.session_id WHERE a.student_id=%s AND a.status='present'",
            (student[0]["student_id"],))[0]["n"]
        percentage = round(attended / eligible * 100, 1) if eligible else 0
    return render_template("student.html", history=history, percentage=percentage)


@student_bp.route("/scanner")
def scanner():
    if not require_student():
        return redirect(url_for("login"))
    return render_template("scanner.html")


@student_bp.route("/scan")
def scan_token():
    if not require_student():
        flash("Please log in as a student first.")
        return redirect(url_for("login"))
    token = request.args.get("token")
    uid = session["user_id"]
    student = _rows("SELECT * FROM students WHERE user_id=%s", (uid,))
    if not student:
        flash("Student record not found.")
        return redirect(url_for("student.index"))
    return render_template("confirm_scan.html", token=token, student_id=student[0]["student_id"])


@student_bp.route("/scan/submit", methods=["POST"])
def submit_scan():
    if not require_student():
        return redirect(url_for("login"))
    token = request.form.get("token", "")
    device_id = request.form.get("device_id", "").strip() or "unknown"
    uid = session["user_id"]
    students = _rows("SELECT * FROM students WHERE user_id=%s", (uid,))
    if not students:
        flash("Student record not found.")
        return redirect(url_for("student.index"))
    student = students[0]

    rows = _rows("SELECT * FROM sessions WHERE qr_token=%s", (token,))
    if not rows:
        flash("Invalid QR code.")
        return redirect(url_for("student.index"))
    s = rows[0]

    if s["class_id"] != student["class_id"]:
        flash("You are not enrolled in this class.")
        return redirect(url_for("student.index"))

    now = datetime.now()
    student_dt = datetime.now()
    today = now.date()
    if s["date"] != today:
        flash("Session is not active today.")
        return redirect(url_for("student.index"))
    session_start = datetime.combine(s["date"], s["start_time"])
    session_end = datetime.combine(s["date"], s["end_time"])
    if not (session_start <= student_dt <= session_end):
        flash("Session is not active at this time.")
        return redirect(url_for("student.index"))

    existing = _rows("SELECT device_id, student_id FROM attendance WHERE device_id=%s AND student_id<>%s LIMIT 1",
                     (device_id, student["student_id"]))
    if existing:
        flash("This device is already linked to another student.")
        return redirect(url_for("student.index"))

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO attendance (session_id, student_id, status, scan_time, device_id) VALUES (%s,%s,'present',NOW(),%s)",
            (s["session_id"], student["student_id"], device_id))
        conn.commit()
        cur.close(); conn.close()
        flash("Attendance marked!")
    except Exception:
        flash("Attendance could not be marked (already marked for this session?).")
    return redirect(url_for("student.index"))
