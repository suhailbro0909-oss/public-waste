
from flask import Flask, render_template, request, redirect, url_for
import sqlite3
from pathlib import Path

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending'
            )
        """)


@app.route("/")
def home():
    with get_db() as db:
        complaints = db.execute(
            "SELECT * FROM complaints ORDER BY id DESC LIMIT 5"
        ).fetchall()

    return render_template("index.html", complaints=complaints)


@app.route("/report", methods=["POST"])
def report():
    location = request.form.get("location", "").strip()
    description = request.form.get("description", "").strip()

    if not location or not description:
        return "Please enter both location and description.", 400

    if len(location) > 200 or len(description) > 2000:
        return "Your input is too long.", 400

    with get_db() as db:
        db.execute(
            "INSERT INTO complaints (location, description) VALUES (?, ?)",
            (location, description)
        )

    return redirect(url_for("home"))


@app.route("/admin")
def admin():
    with get_db() as db:
        complaints = db.execute(
            "SELECT * FROM complaints ORDER BY id DESC"
        ).fetchall()

    return render_template("admin.html", complaints=complaints)


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for
from werkzeug.utils import secure_filename
from pathlib import Path
import sqlite3
import uuid

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"
UPLOAD_DIR = BASE_DIR / "static" / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS complaints (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending'
            )
        """)

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


@app.route("/")
def home():
    with get_db() as db:
        complaints = db.execute(
            "SELECT * FROM complaints ORDER BY id DESC LIMIT 5"
        ).fetchall()

    return render_template("index.html", complaints=complaints)


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
                (location, description, photo)
                VALUES (?, ?, ?)
                """,
                (location, description, photo_name)
            )
    except Exception:
        if photo_name:
            (UPLOAD_DIR / photo_name).unlink(missing_ok=True)
        raise

    return redirect(url_for("home"))


@app.route("/admin")
def admin():
    with get_db() as db:
        complaints = db.execute(
            "SELECT * FROM complaints ORDER BY id DESC"
        ).fetchall()

    return render_template("admin.html", complaints=complaints)


@app.errorhandler(413)
def file_too_large(error):
    return "Photo is too large. Maximum size is 5 MB.", 413


if __name__ == "__main__":
    initialize_database()
    app.run(debug=True)
