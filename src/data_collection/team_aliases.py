"""
team_aliases.py

Canonical team names.

Ballchasing team names are free text typed per upload, so one organisation can
appear under several spellings (e.g. "NRG" and "NRG ESPORTS"). Because Elo,
rolling features, head-to-head history and the leaderboard are all keyed on the
team-name string, every alias must be collapsed to one canonical name *before*
any of them run.

Add new aliases to ALIASES (alias -> canonical, both uppercase). Lookup is
case- and whitespace-insensitive. Canonical names are the org's full name.

Usage
-----
    from src.data_collection.team_aliases import canonical_team
    canonical_team("gk esports")   # -> "GEEKAY ESPORTS"
    canonical_team(None)           # -> None

Existing data is rewritten with:
    python -m src.data_collection.team_aliases
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

ALIASES: dict[str, str] = {
    "GK ESPORTS": "GEEKAY ESPORTS",
    "MAN CITY": "MANCHESTER CITY",
    "NRG": "NRG ESPORTS",
    "MIBR": "MADE IN BRAZIL",
    "MAN CITY ESPORTS": "MANCHESTER CITY",
    "TSM": "WOLVES ESPORTS"
}


def canonical_team(name: Optional[str]) -> Optional[str]:
    """Return the canonical form of a team name (None passes through)."""
    if name is None:
        return None
    key = " ".join(name.split()).upper()
    return ALIASES.get(key, name)


def normalize_matches(path: Path) -> int:
    """Rewrite team-name columns of a matches parquet in place. Returns rows changed."""
    import pandas as pd

    df = pd.read_parquet(path)
    changed = 0
    for col in ("blue_team_name", "orange_team_name"):
        new = df[col].map(canonical_team)
        changed += int((new != df[col]).sum())
        df[col] = new
    df.to_parquet(path, index=False)
    return changed


if __name__ == "__main__":
    p = Path("data/processed/matches.parquet")
    print(f"{normalize_matches(p)} team-name cells rewritten in {p}")
