"""Legacy web endpoints (Flask-style)."""

from flask import Flask

app = Flask(__name__)


@app.route("/health")
def health():
    return "ok"


@app.route("/admin", methods=["GET", "POST"])
def admin():
    return "admin"
