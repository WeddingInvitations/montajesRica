"""Validación del formato de ClasificacionesMontajes, sin guardar el Excel."""

from __future__ import annotations

import unicodedata
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from defusedxml.common import DefusedXmlException

MAX_EXCEL_BYTES = 2 * 1024 * 1024
SHEETS = {
    "clasificacion 500": "equipo-1",
    "clasificacion future": "equipo-2",
    "clasificacion fem": "equipo-3",
}
HEADERS = ["puntos", "j", "g", "p", "a", "sg", "sp", "ds", "jg", "jp", "dj"]
FIELDS = ["points", "played", "wins", "losses", "source_a", "sets_won", "sets_lost", "sets_difference", "games_won", "games_lost", "games_difference"]


def normalized(value):
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def parse_standings_excel(source, teams):
    """Devuelve filas de hojas no vacías; un error invalida el libro completo."""
    try:
        source.seek(0)
        content = source.read(MAX_EXCEL_BYTES + 1)
        if len(content) > MAX_EXCEL_BYTES:
            raise ValueError("El Excel no puede superar 2 MB.")
        # BytesIO también soporta seekable() en Python 3.9, a diferencia del
        # SpooledTemporaryFile de algunas versiones de Werkzeug/Python.
        source = BytesIO(content)
        with ZipFile(source) as archive:
            if len(archive.infolist()) > 200 or sum(item.file_size for item in archive.infolist()) > 8 * 1024 * 1024:
                raise ValueError("El contenido descomprimido del Excel es demasiado grande.")
        source.seek(0)
        workbook = load_workbook(source, read_only=True, data_only=False, keep_links=False)
        try:
            sheet_names = {normalized(name): name for name in workbook.sheetnames}
            if set(sheet_names) != set(SHEETS) or len(workbook.sheetnames) != 3:
                raise ValueError("El Excel necesita las hojas Clasificación 500, Clasificación Future y Clasificación Fem.")
            team_by_id = {team["id"]: team for team in teams}
            result = []
            for sheet_key, team_id in SHEETS.items():
                sheet = workbook[sheet_names[sheet_key]]
                populated = []
                for number, row in enumerate(sheet.iter_rows(max_col=14, values_only=True), 1):
                    if number > 10000:
                        raise ValueError(f"La hoja {sheet.title} contiene demasiadas filas de formato.")
                    if any(value is not None and str(value).strip() for value in row):
                        populated.append((number, row))
                        if len(populated) > 101:
                            raise ValueError(f"La hoja {sheet.title} admite como máximo 100 equipos.")
                if not populated:
                    continue
                header_number, header = populated[0]
                # El libro original de Femenino deja C (Puntos) sin título.
                # Solo se admite ese hueco si J..DJ están en su posición exacta.
                actual_headers = [normalized(value) for value in header[2:13]]
                if actual_headers[0] == "" and actual_headers[1:] == HEADERS[1:]:
                    actual_headers[0] = "puntos"
                for column, (actual, expected) in enumerate(zip(actual_headers, HEADERS), 3):
                    if actual != expected:
                        raise ValueError(f"Hoja «{sheet.title}», fila {header_number}, columna {get_column_letter(column)}: "
                                         f"se esperaba la cabecera «{expected.upper()}»; recibido «{str(header[column - 1] or '(vacía)')[:80]}».")
                if len(populated) == 1:
                    continue
                team = team_by_id.get(team_id)
                if not team:
                    raise ValueError(f"Falta configurar el equipo de {sheet.title}.")
                positions, names = set(), set()
                for number, row in populated[1:]:
                    def integer(value, label, column, minimum=0):
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= 99999 or int(value) != value:
                            received = "(vacío)" if value is None else str(value)[:80]
                            raise ValueError(f"Hoja «{sheet.title}», fila {number}, columna {column} ({label}): "
                                             f"se esperaba un entero entre {minimum} y 99999; recibido «{received}». No se admiten fórmulas.")
                        return int(value)

                    position = integer(row[0], "posición", "A", 1)
                    name = row[1].strip() if isinstance(row[1], str) else ""
                    if not name or len(name) > 120 or name.startswith(("=", "+", "@")):
                        raise ValueError(f"Hoja «{sheet.title}», fila {number}, columna B (equipo): indica un nombre de 1 a 120 caracteres, sin fórmulas.")
                    if position in positions or normalized(name) in names:
                        raise ValueError(f"{sheet.title}, fila {number}: posición o equipo duplicado.")
                    positions.add(position)
                    names.add(normalized(name))
                    values = {field: integer(value, HEADERS[index].upper(), get_column_letter(index + 3), -99999 if field.endswith("difference") else 0)
                              for index, (field, value) in enumerate(zip(FIELDS, row[2:13]))}
                    if values["wins"] + values["losses"] > values["played"]:
                        raise ValueError(f"Hoja «{sheet.title}», fila {number}, columnas D–F (J/G/P): ganados ({values['wins']}) y perdidos ({values['losses']}) superan los jugados ({values['played']}).")
                    for won, lost, difference, column, label in [
                        ("sets_won", "sets_lost", "sets_difference", "J", "DS = SG − SP"),
                        ("games_won", "games_lost", "games_difference", "M", "DJ = JG − JP"),
                    ]:
                        expected = values[won] - values[lost]
                        if values[difference] != expected:
                            raise ValueError(f"Hoja «{sheet.title}», fila {number}, columna {column} ({label}): se esperaba {expected}; recibido {values[difference]}.")
                    result.append({**values, "team_id": team_id, "division": team.get("division", "División por configurar"),
                                   "season": team.get("season", "Por configurar"), "position": position,
                                   "team_name": name, "is_club": normalized(name).startswith("montajes rica"), "source_sheet": sheet.title})
            if not result:
                raise ValueError("El Excel no contiene filas de clasificación para importar.")
            return result
        finally:
            workbook.close()
    except (BadZipFile, InvalidFileException, KeyError, DefusedXmlException, ParseError) as error:
        raise ValueError("No se ha podido leer el Excel. Sube un archivo .xlsx válido.") from error