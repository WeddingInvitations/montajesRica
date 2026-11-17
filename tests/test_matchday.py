import pytest
from flask import g, render_template
from werkzeug.exceptions import BadRequest

from app import app
from admin_routes import _match_values

CLUB = {"teams": [{"id": "equipo-1", "name": "Equipo de prueba"}], "players": []}
FORM = {"team_id": "equipo-1", "opponent": "Rival prueba", "division": "División prueba",
        "date": "2026-11-17", "venue": "Pista prueba", "status": "scheduled"}


@pytest.mark.parametrize("value,expected", [("1", 1), ("12", 12), ("999", 999), ("", None)])
def test_matchday_is_validated_and_stored_as_number(value, expected):
    with app.test_request_context("/", method="POST", data={**FORM, "jornada": value}):
        assert _match_values(CLUB)["jornada"] == expected


@pytest.mark.parametrize("value", ["0", "-1", "1000", "1.5", "texto", "<script>"])
def test_bad_matchday_is_rejected(value):
    with app.test_request_context("/", method="POST", data={**FORM, "jornada": value}):
        with pytest.raises(BadRequest, match="jornada"):
            _match_values(CLUB)


def test_existing_matchday_is_preserved_when_field_is_absent_and_can_be_cleared():
    with app.test_request_context("/", method="POST", data=FORM):
        assert _match_values(CLUB, {"jornada": 5})["jornada"] == 5
    with app.test_request_context("/", method="POST", data={**FORM, "jornada": ""}):
        assert _match_values(CLUB, {"jornada": 5})["jornada"] is None


def test_admin_create_and_edit_persist_matchday_for_old_matches(monkeypatch):
    monkeypatch.setattr("app.authenticate_request", lambda: setattr(g, "current_user", {"uid": "admin-test", "role": "admin", "active": True}))
    monkeypatch.setattr("admin_routes.storage_enabled", lambda: True)
    monkeypatch.setattr("admin_routes.load_club_data", lambda: CLUB)
    monkeypatch.setattr("club_store.get_record", lambda *args: {**FORM, "pairings": []})
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", False)
    writes = []
    monkeypatch.setattr("admin_routes.create_record", lambda collection, values: writes.append(values))
    monkeypatch.setattr("admin_routes.update_record", lambda collection, key, values: writes.append(values))
    client = app.test_client()
    for path in ["/admin/matches", "/admin/matches/old-match"]:
        response = client.post(path, data={**FORM, "jornada": "4"})
        assert response.status_code == 302
        assert writes[-1]["jornada"] == 4
    with app.test_request_context("/"):
        html = render_template("partials/match_fields.html", club=CLUB, editing={"jornada": 4})
    assert 'name="jornada"' in html
    assert 'value="4"' in html