from player_stats import calculate_player_stats
import pytest


def test_stats_count_each_played_match_and_player_sets_once():
    matches = [
        {
            "id": "m1",
            "status": "played",
            "score": "2-1",
            "pairings": [
                {"player_ids": ["p1", "p2"], "sets": [{"home": 6, "away": 4}, {"home": 7, "away": 5}]},
                {"player_ids": ["p3", "p4"], "sets": [{"home": 4, "away": 6}, {"home": 3, "away": 6}]},
            ],
        },
        {
            "id": "m2",
            "status": "scheduled",
            "score": "",
            "pairings": [{"player_ids": ["p1", "p2"], "sets": []}],
        },
    ]

    stats = calculate_player_stats(matches)

    assert stats["p1"] == {"played": 1, "wins": 1, "losses": 0, "sets_won": 2, "sets_lost": 0}
    assert stats["p3"] == {"played": 1, "wins": 0, "losses": 1, "sets_won": 0, "sets_lost": 2}
    assert "p1" not in stats or stats["p1"]["played"] == 1


def test_stats_use_overall_score_when_pair_has_no_set_detail():
    stats = calculate_player_stats([{
        "id": "m1",
        "status": "played",
        "score": "1-2",
        "pairings": [{"player_ids": ["p1", "p2"], "sets": []}],
    }])

    assert stats["p1"] == {"played": 1, "wins": 0, "losses": 1, "sets_won": 0, "sets_lost": 0}


@pytest.mark.parametrize("home,score,wins,losses", [
    (True, "12-0", 1, 0), (False, "12-0", 0, 1),
    (True, "0-12", 0, 1), (False, "0-12", 1, 0),
    (True, "6-6", 0, 0), (False, "6-6", 0, 0),
])
def test_overall_score_is_local_visitor(home, score, wins, losses):
    stats = calculate_player_stats([{
        "status": "played", "home": home, "score": score,
        "pairings": [{"player_ids": ["test-player"], "sets": []}],
    }])
    assert stats["test-player"]["wins"] == wins
    assert stats["test-player"]["losses"] == losses


def test_away_pair_sets_stay_club_rival_and_override_overall_result():
    stats = calculate_player_stats([{
        "status": "played", "home": False, "score": "12-0",
        "pairings": [{"player_ids": ["test-player"], "sets": [{"home": 6, "away": 0}]}],
    }])
    assert stats["test-player"] == {"played": 1, "wins": 1, "losses": 0, "sets_won": 1, "sets_lost": 0}
