
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pathlib import Path
import sqlite3
import uuid
import os

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "change-this-secret-key-before-deployment"
)
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_db() as db:

        # Citizens table
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL
            )
        """)

        # Complaints table
        db.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending'
            )
        """)

        # Preserve existing database and add missing columns
        columns = {
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(complaints)"
            ).fetchall()
        }

        if "photo" not in columns:
            db.execute(
                "ALTER TABLE complaints ADD COLUMN photo TEXT"
            )

        if "user_id" not in columns:
            db.execute(
                "ALTER TABLE complaints ADD COLUMN user_id INTEGER"
            )

# Add GPS latitude column
if "latitude" not in columns:
    db.execute(
        "ALTER TABLE complaints ADD COLUMN latitude REAL"
    )

# Add GPS longitude column
if "longitude" not in columns:
    db.execute(
        "ALTER TABLE complaints ADD COLUMN longitude REAL"
    )

# HOME PAGE
@app.route("/")
def home():
    with get_db() as db:
        complaints = db.execute(
            "SELECT * FROM complaints ORDER BY id DESC LIMIT 5"
        ).fetchall()

    return render_template("index.html", complaints=complaints)


# CITIZEN REGISTRATION
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return "Please fill all fields.", 400

        if len(name) > 100 or len(email) > 254:
            return "Input is too long.", 400

        if "@" not in email or "." not in email:
            return "Enter a valid email address.", 400

        if len(password) < 8:
            return "Password must contain at least 8 characters.", 400

        hashed_password = generate_password_hash(password)

        try:
            with get_db() as db:
                db.execute(
                    """
                    INSERT INTO users (name, email, password)
                    VALUES (?, ?, ?)
                    """,
                    (name, email, hashed_password)
                )

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            return "This email is already registered.", 409

    return render_template("register.html")


# CITIZEN LOGIN
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as db:
            user = db.execute(
                "SELECT * FROM users WHERE email = ?",
                (email,)
            ).fetchone()

        if user and check_password_hash(user["password"], password):

            session.clear()
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]

            return redirect(url_for("citizen_dashboard"))

        return "Invalid email or password.", 401

    return render_template("login.html")


# CITIZEN DASHBOARD
@app.route("/citizen-dashboard")
def citizen_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    with get_db() as db:
        complaints = db.execute(
            """
            SELECT * FROM complaints
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (session["user_id"],)
        ).fetchall()

    return render_template(
        "citizen_dashboard.html",
        complaints=complaints,
        name=session["user_name"]
    )


# LOGOUT
@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# GARBAGE COMPLAINT REPORT
@app.route("/report", methods=["POST"])
def report():

    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()
    uploaded_file = request.files.get("photo")

    if not location or not description:
        return "Please enter location and description.", 400

    if len(location) > 200 or len(description) > 2000:
        return "Input is too long.", 400

    photo_name = None

    if uploaded_file and uploaded_file.filename:

        original_name = secure_filename(uploaded_file.filename)

        if "." not in original_name:
            return "Invalid image filename.", 400

        extension = original_name.rsplit(".", 1)[1].lower()

        if extension not in ALLOWED_EXTENSIONS:
            return "Use JPG, JPEG, PNG or WEBP images.", 400

        photo_name = f"{uuid.uuid4().hex}.{extension}"
        uploaded_file.save(UPLOAD_DIR / photo_name)

    try:
        with get_db() as db:
            db.execute(
                """
                INSERT INTO complaints
                (location, description, photo, user_id)
                VALUES (?, ?, ?, ?)
                """,
                (
                    location,
                    description,
                    photo_name,
                    session.get("user_id")
                )
            )

    except Exception:
        if photo_name:
            (UPLOAD_DIR / photo_name).unlink(missing_ok=True)
        raise

    if "user_id" in session:
        return redirect(url_for("citizen_dashboard"))

    return redirect(url_for("home"))


# ADMIN DASHBOARD
@app.route("/admin")
def admin():

    with get_db() as db:
        complaints = db.execute(
            "SELECT * FROM complaints ORDER BY id DESC"
        ).fetchall()

    return render_template(
        "admin.html",
        complaints=complaints
    )


# PHOTO SIZE ERROR
@app.errorhandler(413)
def file_too_large(error):
    return "Photo is too large. Maximum size is 5 MB.", 413


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
