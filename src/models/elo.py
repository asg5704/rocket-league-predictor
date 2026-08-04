"""
elo.py

Elo rating system for Rocket League pro teams.

Ratings are computed chronologically from match history. Each team starts at
`initial_rating` (default 1500) and updates after every match using the
standard Elo formula with a fixed K-factor.

Formula
-------
    E_a = 1 / (1 + 10 ** ((R_b - R_a) / 400))   # expected win prob
    R_a' = R_a + K * (outcome - E_a)              # outcome: 1=win, 0=loss

Entry point
-----------
    model = EloModel(k_factor=32, initial_rating=1500)
    model.fit(matches_df)

    # Current ratings
    rating = model.rating("TEAM VITALITY")
    df = model.ratings_df()

    # Per-match ELO snapshot (for joining onto features — anti-leakage)
    elos = model.match_elos()   # columns: match_id, blue_elo, orange_elo, elo_diff

    model.save("data/models/elo.pkl")
    model = EloModel.load("data/models/elo.pkl")

Notes
-----
- `match_elos()` returns the rating of each team *before* the match was
  processed, so it is safe to use as a feature without data leakage.
- Teams absent from the training data are assigned `initial_rating` when
  `rating()` is called.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import pandas as pd


class EloModel:
    """
    Elo rating system for a fixed set of teams.

    Parameters
    ----------
    k_factor       : Controls rating volatility. Higher = faster adaptation.
    initial_rating : Starting rating for all teams (and unknown teams at
                     inference time).
    """

    def __init__(self, k_factor: float = 32.0, initial_rating: float = 1500.0):
        self.k_factor = k_factor
        self.initial_rating = initial_rating

        self._ratings: dict[str, float] = {}
        self._match_elos: Optional[pd.DataFrame] = None

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(self, matches: pd.DataFrame) -> "EloModel":
        """
        Process all matches chronologically and compute Elo ratings.

        Parameters
        ----------
        matches : DataFrame with columns:
                  match_id, date, blue_team_name, orange_team_name, winner
                  winner must be "blue" or "orange"

        Returns
        -------
        self (for chaining)
        """
        df = matches[
            ["match_id", "date", "blue_team_name", "orange_team_name", "winner"]
        ].copy()
        df["date"] = pd.to_datetime(df["date"], utc=True)
        df = df.sort_values("date").reset_index(drop=True)

        ratings: dict[str, float] = {}
        records = []

        for _, row in df.iterrows():
            blue = row["blue_team_name"]
            orange = row["orange_team_name"]

            r_blue = ratings.get(blue, self.initial_rating)
            r_orange = ratings.get(orange, self.initial_rating)

            e_blue = _expected(r_blue, r_orange)
            e_orange = 1.0 - e_blue

            outcome_blue = 1.0 if row["winner"] == "blue" else 0.0
            outcome_orange = 1.0 - outcome_blue

            records.append(
                {
                    "match_id": row["match_id"],
                    "blue_elo": r_blue,
                    "orange_elo": r_orange,
                    "elo_diff": r_blue - r_orange,
                }
            )

            ratings[blue] = r_blue + self.k_factor * (outcome_blue - e_blue)
            ratings[orange] = r_orange + self.k_factor * (outcome_orange - e_orange)

        self._ratings = ratings
        self._match_elos = pd.DataFrame(records)
        return self

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def rating(self, team_name: str) -> float:
        """Return the final Elo rating for a team after all fitted matches."""
        return self._ratings.get(team_name, self.initial_rating)

    def ratings_df(self) -> pd.DataFrame:
        """Return all final ratings as a sorted DataFrame (team_name, elo)."""
        self._require_fit()
        return (
            pd.DataFrame(
                list(self._ratings.items()), columns=["team_name", "elo"]
            )
            .sort_values("elo", ascending=False)
            .reset_index(drop=True)
        )

    def match_elos(self) -> pd.DataFrame:
        """
        Return per-match Elo snapshots taken *before* each match is processed.

        Columns: match_id, blue_elo, orange_elo, elo_diff

        Safe to join directly onto features for use as model inputs — no leakage.
        """
        self._require_fit()
        return self._match_elos.copy()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        self._require_fit()
        joblib.dump(
            {
                "k_factor": self.k_factor,
                "initial_rating": self.initial_rating,
                "ratings": self._ratings,
                "match_elos": self._match_elos,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "EloModel":
        data = joblib.load(path)
        obj = cls(k_factor=data["k_factor"], initial_rating=data["initial_rating"])
        obj._ratings = data["ratings"]
        obj._match_elos = data["match_elos"]
        return obj

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_fit(self) -> None:
        if self._match_elos is None:
            raise RuntimeError("Model has not been fitted. Call fit() first.")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _expected(rating_a: float, rating_b: float) -> float:
    """Standard Elo expected score for player A given ratings A and B."""
    return 1.0 / (1.0 + 10.0 ** ((rating_b - rating_a) / 400.0))


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    matches_path = Path("data/processed/matches.parquet")
    output_path = Path("data/processed/elo_ratings.parquet")
    model_path = Path("data/models/elo.pkl")

    matches = pd.read_parquet(matches_path)
    print(f"Loaded {len(matches)} matches from {matches_path}\n")

    model = EloModel(k_factor=32, initial_rating=1500)
    model.fit(matches)

    ratings_df = model.ratings_df()
    print("=== Final Elo Ratings ===")
    print(ratings_df.to_string(index=False))
    print()

    match_elos = model.match_elos()
    match_elos.to_parquet(output_path, index=False)
    print(f"Per-match Elo snapshots → {output_path}")

    model.save(model_path)
    print(f"Model → {model_path}")
