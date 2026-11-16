from openpyxl import Workbook
from google.cloud import datastore

from scripts.import_players import parse_workbook, stable_player_id
from datastore_store import _decode_entity, _encode_values


def test_workbook_maps_sheets_to_teams_and_positions(tmp_path):
    path = tmp_path / "sample.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Masc 500"
    sheet.append(["Jugador", "Posición"])
    sheet.append(["Jugador Demo Uno", "Drive"])
    future = workbook.create_sheet("Masc Future")
    future.append(["Jugador", "Posición"])
    future.append(["Jugador Demo Dos", "Reves"])
    women = workbook.create_sheet("Fem")
    women.append(["Jugador", "Posición"])
    women.append(["Jugador Demo Tres", "Revés"])
    workbook.save(path)

    records = parse_workbook(path)

    assert [(row["team_id"], row["handedness"]) for row in records] == [
        ("equipo-1", "Drive"),
        ("equipo-2", "Revés"),
        ("equipo-3", "Revés"),
    ]
    assert stable_player_id(records[0]) == stable_player_id(records[0])
    assert len({stable_player_id(record) for record in records}) == 3


def test_workbook_rejects_unknown_player_position(tmp_path):
    path = tmp_path / "invalid.xlsx"
    workbook = Workbook()
    workbook.active.title = "Masc 500"
    workbook.active.append(["Jugador", "Posición"])
    workbook.active.append(["Jugador Demo", "Ambos"])
    for sheet_name in ("Masc Future", "Fem"):
        sheet = workbook.create_sheet(sheet_name)
        sheet.append(["Jugador", "Posición"])
    workbook.save(path)

    try:
        parse_workbook(path)
    except ValueError as error:
        assert "Drive o Revés" in str(error)
    else:
        raise AssertionError("Expected an invalid player position to be rejected")


def test_datastore_records_round_trip_nested_match_data():
    pairings = [{"player_ids": ["p1", "p2"], "sets": [{"home": 6, "away": 4}]}]
    encoded = _encode_values({"team_id": "equipo-1", "pairings": pairings})
    entity = datastore.Entity(key=datastore.Key("Match", "match-test", project="montajesrica"))
    entity.update(encoded)

    decoded = _decode_entity(entity)

    assert decoded["id"] == "match-test"
    assert decoded["team_id"] == "equipo-1"
    assert decoded["pairings"] == pairings
