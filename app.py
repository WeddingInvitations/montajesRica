"""Portal privado de equipos de pádel Montajes Rica."""

from __future__ import annotations

import os
from pathlib import Path

from flask import Flask, abort, g, jsonify, make_response, render_template, request, send_from_directory
from flask_wtf.csrf import CSRFProtect
from firebase_admin import exceptions as firebase_exceptions
from werkzeug.exceptions import HTTPException

from admin_routes import admin_bp
from club_store import ensure_user_profile, load_club_data
from firebase_auth import SESSION_DURATION, create_session_cookie, verify_firebase_id_token
from security import SESSION_COOKIE_NAME, authenticate_request

BASE_DIR = Path(__file__).resolve().parent
app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("APP_ENV", "development") == "production"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


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
    if request.endpoint in {"health", "static"}:
        g.current_user = None
        return
    authenticate_request()


@app.context_processor
def inject_identity():
    user = getattr(g, "current_user", None)
    return {
        "current_user": user,
        "current_user_is_admin": bool(user and user.get("role") == "admin"),
    }


@app.get("/")
def home():
    user = getattr(g, "current_user", None)
    club = load_club_data() if user else None
    response = make_response(render_template("index.html", club=club))
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    return response


@app.post("/auth/session")
def create_auth_session():
    payload = request.get_json(silent=True)
    id_token = payload.get("idToken") if isinstance(payload, dict) else None
    if not isinstance(id_token, str) or not id_token or len(id_token) > 12_000:
        abort(400, description="Falta un token de inicio de sesión válido.")
    try:
        claims = verify_firebase_id_token(id_token)
        cookie_value = create_session_cookie(id_token)
        profile = ensure_user_profile(
            uid=claims["uid"],
            email=claims["email"],
            display_name=claims.get("name") or claims["email"].split("@", 1)[0],
            provider=claims.get("firebase", {}).get("sign_in_provider", "unknown"),
        )
        if not profile.get("active", True):
            abort(403, description="Tu cuenta está desactivada. Contacta con administración.")
    except ValueError as error:
        abort(401, description=str(error))
    except firebase_exceptions.FirebaseError:
        app.logger.exception("Firebase Auth session creation failed")
        abort(401, description="Firebase no ha podido validar la cuenta. Inténtalo de nuevo.")
    except HTTPException:
        raise
    except Exception:
        app.logger.exception("Could not exchange Firebase identity for an application session")
        abort(503, description="El servidor no pudo completar la sesión. Comprueba sus permisos de Firebase/Firestore.")

    response = jsonify({"ok": True, "role": profile.get("role", "watcher")})
    response.set_cookie(
        SESSION_COOKIE_NAME,
        cookie_value,
        max_age=int(SESSION_DURATION.total_seconds()),
        httponly=True,
        secure=app.config["SESSION_COOKIE_SECURE"] or request.is_secure,
        samesite="Lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/auth/logout")
def logout():
    response = jsonify({"ok": True})
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=app.config["SESSION_COOKIE_SECURE"] or request.is_secure,
        httponly=True,
        samesite="Lax",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/healthz")
def health():
    return jsonify(status="ok"), 200


@app.get("/logoMontajes.jpeg")
def club_logo():
    return send_from_directory(BASE_DIR, "logoMontajes.jpeg", max_age=86400)


@app.after_request
def clear_invalid_session_cookie(response):
    if request.endpoint not in {"static", "club_logo"}:
        response.headers["Cache-Control"] = "private, no-store, max-age=0"
    if getattr(g, "clear_firebase_session", False):
        response.delete_cookie(
            SESSION_COOKIE_NAME,
            path="/",
            secure=app.config["SESSION_COOKIE_SECURE"] or request.is_secure,
            httponly=True,
            samesite="Lax",
        )
    return response


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
