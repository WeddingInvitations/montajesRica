"""Inicializa los datos públicos del club y los equipos en Firestore."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="ID del proyecto Google Cloud.")
    parser.add_argument("--force", action="store_true", help="Reemplaza club/current si ya existe.")
    parser.add_argument("--gcloud-auth", action="store_true", help="Usa la cuenta activa de gcloud auth login en lugar de ADC.")
    args = parser.parse_args()

    club_path = PROJECT_DIR / "data" / "club.json"
    club = json.loads(club_path.read_text(encoding="utf-8"))
    os.environ["GOOGLE_CLOUD_PROJECT"] = args.project
    from club_store import firestore_client

    if args.gcloud_auth:
        from scripts.gcloud_credentials import credentials_from_gcloud

        # Use a separate client for this one-shot initialization; the token is not persisted.
        from google.cloud import firestore

        client = firestore.Client(project=args.project, credentials=credentials_from_gcloud())
    else:
        client = firestore_client()
    document = client.collection("club").document("current")
    if document.get().exists and not args.force:
        parser.error("club/current ya existe; revisa sus datos o confirma su reemplazo con --force.")
    document.set({"club_name": club["club_name"], "season": club["season"], "teams": club["teams"], "standings": []})
    print("Datos iniciales del club y sus tres equipos guardados en Firestore Native.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
