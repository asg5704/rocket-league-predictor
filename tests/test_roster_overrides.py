"""Tests for manual roster overrides."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.api.roster_overrides import (
    apply_roster_overrides,
    load_overrides,
    validate_overrides,
)

NAMES = {"p1": "Alpha", "p2": "Bravo", "p3": "Charlie", "p4": "charlie"}
TEAMS = pd.DataFrame(
    {"player_id": ["p1", "p2", "p3"], "team_name": ["OLD A", "OLD A", "OLD B"]}
)


def _team_map(df):
    return dict(zip(df["player_id"], df["team_name"]))


def test_no_overrides_is_identity():
    assert _team_map(apply_roster_overrides(TEAMS, NAMES, [])) == _team_map(TEAMS)


def test_override_moves_player_case_insensitive():
    o = [{"player": "alpha", "team": "NEW", "effective": "2026-11-20"}]
    out = _team_map(apply_roster_overrides(TEAMS, NAMES, o))
    assert out["p1"] == "NEW"
    assert out["p2"] == "OLD A"


def test_latest_effective_date_wins_regardless_of_file_order():
    o = [
        {"player": "Alpha", "team": "LATER", "effective": "2026-12-01"},
        {"player": "Alpha", "team": "EARLIER", "effective": "2026-11-01"},
    ]
    assert _team_map(apply_roster_overrides(TEAMS, NAMES, o))["p1"] == "LATER"


def test_override_can_add_player_without_replays():
    o = [{"player": "Bravo", "team": "X", "effective": "2026-11-20"}]
    names = {**NAMES, "p9": "Rookie"}
    o.append({"player": "Rookie", "team": "X", "effective": "2026-11-20"})
    assert _team_map(apply_roster_overrides(TEAMS, names, o))["p9"] == "X"


def test_invalid_entries_are_skipped_not_raised():
    o = [
        {"player": "Nobody", "team": "X", "effective": "2026-11-20"},
        {"player": "Charlie", "team": "X", "effective": "2026-11-20"},  # ambiguous
        {"player": "Alpha", "team": "", "effective": "2026-11-20"},
    ]
    assert _team_map(apply_roster_overrides(TEAMS, NAMES, o)) == _team_map(TEAMS)


def test_validate_reports_problems():
    o = [
        {"player": "Nobody", "team": "X", "effective": "2026-11-20"},
        {"player": "Charlie", "team": "X", "effective": "2026-11-20"},
        {"player": "Alpha", "team": "X", "effective": "not-a-date"},
        {"player": "Bravo", "effective": "2026-11-20"},
    ]
    problems = validate_overrides(o, NAMES)
    assert len(problems) == 4


def test_missing_file_means_no_overrides(tmp_path):
    assert load_overrides(tmp_path / "nope.json") == []


def test_real_overrides_file_is_valid():
    """Fails CI-style on typos before they reach production."""
    root = Path(__file__).resolve().parents[1]
    overrides = load_overrides(root / "data" / "players" / "roster_overrides.json")
    names = json.loads((root / "data" / "processed" / "player_names.json").read_text())
    assert validate_overrides(overrides, names) == []
