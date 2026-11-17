from io import BytesIO

import pytest
from openpyxl import Workbook

from app import app
from standings_import import MAX_EXCEL_BYTES, parse_standings_excel

TEAMS = [{"id": f"equipo-{index}", "division": f"División de prueba {index}", "season": "Temporada de prueba"} for index in range(1, 4)]
HEADER = [None, None, "Puntos", "J", "G", "P", "A", "SG", "SP", "DS", "JG", "JP", "DJ"]
ROW = [1, "MONTAJES RICA PRUEBA", 20, 3, 2, 1, 0, 12, 8, 4, 90, 75, 15]


def excel(rows=None, future=None, header=None, fem=None):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Clasificación 500"
    sheet.append(HEADER if header is None else header)
    for row in [ROW] if rows is None else rows:
        sheet.append(row)
    second = workbook.create_sheet("Clasificación Future")
    if future:
        second.append(HEADER)
        for row in future:
            second.append(row)
    third = workbook.create_sheet("Clasificación Fem")
    if fem:
        third.append(HEADER)
        for row in fem:
            third.append(row)
    result = BytesIO()
    workbook.save(result)
    workbook.close()
    result.seek(0)
    return result


def test_real_structure_ignores_empty_sheets_and_preserves_every_statistic():
    rows = parse_standings_excel(excel(), TEAMS)
    assert len(rows) == 1
    assert rows[0] == {
        "team_id": "equipo-1", "division": "División de prueba 1", "season": "Temporada de prueba",
        "position": 1, "team_name": "MONTAJES RICA PRUEBA", "is_club": True,
        "points": 20, "played": 3, "wins": 2, "losses": 1, "source_a": 0,
        "sets_won": 12, "sets_lost": 8, "sets_difference": 4,
        "games_won": 90, "games_lost": 75, "games_difference": 15, "source_sheet": "Clasificación 500",
    }


def excel_with_missing_points_header():
    from openpyxl import load_workbook

    workbook = load_workbook(excel(future=[ROW], fem=[ROW]))
    workbook["Clasificación Fem"].cell(1, 3).value = None
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    stream.seek(0)
    return stream


def test_original_three_sheet_layout_accepts_missing_points_title_in_fem():
    rows = parse_standings_excel(excel_with_missing_points_header(), TEAMS)
    assert [row["team_id"] for row in rows] == ["equipo-1", "equipo-2", "equipo-3"]
    assert all(row["points"] == 20 for row in rows)


def test_missing_points_title_does_not_allow_other_missing_or_shifted_headers():
    header = list(HEADER)
    header[2] = None
    header[3] = None
    with pytest.raises(ValueError, match="columna C"):
        parse_standings_excel(excel(header=header), TEAMS)


def test_invalid_cell_reports_sheet_row_column_field_and_value():
    row = list(ROW)
    row[3] = "no-numérico"
    with pytest.raises(ValueError) as error:
        parse_standings_excel(excel(fem=[row]), TEAMS)
    for detail in ["Clasificación Fem", "fila 2", "columna D", "(J)", "no-numérico", "entero"]:
        assert detail in str(error.value)


def test_future_rows_have_their_own_team_and_negative_differences_are_valid():
    row = [1, "Equipo de prueba", 0, 1, 0, 1, 0, 0, 2, -2, 0, 12, -12]
    rows = parse_standings_excel(excel(future=[row]), TEAMS)
    assert rows[1]["team_id"] == "equipo-2"
    assert rows[1]["sets_difference"] == -2
    assert rows[1]["is_club"] is False


def test_formatted_empty_rows_do_not_count_as_teams():
    from openpyxl import load_workbook

    workbook = load_workbook(excel())
    workbook.worksheets[0].cell(1000, 1).number_format = "0"
    source = BytesIO()
    workbook.save(source)
    workbook.close()
    assert len(parse_standings_excel(source, TEAMS)) == 1


@pytest.mark.parametrize("column,value", [(0, 0), (2, -1), (3, "3"), (4, 99), (5, 1.5), (7, "=1+1"), (9, 0), (12, 1), (1, "")])
def test_invalid_rows_reject_entire_workbook(column, value):
    row = list(ROW)
    row[column] = value
    with pytest.raises(ValueError):
        parse_standings_excel(excel(rows=[row]), TEAMS)


def test_duplicates_bad_headers_empty_book_and_invalid_zip_are_rejected():
    for source in [excel(rows=[ROW, ROW]), excel(header=["wrong"]), excel(rows=[]), BytesIO(b"not an excel")]:
        with pytest.raises(ValueError):
            parse_standings_excel(source, TEAMS)
    with pytest.raises(ValueError, match="2 MB"):
        parse_standings_excel(BytesIO(b"x" * (MAX_EXCEL_BYTES + 1)), TEAMS)


def admin_context(monkeypatch, role="admin"):
    from flask import g

    monkeypatch.setattr("app.authenticate_request", lambda: setattr(g, "current_user", {"uid": "test-uid", "role": role, "active": True}))
    monkeypatch.setattr("admin_routes.storage_enabled", lambda: True)
    monkeypatch.setattr("admin_routes.load_club_data", lambda: {"teams": TEAMS})
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", False)


def test_admin_upload_validates_then_writes_and_redirects(monkeypatch):
    admin_context(monkeypatch)
    writes = []
    monkeypatch.setattr("admin_routes.replace_standings", lambda rows: writes.extend(rows) or len(rows))
    response = app.test_client().post("/admin/standings/import", data={"standings_file": (excel(), "clasificaciones.xlsx")})
    assert response.status_code == 302
    assert response.location.endswith("/admin#clasificacion")
    assert len(writes) == 1
    assert writes[0]["team_id"] == "equipo-1"


def test_bad_upload_does_not_write(monkeypatch):
    admin_context(monkeypatch)
    monkeypatch.setattr("admin_routes.replace_standings", lambda rows: pytest.fail("must not write"))
    client = app.test_client()
    for data in [{}, {"standings_file": (BytesIO(b"invalid"), "file.xlsx")}, {"standings_file": (excel(), "file.csv")}]:
        assert client.post("/admin/standings/import", data=data).status_code == 302


def test_single_upload_imports_all_three_sheets_in_one_write(monkeypatch):
    admin_context(monkeypatch)
    writes = []
    monkeypatch.setattr("admin_routes.replace_standings", lambda rows: writes.append(rows) or len(rows))
    response = app.test_client().post("/admin/standings/import", data={
        "standings_file": (excel(future=[ROW], fem=[ROW]), "tres-clasificaciones.xlsx"),
    })
    assert response.status_code == 302
    assert len(writes) == 1
    assert [(row["team_id"], row["source_sheet"]) for row in writes[0]] == [
        ("equipo-1", "Clasificación 500"),
        ("equipo-2", "Clasificación Future"),
        ("equipo-3", "Clasificación Fem"),
    ]


def test_error_in_last_sheet_prevents_writes_for_all_three(monkeypatch):
    admin_context(monkeypatch)
    monkeypatch.setattr("admin_routes.replace_standings", lambda rows: pytest.fail("must not write any sheet"))
    invalid = list(ROW)
    invalid[3] = "inválido"
    response = app.test_client().post("/admin/standings/import", data={
        "standings_file": (excel(future=[ROW], fem=[invalid]), "tres-clasificaciones.xlsx"),
    })
    assert response.status_code == 302
    assert response.location.endswith("/admin#clasificacion")


def test_watcher_cannot_import_and_admin_requires_csrf(monkeypatch):
    monkeypatch.setattr("admin_routes.replace_standings", lambda rows: pytest.fail("must not write"))
    admin_context(monkeypatch, role="watcher")
    assert app.test_client().post("/admin/standings/import", data={"standings_file": (excel(), "file.xlsx")}).status_code == 403
    admin_context(monkeypatch)
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
    assert app.test_client().post("/admin/standings/import", data={"standings_file": (excel(), "file.xlsx")}).status_code == 400


def test_json_upload_returns_all_three_sheet_counts(monkeypatch):
    admin_context(monkeypatch)
    writes = []
    monkeypatch.setattr("admin_routes.replace_standings", lambda rows: writes.append(rows) or len(rows))
    response = app.test_client().post("/admin/standings/import", headers={"Accept": "application/json"}, data={
        "standings_file": (excel_with_missing_points_header(), "clasificaciones.xlsx"),
    })
    assert response.status_code == 200
    assert response.json["ok"] is True
    assert response.json["count"] == 3
    assert [sheet["count"] for sheet in response.json["sheets"]] == [1, 1, 1]
    assert len(writes) == 1


def test_json_upload_reports_empty_sheets_explicitly(monkeypatch):
    admin_context(monkeypatch)
    monkeypatch.setattr("admin_routes.replace_standings", lambda rows: len(rows))
    response = app.test_client().post("/admin/standings/import", headers={"Accept": "application/json"}, data={
        "standings_file": (excel(), "clasificaciones.xlsx"),
    })
    assert [sheet["count"] for sheet in response.json["sheets"]] == [1, 0, 0]
    assert "Clasificación Future: vacía, sin cambios" in response.json["message"]


def test_json_error_in_fem_is_visible_and_nothing_is_written(monkeypatch):
    admin_context(monkeypatch)
    monkeypatch.setattr("admin_routes.replace_standings", lambda rows: pytest.fail("must not write"))
    row = list(ROW)
    row[3] = "incorrecto"
    response = app.test_client().post("/admin/standings/import", headers={"Accept": "application/json"}, data={
        "standings_file": (excel(future=[ROW], fem=[row]), "clasificaciones.xlsx"),
    })
    assert response.status_code == 400
    assert response.json["ok"] is False
    for detail in ["No se ha guardado ninguna hoja", "Clasificación Fem", "fila 2", "columna D", "incorrecto"]:
        assert detail in response.json["message"]


def test_json_server_failure_returns_reference_without_private_details(monkeypatch):
    admin_context(monkeypatch)

    def fail(rows):
        raise RuntimeError("private backend details")

    monkeypatch.setattr("admin_routes.replace_standings", fail)
    response = app.test_client().post("/admin/standings/import", headers={"Accept": "application/json"}, data={
        "standings_file": (excel(), "clasificaciones.xlsx"),
    })
    assert response.status_code == 503
    assert "Referencia:" in response.json["message"]
    assert "private backend details" not in response.json["message"]
    assert "No se ha guardado" not in response.json["message"]


def test_json_csrf_permissions_and_oversize_errors_are_actionable(monkeypatch):
    admin_context(monkeypatch, role="watcher")
    headers = {"Accept": "application/json"}
    response = app.test_client().post("/admin/standings/import", headers=headers)
    assert response.status_code == 403
    assert response.json["ok"] is False
    assert "administradores" in response.json["message"]
    admin_context(monkeypatch)
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", True)
    response = app.test_client().post("/admin/standings/import", headers=headers)
    assert response.status_code == 400
    assert "CSRF" in response.json["message"]
    monkeypatch.setitem(app.config, "WTF_CSRF_ENABLED", False)
    response = app.test_client().post("/admin/standings/import", headers=headers, data={
        "standings_file": (BytesIO(b"x" * (3 * 1024 * 1024)), "big.xlsx"),
    })
    assert response.status_code == 413
    assert "2 MB" in response.json["message"]


def test_replace_is_atomic_idempotent_and_preserves_other_teams(monkeypatch):
    from types import SimpleNamespace
    from google.cloud import firestore
    from club_store import replace_standings

    monkeypatch.setenv("USE_DATASTORE", "false")
    state = {"old-500": {"team_id": "equipo-1"}, "future": {"team_id": "equipo-2"}, "fem": {"team_id": "equipo-3"}}
    commits = []

    class Transaction:
        def __init__(self):
            self.writes = []

        def set(self, reference, row):
            self.writes.append((reference, row))

        def delete(self, reference):
            self.writes.append((reference, None))

    def transactional(function):
        def execute(transaction):
            result = function(transaction)
            for key, row in transaction.writes:
                if row is None:
                    state.pop(key, None)
                else:
                    state[key] = row
            commits.append(transaction.writes)
            return result
        return execute

    monkeypatch.setattr(firestore, "transactional", transactional)
    collection = SimpleNamespace(document=lambda key: key, stream=lambda transaction: [
        SimpleNamespace(id=key, reference=key, to_dict=lambda row=row: row) for key, row in state.items()
    ])
    db = SimpleNamespace(collection=lambda name: collection, transaction=Transaction)
    rows = parse_standings_excel(excel(), TEAMS)
    assert replace_standings(rows, db=db) == 1
    assert len(state) == 3
    assert state["future"] == {"team_id": "equipo-2"}
    assert state["fem"] == {"team_id": "equipo-3"}
    assert "old-500" not in state
    assert replace_standings(rows, db=db) == 1
    assert len(state) == 3
    assert len(commits) == 2
    before = dict(state)
    for index in range(451):
        state[f"obsolete-{index}"] = {"team_id": "equipo-1"}
    with pytest.raises(ValueError, match="450"):
        replace_standings(rows, db=db)
    assert len(commits) == 2
    assert all(state[key] == value for key, value in before.items())