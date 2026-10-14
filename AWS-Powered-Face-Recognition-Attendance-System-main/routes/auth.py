from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database.database import get_db_connection, get_settings

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/", methods=["GET"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("dashboard.dashboard") if session.get("role") == "admin"
                        else url_for("auth.student_portal"))
    return render_template("login.html")


@auth_bp.route("/login", methods=["POST"])
def login():
    role = request.form.get("role", "admin")
    if role == "student":
        roll = request.form.get("roll", "").strip()
        conn = get_db_connection()
        student = conn.execute("SELECT * FROM students WHERE roll_number = ?", (roll,)).fetchone()
        conn.close()
        if not student:
            flash("Roll number not found. Please contact your teacher.", "error")
            return redirect(url_for("auth.login_page"))
        session.clear()
        session.update(logged_in=True, role="student", student_id=student["id"])
        return redirect(url_for("auth.student_portal"))

    s = get_settings()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    if username == s.get("admin_username") and check_password_hash(s.get("admin_password", ""), password):
        session.clear()
        session.update(logged_in=True, role="admin", username=username)
        return redirect(url_for("dashboard.dashboard"))
    flash("Invalid username or password.", "error")
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login_page"))


@auth_bp.route("/student/portal")
def student_portal():
    if session.get("role") != "student":
        return redirect(url_for("auth.login_page"))
    conn = get_db_connection()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (session["student_id"],)).fetchone()
    if not student:
        conn.close()
        session.clear()
        return redirect(url_for("auth.login_page"))
    attendance = conn.execute(
        "SELECT date, time, status FROM attendance WHERE student_id = ? ORDER BY date DESC, time DESC",
        (student["id"],)).fetchall()
    total_days = conn.execute("SELECT COUNT(DISTINCT date) FROM attendance").fetchone()[0]
    conn.close()
    present_days = len({r["date"] for r in attendance})
    rate = round(present_days / total_days * 100) if total_days else 0
    return render_template("student_portal.html", student=student, attendance=attendance,
                           present_days=present_days, attendance_rate=rate)
