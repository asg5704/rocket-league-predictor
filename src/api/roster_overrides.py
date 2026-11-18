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

Use "team": null for a player who is now a free agent.

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


def load_manual_players(path: Path, player_names: dict[str, str]) -> dict[str, str]:
    """
    Return {synthetic_id: display_name} for players with no replay data.

    These are players we want on rosters before they have a Steam ID or any
    replays (data/players/manual_players.json). Each gets a stable synthetic id
    ("manual:<lowercase name>"). Names already in the registry are skipped, so
    once a player has real data the manual entry becomes a harmless no-op.
    """
    if not path.is_file():
        return {}
    existing = {n.lower() for n in player_names.values()}
    out: dict[str, str] = {}
    for entry in json.loads(path.read_text()).get("players", []):
        name = str(entry.get("name", "")).strip()
        if not name:
            logger.warning("Skipping manual player with no name: %s", entry)
            continue
        if name.lower() in existing:
            logger.info("Manual player %r already in registry; skipping", name)
            continue
        out[f"manual:{name.lower()}"] = name
        existing.add(name.lower())
    return out


def resolve_team(team: str | None, known_teams: set[str]) -> str | None:
    """
    Map an override's free-text team to the canonical spelling.

    Applies the alias map, then matches case-insensitively against teams that
    already have an Elo rating so "Wildcard" inherits WILDCARD's rating. Unknown
    teams are returned unchanged (they start at the default rating).
    """
    from src.data_collection.team_aliases import canonical_team

    if team is None:
        return None
    name = canonical_team(team) or team
    by_upper = {t.upper(): t for t in known_teams}
    return by_upper.get(" ".join(name.split()).upper(), name)


def merge_rosters(
    rosters: dict[str, list[str]],
    before: pd.DataFrame,
    after: pd.DataFrame,
    player_names: dict[str, str],
) -> dict[str, list[str]]:
    """
    Apply overrides to a team → [display names] roster map.

    Players whose team changed between `before` (replay-derived) and `after`
    (overrides applied) are removed from their old roster and added to the new
    one. Lists are sorted case-insensitively.
    """
    old = dict(zip(before["player_id"], before["team_name"]))
    new = dict(zip(after["player_id"], after["team_name"]))
    out = {team: list(names) for team, names in rosters.items()}
    for pid, team in new.items():
        name = player_names.get(pid)
        team = None if pd.isna(team) else team
        if name is None or old.get(pid) == team:
            continue
        prev = old.get(pid)
        if prev in out and name in out[prev]:
            out[prev].remove(name)
        if team is None:  # free agent: leaves the old roster, joins none
            continue
        out.setdefault(team, [])
        if name not in out[team]:
            out[team].append(name)
    return {t: sorted(n, key=str.lower) for t, n in out.items() if n}


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
        for field in ("player", "effective"):
            if not str(o.get(field, "")).strip():
                problems.append(f"{label}: missing '{field}'")
        # "team": null is allowed and means free agent; the key must still exist.
        if "team" not in o or (o["team"] is not None and not str(o["team"]).strip()):
            problems.append(f"{label}: missing 'team' (use null for a free agent)")
        try:
            pd.Timestamp(o.get("effective"))
        except (ValueError, TypeError):
            problems.append(f"{label}: 'effective' is not a valid date")
        ids = by_name.get(str(o.get("player", "")).lower(), [])
        if not ids:
            problems.append(f"{label}: unknown player")
        elif len(ids) > 1:
            problems.append(f"{label}: ambiguous name, matches {len(ids)} players")

    seen: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for i, o in enumerate(overrides):
        key = (str(o.get("player", "")).lower(), str(o.get("effective", "")))
        seen.setdefault(key, []).append((i, str(o.get("team") or "").strip().upper()))
    for (player, effective), entries in seen.items():
        if not player or len(entries) < 2:
            continue
        idx = ", ".join(str(i) for i, _ in entries)
        if len({t for _, t in entries}) > 1:
            problems.append(
                f"{player!r} on {effective}: conflicting teams in overrides[{idx}]"
            )
        else:
            problems.append(f"{player!r} on {effective}: duplicate entries overrides[{idx}]")
    return problems


def apply_roster_overrides(
    player_teams_df: pd.DataFrame,
    player_names: dict[str, str],
    overrides: list[dict],
    known_teams: set[str] | None = None,
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
        if len(ids) != 1 or "team" not in o:
            logger.warning("Skipping invalid roster override: %s", o)
            continue
        team = o["team"]
        if team is not None and not str(team).strip():
            logger.warning("Skipping invalid roster override: %s", o)
            continue
        teams[ids[0]] = resolve_team(
            None if team is None else str(team).strip(), known_teams or set()
        )

    # dtype=object keeps free agents as None (pandas would otherwise turn it into NaN)
    return pd.DataFrame(
        {"player_id": list(teams), "team_name": list(teams.values())}, dtype=object
    )
