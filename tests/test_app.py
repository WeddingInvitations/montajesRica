from app import app, load_club_data
from security import admin_document_id


def test_home_displays_three_configurable_teams():
    app.config["TESTING"] = True
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


def test_admin_dashboard_renders_for_an_authorized_iap_user(monkeypatch):
    import admin_routes
    import security

    monkeypatch.setenv("REQUIRE_IAP", "true")
    monkeypatch.setenv("IAP_AUDIENCE", "test-audience")
    monkeypatch.setenv("USE_FIRESTORE", "true")
    monkeypatch.setattr(security, "verify_iap_identity", lambda assertion, audience: {"email": "admin@example.com", "name": "Admin"})
    monkeypatch.setattr(security, "is_admin", lambda email: True)
    monkeypatch.setattr("app.is_admin", lambda email: True)
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

    response = app.test_client().get("/admin", headers={"X-Goog-IAP-JWT-Assertion": "verified-by-test"})

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


def test_admin_can_create_player_only_after_iap_authorization(monkeypatch):
    import admin_routes
    import security

    monkeypatch.setenv("REQUIRE_IAP", "true")
    monkeypatch.setenv("IAP_AUDIENCE", "test-audience")
    monkeypatch.setenv("USE_FIRESTORE", "true")
    monkeypatch.setattr(security, "verify_iap_identity", lambda assertion, audience: {"email": "admin@example.com", "name": "Admin"})
    monkeypatch.setattr(security, "is_admin", lambda email: True)
    monkeypatch.setattr("app.is_admin", lambda email: True)
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
        headers={"X-Goog-IAP-JWT-Assertion": "verified-by-test"},
        data={"name": "Jugador de prueba", "team_id": "equipo-prueba", "handedness": "Drive"},
    )

    assert response.status_code == 302
    assert created == [("players", {"name": "Jugador de prueba", "team_id": "equipo-prueba", "handedness": "Drive"})]
