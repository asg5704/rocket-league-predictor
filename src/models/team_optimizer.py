"""
team_optimizer.py

Given a pool of candidate players, find the optimal 3-player lineup using a
combinatorial score that combines synergy, archetype balance, and ELO strength.

The scoring function for each candidate trio is:

    score = w_synergy  * synergy
          + w_archetype * archetype_bonus
          + w_elo       * normalized_elo

Where:
  synergy        — synergy score from SynergyScoreModel (0 if trio unseen)
  archetype_bonus — reward for balanced archetypes, penalty for imbalanced
  normalized_elo  — mean of the three players' own Elo ratings, z-scored
                    across all players in the pool

All C(n, 3) combos are evaluated; the top-k results are returned.

Entry point
-----------
    optimizer = TeamOptimizer(
        synergy_model=synergy_model,
        archetypes_df=archetypes_df,       # player_id, archetype columns
        player_teams_df=player_teams_df,   # player_id, team_name columns
        elo_model=elo_model,
    )

    results = optimizer.optimize(
        player_pool=["pid_1", "pid_2", ..., "pid_10"],
        top_k=5,
    )
    # Returns list of RankedLineup dicts, sorted by score descending.

Output (RankedLineup)
---------------------
    {
        "rank":            int,
        "players":         tuple[str, str, str],   # canonical sorted trio
        "score":           float,                  # composite score
        "synergy":         float,
        "archetype_combo": str,                    # e.g. "anchor+flex+striker"
        "archetype_bonus": float,
        "mean_elo":        float,
        "n_matches":       int,                    # 0 if trio never observed
        "low_sample":      bool,
    }

Notes
-----
- Trios not seen in SynergyScoreModel.fit() receive synergy=0 and
  low_sample=True (treat as neutral, not missing).
- ELO lookup is per-player (PlayerEloModel.rating). Players with no rating
  get elo_model.initial_rating.
- Weights are configurable at construction time.
"""

from __future__ import annotations

from itertools import combinations
from typing import Optional, TypedDict

import numpy as np
import pandas as pd

from src.models.elo import PlayerEloModel
from src.models.synergy_score import SynergyScoreModel

# Archetype bonus table — reward balanced, penalise stacked roles
_ARCHETYPE_BONUS: dict[str, float] = {
    "anchor+flex+striker": 0.10,   # textbook balanced lineup
    "anchor+flex+flex": 0.05,
    "flex+flex+striker": 0.05,
    "anchor+anchor+striker": 0.05,
    "anchor+striker+striker": 0.00,
    "flex+flex+flex": -0.05,
    "anchor+anchor+flex": -0.05,
    "anchor+anchor+anchor": -0.10,
    "striker+striker+striker": -0.10,
}

_DEFAULT_WEIGHTS = {
    "synergy": 1.0,
    "archetype": 0.5,
    "elo": 0.3,
}


class RankedLineup(TypedDict):
    rank: int
    players: tuple[str, str, str]
    score: float
    synergy: float
    archetype_combo: str
    archetype_bonus: float
    mean_elo: float
    n_matches: int
    low_sample: bool


class TeamOptimizer:
    """
    Combinatorial team optimizer.

    Parameters
    ----------
    synergy_model   : Fitted SynergyScoreModel
    archetypes_df   : DataFrame with columns [player_id, archetype]
    player_teams_df : DataFrame with columns [player_id, team_name].
                      Kept for API compatibility; Elo no longer depends on team.
    elo_model       : Optional fitted PlayerEloModel. When absent, ELO term is zero.
    weights         : Dict with keys "synergy", "archetype", "elo".
                      Controls relative importance of each component.
    """

    def __init__(
        self,
        synergy_model: SynergyScoreModel,
        archetypes_df: pd.DataFrame,
        player_teams_df: pd.DataFrame,
        elo_model: Optional[PlayerEloModel] = None,
        weights: Optional[dict[str, float]] = None,
    ):
        self._synergy = synergy_model
        self._archetype_map: dict[str, str] = (
            archetypes_df.set_index("player_id")["archetype"].to_dict()
        )
        self._team_map: dict[str, str] = (
            player_teams_df.set_index("player_id")["team_name"].to_dict()
        )
        self._elo = elo_model
        self._weights = dict(_DEFAULT_WEIGHTS)
        if weights:
            self._weights.update(weights)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def optimize(
        self,
        player_pool: list[str],
        top_k: int = 5,
        weights: Optional[dict[str, float]] = None,
    ) -> list[RankedLineup]:
        """
        Find the top-k lineups from a pool of candidate players.

        Parameters
        ----------
        player_pool : list of player_ids to consider (order doesn't matter)
        top_k       : number of results to return (default 5)
        weights     : optional per-call weight override — dict with keys
                      "synergy", "archetype", "elo". Falls back to the
                      instance weights set at construction time.

        Returns
        -------
        List of RankedLineup dicts sorted by composite score descending.
        """
        if len(player_pool) < 3:
            raise ValueError(
                f"player_pool must contain at least 3 players, got {len(player_pool)}"
            )

        active_weights = dict(self._weights)
        if weights:
            active_weights.update(weights)

        pool_elos = self._pool_elos(player_pool)
        elo_mean = np.mean(list(pool_elos.values()))
        elo_std = np.std(list(pool_elos.values())) or 1.0

        results = []
        for trio in combinations(sorted(player_pool), 3):
            entry = self._score_trio(trio, pool_elos, elo_mean, elo_std, active_weights)
            results.append(entry)

        results.sort(key=lambda x: x["score"], reverse=True)

        ranked = []
        for i, entry in enumerate(results[:top_k]):
            entry["rank"] = i + 1
            ranked.append(entry)

        return ranked

    def score_trio(self, player_ids: list[str]) -> RankedLineup:
        """
        Score a specific trio regardless of the pool.

        Useful for evaluating a single lineup in isolation.
        """
        if len(player_ids) != 3:
            raise ValueError("Exactly 3 player IDs required.")

        trio = tuple(sorted(player_ids))
        pool_elos = self._pool_elos(list(trio))
        elo_mean = np.mean(list(pool_elos.values()))
        elo_std = 1.0  # no normalisation in isolation mode
        entry = self._score_trio(trio, pool_elos, elo_mean, elo_std, self._weights)
        entry["rank"] = 1
        return entry

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _pool_elos(self, player_pool: list[str]) -> dict[str, float]:
        """Return each player's own Elo rating (unknown players get the initial rating)."""
        if self._elo is None:
            return {pid: 0.0 for pid in player_pool}
        return {pid: self._elo.rating(pid) for pid in player_pool}

    def _score_trio(
        self,
        trio: tuple[str, str, str],
        pool_elos: dict[str, float],
        elo_mean: float,
        elo_std: float,
        weights: Optional[dict[str, float]] = None,
    ) -> RankedLineup:
        # Synergy
        try:
            syn_record = self._synergy.score(list(trio))
            synergy = float(syn_record["synergy"])
            n_matches = int(syn_record["n_matches"])
            low_sample = bool(syn_record["low_sample"])
        except KeyError:
            synergy = 0.0
            n_matches = 0
            low_sample = True

        # Archetype
        archetypes = [self._archetype_map.get(pid, "unknown") for pid in trio]
        archetype_combo = "+".join(sorted(archetypes))
        archetype_bonus = _ARCHETYPE_BONUS.get(archetype_combo, 0.0)

        # ELO (z-scored within pool so scale matches synergy)
        trio_elos = [pool_elos[pid] for pid in trio]
        mean_elo = float(np.mean(trio_elos))
        elo_z = (mean_elo - elo_mean) / elo_std

        # Composite
        w = weights if weights is not None else self._weights
        score = (
            w["synergy"] * synergy
            + w["archetype"] * archetype_bonus
            + w["elo"] * elo_z
        )

        return RankedLineup(
            rank=0,  # filled in by caller
            players=trio,
            score=round(score, 6),
            synergy=round(synergy, 6),
            archetype_combo=archetype_combo,
            archetype_bonus=round(archetype_bonus, 6),
            mean_elo=round(mean_elo, 2),
            n_matches=n_matches,
            low_sample=low_sample,
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from pathlib import Path

    import joblib

    from src.models.win_probability import WinProbabilityModel

    synergy_path = Path("data/models/synergy_score.pkl")
    archetypes_path = Path("data/processed/player_archetypes.parquet")
    player_stats_path = Path("data/processed/player_stats.parquet")
    elo_path = Path("data/models/elo.pkl")

    from pathlib import Path as _Path
    matches_path = _Path("data/processed/matches.parquet")

    synergy_model = SynergyScoreModel.load(synergy_path)
    archetypes_df = pd.read_parquet(archetypes_path)
    player_stats_df = pd.read_parquet(player_stats_path)
    matches_df = pd.read_parquet(matches_path)
    elo_model = PlayerEloModel.load(elo_path)

    # Build player → team_name from most recent match appearance
    # team_side tells us blue/orange; join onto matches to get the name
    merged = player_stats_df[["match_id", "player_id", "team_side"]].merge(
        matches_df[["match_id", "blue_team_name", "orange_team_name"]],
        on="match_id",
    )
    merged["team_name"] = merged.apply(
        lambda r: r["blue_team_name"] if r["team_side"] == "blue" else r["orange_team_name"],
        axis=1,
    )
    player_teams = (
        merged.sort_values("match_id")
        .groupby("player_id")["team_name"]
        .last()
        .reset_index()
    )

    optimizer = TeamOptimizer(
        synergy_model=synergy_model,
        archetypes_df=archetypes_df,
        player_teams_df=player_teams,
        elo_model=elo_model,
    )

    # Demo: use all known players as the pool
    known_players = archetypes_df["player_id"].tolist()
    print(f"Player pool size: {len(known_players)}")
    print(f"Possible trios: {len(known_players) * (len(known_players)-1) * (len(known_players)-2) // 6:,}\n")

    results = optimizer.optimize(known_players, top_k=10)

    print("=== Top 10 lineups ===")
    for r in results:
        print(
            f"#{r['rank']:2d}  score={r['score']:+.4f}  "
            f"synergy={r['synergy']:+.4f}  "
            f"archetype={r['archetype_combo']:30s}  "
            f"elo={r['mean_elo']:.0f}  "
            f"matches={r['n_matches']}  "
            f"players={r['players']}"
        )
