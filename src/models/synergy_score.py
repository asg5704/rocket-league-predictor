"""
synergy_score.py

Compute Synergy Score for every player trio observed in the dataset.

Synergy Score = actual_win_rate − mean(P(win))

Where:
  - actual_win_rate  is the fraction of matches the trio won
  - mean(P(win))     is the mean predicted win probability from the logistic model

A positive synergy means the trio wins more than their rolling stats predict.
A negative synergy means they underperform. Zero means the model fully explains
their results.

Entry point
-----------
    win_model = WinProbabilityModel.load("data/models/win_probability_logistic.pkl")
    synergy_model = SynergyScoreModel()
    synergy_df = synergy_model.fit(
        features_df,
        player_stats_df,
        win_prob_model=win_model,
        archetypes_df=archetypes_df,   # optional
    )

    # Look up a known trio
    score = synergy_model.score(["player_a_id", "player_b_id", "player_c_id"])

    synergy_model.save("data/models/synergy_score.pkl")

Output columns (synergy_df)
----------------------------
    trio             — tuple of 3 sorted player_ids (canonical key)
    player_a/b/c     — individual player IDs (alphabetical order)
    n_matches        — number of matches played together (with valid features)
    actual_win_rate  — fraction of those matches the trio won
    mean_p_win       — mean model-predicted P(win) across those matches
    synergy          — actual_win_rate − mean_p_win
    archetype_a/b/c  — archetype labels (if archetypes_df provided, else None)
    archetype_combo  — sorted archetype labels joined by "+", e.g. "anchor+flex+striker"

Notes
-----
- Only matches with non-null P(win) from the win probability model are counted.
  Matches with null features (e.g. first appearance, rolling window warmup)
  do not contribute to either actual_win_rate or mean_p_win.
- Trios with n_matches < min_matches are included but flagged via a
  `low_sample` boolean column.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import joblib
import numpy as np
import pandas as pd

from src.models.win_probability import WinProbabilityModel


class SynergyScoreModel:
    """
    Compute and store synergy scores for all observed player trios.

    Parameters
    ----------
    min_matches : int
        Trios with fewer matches are included but flagged as low_sample=True.
        Default 3.
    """

    def __init__(self, min_matches: int = 3):
        self.min_matches = min_matches
        self._synergy_df: Optional[pd.DataFrame] = None
        self._trio_index: Optional[dict[tuple, dict]] = None

    # ------------------------------------------------------------------
    # Fit
    # ------------------------------------------------------------------

    def fit(
        self,
        features_df: pd.DataFrame,
        player_stats_df: pd.DataFrame,
        win_prob_model: WinProbabilityModel,
        archetypes_df: Optional[pd.DataFrame] = None,
    ) -> "SynergyScoreModel":
        """
        Compute synergy for every trio observed in features_df.

        Parameters
        ----------
        features_df      : DataFrame from features.parquet / build_features()
        player_stats_df  : DataFrame from player_stats.parquet
        win_prob_model   : Fitted WinProbabilityModel (logistic recommended)
        archetypes_df    : Optional DataFrame from player_archetypes.parquet
                           (needs player_id and archetype columns)

        Returns
        -------
        self (for chaining)
        """
        # Step 1 — get P(blue wins) for every match
        p_blue = win_prob_model.predict_proba(features_df)
        match_proba = features_df[["match_id", "winner"]].copy()
        match_proba["p_blue_wins"] = p_blue

        # Drop matches where the model returned NaN (incomplete rolling features)
        match_proba = match_proba[match_proba["p_blue_wins"].notna()].copy()

        # Step 2 — build (match_id, team_side, trio) mapping
        team_trios = _build_team_trios(player_stats_df)

        # Step 3 — join proba onto team observations
        obs = match_proba.merge(team_trios, on="match_id", how="inner")

        # Step 4 — from each team's perspective: did they win? what was P(win)?
        obs["won"] = obs["winner"] == obs["team_side"]
        obs["p_win"] = np.where(
            obs["team_side"] == "blue",
            obs["p_blue_wins"],
            1.0 - obs["p_blue_wins"],
        )

        # Step 5 — aggregate per trio
        agg = (
            obs.groupby("trio")
            .agg(
                n_matches=("won", "count"),
                actual_win_rate=("won", "mean"),
                mean_p_win=("p_win", "mean"),
            )
            .reset_index()
        )
        agg["synergy"] = agg["actual_win_rate"] - agg["mean_p_win"]
        agg["low_sample"] = agg["n_matches"] < self.min_matches

        # Step 6 — expand trio tuple into individual player columns
        agg[["player_a", "player_b", "player_c"]] = pd.DataFrame(
            agg["trio"].tolist(), index=agg.index
        )

        # Step 7 — attach archetype labels if provided
        if archetypes_df is not None:
            agg = _attach_archetypes(agg, archetypes_df)
        else:
            for col in ("archetype_a", "archetype_b", "archetype_c", "archetype_combo"):
                agg[col] = None

        self._synergy_df = agg.sort_values("synergy", ascending=False).reset_index(drop=True)
        self._trio_index = {row["trio"]: row for _, row in self._synergy_df.iterrows()}

        return self

    # ------------------------------------------------------------------
    # Lookup / scoring
    # ------------------------------------------------------------------

    def score(self, player_ids: list[str]) -> dict:
        """
        Return the synergy record for a known trio.

        Parameters
        ----------
        player_ids : list of 3 player IDs (order doesn't matter)

        Returns
        -------
        dict with keys: trio, n_matches, actual_win_rate, mean_p_win, synergy,
                        archetype_combo, low_sample

        Raises
        ------
        KeyError if the trio has no match history in the fitted data.
        RuntimeError if the model has not been fitted.
        """
        self._require_fit()
        trio = tuple(sorted(player_ids))
        if trio not in self._trio_index:
            raise KeyError(
                f"Trio {trio} not found. Only trios seen during fit() are available."
            )
        return dict(self._trio_index[trio])

    def results(self) -> pd.DataFrame:
        """Return the full synergy DataFrame sorted by synergy descending."""
        self._require_fit()
        return self._synergy_df.copy()

    def archetype_summary(self) -> pd.DataFrame:
        """
        Mean synergy grouped by archetype_combo.

        Useful for asking: "does striker+anchor+flex outperform other combos?"
        Only includes trios with archetype labels and n_matches >= min_matches.
        """
        self._require_fit()
        df = self._synergy_df
        df = df[(df["archetype_combo"].notna()) & (~df["low_sample"])]
        return (
            df.groupby("archetype_combo")
            .agg(
                n_trios=("synergy", "count"),
                mean_synergy=("synergy", "mean"),
                mean_n_matches=("n_matches", "mean"),
            )
            .sort_values("mean_synergy", ascending=False)
            .round(4)
        )

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        self._require_fit()
        joblib.dump(
            {
                "min_matches": self.min_matches,
                "synergy_df": self._synergy_df,
                "trio_index": self._trio_index,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "SynergyScoreModel":
        data = joblib.load(path)
        obj = cls(min_matches=data["min_matches"])
        obj._synergy_df = data["synergy_df"]
        obj._trio_index = data["trio_index"]
        return obj

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _require_fit(self) -> None:
        if self._synergy_df is None:
            raise RuntimeError("Model has not been fitted. Call fit() first.")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _build_team_trios(player_stats_df: pd.DataFrame) -> pd.DataFrame:
    """
    Return a DataFrame with one row per (match_id, team_side) containing
    the canonical trio tuple (sorted player_ids).

    Only includes sides with exactly 3 players.
    """
    counts = (
        player_stats_df.groupby(["match_id", "team_side"])
        .size()
        .reset_index(name="n")
    )
    valid = counts[counts["n"] == 3][["match_id", "team_side"]]

    trios = (
        player_stats_df.merge(valid, on=["match_id", "team_side"])
        .groupby(["match_id", "team_side"])["player_id"]
        .apply(lambda x: tuple(sorted(x)))
        .reset_index()
        .rename(columns={"player_id": "trio"})
    )
    return trios


def _attach_archetypes(
    agg: pd.DataFrame,
    archetypes_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Join archetype labels for player_a, player_b, player_c.

    Builds archetype_combo as a sorted, "+"-joined string of the three labels.
    Players not present in archetypes_df (e.g. unknown) get label "unknown".
    """
    label_map = archetypes_df.set_index("player_id")["archetype"].to_dict()

    for col, player_col in [("archetype_a", "player_a"), ("archetype_b", "player_b"), ("archetype_c", "player_c")]:
        agg[col] = agg[player_col].map(label_map).fillna("unknown")

    agg["archetype_combo"] = agg.apply(
        lambda r: "+".join(sorted([r["archetype_a"], r["archetype_b"], r["archetype_c"]])),
        axis=1,
    )
    return agg


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    features_path = Path("data/processed/features.parquet")
    player_stats_path = Path("data/processed/player_stats.parquet")
    archetypes_path = Path("data/processed/player_archetypes.parquet")
    model_path = Path("data/models/win_probability_logistic.pkl")
    output_path = Path("data/processed/synergy_scores.parquet")
    save_path = Path("data/models/synergy_score.pkl")

    features_df = pd.read_parquet(features_path)
    player_stats_df = pd.read_parquet(player_stats_path)
    archetypes_df = pd.read_parquet(archetypes_path)
    win_model = WinProbabilityModel.load(model_path)

    print(f"Loaded {len(features_df)} matches, {len(player_stats_df)} player rows")
    print(f"Win probability model: {win_model.model_type}\n")

    synergy_model = SynergyScoreModel(min_matches=3)
    synergy_df = synergy_model.fit(
        features_df, player_stats_df, win_model, archetypes_df
    ).results()

    print(f"Computed synergy for {len(synergy_df)} trios\n")

    print("=== Top 10 trios by synergy ===")
    print(synergy_df.head(10)[["player_a", "player_b", "player_c", "n_matches", "actual_win_rate", "mean_p_win", "synergy", "archetype_combo"]].to_string(index=False))
    print()

    print("=== Bottom 10 trios by synergy ===")
    print(synergy_df.tail(10)[["player_a", "player_b", "player_c", "n_matches", "actual_win_rate", "mean_p_win", "synergy", "archetype_combo"]].to_string(index=False))
    print()

    print("=== Synergy by archetype combo ===")
    print(synergy_model.archetype_summary().to_string())
    print()

    # Distribution summary
    print("=== Synergy distribution ===")
    print(synergy_df["synergy"].describe().round(4).to_string())
    print(f"\nTrios with synergy > 0:  {(synergy_df['synergy'] > 0).sum()}")
    print(f"Trios with synergy < 0:  {(synergy_df['synergy'] < 0).sum()}")
    print(f"Low-sample trios:        {synergy_df['low_sample'].sum()}")

    synergy_df.to_parquet(output_path, index=False)
    synergy_model.save(save_path)
    print(f"\nSynergy scores → {output_path}")
    print(f"Model → {save_path}")

    # Persist summary
    summary = {
        "n_trios": len(synergy_df),
        "synergy_mean": float(synergy_df["synergy"].mean()),
        "synergy_std": float(synergy_df["synergy"].std()),
        "synergy_max": float(synergy_df["synergy"].max()),
        "synergy_min": float(synergy_df["synergy"].min()),
        "low_sample_trios": int(synergy_df["low_sample"].sum()),
    }
    with open(Path("data/models/synergy_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
