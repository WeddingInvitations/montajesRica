from app import app, load_club_data
from security import admin_document_id


def test_home_displays_three_teams_after_authentication(monkeypatch):
    from flask import g

    monkeypatch.setattr("app.authenticate_request", lambda: setattr(g, "current_user", {
        "uid": "firebase-watcher-uid", "email": "watcher@example.com", "display_name": "Watcher", "role": "watcher", "active": True
    }))
    monkeypatch.setattr("app.load_club_data", lambda: load_club_data())
    response = app.test_client().get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Montajes Rica" in page
    assert "Masculino 500" in page
    assert "Masculino Future" in page
    assert "Femenino" in page
    assert 'data-view="ranking"' in page
    assert 'id="view-ranking"' in page
    assert 'id="ranking-team-filter"' in page
    assert 'Clasificación general' in page
    assert 'Wilson' in page
    visible_html = page.split('<script id="club-data"')[0]
    assert "por configurar" not in visible_html.lower()
    assert "divisiones y temporada por confirmar" not in visible_html.lower()
    assert 'class="demo-disclaimer"' not in visible_html
    assert 'class="club-note"' not in visible_html
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin-allow-popups"


def test_health_check():
    response = app.test_client().get("/healthz")
    assert response.status_code == 200
    assert response.json == {"status": "ok"}


def test_club_logo_is_served():
    response = app.test_client().get("/logoMontajes.jpeg")
    assert response.status_code == 200
    assert response.mimetype == "image/jpeg"


def test_demo_data_has_no_fabricated_players_or_matches():
    data = load_club_data()
    assert data["players"] == []
    assert data["matches"] == []
    assert data["standings"] == []


def test_admin_panel_requires_an_authorized_identity(monkeypatch):
    monkeypatch.setitem(app.config, "TESTING", True)
    response = app.test_client().get("/admin")
    assert response.status_code == 401


def test_admin_document_id_is_normalized_and_opaque():
    assert admin_document_id(" CLUB@example.com ") == admin_document_id("club@example.com")
    assert "@" not in admin_document_id("club@example.com")


def test_owner_role_is_preserved_instead_of_reset_to_watcher():
    from club_store import normalized_role

    assert normalized_role("owner") == "owner"
    assert normalized_role("admin") == "admin"
    assert normalized_role("watcher") == "watcher"
    assert normalized_role("unknown-role") == "watcher"


def test_owner_can_use_admin_routes():
    from flask import g
    from security import require_admin

    with app.test_request_context("/"):
        g.current_user = {"uid": "owner-uid", "role": "owner", "active": True}
        require_admin()


def test_admin_dashboard_renders_for_an_authorized_firebase_admin(monkeypatch):
    import admin_routes
    from flask import g

    monkeypatch.setenv("USE_FIRESTORE", "true")
    monkeypatch.setattr("app.authenticate_request", lambda: setattr(g, "current_user", {
        "uid": "firebase-admin-uid", "email": "admin@example.com", "display_name": "Admin", "role": "admin", "active": True
    }))
    monkeypatch.setattr(admin_routes, "storage_enabled", lambda: True)
    sample_club = {
        "club_name": "Montajes Rica",
        "season": "Temporada de prueba",
        "teams": [{"id": "equipo-prueba", "name": "Equipo de prueba", "division": "División de prueba"}],
        "players": [],
        "matches": [],
        "standings": [],
    }
    monkeypatch.setattr(admin_routes, "load_club_data", lambda: sample_club)
    monkeypatch.setattr(admin_routes, "list_admins", lambda: [{"email": "admin@example.com", "id": "opaque-id"}])
    monkeypatch.setitem(app.config, "TESTING", True)

    response = app.test_client().get("/admin")

    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Panel de administración" in page
    assert "Añadir jugador" in page
    assert "Parejas y marcadores por sets" in page
    assert 'class="admin-player-stats"' not in page
    assert 'role="tablist"' in page
    assert 'id="equipos" role="tabpanel" aria-labelledby="tab-equipos"' in page
    assert 'id="jugadores" role="tabpanel" aria-labelledby="tab-jugadores" hidden' in page
    assert 'data-admin-tab="partidos"' in page
    assert 'enctype="multipart/form-data"' in page
    assert 'action="/admin/standings/import"' in page
    assert 'name="standings_file"' in page


def test_match_pairing_accepts_two_team_players_and_set_scores():
    from admin_routes import _parse_pairings

    players = [
        {"id": "p1", "name": "Jugador Uno", "team_id": "equipo-1"},
        {"id": "p2", "name": "Jugador Dos", "team_id": "equipo-1"},
        {"id": "p3", "name": "Jugador Tres", "team_id": "equipo-2"},
    ]
    with app.test_request_context("/", method="POST", data={
        "pairing_player_1_1": "p1",
        "pairing_player_1_2": "p2",
        "pairing_opponent_1": "Rival",
        "pairing_sets_1": "6-4, 7-5",
    }):
        result = _parse_pairings(players, "equipo-1")
    assert result == [{
        "player_ids": ["p1", "p2"],
        "player_names": ["Jugador Uno", "Jugador Dos"],
        "opponent_pair": "Rival",
        "sets": [{"home": 6, "away": 4}, {"home": 7, "away": 5}],
    }]


def test_played_match_can_be_created_and_edited_without_opponent_pair_names():
    from admin_routes import _match_values

    club = {
        "teams": [{"id": "equipo-1"}],
        "players": [
            {"id": "p1", "name": "Jugador Uno", "team_id": "equipo-1"},
            {"id": "p2", "name": "Jugador Dos", "team_id": "equipo-1"},
        ],
    }
    data = {
        "team_id": "equipo-1", "opponent": "Equipo de prueba",
        "division": "División de prueba", "date": "2026-11-17",
        "venue": "Pista de prueba", "status": "played",
        "pairing_player_1_1": "p1", "pairing_player_1_2": "p2",
        "pairing_sets_1": "6-4, 7-5",
    }
    for existing in (None, {"pairings": [{
        "player_ids": ["p1", "p2"], "opponent_pair": "Nombre anterior",
    }]}):
        for opponent_fields in ({}, {"pairing_opponent_1": ""}, {"pairing_opponent_1": "   "}):
            with app.test_request_context("/", method="POST", data={**data, **opponent_fields}):
                result = _match_values(club, existing)
            assert result["pairings"][0]["opponent_pair"] == ""
            assert result["pairings"][0]["sets"] == [{"home": 6, "away": 4}, {"home": 7, "away": 5}]


def test_archived_player_can_be_kept_only_in_its_existing_match():
    from admin_routes import _parse_pairings

    players = [
        {"id": "archived-1", "name": "Jugador histórico", "team_id": "equipo-1", "active": False},
        {"id": "active-2", "name": "Jugador activo", "team_id": "equipo-1", "active": True},
    ]
    form_data = {
        "pairing_player_1_1": "archived-1",
        "pairing_player_1_2": "active-2",
    }
    with app.test_request_context("/", method="POST", data=form_data):
        kept = _parse_pairings(players, "equipo-1", existing_pairings=[{
            "player_ids": ["archived-1", "active-2"],
            "player_names": ["Nombre histórico", "Jugador activo"],
        }])
    assert kept[0]["player_names"] == ["Nombre histórico", "Jugador activo"]

    with app.test_request_context("/", method="POST", data=form_data):
        from werkzeug.exceptions import BadRequest

        try:
            _parse_pairings(players, "equipo-1")
        except BadRequest:
            pass
        else:
            raise AssertionError("An archived player must not be added to a new match")


def test_future_call_up_requires_explicit_exception_and_excludes_other_teams():
    import pytest
    from werkzeug.exceptions import BadRequest
    from admin_routes import _parse_pairings

    players = [
        {"id": "first", "name": "Jugador Uno", "team_id": "equipo-1"},
        {"id": "future", "name": "Jugador Dos", "team_id": "equipo-2"},
        {"id": "other", "name": "Jugador Tres", "team_id": "equipo-3"},
    ]
    data = {"pairing_player_1_1": "first", "pairing_player_1_2": "future"}
    with app.test_request_context("/", method="POST", data=data):
        with pytest.raises(BadRequest):
            _parse_pairings(players, "equipo-1")
        result = _parse_pairings(players, "equipo-1", allow_future_players=True)
        assert result[0]["player_ids"] == ["first", "future"]
    data["pairing_player_1_2"] = "other"
    with app.test_request_context("/", method="POST", data=data):
        with pytest.raises(BadRequest):
            _parse_pairings(players, "equipo-1", allow_future_players=True)


def test_remove_player_archives_without_deleting(monkeypatch):
    import admin_routes
    from flask import g

    monkeypatch.setattr("app.authenticate_request", lambda: setattr(g, "current_user", {
        "uid": "firebase-admin-uid", "email": "admin@example.com", "display_name": "Admin", "role": "owner", "active": True
    }))
    monkeypatch.setattr(admin_routes, "storage_enabled", lambda: True)
    archived = []
    monkeypatch.setattr(admin_routes, "set_player_active", lambda player_id, active, actor_uid: archived.append((player_id, active, actor_uid)))
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", False)

    response = app.test_client().post("/admin/players/player-1/delete")

    assert response.status_code == 302
    assert archived == [("player-1", False, "firebase-admin-uid")]


def test_admin_can_create_player_only_after_firebase_role_check(monkeypatch):
    import admin_routes
    from flask import g

    monkeypatch.setenv("USE_FIRESTORE", "true")
    monkeypatch.setattr("app.authenticate_request", lambda: setattr(g, "current_user", {
        "uid": "firebase-admin-uid", "email": "admin@example.com", "display_name": "Admin", "role": "admin", "active": True
    }))
    monkeypatch.setattr(admin_routes, "storage_enabled", lambda: True)
    monkeypatch.setattr(admin_routes, "load_club_data", lambda: {
        "teams": [{"id": "equipo-prueba", "name": "Equipo de prueba"}],
        "players": [],
    })
    created = []
    monkeypatch.setattr(admin_routes, "create_record", lambda collection, values: created.append((collection, values)))
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", False)

    response = app.test_client().post(
        "/admin/players",
        data={"name": "Jugador de prueba", "team_id": "equipo-prueba", "handedness": "Drive"},
    )

    assert response.status_code == 302
    assert created == [("players", {"name": "Jugador de prueba", "team_id": "equipo-prueba", "handedness": "Drive", "active": True})]


def test_anonymous_home_does_not_load_or_expose_private_club_data(monkeypatch):
    monkeypatch.setattr("app.load_club_data", lambda: (_ for _ in ()).throw(AssertionError("private data must not load")))
    response = app.test_client().get("/")
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "Continuar con Google" in page
    assert 'id="email-auth-form"' in page
    assert "Crear una cuenta" in page
    assert 'id="google-password-setup"' in page
    assert 'id="club-data" type="application/json">null' in page


def test_archived_player_is_hidden_from_roster_but_kept_in_match_history(monkeypatch):
    import json
    import re
    from flask import g

    club = {
        "club_name": "Montajes Rica", "season": "Temporada de prueba",
        "teams": [{"id": "equipo-1", "name": "Masculino 500", "division": "División", "season": "Prueba"}],
        "players": [
            {"id": "active-player", "name": "Jugador activo", "team_id": "equipo-1", "handedness": "Drive", "active": True},
            {"id": "archived-player", "name": "Jugador archivado", "team_id": "equipo-1", "handedness": "Revés", "active": False},
        ],
        "matches": [{"id": "match-1", "team_id": "equipo-1", "status": "played", "score": "1-0", "pairings": [{
            "player_ids": ["archived-player"], "player_names": ["Jugador archivado"], "sets": [{"home": 6, "away": 4}],
        }]}],
        "standings": [],
    }
    monkeypatch.setattr("app.authenticate_request", lambda: setattr(g, "current_user", {
        "uid": "watcher", "email": "watcher@example.com", "display_name": "Watcher", "role": "watcher", "active": True
    }))
    monkeypatch.setattr("app.load_club_data", lambda: club)

    response = app.test_client().get("/")
    page = response.get_data(as_text=True)
    serialized = re.search(r'<script id="club-data" type="application/json">(.*?)</script>', page).group(1)
    rendered_club = json.loads(serialized)

    assert [player["id"] for player in rendered_club["players"]] == ["active-player"]
    assert rendered_club["player_stats"]["archived-player"]["played"] == 1
    assert rendered_club["matches"][0]["pairings"][0]["player_names"] == ["Jugador archivado"]


def test_firebase_identity_profile_defaults_to_watcher(monkeypatch):
    import security
    import firebase_auth

    monkeypatch.setattr(firebase_auth, "verify_session_cookie", lambda cookie: {
        "uid": "watcher-uid",
        "email": "watcher@example.com",
        "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    })
    monkeypatch.setattr("club_store.ensure_user_profile", lambda **kwargs: {
        "uid": kwargs["uid"], "email": kwargs["email"], "role": "watcher", "active": True
    })
    with app.test_request_context("/", headers={"Cookie": "montajesrica_session=firebase-session"}):
        security.authenticate_request()
        from flask import g

        assert g.current_user["role"] == "watcher"
        assert security.is_admin(g.current_user["uid"]) is False


def test_firebase_id_token_is_exchanged_for_http_only_session_cookie(monkeypatch):
    import re

    monkeypatch.setattr("app.verify_firebase_id_token", lambda token: {
        "uid": "new-watcher", "email": "watcher@example.com", "email_verified": True, "name": "Watcher",
        "firebase": {"sign_in_provider": "password"},
    })
    monkeypatch.setattr("app.create_session_cookie", lambda token: "signed-firebase-session")
    profile_provider = []

    def create_profile(**kwargs):
        profile_provider.append(kwargs["provider"])
        return {"uid": kwargs["uid"], "email": kwargs["email"], "role": "watcher", "active": True}

    monkeypatch.setattr("app.ensure_user_profile", create_profile)
    client = app.test_client()
    home = client.get("/")
    csrf_token = re.search(r'<meta name="csrf-token" content="([^"]+)"', home.get_data(as_text=True)).group(1)

    response = client.post(
        "/auth/session",
        json={"idToken": "firebase-id-token"},
        headers={"X-CSRFToken": csrf_token},
    )

    assert response.status_code == 200
    assert response.json == {"ok": True, "role": "watcher"}
    assert profile_provider[0] == "password"
    cookie = response.headers["Set-Cookie"]
    assert "montajesrica_session=signed-firebase-session" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_missing_firebase_permissions_returns_actionable_503(monkeypatch):
    import re
    from firebase_admin import auth as firebase_auth

    monkeypatch.setattr("app.verify_firebase_id_token", lambda token: (_ for _ in ()).throw(
        firebase_auth.InsufficientPermissionError("Permission denied", None, None)
    ))
    client = app.test_client()
    home = client.get("/")
    csrf_token = re.search(r'<meta name="csrf-token" content="([^"]+)"', home.get_data(as_text=True)).group(1)

    response = client.post("/auth/session", json={"idToken": "valid-shaped-token"}, headers={"X-CSRFToken": csrf_token})

    assert response.status_code == 503
    assert "ADC" in response.json["description"]


def test_invalid_firebase_token_returns_401(monkeypatch):
    import re
    from firebase_admin import auth as firebase_auth

    monkeypatch.setattr("app.verify_firebase_id_token", lambda token: (_ for _ in ()).throw(
        firebase_auth.InvalidIdTokenError("Invalid Firebase ID token")
    ))
    client = app.test_client()
    home = client.get("/")
    csrf_token = re.search(r'<meta name="csrf-token" content="([^"]+)"', home.get_data(as_text=True)).group(1)

    response = client.post("/auth/session", json={"idToken": "invalid-token"}, headers={"X-CSRFToken": csrf_token})

    assert response.status_code == 401
    assert "sesión de Google" in response.json["description"]


def test_watcher_cannot_open_admin_panel(monkeypatch):
    import firebase_auth

    monkeypatch.setattr(firebase_auth, "verify_session_cookie", lambda cookie: {
        "uid": "watcher-uid", "email": "watcher@example.com", "email_verified": True,
        "firebase": {"sign_in_provider": "google.com"},
    })
    monkeypatch.setattr("club_store.ensure_user_profile", lambda **kwargs: {
        "uid": kwargs["uid"], "email": kwargs["email"], "role": "watcher", "active": True
    })

    client = app.test_client()
    client.set_cookie("montajesrica_session", "valid-session")
    response = client.get("/admin")

    assert response.status_code == 403
