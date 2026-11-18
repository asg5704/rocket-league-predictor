"""Tests for manual roster overrides."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.api.roster_overrides import (
    apply_roster_overrides,
    load_manual_players,
    load_overrides,
    merge_rosters,
    resolve_team,
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
    names.update(load_manual_players(root / "data" / "players" / "manual_players.json", names))
    assert validate_overrides(overrides, names) == []


def test_manual_players_get_synthetic_ids_and_skip_known(tmp_path):
    f = tmp_path / "manual.json"
    f.write_text(json.dumps({"players": [{"name": "Rookie"}, {"name": "alpha"}, {"name": ""}]}))
    assert load_manual_players(f, NAMES) == {"manual:rookie": "Rookie"}
    assert load_manual_players(tmp_path / "none.json", NAMES) == {}


def test_override_can_place_manual_player():
    names = {**NAMES, "manual:rookie": "Rookie"}
    o = [{"player": "Rookie", "team": "NEW", "effective": "2026-11-20"}]
    out = apply_roster_overrides(TEAMS, names, o)
    assert _team_map(out)["manual:rookie"] == "NEW"


def test_resolve_team_uses_known_spelling_and_aliases():
    known = {"WILDCARD", "MANCHESTER CITY"}
    assert resolve_team("Wildcard", known) == "WILDCARD"
    assert resolve_team("Man City Esports", known) == "MANCHESTER CITY"
    assert resolve_team("Brand New Org", known) == "Brand New Org"


def test_override_team_resolved_against_known_teams():
    o = [{"player": "Alpha", "team": "old b", "effective": "2026-11-20"}]
    out = apply_roster_overrides(TEAMS, NAMES, o, known_teams={"OLD B"})
    assert _team_map(out)["p1"] == "OLD B"


def test_merge_rosters_moves_players_and_adds_manual():
    names = {**NAMES, "manual:rookie": "Rookie"}
    rosters = {"OLD A": ["Alpha", "Bravo"], "OLD B": ["Charlie"]}
    after = pd.DataFrame(
        {
            "player_id": ["p1", "p2", "p3", "manual:rookie"],
            "team_name": ["NEW", "OLD A", "OLD B", "NEW"],
        }
    )
    out = merge_rosters(rosters, TEAMS, after, names)
    assert out == {"OLD A": ["Bravo"], "OLD B": ["Charlie"], "NEW": ["Alpha", "Rookie"]}


def test_validate_flags_duplicates_and_same_day_conflicts():
    o = [
        {"player": "Alpha", "team": "X", "effective": "2026-11-20"},
        {"player": "alpha", "team": "x", "effective": "2026-11-20"},
        {"player": "Bravo", "team": "X", "effective": "2026-11-20"},
        {"player": "Bravo", "team": "Y", "effective": "2026-11-20"},
        {"player": "Bravo", "team": "Z", "effective": "2026-12-01"},
    ]
    problems = validate_overrides(o, NAMES)
    assert len(problems) == 2
    assert any("duplicate" in p for p in problems)
    assert any("conflicting" in p for p in problems)


def test_free_agent_override_clears_team():
    o = [{"player": "Alpha", "team": None, "effective": "2026-11-20"}]
    assert apply_roster_overrides(TEAMS, NAMES, o).set_index("player_id")["team_name"]["p1"] is None
    assert validate_overrides(o, NAMES) == []


def test_missing_team_key_is_still_invalid():
    o = [{"player": "Alpha", "effective": "2026-11-20"}]
    assert len(validate_overrides(o, NAMES)) == 1


def test_merge_rosters_free_agent_leaves_team_joins_none():
    after = pd.DataFrame(
        {"player_id": ["p1", "p2", "p3"], "team_name": [None, "OLD A", "OLD B"]}
    )
    out = merge_rosters({"OLD A": ["Alpha", "Bravo"], "OLD B": ["Charlie"]}, TEAMS, after, NAMES)
    assert out == {"OLD A": ["Bravo"], "OLD B": ["Charlie"]}
