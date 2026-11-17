"""Estadísticas individuales calculadas desde resultados de partidos guardados."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

SCORE_PATTERN = re.compile(r"^\s*(\d{1,2})\s*-\s*(\d{1,2})\s*$")


def _score(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    match = SCORE_PATTERN.fullmatch(value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _match_result(match: dict[str, Any]) -> int:
    """Return 1 if Montajes Rica won, -1 if lost, or 0 if unknown/tied.

    The overall score is local-away. Pairing set scores remain MR-rival.
    """
    score = _score(match.get("score"))
    if not score or score[0] == score[1]:
        return 0
    club, opponent = score if match.get("home", True) else (score[1], score[0])
    return 1 if club > opponent else -1


def _pair_result(pairing: dict[str, Any], match_result: int) -> int:
    sets = pairing.get("sets") or []
    won_sets = sum(1 for item in sets if int(item.get("home", 0)) > int(item.get("away", 0)))
    lost_sets = sum(1 for item in sets if int(item.get("home", 0)) < int(item.get("away", 0)))
    if won_sets != lost_sets:
        return 1 if won_sets > lost_sets else -1
    return match_result


def calculate_player_stats(matches: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Calculate match W/L and set W/L once per player and played match."""
    totals: dict[str, dict[str, int]] = defaultdict(lambda: {
        "played": 0,
        "wins": 0,
        "losses": 0,
        "sets_won": 0,
        "sets_lost": 0,
    })

    for match in matches:
        if match.get("status") != "played":
            continue
        match_result = _match_result(match)
        seen_in_match: set[str] = set()
        for pairing in match.get("pairings") or []:
            player_ids = pairing.get("player_ids") or []
            result = _pair_result(pairing, match_result)
            sets = pairing.get("sets") or []
            won_sets = sum(1 for item in sets if int(item.get("home", 0)) > int(item.get("away", 0)))
            lost_sets = sum(1 for item in sets if int(item.get("home", 0)) < int(item.get("away", 0)))
            for player_id in player_ids:
                if not player_id or player_id in seen_in_match:
                    continue
                seen_in_match.add(player_id)
                stats = totals[player_id]
                stats["played"] += 1
                stats["sets_won"] += won_sets
                stats["sets_lost"] += lost_sets
                if result > 0:
                    stats["wins"] += 1
                elif result < 0:
                    stats["losses"] += 1

    return dict(totals)
