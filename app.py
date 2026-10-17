
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
