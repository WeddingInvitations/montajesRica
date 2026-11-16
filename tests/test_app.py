from app import app, load_club_data


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
