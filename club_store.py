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
    add_admin as datastore_add_admin,
    delete_record as datastore_delete_record,
    get_club as datastore_get_club,
    list_admins as datastore_list_admins,
    list_records as datastore_list_records,
    remove_admin as datastore_remove_admin,
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


def update_record(collection: str, record_id: str, values: dict[str, Any]) -> None:
    if datastore_mode_enabled():
        datastore_update_record(collection, record_id, values)
        return
    reference = firestore_client().collection(collection).document(record_id)
    if not reference.get().exists:
        abort(404, description="No se encontró el registro solicitado.")
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
    if datastore_mode_enabled():
        return datastore_list_admins()
    admins = []
    for snapshot in firestore_client().collection("admins").stream():
        record = snapshot.to_dict() or {}
        if record.get("active", True) and record.get("email"):
            admins.append({"email": record["email"], "id": snapshot.id})
    return sorted(admins, key=lambda item: item["email"].lower())


def add_admin(email: str) -> None:
    from security import admin_document_id, normalized_email

    cleaned = normalized_email(email)
    if datastore_mode_enabled():
        datastore_add_admin(admin_document_id(cleaned), cleaned)
        return
    firestore_client().collection("admins").document(admin_document_id(cleaned)).set(
        {"email": cleaned, "active": True}, merge=True
    )


def remove_admin(admin_id: str, current_email: str) -> None:
    from security import admin_document_id

    if datastore_mode_enabled():
        datastore_remove_admin(admin_id, admin_document_id(current_email))
        return
    admins = firestore_client().collection("admins")
    current_id = admin_document_id(current_email)
    if admin_id == current_id:
        abort(400, description="No puedes retirar tu propio acceso de administrador.")
    reference = admins.document(admin_id)
    if not reference.get().exists:
        abort(404, description="No se encontró el administrador.")
    reference.delete()
