"""Validación del formato de ClasificacionesMontajes, sin guardar el Excel."""

from __future__ import annotations

import unicodedata
from io import BytesIO
from zipfile import BadZipFile, ZipFile
from xml.etree.ElementTree import ParseError

from openpyxl import load_workbook
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
                _, header = populated[0]
                if [normalized(value) for value in header[2:13]] != HEADERS:
                    raise ValueError(f"Cabeceras incorrectas en {sheet.title}: se esperan posición, equipo, Puntos, J, G, P, A, SG, SP, DS, JG, JP y DJ.")
                if len(populated) == 1:
                    continue
                team = team_by_id.get(team_id)
                if not team:
                    raise ValueError(f"Falta configurar el equipo de {sheet.title}.")
                positions, names = set(), set()
                for number, row in populated[1:]:
                    def integer(value, label, minimum=0):
                        if isinstance(value, bool) or not isinstance(value, (int, float)) or not minimum <= value <= 99999 or int(value) != value:
                            raise ValueError(f"{sheet.title}, fila {number}: {label} debe ser un entero válido.")
                        return int(value)

                    position = integer(row[0], "posición", 1)
                    name = row[1].strip() if isinstance(row[1], str) else ""
                    if not name or len(name) > 120 or name.startswith(("=", "+", "@")):
                        raise ValueError(f"{sheet.title}, fila {number}: nombre de equipo inválido.")
                    if position in positions or normalized(name) in names:
                        raise ValueError(f"{sheet.title}, fila {number}: posición o equipo duplicado.")
                    positions.add(position)
                    names.add(normalized(name))
                    values = {field: integer(value, HEADERS[index], -99999 if field.endswith("difference") else 0)
                              for index, (field, value) in enumerate(zip(FIELDS, row[2:13]))}
                    if values["wins"] + values["losses"] > values["played"]:
                        raise ValueError(f"{sheet.title}, fila {number}: ganados y perdidos superan los jugados.")
                    if values["sets_won"] - values["sets_lost"] != values["sets_difference"] or values["games_won"] - values["games_lost"] != values["games_difference"]:
                        raise ValueError(f"{sheet.title}, fila {number}: las diferencias de sets o juegos no coinciden.")
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