import base64
from datetime import datetime
import numpy as np
from flask import Blueprint, render_template, request, jsonify
from database.database import get_db_connection, get_settings
from services import face_engine, aws_sync

attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.route("/attendance")
def attendance():
    return render_template("attendance.html")


@attendance_bp.route("/attendance/detect", methods=["POST"])
def detect():
    payload = request.get_json(silent=True) or {}
    image_b64 = payload.get("image", "")
    if "," in image_b64:
        image_b64 = image_b64.split(",", 1)[1]
    try:
        img = face_engine.decode_image(base64.b64decode(image_b64))
    except Exception:
        return jsonify(status="error", message="Invalid image"), 400

    conn = get_db_connection()
    students = conn.execute("SELECT id, name, roll_number, photo, embedding FROM students "
                            "WHERE embedding IS NOT NULL").fetchall()
    if not students:
        conn.close()
        return jsonify(status="no_students")

    try:
        emb = face_engine.get_embedding(img)
    except RuntimeError as exc:
        conn.close()
        return jsonify(status="error", message=str(exc)), 500
    if emb is None:
        conn.close()
        return jsonify(status="no_face")

    candidates = [(s, np.frombuffer(s["embedding"], dtype=np.float32)) for s in students]
    student, score = face_engine.best_match(emb, candidates)
    threshold = float(get_settings().get("threshold", 0.4))
    if student is None or score < threshold:
        conn.close()
        return jsonify(status="unknown", confidence=max(score, 0))

    now = datetime.now()
    today, clock = now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    info = dict(name=student["name"], roll=student["roll_number"], photo=student["photo"], confidence=score)
    if conn.execute("SELECT 1 FROM attendance WHERE student_id = ? AND date = ?",
                    (student["id"], today)).fetchone():
        conn.close()
        return jsonify(status="already_marked", **info)
    conn.execute("INSERT INTO attendance (student_id, student_name, roll_number, date, time, status) "
                 "VALUES (?,?,?,?,?, 'Present')",
                 (student["id"], student["name"], student["roll_number"], today, clock))
    conn.commit()
    conn.close()
    aws_sync.sync_attendance(student["roll_number"], student["name"], today, clock)
    return jsonify(status="success", **info)
