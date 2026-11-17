"""Persistencia de club en Firestore; los datos locales solo sirven de muestra."""

from __future__ import annotations

import json
import logging
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from flask import abort

from datastore_store import (
    delete_record as datastore_delete_record,
    get_club as datastore_get_club,
    list_records as datastore_list_records,
    update_record as datastore_update_record,
    update_team as datastore_update_team,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "club.json"


@lru_cache(maxsize=1)
def firestore_client():
    from google.cloud import firestore

    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    return firestore.Client(project=project_id)


def firestore_enabled() -> bool:
    return os.getenv("USE_FIRESTORE", "false").lower() == "true" or os.getenv("USE_DATASTORE", "false").lower() == "true"


storage_enabled = firestore_enabled


def datastore_mode_enabled() -> bool:
    return os.getenv("USE_DATASTORE", "false").lower() == "true"


def _collection_records(name: str) -> list[dict[str, Any]]:
    return [dict(snapshot.to_dict() or {}, id=snapshot.id) for snapshot in firestore_client().collection(name).stream()]


def get_user_profile(uid: str) -> dict[str, Any] | None:
    snapshot = firestore_client().collection("users").document(uid).get()
    if not snapshot.exists:
        return None
    return dict(snapshot.to_dict() or {}, uid=snapshot.id)


def normalized_role(value: Any) -> str:
    """Preserve explicitly assigned roles, including the project owner role."""
    return value if value in {"watcher", "admin", "owner"} else "watcher"


def ensure_user_profile(uid: str, email: str, display_name: str, provider: str) -> dict[str, Any]:
    """Create new accounts as watchers and never promote from client-supplied data."""
    from google.cloud import firestore

    reference = firestore_client().collection("users").document(uid)
    transaction = firestore_client().transaction()

    @firestore.transactional
    def create_or_refresh(transaction):
        snapshot = reference.get(transaction=transaction)
        existing = snapshot.to_dict() or {} if snapshot.exists else {}
        role = normalized_role(existing.get("role", "watcher"))
        profile = {
            "uid": uid,
            "email": email.strip().lower(),
            "display_name": display_name[:120],
            "provider": provider,
            "role": role,
            "active": existing.get("active", True) is True,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }
        if not snapshot.exists:
            profile["created_at"] = firestore.SERVER_TIMESTAMP
        transaction.set(reference, profile, merge=True)
        profile.pop("created_at", None)
        return {**existing, **profile, "uid": uid}

    return create_or_refresh(transaction)


def load_club_data() -> dict[str, Any]:
    if datastore_mode_enabled():
        try:
            club = datastore_get_club()
            for collection in ("players", "matches", "standings"):
                club[collection] = datastore_list_records(collection)
            return club
        except Exception as error:
            from werkzeug.exceptions import HTTPException

            if isinstance(error, HTTPException):
                raise
            logging.exception("Could not load club data from Datastore")
            abort(503, description="No se han podido cargar los datos del club.")

    if not firestore_enabled():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logging.exception("Could not read local club demo data")
            abort(500, description="No se han podido cargar los datos del club.")

    try:
        snapshot = firestore_client().collection("club").document("current").get()
        club = snapshot.to_dict() if snapshot.exists else None
        if not isinstance(club, dict):
            abort(503, description="Falta configurar el documento club/current en Firestore.")
        club = dict(club)
        for collection in ("players", "matches", "standings"):
            club[collection] = _collection_records(collection)
        return club
    except Exception as error:
        from werkzeug.exceptions import HTTPException

        if isinstance(error, HTTPException):
            raise
        logging.exception("Could not load club data from Firestore")
        abort(503, description="No se han podido cargar los datos del club.")


def create_record(collection: str, values: dict[str, Any]) -> str:
    record_id = str(uuid.uuid4())
    if datastore_mode_enabled():
        from datastore_store import create_record as datastore_create

        datastore_create(collection, record_id, values)
        return record_id
    firestore_client().collection(collection).document(record_id).set(values)
    return record_id


def get_record(collection: str, record_id: str) -> dict[str, Any] | None:
    if datastore_mode_enabled():
        from datastore_store import get_record as datastore_get_record

        return datastore_get_record(collection, record_id)
    snapshot = firestore_client().collection(collection).document(record_id).get()
    if not snapshot.exists:
        return None
    return dict(snapshot.to_dict() or {}, id=snapshot.id)


def update_record(collection: str, record_id: str, values: dict[str, Any]) -> None:
    if datastore_mode_enabled():
        datastore_update_record(collection, record_id, values)
        return
    reference = firestore_client().collection(collection).document(record_id)
    if not reference.get().exists:
        abort(404, description="No se encontró el registro solicitado.")
    reference.set(values, merge=True)


def set_player_active(player_id: str, active: bool, actor_uid: str) -> None:
    if datastore_mode_enabled():
        from datastore_store import set_player_active as datastore_set_player_active

        datastore_set_player_active(player_id, active, actor_uid)
        return

    from google.cloud import firestore

    reference = firestore_client().collection("players").document(player_id)
    snapshot = reference.get()
    if not snapshot.exists:
        abort(404, description="No se encontró el jugador.")
    values: dict[str, Any] = {
        "active": active,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    if active:
        values.update({"deleted_at": firestore.DELETE_FIELD, "deleted_by": firestore.DELETE_FIELD})
    else:
        values.update({"deleted_at": firestore.SERVER_TIMESTAMP, "deleted_by": actor_uid})
    reference.set(values, merge=True)


def delete_record(collection: str, record_id: str) -> None:
    if datastore_mode_enabled():
        datastore_delete_record(collection, record_id)
        return
    reference = firestore_client().collection(collection).document(record_id)
    if not reference.get().exists:
        abort(404, description="No se encontró el registro solicitado.")
    reference.delete()


def update_team(team_id: str, values: dict[str, str]) -> None:
    if datastore_mode_enabled():
        datastore_update_team(team_id, values)
        return
    reference = firestore_client().collection("club").document("current")
    from google.cloud import firestore

    transaction = firestore_client().transaction()

    @firestore.transactional
    def apply_update(transaction):
        snapshot = reference.get(transaction=transaction)
        if not snapshot.exists:
            abort(503, description="Falta configurar el documento club/current en Firestore.")
        club = snapshot.to_dict() or {}
        teams = club.get("teams", [])
        updated = False
        for index, team in enumerate(teams):
            if team.get("id") == team_id:
                teams[index] = {**team, **values}
                updated = True
                break
        if not updated:
            abort(404, description="No se encontró el equipo.")
        transaction.set(reference, {"teams": teams}, merge=True)

    apply_update(transaction)


def list_admins() -> list[dict[str, str]]:
    admins = []
    users = firestore_client().collection("users")
    for role in ("owner", "admin"):
        for snapshot in users.where("role", "==", role).stream():
            record = snapshot.to_dict() or {}
            if record.get("active", True) and record.get("email"):
                admins.append({"email": record["email"], "id": snapshot.id, "role": role})
    return sorted(admins, key=lambda item: item["email"].lower())


def add_admin(email: str) -> None:
    import firebase_admin.auth as firebase_auth
    from firebase_auth import firebase_app

    cleaned = email.strip().lower()
    try:
        firebase_user = firebase_auth.get_user_by_email(cleaned, app=firebase_app())
    except firebase_auth.UserNotFoundError:
        abort(400, description="Ese correo todavía no está registrado en Firebase Authentication. La persona debe entrar primero con Google o registrarse con correo y contraseña (y verificar su correo). Después podrás asignarle el rol admin.")
    providers = {provider.provider_id for provider in firebase_user.provider_data}
    if firebase_user.disabled:
        abort(400, description="La cuenta está desactivada en Firebase Authentication. Actívala antes de concederle permisos.")
    if not providers.intersection({"google.com", "password"}):
        abort(400, description="La cuenta debe tener Google o correo y contraseña como método de acceso.")
    if "google.com" not in providers and not firebase_user.email_verified:
        abort(400, description="La cuenta debe verificar su correo antes de recibir permisos de administración.")
    ensure_user_profile(
        uid=firebase_user.uid,
        email=firebase_user.email or cleaned,
        display_name=firebase_user.display_name or cleaned.split("@", 1)[0],
        provider="google.com" if "google.com" in providers else "password",
    )
    reference = firestore_client().collection("users").document(firebase_user.uid)
    current_profile = reference.get().to_dict() or {}
    if current_profile.get("role") != "owner":
        reference.set({"role": "admin", "active": True}, merge=True)


def remove_admin(user_id: str, current_uid: str, current_role: str) -> None:
    if user_id == current_uid:
        abort(400, description="No puedes retirar tu propio acceso de administrador.")
    reference = firestore_client().collection("users").document(user_id)
    snapshot = reference.get()
    if not snapshot.exists or (snapshot.to_dict() or {}).get("role") not in {"admin", "owner"}:
        abort(404, description="No se encontró el administrador.")
    target_role = (snapshot.to_dict() or {}).get("role")
    if target_role == "owner" and current_role != "owner":
        abort(403, description="Solo un owner puede cambiar el rol de otro owner.")
    if target_role == "owner" and user_id != current_uid:
        abort(400, description="No se puede retirar a otro owner desde este panel.")
    reference.set({"role": "watcher"}, merge=True)
