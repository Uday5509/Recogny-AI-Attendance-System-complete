import os
import sqlite3
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from database.database import get_db_connection
from services import face_engine, aws_sync

students_bp = Blueprint("students", __name__)
ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


@students_bp.route("/students", methods=["GET", "POST"])
def students():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        roll = request.form.get("roll", "").strip()
        photo = request.files.get("photo")
        if not name or not roll or not photo or not photo.filename:
            flash("Name, roll number and a photo are required.", "error")
            return redirect(url_for("students.students"))
        ext = os.path.splitext(photo.filename)[1].lower()
        if ext not in ALLOWED:
            flash("Unsupported image type. Use JPG, PNG or WEBP.", "error")
            return redirect(url_for("students.students"))

        conn = get_db_connection()
        if conn.execute("SELECT 1 FROM students WHERE roll_number = ?", (roll,)).fetchone():
            conn.close()
            flash(f"Roll number {roll} is already registered.", "error")
            return redirect(url_for("students.students"))

        data = photo.read()
        try:
            emb = face_engine.get_embedding(face_engine.decode_image(data))
        except RuntimeError as exc:
            conn.close()
            flash(str(exc), "error")
            return redirect(url_for("students.students"))
        if emb is None:
            conn.close()
            flash("No face detected in the photo. Upload a clear, front-facing portrait.", "error")
            return redirect(url_for("students.students"))

        filename = uuid.uuid4().hex + ext
        path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        with open(path, "wb") as f:
            f.write(data)
        try:
            conn.execute("INSERT INTO students (name, roll_number, photo, embedding) VALUES (?,?,?,?)",
                         (name, roll, filename, emb.tobytes()))
            conn.commit()
        except sqlite3.IntegrityError:
            os.remove(path)
            flash(f"Roll number {roll} is already registered.", "error")
            conn.close()
            return redirect(url_for("students.students"))
        conn.close()
        aws_sync.sync_student(name, roll, path, filename)
        flash(f"{name} registered successfully.", "success")
        return redirect(url_for("students.students"))

    conn = get_db_connection()
    rows = conn.execute("SELECT id, name, roll_number, photo FROM students ORDER BY name").fetchall()
    conn.close()
    return render_template("students.html", students=rows)


@students_bp.route("/delete_student/<int:student_id>")
def delete_student(student_id):
    conn = get_db_connection()
    row = conn.execute("SELECT photo, name FROM students WHERE id = ?", (student_id,)).fetchone()
    if row:
        conn.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
        if row["photo"]:
            p = os.path.join(current_app.config["UPLOAD_FOLDER"], row["photo"])
            if os.path.exists(p):
                os.remove(p)
        flash(f"{row['name']} deleted.", "success")
    conn.close()
    return redirect(url_for("students.students"))
