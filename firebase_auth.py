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


@lru_cache(maxsize=1)
def firebase_app() -> firebase_admin.App:
    project_id = os.getenv("FIREBASE_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if not project_id:
        raise RuntimeError("FIREBASE_PROJECT_ID no está configurado.")
    try:
        return firebase_admin.get_app()
    except ValueError:
        return firebase_admin.initialize_app(options={"projectId": project_id})


def verify_google_id_token(id_token: str, now: float | None = None) -> dict[str, Any]:
    claims = auth.verify_id_token(id_token, app=firebase_app(), check_revoked=True)
    firebase_claims = claims.get("firebase") or {}
    if firebase_claims.get("sign_in_provider") != "google.com":
        raise ValueError("El acceso debe realizarse con una cuenta Google.")
    if claims.get("email_verified") is not True:
        raise ValueError("La cuenta Google debe tener el correo verificado.")
    if not claims.get("uid") or not claims.get("email"):
        raise ValueError("El token no contiene una identidad de usuario válida.")
    import time

    current_time = now if now is not None else time.time()
    auth_time = claims.get("auth_time")
    if not isinstance(auth_time, (int, float)) or current_time - auth_time > RECENT_SIGN_IN_SECONDS or auth_time > current_time + 30:
        raise ValueError("Vuelve a iniciar sesión para crear una sesión segura.")
    return claims


def create_session_cookie(id_token: str) -> str:
    return auth.create_session_cookie(id_token, expires_in=SESSION_DURATION, app=firebase_app())


def verify_session_cookie(cookie_value: str) -> dict[str, Any]:
    return auth.verify_session_cookie(cookie_value, app=firebase_app(), check_revoked=True)
