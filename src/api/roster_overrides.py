"""
Manual roster overrides.

Teams are normally derived from each player's most recent replay appearance.
After offseason roster moves that mapping is stale until new replays are
ingested, so this module layers a hand-maintained file on top of it.

File format (data/players/roster_overrides.json):

    {
      "overrides": [
        {"player": "Oski", "team": "NEW TEAM", "effective": "2026-11-20",
         "note": "optional free text"}
      ]
    }

See docs/ROSTER_CHANGES.md for how to maintain it.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def load_overrides(path: Path) -> list[dict]:
    """Read the overrides list; a missing file means no overrides."""
    if not path.is_file():
        return []
    return list(json.loads(path.read_text()).get("overrides", []))


def validate_overrides(
    overrides: list[dict], player_names: dict[str, str]
) -> list[str]:
    """Return human-readable problems (empty list means the file is valid)."""
    by_name: dict[str, list[str]] = {}
    for pid, name in player_names.items():
        by_name.setdefault(name.lower(), []).append(pid)

    problems: list[str] = []
    for i, o in enumerate(overrides):
        label = f"overrides[{i}] ({o.get('player', '?')})"
        for field in ("player", "team", "effective"):
            if not str(o.get(field, "")).strip():
                problems.append(f"{label}: missing '{field}'")
        try:
            pd.Timestamp(o.get("effective"))
        except (ValueError, TypeError):
            problems.append(f"{label}: 'effective' is not a valid date")
        ids = by_name.get(str(o.get("player", "")).lower(), [])
        if not ids:
            problems.append(f"{label}: unknown player")
        elif len(ids) > 1:
            problems.append(f"{label}: ambiguous name, matches {len(ids)} players")
    return problems


def apply_roster_overrides(
    player_teams_df: pd.DataFrame,
    player_names: dict[str, str],
    overrides: list[dict],
) -> pd.DataFrame:
    """
    Return a copy of DataFrame[player_id, team_name] with overrides applied.

    Overrides are applied oldest-first, so the latest 'effective' date wins.
    Invalid entries are logged and skipped, never raised, so a typo cannot
    take the API down; tests validate the real file strictly.
    """
    teams = dict(zip(player_teams_df["player_id"], player_teams_df["team_name"]))
    by_name: dict[str, list[str]] = {}
    for pid, name in player_names.items():
        by_name.setdefault(name.lower(), []).append(pid)

    def _date(o: dict) -> pd.Timestamp:
        try:
            return pd.Timestamp(o.get("effective"))
        except (ValueError, TypeError):
            return pd.Timestamp.min

    for o in sorted(overrides, key=_date):
        ids = by_name.get(str(o.get("player", "")).lower(), [])
        team = str(o.get("team", "")).strip()
        if len(ids) != 1 or not team:
            logger.warning("Skipping invalid roster override: %s", o)
            continue
        teams[ids[0]] = team

    return pd.DataFrame(
        {"player_id": list(teams), "team_name": list(teams.values())}
    )
