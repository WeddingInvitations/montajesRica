from pathlib import Path

from flask.cli import load_dotenv


DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / ".flaskenv"


def test_local_defaults_provide_firebase_project_in_a_new_terminal(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for key in ("APP_ENV", "GOOGLE_CLOUD_PROJECT", "FIREBASE_PROJECT_ID", "USE_FIRESTORE", "USE_DATASTORE"):
        monkeypatch.delenv(key, raising=False)

    assert load_dotenv(path=DEFAULT_CONFIG, load_defaults=False)

    import os

    assert os.environ["FIREBASE_PROJECT_ID"] == "montajesrica"
    assert os.environ["GOOGLE_CLOUD_PROJECT"] == "montajesrica"
    assert os.environ["APP_ENV"] == "development"
    assert os.environ["USE_FIRESTORE"] == "false"


def test_local_file_does_not_override_production_environment(monkeypatch, tmp_path):
    import os

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("FIREBASE_PROJECT_ID", "production-project")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "production-project")
    monkeypatch.setenv("USE_FIRESTORE", "true")
    monkeypatch.delenv("USE_DATASTORE", raising=False)

    load_dotenv(path=DEFAULT_CONFIG, load_defaults=False)

    assert os.environ["APP_ENV"] == "production"
    assert os.environ["FIREBASE_PROJECT_ID"] == "production-project"
    assert os.environ["GOOGLE_CLOUD_PROJECT"] == "production-project"
    assert os.environ["USE_FIRESTORE"] == "true"
