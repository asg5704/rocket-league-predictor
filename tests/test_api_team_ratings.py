"""Unit tests for the roster -> team-rating helpers in src/api/main.py."""

import pandas as pd
import pytest

from src.api.main import _team_rating_rosters
from src.models.elo import PlayerEloModel


def test_current_roster_wins_over_last_lineup():
    out = _team_rating_rosters(
        {"X": ["p1", "p2", "p9"]}, {"X": ["p1", "p2", "p3"]}, {"X"}
    )
    assert out["X"] == ["p1", "p2", "p9"]


def test_empty_roster_falls_back_to_last_lineup():
    out = _team_rating_rosters({}, {"DEFUNCT": ["p1", "p2", "p3"]}, {"DEFUNCT"})
    assert out["DEFUNCT"] == ["p1", "p2", "p3"]


def test_only_known_teams_are_rated():
    out = _team_rating_rosters({"NEW": ["p1"]}, {"OLD": ["p2"]}, {"OLD"})
    assert set(out) == {"OLD"}


def test_unknown_team_without_lineup_is_empty():
    assert _team_rating_rosters({}, {}, {"GHOST"}) == {"GHOST": []}


def test_roster_move_changes_team_ranking():
    matches = pd.DataFrame(
        {"match_id": ["m1", "m2"], "date": ["2026-01-01", "2026-01-02"], "winner": ["blue", "blue"]}
    )
    rows = []
    for mid in ("m1", "m2"):
        rows += [{"match_id": mid, "player_id": f"s{i}", "team_side": "blue"} for i in range(3)]
        rows += [{"match_id": mid, "player_id": f"w{i}", "team_side": "orange"} for i in range(3)]
    m = PlayerEloModel(k_factor=32).fit(matches, pd.DataFrame(rows))
    lineups = {"STRONG": ["s0", "s1", "s2"], "WEAK": ["w0", "w1", "w2"]}
    base = m.team_ratings(_team_rating_rosters(lineups, lineups, set(lineups))).set_index("team_name")["elo"]
    # s0 leaves STRONG for WEAK
    moved = {"STRONG": ["s1", "s2", "x"], "WEAK": ["w0", "w1", "s0"]}
    new = m.team_ratings(_team_rating_rosters(moved, lineups, set(lineups))).set_index("team_name")["elo"]
    assert new["STRONG"] < base["STRONG"]
    assert new["WEAK"] > base["WEAK"]
