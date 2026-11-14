
"""Small Flask service used as the target of the DevSecOps pipeline.

It follows secure-coding basics:
* strict input validation
* security headers on every response
* no secrets in code
* no shell/eval/pickle usage
"""

import os
import re
import sqlite3
import tempfile
import time

from flask import Flask, jsonify, request, render_template

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024

NAME_PATTERN = re.compile(r"^[A-Za-z0-9 _.-]{1,50}$")

# API rate-limiting configuration
RATE_LIMIT = 5
RATE_WINDOW = 60

RATE_LIMIT_DB = os.environ.get(
    "RATE_LIMIT_DB",
    os.path.join(tempfile.gettempdir(), "rate_limit.db")
)


def is_rate_limited(client_id):
    """Allow only five requests per client within 60 seconds."""

    now = int(time.time())

    with sqlite3.connect(RATE_LIMIT_DB, timeout=5) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS api_requests (
                client_id TEXT NOT NULL,
                request_time INTEGER NOT NULL
            )
        """)

        db.execute("BEGIN IMMEDIATE")

        db.execute(
            "DELETE FROM api_requests WHERE request_time <= ?",
            (now - RATE_WINDOW,)
        )

        count = db.execute(
            "SELECT COUNT(*) FROM api_requests WHERE client_id = ?",
            (client_id,)
        ).fetchone()[0]

        if count >= RATE_LIMIT:
            return True

        db.execute(
            "INSERT INTO api_requests VALUES (?, ?)",
            (client_id, now)
        )

        return False


@app.after_request
def add_security_headers(response):
    """Attach defensive HTTP security headers."""

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = (
        "geolocation=(), camera=(), microphone=()"
    )

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    )

    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"

    return response


# Original JSON endpoint preserved for existing tests
@app.route("/")
def index():
    return jsonify(
        service="secure-cicd-demo",
        version=os.environ.get("APP_VERSION", "dev"),
        endpoints=[
            "/health",
            "/api/greet?name=<text>",
            "/api/limited-greet?name=<text>",
            "POST /api/echo"
        ],
    )


# Frontend dashboard
@app.route("/dashboard")
def dashboard():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/api/greet")
def greet():
    name = request.args.get("name", "world")

    if not NAME_PATTERN.fullmatch(name):
        return jsonify(error="invalid name"), 400

    return jsonify(message=f"Hello, {name}!")


# New API endpoint with rate limiting
@app.route("/api/limited-greet")
def limited_greet():
    name = request.args.get("name", "world")

    if not NAME_PATTERN.fullmatch(name):
        return jsonify(error="invalid name"), 400

    client_id = request.remote_addr or "unknown"

    if is_rate_limited(client_id):
        return jsonify(
            error="rate limit exceeded. Try again later."
        ), 429

    return jsonify(message=f"Hello, {name}!")


@app.route("/api/echo", methods=["POST"])
def echo():
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not isinstance(data.get("text"), str):
        return jsonify(
            error="body must be JSON with a string field 'text'"
        ), 400

    text = data["text"]

    if len(text) > 200:
        return jsonify(error="text too long (max 200 chars)"), 400

    return jsonify(echo=text, length=len(text))


@app.errorhandler(404)
def not_found(_error):
    return jsonify(error="not found"), 404


@app.errorhandler(405)
def method_not_allowed(_error):
    return jsonify(error="method not allowed"), 405


@app.errorhandler(413)
def too_large(_error):
    return jsonify(error="payload too large"), 413


if __name__ == "__main__":
    # Local development only. In containers the app is served by gunicorn.
    app.run(
        host="127.0.0.1",
        port=int(os.environ.get("PORT", "5000"))
    )
