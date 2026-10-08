import io
import base64
import secrets
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session
import qrcode

from db import get_db

teacher_bp = Blueprint("teacher", __name__, url_prefix="/teacher")


def require_teacher():
    return session.get("role") == "teacher"


def _rows(query, params=()):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@teacher_bp.route("/")
def index():
    if not require_teacher():
        return redirect(url_for("login"))
    uid = session["user_id"]
    classes = _rows("SELECT * FROM classes WHERE teacher_id=%s", (uid,))
    sessions = _rows(
        "SELECT s.*, c.class_name FROM sessions s JOIN classes c ON s.class_id=c.class_id WHERE c.teacher_id=%s ORDER BY s.date DESC, s.start_time DESC",
        (uid,))
    return render_template("teacher.html", classes=classes, sessions=sessions)


@teacher_bp.route("/sessions/create", methods=["POST"])
def create_session():
    if not require_teacher():
        return redirect(url_for("login"))
    class_id = request.form["class_id"]
    date = request.form["date"]
    start_time = request.form["start_time"]
    end_time = request.form["end_time"]
    token = secrets.token_urlsafe(32)
    expires_at = f"{date} {end_time}:00"
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (class_id,date,start_time,end_time,qr_token,expires_at) VALUES (%s,%s,%s,%s,%s,%s)",
        (class_id, date, start_time, end_time, token, expires_at))
    session_id = cur.lastrowid
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for("teacher.session_qr", session_id=session_id))


@teacher_bp.route("/sessions/<int:session_id>/live")
def session_live(session_id):
    if not require_teacher():
        return redirect(url_for("login"))
    rows = _rows(
        "SELECT s.*, c.class_name, c.class_id FROM sessions s JOIN classes c ON s.class_id=c.class_id WHERE s.session_id=%s AND c.teacher_id=%s",
        (session_id, session["user_id"]))
    if not rows:
        return "Not found", 404
    s = rows[0]
    attendees = _rows(
        "SELECT a.*, u.name, u.email, st.roll_number FROM attendance a JOIN students st ON a.student_id=st.student_id JOIN users u ON st.user_id=u.user_id WHERE a.session_id=%s ORDER BY a.scan_time",
        (session_id,))
    roster = _rows("SELECT st.student_id, u.name FROM students st JOIN users u ON st.user_id=u.user_id WHERE st.class_id=%s", (s["class_id"],))
    return render_template("session_live.html", session=s, attendees=attendees, roster=roster)


@teacher_bp.route("/sessions/<int:session_id>/mark", methods=["POST"])
def mark_attendance(session_id):
    if not require_teacher():
        return redirect(url_for("login"))
    student_id = request.form["student_id"]
    status = request.form.get("status", "present")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM attendance WHERE session_id=%s AND student_id=%s", (session_id, student_id))
    cur.execute("INSERT INTO attendance (session_id, student_id, status, scan_time, device_id) VALUES (%s,%s,%s,NOW(),'teacher-override')",
                (session_id, student_id, status))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for("teacher.session_live", session_id=session_id))


@teacher_bp.route("/sessions/<int:session_id>/qr")
def session_qr(session_id):
    if not require_teacher():
        return redirect(url_for("login"))
    rows = _rows(
        "SELECT s.*, c.class_name FROM sessions s JOIN classes c ON s.class_id=c.class_id WHERE s.session_id=%s AND c.teacher_id=%s",
        (session_id, session["user_id"]))
    if not rows:
        return "Not found", 404
    s = rows[0]
    scan_url = url_for("student.scan_token", token=s["qr_token"], _external=True)
    img = qrcode.make(scan_url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()
    return render_template("session_qr.html", session=s, qr=qr_b64, scan_url=scan_url)
