"""Autenticación de App Engine detrás de Identity-Aware Proxy."""

from __future__ import annotations

import hashlib
import logging
import os
from functools import lru_cache
from typing import Any
from urllib.request import Request as URLRequest, urlopen

from flask import abort, g, request

IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"
IAP_ISSUER = "https://cloud.google.com/iap"
METADATA_PROJECT_NUMBER_URL = "http://metadata.google.internal/computeMetadata/v1/project/numeric-project-id"


def normalized_email(email: str) -> str:
    return email.strip().lower()


def admin_document_id(email: str) -> str:
    """Use a stable opaque document ID instead of exposing addresses in paths."""
    return hashlib.sha256(normalized_email(email).encode("utf-8")).hexdigest()


def verify_iap_identity(assertion: str, audience: str) -> dict[str, Any]:
    """Cryptographically verify the signed identity assertion issued by IAP."""
    from google.auth.transport.requests import Request
    from google.oauth2 import id_token

    claims = id_token.verify_token(
        assertion,
        Request(),
        audience=audience,
        certs_url=IAP_CERTS_URL,
    )
    if claims.get("iss") != IAP_ISSUER:
        raise ValueError("Unexpected IAP issuer")
    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        raise ValueError("IAP identity has no verified email")
    return {
        "email": normalized_email(email),
        "name": claims.get("name") or email.split("@", 1)[0],
    }


@lru_cache(maxsize=1)
def _iap_audience() -> str:
    configured = os.getenv("IAP_AUDIENCE", "").strip()
    if configured:
        return configured
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    if not project_id:
        raise RuntimeError("Google Cloud project ID is unavailable")
    metadata_request = URLRequest(METADATA_PROJECT_NUMBER_URL, headers={"Metadata-Flavor": "Google"})
    with urlopen(metadata_request, timeout=2) as response:
        project_number = response.read().decode("ascii").strip()
    if not project_number.isdigit():
        raise RuntimeError("Google Cloud project number is invalid")
    return f"projects/{project_number}/apps/{project_id}"


def authenticate_request() -> None:
    """Populate g.current_user; fail closed if IAP is required but misconfigured."""
    g.current_user = None
    if os.getenv("REQUIRE_IAP", "false").lower() != "true":
        if os.getenv("APP_ENV", "development") != "production" and os.getenv("LOCAL_AUTH_BYPASS", "false").lower() == "true":
            g.current_user = {
                "email": normalized_email(os.getenv("LOCAL_AUTH_EMAIL", "local@example.invalid")),
                "name": "Usuario local",
            }
        return

    try:
        audience = _iap_audience()
    except Exception:
        logging.exception("Could not determine the IAP JWT audience")
        abort(503, description="No se ha podido verificar la configuración de acceso seguro.")

    assertion = request.headers.get("X-Goog-IAP-JWT-Assertion", "")
    if not assertion:
        abort(401, description="Inicia sesión con una cuenta de Google autorizada.")

    try:
        g.current_user = verify_iap_identity(assertion, audience)
    except Exception:
        logging.exception("Rejected invalid IAP identity assertion")
        abort(401, description="No se pudo verificar tu identidad.")


def is_admin(email: str | None) -> bool:
    if not email:
        return False
    if os.getenv("APP_ENV", "development") != "production" and os.getenv("LOCAL_AUTH_BYPASS", "false").lower() == "true":
        return normalized_email(email) == normalized_email(os.getenv("LOCAL_ADMIN_EMAIL", ""))
    datastore_mode = os.getenv("USE_DATASTORE", "false").lower() == "true"
    firestore_mode = os.getenv("USE_FIRESTORE", "false").lower() == "true"
    if not datastore_mode and not firestore_mode:
        return False

    try:
        if datastore_mode:
            from datastore_store import is_admin as datastore_is_admin

            return datastore_is_admin(admin_document_id(email))
        from club_store import firestore_client

        document = firestore_client().collection("admins").document(admin_document_id(email)).get()
        return document.exists and document.to_dict().get("active", True) is True
    except Exception:
        logging.exception("Could not check the administrator allowlist")
        return False


def require_admin() -> None:
    user = getattr(g, "current_user", None)
    if user is None:
        abort(401, description="Inicia sesión antes de continuar.")
    if not is_admin(user.get("email")):
        abort(403, description="Tu cuenta no tiene permisos de administración.")
