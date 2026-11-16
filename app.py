"""Portal de equipos de pádel Montajes Rica."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from flask import Flask, abort, jsonify, render_template, send_from_directory

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "data" / "club.json"

app = Flask(__name__)
app.config["JSON_AS_ASCII"] = False


def load_club_data() -> dict[str, Any]:
    """Load demo data locally; optionally read the club document from Firestore."""
    if os.getenv("USE_FIRESTORE", "false").lower() == "true":
        try:
            from google.cloud import firestore

            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCLOUD_PROJECT")
            client = firestore.Client(project=project_id)
            document = client.collection("club").document("current").get()
            if not document.exists:
                logging.warning("Firestore document club/current does not exist; using demo data")
            else:
                data = document.to_dict()
                if isinstance(data, dict):
                    return data
        except Exception:
            logging.exception("Could not load club/current from Firestore")
            if os.getenv("APP_ENV", "development") == "production":
                abort(503, description="No se han podido cargar los datos del club.")

    try:
        return json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logging.exception("Could not read local club data")
        abort(500, description="No se han podido cargar los datos del club.")


@app.get("/")
def home():
    club = load_club_data()
    return render_template("index.html", club=club)


@app.get("/healthz")
def health():
    return jsonify(status="ok"), 200


@app.get("/logoMontajes.jpeg")
def club_logo():
    return send_from_directory(BASE_DIR, "logoMontajes.jpeg", max_age=86400)


@app.errorhandler(503)
def service_unavailable(error):
    return render_template("error.html", message=error.description), 503


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "8080")), debug=True)
