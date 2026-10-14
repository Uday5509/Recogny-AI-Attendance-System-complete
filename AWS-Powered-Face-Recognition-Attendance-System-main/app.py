from flask import Flask, session, redirect, url_for, request
import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Create Flask App
app = Flask(__name__)

# Config
app.secret_key = os.getenv("SECRET_KEY", "recogny_secret_key_change_me_in_production")
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Register Blueprints
from routes.auth import auth_bp
from routes.dashboard import dashboard_bp
from routes.students import students_bp
from routes.attendance import attendance_bp
from routes.reports import reports_bp
from routes.settings import settings_bp

app.register_blueprint(auth_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(students_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(settings_bp)

# Request context processor to inject system configuration to all templates
@app.context_processor
def inject_system_settings():
    from database.database import get_db_connection
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM settings")
        rows = cursor.fetchall()
        settings_dict = {row["key"]: row["value"] for row in rows}
        conn.close()
    except Exception:
        settings_dict = {
            "school_name": "Recogny AI Academy",
            "threshold": "0.6"
        }
    return dict(system_settings=settings_dict)

# Global route authentication middleware check
@app.before_request
def check_login():
    # Endpoints that do not require authentication
    allowed_routes = ["auth.login_page", "auth.login", "static"]
    
    # If endpoint matches allowed routes, bypass check
    if request.endpoint in allowed_routes or request.endpoint is None:
        return None
        
    # If not logged in, redirect to login page
    if not session.get("logged_in"):
        return redirect(url_for("auth.login_page"))

    # Role-based access control: Students can only access student_portal and logout
    if session.get("role") == "student" and request.endpoint not in ["auth.student_portal", "auth.logout"]:
        return redirect(url_for("auth.student_portal"))

# Main Entry Point
if __name__ == "__main__":
    print("=" * 40)
    print("        Recogny AI")
    print("=" * 40)
    print("Starting Flask Development Server...")
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
