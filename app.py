"""Portal privado de equipos de pádel Montajes Rica."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, g, jsonify, render_template, request, send_from_directory
from flask_wtf.csrf import CSRFProtect

from admin_routes import admin_bp
from club_store import load_club_data
from security import authenticate_request, is_admin

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("APP_ENV", "development") == "production"


def _session_secret() -> str:
    configured = os.getenv("FLASK_SECRET_KEY")
    if configured:
        return configured
    if os.getenv("APP_ENV", "development") != "production":
        return "local-development-only-not-for-production"

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    secret_name = os.getenv("FLASK_SECRET_NAME", "montajes-rica-flask-secret")
    if not project_id:
        raise RuntimeError("GOOGLE_CLOUD_PROJECT is required to load the Flask secret")
    from google.cloud import secretmanager

    client = secretmanager.SecretManagerServiceClient()
    resource = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
    return client.access_secret_version(request={"name": resource}).payload.data.decode("utf-8")


app.config["SECRET_KEY"] = _session_secret()
csrf = CSRFProtect(app)
app.register_blueprint(admin_bp)


@app.before_request
def identify_request():
    if request.endpoint == "health":
        g.current_user = None
        return
    authenticate_request()


@app.context_processor
def inject_identity():
    user = getattr(g, "current_user", None)
    return {
        "current_user": user,
        "current_user_is_admin": bool(user and is_admin(user.get("email"))),
    }


@app.get("/")
def home():
    return render_template("index.html", club=load_club_data())


@app.get("/healthz")
def health():
    return jsonify(status="ok"), 200


@app.get("/logoMontajes.jpeg")
def club_logo():
    return send_from_directory(BASE_DIR, "logoMontajes.jpeg", max_age=86400)


@app.errorhandler(400)
@app.errorhandler(401)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(500)
@app.errorhandler(503)
def application_error(error):
    description = getattr(error, "description", "Ha ocurrido un error inesperado.")
    return render_template("error.html", message=description), error.code


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8080")), debug=True)
