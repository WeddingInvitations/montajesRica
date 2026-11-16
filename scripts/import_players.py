"""Importa listadoJugadores.xlsx a Firestore; por defecto solo valida y cuenta."""

from __future__ import annotations

import argparse
import os
import uuid
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

TEAM_SHEETS = {
    "Masc 500": "equipo-1",
    "Masc Future": "equipo-2",
    "Fem": "equipo-3",
}
POSITION_MAP = {"drive": "Drive", "revés": "Revés", "reves": "Revés"}
PLAYER_NAMESPACE = uuid.UUID("3f30f03f-3f21-4973-8db2-20df819dc2b1")
PROJECT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_WORKBOOK = PROJECT_DIR / "listadoJugadores.xlsx"


def parse_workbook(path: str | Path) -> list[dict[str, str]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        missing_sheets = set(TEAM_SHEETS) - set(workbook.sheetnames)
        if missing_sheets:
            raise ValueError("El Excel no contiene las tres hojas de equipos esperadas.")

        records: list[dict[str, str]] = []
        for sheet_name, team_id in TEAM_SHEETS.items():
            sheet = workbook[sheet_name]
            rows = sheet.iter_rows(values_only=True)
            headers = next(rows, ())
            normalized_headers = [str(value or "").strip().casefold() for value in headers]
            try:
                name_index = normalized_headers.index("jugador")
                side_index = normalized_headers.index("posición")
            except ValueError as exc:
                raise ValueError(f"La hoja {sheet_name} necesita las columnas Jugador y Posición.") from exc

            for row_number, row in enumerate(rows, start=2):
                name_value = row[name_index] if name_index < len(row) else None
                side_value = row[side_index] if side_index < len(row) else None
                if name_value is None or not str(name_value).strip():
                    if side_value is not None and str(side_value).strip():
                        raise ValueError(f"Hay una posición sin jugador en la fila {row_number} de {sheet_name}.")
                    continue
                if side_value is None or str(side_value).strip().casefold() not in POSITION_MAP:
                    raise ValueError(f"La posición de la fila {row_number} de {sheet_name} debe ser Drive o Revés.")
                records.append({
                    "name": str(name_value).strip(),
                    "team_id": team_id,
                    "handedness": POSITION_MAP[str(side_value).strip().casefold()],
                    "source_sheet": sheet_name,
                    "_row": str(row_number),
                })
        return records
    finally:
        workbook.close()


def stable_player_id(record: dict[str, str]) -> str:
    source_key = f"{record['team_id']}:{record['source_sheet']}:{record['_row']}:{record['name'].casefold()}"
    return str(uuid.uuid5(PLAYER_NAMESPACE, source_key))


def import_records(
    records: list[dict[str, str]],
    project: str,
    replace: bool = False,
    datastore_mode: bool = False,
    gcloud_auth: bool = False,
) -> tuple[int, int]:
    os.environ["GOOGLE_CLOUD_PROJECT"] = project
    credentials = None
    if gcloud_auth:
        from scripts.gcloud_credentials import credentials_from_gcloud

        credentials = credentials_from_gcloud()

    if datastore_mode:
        from google.cloud import datastore

        client = datastore.Client(project=project, credentials=credentials)
        keys = [client.key("Player", stable_player_id(record)) for record in records]
        existing_ids = {
            str(entity.key.name if entity.key.name is not None else entity.key.id)
            for entity in client.get_multi(keys)
            if entity is not None
        }
        to_write = []
        skipped = 0
        for record, key in zip(records, keys):
            record_id = str(key.name if key.name is not None else key.id)
            if record_id in existing_ids and not replace:
                skipped += 1
                continue
            entity = datastore.Entity(key=key)
            entity.update({key: value for key, value in record.items() if not key.startswith("_")})
            to_write.append(entity)
        for start in range(0, len(to_write), 450):
            client.put_multi(to_write[start : start + 450])
        return len(to_write), skipped

    from google.cloud import firestore

    db = firestore.Client(project=project, credentials=credentials)
    collection = db.collection("players")
    batch = db.batch()
    written = 0
    skipped = 0
    existing_snapshots = list(collection.stream())
    existing_ids = {snapshot.id for snapshot in existing_snapshots}
    existing_people = {
        (str(snapshot.to_dict().get("name", "")).strip().casefold(), snapshot.to_dict().get("team_id"))
        for snapshot in existing_snapshots
    }
    pending_people: set[tuple[str, str]] = set()
    for record in records:
        player_id = stable_player_id(record)
        person_key = (record["name"].strip().casefold(), record["team_id"])
        if not replace and (player_id in existing_ids or person_key in existing_people or person_key in pending_people):
            skipped += 1
            continue
        pending_people.add(person_key)
        reference = collection.document(player_id)
        data: dict[str, Any] = {key: value for key, value in record.items() if not key.startswith("_")}
        batch.set(reference, data)
        written += 1
        if written % 450 == 0:
            batch.commit()
            batch = db.batch()
    if written % 450:
        batch.commit()
    return written, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_WORKBOOK, help="Ruta del Excel local (ignorado por Git).")
    parser.add_argument("--project", help="ID del proyecto Google Cloud; por defecto usa ADC.")
    parser.add_argument("--datastore-mode", action="store_true", help="Importa como entidades de la base Datastore mode existente.")
    parser.add_argument("--gcloud-auth", action="store_true", help="Usa la cuenta activa de gcloud auth login en lugar de ADC.")
    parser.add_argument("--apply", action="store_true", help="Confirma la escritura en Firestore. Sin esta opción solo valida.")
    parser.add_argument("--replace", action="store_true", help="Sobrescribe las fichas importadas que ya existan; requiere --apply.")
    args = parser.parse_args()
    if args.replace and not args.apply:
        parser.error("--replace requiere --apply.")

    records = parse_workbook(args.file)
    counts = {team_id: sum(record["team_id"] == team_id for record in records) for team_id in TEAM_SHEETS.values()}
    print(f"Excel validado: {len(records)} fichas en {len(TEAM_SHEETS)} equipos.")
    print("Distribución por equipo: " + ", ".join(f"{team}: {count}" for team, count in counts.items()))
    if not args.apply:
        print("Modo de prueba: no se escribió nada. Revisa los datos y vuelve a ejecutar con --apply cuando Firestore esté configurado.")
        return 0

    project = args.project or os.getenv("GOOGLE_CLOUD_PROJECT")
    if not project:
        parser.error("Indica --project o configura GOOGLE_CLOUD_PROJECT.")
    written, skipped = import_records(
        records,
        project,
        replace=args.replace,
        datastore_mode=args.datastore_mode,
        gcloud_auth=args.gcloud_auth,
    )
    print(f"Importación completada: {written} creados/actualizados; {skipped} ya existentes omitidos.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
