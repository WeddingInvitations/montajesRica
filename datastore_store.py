"""Persistencia para la base existente de Firestore en Datastore mode."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any

from flask import abort
from google.cloud import datastore

KIND_BY_COLLECTION = {
    "players": "Player",
    "matches": "Match",
    "standings": "Standing",
    "admins": "Admin",
}


@lru_cache(maxsize=1)
def datastore_client() -> datastore.Client:
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
    return datastore.Client(project=project_id)


def _entity_id(key: datastore.Key) -> str:
    return str(key.name if key.name is not None else key.id)


def _decode_entity(entity: datastore.Entity) -> dict[str, Any]:
    record = dict(entity)
    record["id"] = _entity_id(entity.key)
    if "teams_json" in record:
        try:
            record["teams"] = json.loads(record.pop("teams_json"))
        except (TypeError, json.JSONDecodeError):
            record["teams"] = []
    if "pairings_json" in record:
        try:
            record["pairings"] = json.loads(record.pop("pairings_json"))
        except (TypeError, json.JSONDecodeError):
            record["pairings"] = []
    return record


def _encode_values(values: dict[str, Any]) -> dict[str, Any]:
    clean = dict(values)
    if "pairings" in clean:
        clean["pairings_json"] = json.dumps(clean.pop("pairings"), ensure_ascii=False)
    return clean


def get_club() -> dict[str, Any]:
    entity = datastore_client().get(datastore_client().key("Club", "current"))
    if entity is None:
        abort(503, description="Falta configurar la entidad Club/current en Datastore.")
    record = _decode_entity(entity)
    return {key: value for key, value in record.items() if key != "id"}


def list_records(collection: str) -> list[dict[str, Any]]:
    kind = KIND_BY_COLLECTION[collection]
    query = datastore_client().query(kind=kind)
    return [_decode_entity(entity) for entity in query.fetch()]


def create_record(collection: str, record_id: str, values: dict[str, Any]) -> None:
    client = datastore_client()
    entity = datastore.Entity(key=client.key(KIND_BY_COLLECTION[collection], record_id))
    entity.update(_encode_values(values))
    client.put(entity)


def update_record(collection: str, record_id: str, values: dict[str, Any]) -> None:
    client = datastore_client()
    key = client.key(KIND_BY_COLLECTION[collection], record_id)
    entity = client.get(key)
    if entity is None:
        abort(404, description="No se encontró el registro solicitado.")
    entity.update(_encode_values(values))
    client.put(entity)


def delete_record(collection: str, record_id: str) -> None:
    client = datastore_client()
    key = client.key(KIND_BY_COLLECTION[collection], record_id)
    if client.get(key) is None:
        abort(404, description="No se encontró el registro solicitado.")
    client.delete(key)


def update_team(team_id: str, values: dict[str, str]) -> None:
    client = datastore_client()
    key = client.key("Club", "current")
    with client.transaction() as transaction:
        entity = transaction.get(key)
        if entity is None:
            abort(503, description="Falta configurar la entidad Club/current en Datastore.")
        try:
            teams = json.loads(entity.get("teams_json", "[]"))
        except (TypeError, json.JSONDecodeError):
            teams = []
        for index, team in enumerate(teams):
            if team.get("id") == team_id:
                teams[index] = {**team, **values}
                entity["teams_json"] = json.dumps(teams, ensure_ascii=False)
                transaction.put(entity)
                return
        abort(404, description="No se encontró el equipo.")


def is_admin(email_hash: str) -> bool:
    entity = datastore_client().get(datastore_client().key("Admin", email_hash))
    return bool(entity and entity.get("active", True) is True)


def list_admins() -> list[dict[str, str]]:
    records = list_records("admins")
    return sorted(
        [{"email": record["email"], "id": record["id"]} for record in records if record.get("active", True) and record.get("email")],
        key=lambda item: item["email"].lower(),
    )


def add_admin(email_hash: str, email: str) -> None:
    create_record("admins", email_hash, {"email": email, "active": True})


def remove_admin(admin_id: str, current_email_hash: str) -> None:
    if admin_id == current_email_hash:
        abort(400, description="No puedes retirar tu propio acceso de administrador.")
    delete_record("admins", admin_id)


def initialize_club(club: dict[str, Any], force: bool = False) -> None:
    client = datastore_client()
    key = client.key("Club", "current")
    existing = client.get(key)
    if existing is not None and not force:
        raise ValueError("Club/current ya existe; revisa sus datos o confirma su reemplazo con --force.")
    entity = datastore.Entity(key=key)
    entity.update({
        "club_name": club["club_name"],
        "season": club["season"],
        "teams_json": json.dumps(club["teams"], ensure_ascii=False),
    })
    client.put(entity)


def initialize_admin(email: str, email_hash: str) -> None:
    add_admin(email_hash, email)
