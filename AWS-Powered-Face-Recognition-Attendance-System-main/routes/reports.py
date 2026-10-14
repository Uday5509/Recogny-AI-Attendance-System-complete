import csv
import io
from flask import Blueprint, render_template, request, Response
from database.database import get_db_connection, get_settings

reports_bp = Blueprint("reports", __name__)


def _query():
    start = request.args.get("start_date", "").strip()
    end = request.args.get("end_date", "").strip()
    search = request.args.get("search_query", "").strip()
    sql = "SELECT student_name, roll_number, date, time, status FROM attendance WHERE 1=1"
    params = []
    if start:
        sql += " AND date >= ?"; params.append(start)
    if end:
        sql += " AND date <= ?"; params.append(end)
    if search:
        sql += " AND (student_name LIKE ? OR roll_number LIKE ?)"; params += [f"%{search}%"] * 2
    sql += " ORDER BY date DESC, time DESC"
    conn = get_db_connection()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return rows, start, end, search


@reports_bp.route("/reports")
def reports():
    rows, start, end, search = _query()
    return render_template("reports.html", records=rows, start_date=start, end_date=end,
                           search_query=search, total_records=len(rows),
                           total_students=len({r["roll_number"] for r in rows}))


@reports_bp.route("/reports/export/csv")
def export_csv():
    rows, *_ = _query()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Student Name", "Roll Number", "Date", "Time", "Status"])
    for r in rows:
        w.writerow([r["student_name"], r["roll_number"], r["date"], r["time"], r["status"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=attendance_report.csv"})


@reports_bp.route("/reports/export/pdf")
def export_pdf():
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    rows, start, end, search = _query()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    school = get_settings().get("school_name", "Recogny AI")
    parts = [Paragraph(f"{school} - Attendance Report", styles["Title"]),
             Paragraph(f"Range: {start or 'start'} to {end or 'today'} | Records: {len(rows)}", styles["Normal"]),
             Spacer(1, 12)]
    data = [["Name", "Roll", "Date", "Time", "Status"]] + \
           [[r["student_name"], r["roll_number"], r["date"], r["time"], r["status"]] for r in rows]
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4f46e5")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                           ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")])]))
    parts.append(t)
    doc.build(parts)
    return Response(buf.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=attendance_report.pdf"})
