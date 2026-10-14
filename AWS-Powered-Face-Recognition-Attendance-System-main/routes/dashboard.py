from datetime import date
from flask import Blueprint, render_template
from database.database import get_db_connection

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/dashboard")
def dashboard():
    conn = get_db_connection()
    total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    present = conn.execute("SELECT COUNT(DISTINCT student_id) FROM attendance WHERE date = ?",
                           (date.today().isoformat(),)).fetchone()[0]
    conn.close()
    return render_template("dashboard.html", total_students=total, present_count=present,
                           absent_count=max(total - present, 0))
