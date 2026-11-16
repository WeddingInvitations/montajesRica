"""Concede al primer usuario el rol de administrador en Firestore."""

from __future__ import annotations

import argparse
import os
import re


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="ID del proyecto Google Cloud.")
    parser.add_argument("--gcloud-auth", action="store_true", help="Usa la cuenta activa de gcloud auth login en lugar de ADC.")
    args = parser.parse_args()

    email = input("Correo de Google del primer administrador: ").strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        parser.error("El correo no tiene un formato válido.")

    os.environ["GOOGLE_CLOUD_PROJECT"] = args.project
    from security import admin_document_id
    from google.cloud import firestore

    credentials = None
    if args.gcloud_auth:
        from scripts.gcloud_credentials import credentials_from_gcloud

        credentials = credentials_from_gcloud()
    client = firestore.Client(project=args.project, credentials=credentials)
    client.collection("admins").document(admin_document_id(email)).set({"email": email, "active": True}, merge=True)
    print("Administrador inicial registrado en Firestore Native.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
