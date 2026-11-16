"""Autenticación Firebase y autorización basada en rol persistido en Firestore."""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

from flask import abort, g, request

SESSION_COOKIE_NAME = "montajesrica_session"


def normalized_email(email: str) -> str:
    return email.strip().lower()


def admin_document_id(email: str) -> str:
    """Compatibilidad de ID opaco para las herramientas antiguas de bootstrap."""
    return hashlib.sha256(normalized_email(email).encode("utf-8")).hexdigest()


def authenticate_request() -> None:
    """Verifica cookie Firebase y lee el rol actual desde la colección users."""
    g.current_user = None
    session_cookie = request.cookies.get(SESSION_COOKIE_NAME, "")
    if not session_cookie:
        return

    try:
        from firebase_auth import verify_session_cookie
        from club_store import ensure_user_profile

        claims = verify_session_cookie(session_cookie)
        provider = claims.get("firebase", {}).get("sign_in_provider")
        if provider not in {"google.com", "password"}:
            raise ValueError("La sesión no pertenece a un proveedor permitido.")
        if claims.get("email_verified") is not True:
            raise ValueError("El correo de la sesión no está verificado.")
        user = ensure_user_profile(
            uid=claims["uid"],
            email=claims["email"],
            display_name=claims.get("name") or claims["email"].split("@", 1)[0],
            provider=provider,
        )
        if not user.get("active", True):
            raise ValueError("La cuenta está desactivada.")
        g.current_user = user
    except Exception:
        logging.info("Firebase session rejected", exc_info=True)
        g.current_user = None
        g.clear_firebase_session = True


def is_admin(uid: str | None) -> bool:
    if not uid:
        return False
    user = getattr(g, "current_user", None)
    if user and user.get("uid") == uid:
        return user.get("role") == "admin" and user.get("active", True) is True
    try:
        from club_store import get_user_profile

        profile = get_user_profile(uid)
        return bool(profile and profile.get("role") == "admin" and profile.get("active", True) is True)
    except Exception:
        logging.exception("Could not check the user's Firestore role")
        return False


def require_user() -> dict[str, Any]:
    user = getattr(g, "current_user", None)
    if user is None:
        abort(401, description="Inicia sesión con Google para consultar el club.")
    if not user.get("active", True):
        abort(403, description="Tu cuenta está desactivada.")
    return user


def require_admin() -> None:
    user = require_user()
    if user.get("role") != "admin":
        abort(403, description="Tu cuenta tiene rol watcher; solo administración puede realizar cambios.")
