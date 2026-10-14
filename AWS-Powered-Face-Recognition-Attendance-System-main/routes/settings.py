import os
import sqlite3
import tempfile
from flask import Blueprint, render_template, request, redirect, url_for, flash, send_file
from werkzeug.security import check_password_hash, generate_password_hash
from database.database import get_db_connection, get_settings, DB_PATH

settings_bp = Blueprint("settings", __name__)


def _set(conn, key, value):
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


@settings_bp.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        conn = get_db_connection()
        form = request.form.get("form_type")
        if form == "general":
            name = request.form.get("school_name", "").strip()
            try:
                thr = float(request.form.get("threshold", "0.4"))
                assert 0.1 <= thr <= 1.0
            except (ValueError, AssertionError):
                flash("Threshold must be a number between 0.1 and 1.0.", "error")
                conn.close()
                return redirect(url_for("settings.settings"))
            _set(conn, "school_name", name or "Recogny AI Academy")
            _set(conn, "threshold", str(thr))
            conn.commit()
            flash("Settings saved.", "success")
        elif form == "security":
            s = get_settings()
            new = request.form.get("new_password", "")
            if not check_password_hash(s["admin_password"], request.form.get("current_password", "")):
                flash("Current password is incorrect.", "error")
            elif len(new) < 6:
                flash("New password must be at least 6 characters.", "error")
            else:
                _set(conn, "admin_password", generate_password_hash(new))
                conn.commit()
                flash("Password updated.", "success")
        conn.close()
        return redirect(url_for("settings.settings"))
    return render_template("settings.html", settings=get_settings())


@settings_bp.route("/settings/backup")
def backup():
    return send_file(DB_PATH, as_attachment=True, download_name="attendance_backup.db")


@settings_bp.route("/settings/restore", methods=["POST"])
def restore():
    f = request.files.get("backup_file")
    if not f or not f.filename.endswith(".db"):
        flash("Please choose a .db backup file.", "error")
        return redirect(url_for("settings.settings"))
    fd, tmp = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    f.save(tmp)
    try:
        c = sqlite3.connect(tmp)
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        c.close()
        if not {"students", "attendance", "settings"} <= tables:
            raise ValueError("missing tables")
    except Exception:
        os.remove(tmp)
        flash("Invalid backup file.", "error")
        return redirect(url_for("settings.settings"))
    with open(tmp, "rb") as src, open(DB_PATH, "wb") as dst:
        dst.write(src.read())
    os.remove(tmp)
    flash("Database restored. Log in again if your password changed.", "success")
    return redirect(url_for("settings.settings"))
