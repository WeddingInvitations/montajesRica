"""Vistas y operaciones protegidas por sesiones Firebase y rol admin en Firestore."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from werkzeug.exceptions import BadRequest

from club_store import (
    add_admin,
    create_record,
    delete_record,
    storage_enabled,
    list_admins,
    load_club_data,
    remove_admin,
    set_player_active,
    update_record,
    update_team,
)
from player_stats import calculate_player_stats
from security import require_admin

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _required_text(field: str, label: str, max_length: int = 160) -> str:
    value = request.form.get(field, "").strip()
    if not value:
        abort(400, description=f"El campo {label} es obligatorio.")
    if len(value) > max_length:
        abort(400, description=f"El campo {label} supera la longitud permitida.")
    return value


def _optional_text(field: str, max_length: int = 250) -> str:
    value = request.form.get(field, "").strip()
    if len(value) > max_length:
        abort(400, description="Uno de los campos supera la longitud permitida.")
    return value


def _club_or_fail() -> dict[str, Any]:
    return load_club_data()


def _player_values(club: dict[str, Any]) -> dict[str, str]:
    name = _required_text("name", "nombre", 100)
    team_id = _required_text("team_id", "equipo", 80)
    handedness = _required_text("handedness", "lado de juego", 30)
    team_ids = {team.get("id") for team in club.get("teams", [])}
    if team_id not in team_ids:
        abort(400, description="El equipo seleccionado no es válido.")
    if handedness not in {"Drive", "Revés"}:
        abort(400, description="El lado debe ser Drive o Revés.")
    return {"name": name, "team_id": team_id, "handedness": handedness}


def _team_values() -> dict[str, str]:
    return {
        "name": _required_text("name", "nombre del equipo", 100),
        "division": _required_text("division", "división", 100),
        "season": _required_text("season", "temporada", 40),
    }


def _standing_values(club: dict[str, Any]) -> dict[str, Any]:
    team_id = _required_text("team_id", "equipo del club", 80)
    team = next((item for item in club.get("teams", []) if item.get("id") == team_id), None)
    if not team:
        abort(400, description="El equipo del club seleccionado no es válido.")

    def integer(field: str, label: str, minimum: int, maximum: int) -> int:
        try:
            value = int(request.form.get(field, ""))
        except (TypeError, ValueError):
            abort(400, description=f"{label} debe ser un número entero.")
        if value < minimum or value > maximum:
            abort(400, description=f"{label} está fuera del rango permitido.")
        return value

    played = integer("played", "Partidos jugados", 0, 999)
    wins = integer("wins", "Partidos ganados", 0, 999)
    losses = integer("losses", "Partidos perdidos", 0, 999)
    if wins + losses > played:
        abort(400, description="Las victorias y derrotas no pueden superar los partidos jugados.")
    return {
        "team_id": team_id,
        "division": _required_text("division", "división", 100),
        "season": _required_text("season", "temporada", 40),
        "position": integer("position", "Posición", 1, 999),
        "team_name": _required_text("team_name", "nombre en la clasificación", 120),
        "played": played,
        "wins": wins,
        "losses": losses,
        "points": integer("points", "Puntos", 0, 9999),
        "is_club": request.form.get("is_club") == "on",
    }


def _parse_pairings(
    players: list[dict[str, Any]],
    team_id: str,
    existing_pairings: list[dict[str, Any]] | None = None,
    allow_future_players: bool = False,
) -> list[dict[str, Any]]:
    eligible_teams = {team_id}
    if allow_future_players and team_id == 'equipo-1':
        eligible_teams.add('equipo-2')
    player_by_id = {player["id"]: player for player in players}
    active_player_ids = {
        player["id"]
        for player in players
        if player.get("team_id") in eligible_teams
        and player.get("active", True) is not False
    }
    validated = []
    seen_in_match: set[str] = set()
    set_pattern = re.compile(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$")
    for index in range(1, 6):
        player_ids = [
            player_id
            for player_id in (
                request.form.get(f"pairing_player_{index}_1", ""),
                request.form.get(f"pairing_player_{index}_2", ""),
            )
            if player_id
        ]
        opponent_pair = _optional_text(f"pairing_opponent_{index}", 100)
        raw_sets = _optional_text(f"pairing_sets_{index}", 40)
        if not player_ids and not opponent_pair and not raw_sets:
            continue
        old_pairing = (existing_pairings or [])[index - 1] if len(existing_pairings or []) >= index else {}
        old_player_ids = set(old_pairing.get("player_ids", []))
        valid_player_ids = active_player_ids | {
            player_id for player_id in old_player_ids
            if player_id in player_by_id and player_by_id[player_id].get("team_id") in eligible_teams
        }
        if len(player_ids) != 2 or len(set(player_ids)) != 2 or any(player_id not in valid_player_ids for player_id in player_ids):
            abort(400, description=f"La pareja {index} debe tener dos jugadores del equipo seleccionado.")
        if any(player_id in seen_in_match for player_id in player_ids):
            abort(400, description="Un jugador no puede aparecer en más de una pareja del mismo partido.")
        seen_in_match.update(player_ids)
        clean_sets = []
        if raw_sets:
            for raw_score in raw_sets.split(","):
                result = set_pattern.fullmatch(raw_score)
                if not result:
                    abort(400, description=f"Los sets de la pareja {index} deben escribirse como 6-4, 7-5.")
                home_score, away_score = map(int, result.groups())
                if home_score > 99 or away_score > 99:
                    abort(400, description=f"El marcador de la pareja {index} contiene un set inválido.")
                clean_sets.append({"home": home_score, "away": away_score})
        if len(clean_sets) > 5:
            abort(400, description=f"La pareja {index} no puede tener más de cinco sets.")
        for score in clean_sets:
            home_score, away_score = score["home"], score["away"]
            if not (0 <= home_score <= 99 and 0 <= away_score <= 99) or home_score == away_score:
                abort(400, description=f"El marcador de la pareja {index} contiene un set inválido.")
        if clean_sets and not opponent_pair:
            abort(400, description=f"Indica el nombre de la pareja rival {index}.")
        old_pair = next(
            (item for item in (existing_pairings or []) if item.get("player_ids") == player_ids),
            {},
        )
        old_names = old_pair.get("player_names", [])
        player_names = []
        for player_index, player_id in enumerate(player_ids):
            if player_index < len(old_names) and old_names[player_index]:
                player_names.append(old_names[player_index])
            else:
                player_names.append(player_by_id[player_id]["name"])
        validated.append({
            "player_ids": player_ids,
            "player_names": player_names,
            "opponent_pair": opponent_pair,
            "sets": clean_sets,
        })
    return validated


def _match_values(club: dict[str, Any], existing_match: dict[str, Any] | None = None) -> dict[str, Any]:
    team_id = _required_text("team_id", "equipo", 80)
    team_ids = {team.get("id") for team in club.get("teams", [])}
    if team_id not in team_ids:
        abort(400, description="El equipo seleccionado no es válido.")
    opponent = _required_text("opponent", "rival", 120)
    division = _required_text("division", "división", 100)
    match_date = _required_text("date", "fecha", 10)
    try:
        date.fromisoformat(match_date)
    except ValueError:
        abort(400, description="La fecha no tiene un formato válido.")
    time = _optional_text("time", 8)
    if time:
        try:
            from datetime import time as time_type

            time_type.fromisoformat(time)
        except ValueError:
            abort(400, description="La hora no tiene un formato válido.")
    venue = _required_text("venue", "lugar", 160)
    status = _required_text("status", "estado", 20)
    if status not in {"scheduled", "played"}:
        abort(400, description="El estado del partido no es válido.")
    score = _optional_text("score", 30)
    allow_future_players = request.form.get("allow_future_players") == "on"
    if allow_future_players and team_id != "equipo-1":
        abort(400, description="La excepción solo permite convocar jugadores de Masculino Future en Masculino 500.")
    pairings = _parse_pairings(
        club.get("players", []),
        team_id,
        existing_pairings=(existing_match or {}).get("pairings", []),
        allow_future_players=allow_future_players,
    )
    if score and not re.fullmatch(r"\d{1,2}\s*-\s*\d{1,2}", score):
        abort(400, description="El resultado general debe escribirse como 3-2.")
    completed_pairings = [pairing for pairing in pairings if pairing["sets"]]
    if status == "played" and not score and (not pairings or len(completed_pairings) != len(pairings)):
        abort(400, description="Un partido jugado necesita el resultado general o los sets de todas las parejas registradas.")
    return {
        "team_id": team_id,
        "opponent": opponent,
        "division": division,
        "date": match_date,
        "time": time,
        "venue": venue,
        "home": request.form.get("home") == "on",
        "status": status,
        "score": score,
        "pairings": pairings,
        "allow_future_players": allow_future_players,
    }


@admin_bp.before_request
def protect_admin_area():
    require_admin()
    if not storage_enabled():
        abort(503, description="El almacenamiento debe estar configurado antes de guardar cambios.")


@admin_bp.get("")
def dashboard():
    club = _club_or_fail()
    return render_template(
        "admin.html",
        club=club,
        admins=list_admins(),
        player_stats=calculate_player_stats(club.get("matches", [])),
    )


@admin_bp.post("/players")
def create_player():
    club = _club_or_fail()
    values = _player_values(club)
    values["active"] = True
    create_record("players", values)
    flash("Jugador añadido.", "success")
    return redirect(url_for("admin.dashboard", _anchor="jugadores"))


@admin_bp.post("/players/<player_id>")
def edit_player(player_id: str):
    club = _club_or_fail()
    values = _player_values(club)
    update_record("players", player_id, values)
    flash("Ficha del jugador actualizada.", "success")
    return redirect(url_for("admin.dashboard", _anchor="jugadores"))


@admin_bp.post("/players/<player_id>/delete")
def remove_player(player_id: str):
    set_player_active(player_id, False, g.current_user["uid"])
    flash("Jugador archivado. Su historial y estadísticas se conservan.", "success")
    return redirect(url_for("admin.dashboard", _anchor="jugadores"))


@admin_bp.post("/players/<player_id>/restore")
def restore_player(player_id: str):
    set_player_active(player_id, True, g.current_user["uid"])
    flash("Jugador restaurado a la plantilla.", "success")
    return redirect(url_for("admin.dashboard", _anchor="jugadores"))


@admin_bp.post("/teams/<team_id>")
def edit_team(team_id: str):
    club = _club_or_fail()
    if team_id not in {team.get("id") for team in club.get("teams", [])}:
        abort(404, description="No se encontró el equipo.")
    update_team(team_id, _team_values())
    flash("Equipo, división y temporada actualizados.", "success")
    return redirect(url_for("admin.dashboard", _anchor="equipos"))


@admin_bp.post("/matches")
def create_match():
    club = _club_or_fail()
    values = _match_values(club)
    create_record("matches", values)
    flash("Partido guardado.", "success")
    return redirect(url_for("admin.dashboard", _anchor="partidos"))


@admin_bp.post("/matches/<match_id>")
def edit_match(match_id: str):
    club = _club_or_fail()
    from club_store import get_record

    existing_match = get_record("matches", match_id)
    if not existing_match:
        abort(404, description="No se encontró el partido.")
    values = _match_values(club, existing_match=existing_match)
    update_record("matches", match_id, values)
    flash("Partido y resultado actualizados.", "success")
    return redirect(url_for("admin.dashboard", _anchor="partidos"))


@admin_bp.post("/matches/<match_id>/delete")
def remove_match(match_id: str):
    delete_record("matches", match_id)
    flash("Partido eliminado.", "success")
    return redirect(url_for("admin.dashboard", _anchor="partidos"))


@admin_bp.post("/standings")
def create_standing():
    values = _standing_values(_club_or_fail())
    create_record("standings", values)
    flash("Posición de clasificación guardada.", "success")
    return redirect(url_for("admin.dashboard", _anchor="clasificacion"))


@admin_bp.post("/standings/<standing_id>")
def edit_standing(standing_id: str):
    values = _standing_values(_club_or_fail())
    update_record("standings", standing_id, values)
    flash("Clasificación actualizada.", "success")
    return redirect(url_for("admin.dashboard", _anchor="clasificacion"))


@admin_bp.post("/standings/<standing_id>/delete")
def remove_standing(standing_id: str):
    delete_record("standings", standing_id)
    flash("Fila de clasificación eliminada.", "success")
    return redirect(url_for("admin.dashboard", _anchor="clasificacion"))


@admin_bp.post("/admins")
def create_admin():
    try:
        email = _required_text("email", "correo", 254).lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            abort(400, description="El correo no tiene un formato válido.")
        add_admin(email)
    except BadRequest as error:
        flash(error.description, "error")
        return redirect(url_for("admin.dashboard", _anchor="administradores"))
    flash("Permisos de administración concedidos.", "success")
    return redirect(url_for("admin.dashboard", _anchor="administradores"))


@admin_bp.post("/admins/<admin_id>/delete")
def remove_admin_route(admin_id: str):
    remove_admin(admin_id, g.current_user["uid"], g.current_user["role"])
    flash("Permisos de administración retirados.", "success")
    return redirect(url_for("admin.dashboard", _anchor="administradores"))
