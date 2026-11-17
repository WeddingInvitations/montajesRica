"""Importación operativa: validación por defecto, escritura solo con --apply."""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from club_store import replace_standings
from scripts.gcloud_credentials import credentials_from_gcloud
from standings_import import parse_standings_excel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, choices=["montajesrica"])
    parser.add_argument("--file", type=Path, default=Path(__file__).resolve().parents[1] / "ClasificacionesMontajes.xlsx")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--account", help="Cuenta de gcloud autorizada, sin cambiar la configuración global")
    args = parser.parse_args()
    db = firestore.Client(project=args.project, credentials=credentials_from_gcloud(account=args.account))
    snapshot = db.collection("club").document("current").get()
    if not snapshot.exists:
        parser.error("Falta club/current en el proyecto seleccionado.")
    with args.file.open("rb") as source:
        rows = parse_standings_excel(source, snapshot.to_dict().get("teams", []))
    for sheet in dict.fromkeys(row["source_sheet"] for row in rows):
        print(f"{sheet}: {sum(row['source_sheet'] == sheet for row in rows)} posiciones validadas.")
    print("Las hojas vacías no se modifican. El Excel no se almacena.")
    if args.apply:
        # El token gcloud usado por Firestore pertenece al operador; no basta con
        # disponer de IAM: exigimos también su rol admin/owner en users/{uid}.
        command = ["gcloud", "config", "get-value", "account"]
        if os.name == "nt":
            command = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "gcloud config get-value account"]
        email = (args.account or subprocess.run(command, capture_output=True, text=True, check=True, timeout=30).stdout.strip()).lower()
        profiles = db.collection("users").where(filter=FieldFilter("email", "==", email)).stream()
        if not any((profile.to_dict() or {}).get("role") in {"admin", "owner"} and (profile.to_dict() or {}).get("active", True) is True for profile in profiles):
            parser.error("La cuenta activa de gcloud no tiene rol admin/owner activo en Firestore.")
        print(f"Importadas {replace_standings(rows, db=db)} posiciones en {args.project}.")
    else:
        print("Solo validación: no se ha escrito nada. Usa --apply para importar.")


if __name__ == "__main__":
    main()