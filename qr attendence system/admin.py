import csv
import io
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, Response
from werkzeug.security import generate_password_hash
from db import get_db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def require_admin():
    if session.get("role") != "admin":
        return False
    return True


def _rows(query, params=()):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(query, params)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


@admin_bp.route("/")
def index():
    if not require_admin():
        return redirect(url_for("login"))
    teachers = _rows("SELECT * FROM users WHERE role='teacher'")
    students = _rows("SELECT s.*, u.name, u.email, c.class_name FROM students s JOIN users u ON s.user_id=u.user_id LEFT JOIN classes c ON s.class_id=c.class_id")
    classes = _rows("SELECT c.*, u.name AS teacher_name FROM classes c LEFT JOIN users u ON c.teacher_id=u.user_id")
    subjects = _rows("SELECT * FROM subjects")
    return render_template("admin.html", teachers=teachers, students=students, classes=classes, subjects=subjects)


@admin_bp.route("/teachers/add", methods=["POST"])
def add_teacher():
    if not require_admin():
        return redirect(url_for("login"))
    name = request.form["name"]
    email = request.form["email"]
    password = request.form["password"]
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,'teacher')",
                    (name, email, generate_password_hash(password)))
        conn.commit()
    except Exception:
        flash("Could not add teacher (email may already exist).")
    cur.close(); conn.close()
    return redirect(url_for("admin.index"))


@admin_bp.route("/subjects/add", methods=["POST"])
def add_subject():
    if not require_admin():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO subjects (subject_name) VALUES (%s)", (request.form["subject_name"],))
        conn.commit()
    except Exception:
        flash("Could not add subject.")
    cur.close(); conn.close()
    return redirect(url_for("admin.index"))


@admin_bp.route("/classes/add", methods=["POST"])
def add_class():
    if not require_admin():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO classes (class_name, subject, teacher_id) VALUES (%s,%s,%s)",
                (request.form["class_name"], request.form["subject"], request.form.get("teacher_id") or None))
    conn.commit()
    cur.close(); conn.close()
    return redirect(url_for("admin.index"))


def _report_rows():
    query = """
      SELECT u.name, st.roll_number, c.class_name,
             (SELECT COUNT(*) FROM sessions ses WHERE ses.class_id = st.class_id AND ses.date <= CURDATE()) AS eligible,
             (SELECT COUNT(DISTINCT a.session_id) FROM attendance a
                JOIN sessions ses ON a.session_id = ses.session_id
                WHERE a.student_id = st.student_id AND a.status = 'present') AS attended
      FROM students st
      JOIN users u ON st.user_id = u.user_id
      LEFT JOIN classes c ON st.class_id = c.class_id
      ORDER BY u.name
    """
    return _rows(query)


@admin_bp.route("/reports")
def reports():
    if not require_admin():
        return redirect(url_for("login"))
    rows = []
    for r in _report_rows():
        r["percentage"] = round(r["attended"] / r["eligible"] * 100, 1) if r["eligible"] else 0
        rows.append(r)
    return render_template("reports.html", rows=rows)


@admin_bp.route("/reports/export.csv")
def export_csv():
    if not require_admin():
        return redirect(url_for("login"))
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Roll Number", "Class", "Eligible Sessions", "Attended", "Percentage"])
    for r in _report_rows():
        pct = round(r["attended"] / r["eligible"] * 100, 1) if r["eligible"] else 0
        writer.writerow([r["name"], r["roll_number"], r["class_name"], r["eligible"], r["attended"], f"{pct}%"])
    return Response(output.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=attendance_report.csv"})


@admin_bp.route("/students/add", methods=["POST"])
def add_student():
    if not require_admin():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO users (name,email,password_hash,role) VALUES (%s,%s,%s,'student')",
                    (request.form["name"], request.form["email"], generate_password_hash(request.form["password"])))
        user_id = cur.lastrowid
        cur.execute("INSERT INTO students (user_id, class_id, roll_number) VALUES (%s,%s,%s)",
                    (user_id, request.form.get("class_id") or None, request.form["roll_number"]))
        conn.commit()
    except Exception:
        conn.rollback()
        flash("Could not add student.")
    cur.close(); conn.close()
    return redirect(url_for("admin.index"))
