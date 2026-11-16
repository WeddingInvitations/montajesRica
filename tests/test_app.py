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
    assert "divisiones y temporada por confirmar" in page.lower()


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
    assert created == [("players", {"name": "Jugador de prueba", "team_id": "equipo-prueba", "handedness": "Drive"})]


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
