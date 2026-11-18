"""
Team metadata: country and active/defunct status.

File format (data/processed/team_status.json), keyed by canonical team name:

    {
      "NRG ESPORTS": {"country": "us", "status": "active"},
      "VIRTUS.PRO":  {"country": "ru", "status": "defunct", "note": "disbanded"}
    }

- country : ISO 3166-1 alpha-2 code ("gb" for the UK; "uk" is accepted).
- status  : "active" (default) or "defunct". Defunct teams keep their Elo in the
            model (it is real history) but are listed apart from the ranking.
- note    : optional free text, ignored by the app.

Teams missing from the file are treated as active with no country.
Use the alias map (src/data_collection/team_aliases.py) for rebrands where the
same roster continues; use status "defunct" when a team's story ends.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

STATUSES = {"active", "defunct"}
_COUNTRY_FIXES = {"uk": "gb"}


@dataclass(frozen=True)
class TeamInfo:
    country: str | None = None
    status: str = "active"


def _country(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    code = raw.strip().lower()
    if len(code) != 2:
        return None
    return _COUNTRY_FIXES.get(code, code)


def load_team_info(path: Path) -> dict[str, TeamInfo]:
    """Read the status file; a missing file means every team is active."""
    if not path.is_file():
        return {}
    out: dict[str, TeamInfo] = {}
    for team, entry in json.loads(path.read_text()).items():
        if not isinstance(entry, dict):
            continue
        status = entry.get("status", "active")
        out[team] = TeamInfo(
            country=_country(entry.get("country")),
            status=status if status in STATUSES else "active",
        )
    return out


def validate_team_info(raw: dict, known_teams: set[str]) -> list[str]:
    """Return human-readable problems (empty list means the file is valid)."""
    problems: list[str] = []
    for team, entry in raw.items():
        if team not in known_teams:
            problems.append(f"{team!r}: not a team in the Elo ratings (alias or typo?)")
        if not isinstance(entry, dict):
            problems.append(f"{team!r}: entry must be an object")
            continue
        status = entry.get("status", "active")
        if status not in STATUSES:
            problems.append(f"{team!r}: status must be one of {sorted(STATUSES)}")
        country = entry.get("country")
        if country not in (None, "") and _country(country) is None:
            problems.append(f"{team!r}: country {country!r} is not a 2-letter code")
    return problems
