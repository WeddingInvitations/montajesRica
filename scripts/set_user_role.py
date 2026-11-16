"""Asigna un rol explícito a una cuenta ya registrada en Firebase Authentication."""

from __future__ import annotations

import argparse
import os
import re


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="montajesrica", help="ID del proyecto Firebase/GCP.")
    parser.add_argument("--role", choices=("watcher", "admin"), required=True)
    parser.add_argument("--gcloud-auth", action="store_true", help="Usa la cuenta activa de gcloud auth login.")
    args = parser.parse_args()

    email = input("Correo de Google de la cuenta ya registrada en Firebase Auth: ").strip().lower()
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        parser.error("El correo no tiene un formato válido.")

    credentials = None
    if args.gcloud_auth:
        from scripts.gcloud_credentials import credentials_from_gcloud

        credentials = credentials_from_gcloud()

    import firebase_admin
    from firebase_admin import auth
    from google.cloud import firestore

    try:
        firebase_app = firebase_admin.get_app()
    except ValueError:
        firebase_app = firebase_admin.initialize_app(
            credential=credentials,
            options={"projectId": args.project},
        )

    try:
        user = auth.get_user_by_email(email, app=firebase_app)
    except auth.UserNotFoundError:
        parser.error("La cuenta aún no existe en Firebase Authentication. Haz que inicie sesión con Google primero.")

    if user.disabled:
        parser.error("La cuenta de Firebase Auth está desactivada.")
    providers = {item.provider_id for item in user.provider_data}
    if "google.com" not in providers:
        parser.error("La cuenta no tiene vinculado el proveedor Google.")

    client = firestore.Client(project=args.project, credentials=credentials)
    reference = client.collection("users").document(user.uid)
    existing = reference.get().to_dict() or {}
    reference.set({
        "uid": user.uid,
        "email": (user.email or email).lower(),
        "display_name": user.display_name or email.split("@", 1)[0],
        "provider": "google.com",
        "role": args.role,
        "active": existing.get("active", True),
        "updated_at": firestore.SERVER_TIMESTAMP,
        **({} if existing else {"created_at": firestore.SERVER_TIMESTAMP}),
    }, merge=True)
    print(f"Rol {args.role} asignado a la cuenta. No se imprimen datos de perfil.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
