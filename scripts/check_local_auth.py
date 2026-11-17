"""Diagnóstico de configuración y permisos locales sin escribir en la base de datos."""

from __future__ import annotations

import os


def main() -> int:
    import importlib.util
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    from flask.cli import load_dotenv

    load_dotenv()

    print("python-dotenv instalado:", bool(importlib.util.find_spec("dotenv")))
    for key in ("GOOGLE_CLOUD_PROJECT", "FIREBASE_PROJECT_ID", "USE_FIRESTORE"):
        print(f"{key}={os.getenv(key, '(no configurado)')}")

    from firebase_auth import firebase_app

    ok = True
    try:
        application = firebase_app()
        print("Proyecto Firebase Admin:", application.project_id)
    except Exception as error:
        print("Inicialización Firebase:", type(error).__name__, str(error))
        ok = False

    try:
        credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or "montajesrica"
        print("Proyecto de cuota ADC:", getattr(credentials, "quota_project_id", None))
        permissions = [
            "firebaseauth.users.get", "firebaseauth.users.createSession",
            "datastore.entities.get", "datastore.entities.list",
            "datastore.entities.create", "datastore.entities.update", "serviceusage.services.use",
        ]
        with AuthorizedSession(credentials) as session:
            response = session.post(
                f"https://cloudresourcemanager.googleapis.com/v1/projects/{project_id}:testIamPermissions",
                json={"permissions": permissions}, timeout=20,
            )
            print("Consulta IAM HTTP:", response.status_code)
            granted = set(response.json().get("permissions", []))
            for permission in permissions:
                print(f"  {permission}: {'OK' if permission in granted else 'NO'}")
            ok = ok and response.ok and granted == set(permissions)
    except Exception as error:
        print("Comprobación ADC:", type(error).__name__)
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
