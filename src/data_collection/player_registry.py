"""
player_registry.py

Loads pro_players_raw.json and provides query methods for player lookups,
team roster reconstruction, and RLCS split resolution.

Ballchasing stores Steam IDs without the "steam:" prefix, so this module
handles adding it automatically when building API query parameters.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# RLCS split calendar
# Dates are approximate based on official RLCS event calendars.
# Each entry covers the regional league play through the Major/World Champ.
# ---------------------------------------------------------------------------

RLCS_SPLITS: list[dict] = [
    {"season": "2021-22", "split": "Fall",               "start": "2021-09-01", "end": "2021-12-12"},
    {"season": "2021-22", "split": "Winter",             "start": "2022-01-07", "end": "2022-03-20"},
    {"season": "2021-22", "split": "Spring",             "start": "2022-04-01", "end": "2022-06-26"},
    {"season": "2021-22", "split": "World Championship", "start": "2022-08-03", "end": "2022-08-14"},
    {"season": "2022-23", "split": "Fall",               "start": "2022-09-02", "end": "2022-12-04"},
    {"season": "2022-23", "split": "Winter",             "start": "2023-01-06", "end": "2023-03-19"},
    {"season": "2022-23", "split": "Spring",             "start": "2023-03-31", "end": "2023-06-18"},
    {"season": "2022-23", "split": "World Championship", "start": "2023-08-03", "end": "2023-08-13"},
    {"season": "2023-24", "split": "Fall",               "start": "2023-09-01", "end": "2023-12-03"},
    {"season": "2023-24", "split": "Winter",             "start": "2024-01-05", "end": "2024-03-17"},
    {"season": "2023-24", "split": "Spring",             "start": "2024-04-05", "end": "2024-06-16"},
    {"season": "2023-24", "split": "World Championship", "start": "2024-07-25", "end": "2024-08-04"},
    {"season": "2024-25", "split": "Fall",               "start": "2024-09-06", "end": "2024-12-01"},
    {"season": "2024-25", "split": "Winter",             "start": "2025-01-10", "end": "2025-03-16"},
    {"season": "2024-25", "split": "Spring",             "start": "2025-04-04", "end": "2025-06-15"},
    {"season": "2024-25", "split": "World Championship", "start": "2025-07-24", "end": "2025-08-03"},
]


def _parse_date(value: str | date) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


class PlayerRegistry:
    """
    Query interface over pro_players_raw.json.

    Example
    -------
    registry = PlayerRegistry.load("data/players/pro_players_raw.json")

    player   = registry.get_player("76561198960239428")
    api_id   = registry.api_player_id("76561198960239428")   # "steam:76561198960239428"
    team     = registry.get_player_team("76561198960239428", "2024-03-01")
    roster   = registry.get_team_roster("karmine-corp", "2024-03-01")
    split    = registry.get_rlcs_split("2024-03-01")
    """

    def __init__(self, players: list[dict], meta: dict) -> None:
        self.meta = meta
        self._by_id: dict[str, dict] = {p["platform_id"]: p for p in players}
        # Secondary index: lowercase display name → list of platform_ids
        self._by_name: dict[str, list[str]] = {}
        for p in players:
            for name in p.get("display_names", []):
                self._by_name.setdefault(name.lower(), []).append(p["platform_id"])

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> "PlayerRegistry":
        """Load from a pro_players_raw.json file."""
        with open(path) as f:
            data = json.load(f)
        return cls(players=data["players"], meta=data.get("meta", {}))

    # ------------------------------------------------------------------
    # Player lookups
    # ------------------------------------------------------------------

    def get_player(self, platform_id: str) -> Optional[dict]:
        """Return the full player record for a platform ID, or None."""
        return self._by_id.get(platform_id)

    def find_by_name(self, display_name: str) -> list[dict]:
        """
        Search players by display name (case-insensitive).
        Returns a list because IGN collisions are possible across eras.
        """
        ids = self._by_name.get(display_name.lower(), [])
        return [self._by_id[pid] for pid in ids]

    def all_players(self) -> list[dict]:
        """Return all player records."""
        return list(self._by_id.values())

    # ------------------------------------------------------------------
    # API ID helpers
    # ------------------------------------------------------------------

    def api_player_id(self, platform_id: str) -> str:
        """
        Return the platform ID formatted for the Ballchasing API player-id
        filter. Ballchasing stores Steam IDs without a prefix but the API's
        filter parameter requires "steam:<id>".
        """
        if ":" in platform_id:
            return platform_id  # already prefixed
        return f"steam:{platform_id}"

    def all_api_player_ids(self) -> list[str]:
        """Return all platform IDs with the steam: prefix, ready for API calls."""
        return [self.api_player_id(pid) for pid in self._by_id]

    # ------------------------------------------------------------------
    # Team / roster queries  (date-aware)
    # ------------------------------------------------------------------

    def get_player_team(
        self, platform_id: str, as_of: str | date
    ) -> Optional[dict]:
        """
        Return the team_history entry a player was on at a given date,
        or None if they had no active roster spot then.
        """
        player = self._by_id.get(platform_id)
        if not player:
            return None

        target = _parse_date(as_of)
        for stint in player.get("team_history", []):
            if "date_from" not in stint:
                continue  # skip entries not yet migrated to the date format
            date_from = _parse_date(stint["date_from"])
            date_to = _parse_date(stint["date_to"]) if stint.get("date_to") else date.today()
            if date_from <= target <= date_to:
                return stint
        return None

    def get_team_roster(
        self, team_id: str, as_of: str | date
    ) -> list[dict]:
        """
        Return all players rostered on a team on a given date.
        Each entry is the full player record with `active_stint` added.
        """
        roster = []
        for player in self._by_id.values():
            for stint in player.get("team_history", []):
                if stint.get("team_id") != team_id:
                    continue
                if "date_from" not in stint:
                    continue  # skip entries not yet migrated to the date format
                date_from = _parse_date(stint["date_from"])
                date_to = _parse_date(stint["date_to"]) if stint.get("date_to") else date.today()
                target = _parse_date(as_of)
                if date_from <= target <= date_to:
                    roster.append({**player, "active_stint": stint})
                    break
        return roster

    def get_region_players(self, region: str, as_of: str | date) -> list[dict]:
        """Return all players active in a given region on a given date."""
        result = []
        for player in self._by_id.values():
            stint = self.get_player_team(player["platform_id"], as_of)
            if stint and stint.get("region", "").upper() == region.upper():
                result.append({**player, "active_stint": stint})
        return result

    # ------------------------------------------------------------------
    # RLCS split resolution
    # ------------------------------------------------------------------

    @staticmethod
    def get_rlcs_split(date_str: str | date) -> Optional[dict]:
        """
        Return the RLCS split a date falls within, or None if between events.

        Returns a dict with keys: season, split, start, end.
        """
        target = _parse_date(date_str)
        for split in RLCS_SPLITS:
            if _parse_date(split["start"]) <= target <= _parse_date(split["end"]):
                return split
        return None

    def get_players_in_split(self, season: str, split: str) -> list[dict]:
        """
        Return all players who were active on any team during a given
        RLCS split, based on their team_history date ranges.

        E.g. registry.get_players_in_split("2023-24", "Fall")
        """
        split_meta = next(
            (s for s in RLCS_SPLITS if s["season"] == season and s["split"] == split),
            None,
        )
        if not split_meta:
            raise ValueError(f"Unknown split: {season} {split}")

        split_start = _parse_date(split_meta["start"])
        split_end = _parse_date(split_meta["end"])

        result = []
        for player in self._by_id.values():
            for stint in player.get("team_history", []):
                if "date_from" not in stint:
                    continue  # skip entries not yet migrated to the date format
                date_from = _parse_date(stint["date_from"])
                date_to = _parse_date(stint["date_to"]) if stint.get("date_to") else date.today()
                # Active if their stint overlaps with the split window at all
                if date_from <= split_end and date_to >= split_start:
                    result.append({**player, "active_stint": stint})
                    break
        return result

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._by_id)

    def __repr__(self) -> str:
        return f"PlayerRegistry({len(self)} players)"


if __name__ == "__main__":
    registry = PlayerRegistry.load("data/players/pro_players_raw.json")
    print(registry)

    print("\nAll API player IDs:")
    for api_id in registry.all_api_player_ids():
        print(f"  {api_id}")

    print("\nVatira's team on 2024-03-01:")
    vatira_id = "76561198960239428"
    print(f"  {registry.get_player_team(vatira_id, '2024-03-01')}")

    print("\nKarmine Corp roster on 2024-03-01:")
    for p in registry.get_team_roster("karmine-corp", "2024-03-01"):
        print(f"  {p['display_names'][0]} ({p['real_name']})")

    print("\nRLCS split for 2024-03-01:")
    print(f"  {registry.get_rlcs_split('2024-03-01')}")
