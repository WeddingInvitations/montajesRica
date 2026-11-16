"""Validación y sesiones de Firebase Authentication para Flask."""

from __future__ import annotations

import os
from datetime import timedelta
from functools import lru_cache
from typing import Any

import firebase_admin
from firebase_admin import auth

SESSION_DURATION = timedelta(days=5)
RECENT_SIGN_IN_SECONDS = 5 * 60


def has_verified_google_identity(claims: dict[str, Any]) -> bool:
    """Trust Google-authenticated Firebase identities even if email_verified is omitted.

    Firebase signs the identities map into its ID token. A password sign-in is also
    acceptable for an account whose Google provider was previously linked.
    """
    firebase_claims = claims.get("firebase") or {}
    if firebase_claims.get("sign_in_provider") == "google.com":
        return True
    identities = firebase_claims.get("identities") or {}
    return bool(identities.get("google.com"))


@lru_cache(maxsize=1)
def firebase_app() -> firebase_admin.App:
    project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if not project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID no está configurado.")
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(options={"projectId": project_id})


def verify_firebase_id_token(id_token: str, now: float | None = None) -> dict[str, Any]:
    claims = auth.verify_id_token(id_token, app=firebase_app(), check_revoked=True)
    firebase_claims = claims.get("firebase") or {}
    if firebase_claims.get("sign_in_provider") not in {"google.com", "password"}:
        raise ValueError("El acceso debe realizarse con Google o correo y contraseña.")
    if claims.get("email_verified") is not True and not has_verified_google_identity(claims):
        raise ValueError("Debes verificar el correo antes de acceder al club.")
    if not claims.get("uid") or not claims.get("email"):
        raise ValueError("El token no contiene una identidad de usuario válida.")
    import time

    current_time = now if now is not None else time.time()
    auth_time = claims.get("auth_time")
    if not isinstance(auth_time, (int, float)) or current_time - auth_time > RECENT_SIGN_IN_SECONDS or auth_time > current_time + 30:
        raise ValueError("Vuelve a iniciar sesión para crear una sesión segura.")
    return claims


def verify_google_id_token(id_token: str, now: float | None = None) -> dict[str, Any]:
    """Backward-compatible alias for tests or callers using the original name."""
    return verify_firebase_id_token(id_token, now=now)


def create_session_cookie(id_token: str) -> str:
    return auth.create_session_cookie(id_token, expires_in=SESSION_DURATION, app=firebase_app())


def verify_session_cookie(cookie_value: str) -> dict[str, Any]:
    return auth.verify_session_cookie(cookie_value, app=firebase_app(), check_revoked=True)
