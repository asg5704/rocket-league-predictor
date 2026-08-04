"""
player_archetypes.py

Cluster RLCS pro players into archetypes using their career stat averages.

Entry point
-----------
    model = PlayerArchetypeModel()
    archetypes_df = model.fit_predict(player_stats_df)
    model.save("data/models/player_archetypes.pkl")

    model = PlayerArchetypeModel.load("data/models/player_archetypes.pkl")
    labels = model.predict(new_stats_df)

Output columns (archetypes_df)
-------------------------------
    player_id       — Steam ID
    archetype       — "striker" | "anchor" | "flex"
    archetype_id    — 0 | 1 | 2  (stable cluster index)
    n_games         — games used for career averages
    + all 22 normalized career-average stat columns

Archetype semantics
-------------------
    striker — high goals, shots, offensive positioning; lower saves
    anchor  — high saves, defensive positioning; lower goals
    flex    — balanced; elevated assists, boost efficiency

Model selection
---------------
    k=3 K-Means (default, best silhouette in typical RL data)
    GMM (alternative) — softer assignments, useful for borderline players

Persistence
-----------
    model.save("path.pkl")
    model = PlayerArchetypeModel.load("path.pkl")
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

ClusterMethod = Literal["kmeans", "gmm"]

# The 22 per-game stat dimensions to cluster on
STAT_COLS = [
    "goals",
    "assists",
    "saves",
    "shots",
    "score",
    "shooting_pct",
    "demos_inflicted",
    "demos_taken",
    "boost_avg",
    "boost_bcpm",
    "boost_amount_stolen",
    "boost_percent_zero",
    "boost_percent_full",
    "movement_avg_speed",
    "movement_percent_supersonic",
    "movement_percent_high_air",
    "movement_percent_ground",
    "positioning_avg_dist_to_ball",
    "positioning_percent_defensive_third",
    "positioning_percent_offensive_third",
    "positioning_percent_behind_ball",
    "positioning_percent_most_back",
]

# Archetype name assignment: map a raw cluster label → semantic name.
# We determine the mapping post-fit by inspecting centroid values on these
# key dimensions.  The mapping is stored in the model for stable predict().
_KEY_DIMS = {
    "goals": "striker",    # highest goals → striker
    "saves": "anchor",     # highest saves → anchor
}


def _assign_archetype_names(
    centroids_scaled: np.ndarray,
    feature_names: list[str],
) -> dict[int, str]:
    """
    Map raw cluster indices to archetype labels by inspecting centroids.

    Logic (priority order):
      1. Cluster with highest mean 'goals' → "striker"
      2. Cluster with highest mean 'saves' → "anchor"
      3. Remaining cluster → "flex"

    Returns
    -------
    dict mapping cluster_id → archetype name
    """
    goals_idx = feature_names.index("goals")
    saves_idx = feature_names.index("saves")

    goals_by_cluster = centroids_scaled[:, goals_idx]
    saves_by_cluster = centroids_scaled[:, saves_idx]

    striker_id = int(np.argmax(goals_by_cluster))

    # Anchor: highest saves among remaining clusters
    saves_masked = saves_by_cluster.copy()
    saves_masked[striker_id] = -np.inf
    anchor_id = int(np.argmax(saves_masked))

    flex_id = next(
        i for i in range(len(centroids_scaled)) if i not in (striker_id, anchor_id)
    )

    return {striker_id: "striker", anchor_id: "anchor", flex_id: "flex"}


class PlayerArchetypeModel:
    """
    Cluster RLCS players into striker / anchor / flex archetypes.

    Parameters
    ----------
    method : "kmeans" | "gmm"
        Clustering algorithm.
    n_clusters : int
        Number of archetypes (default 3).
    random_state : int
        Reproducibility seed.
    min_games : int
        Minimum games a player must have to be included in clustering.
        Players below this threshold receive archetype="unknown".
        Default 5 — filters out substitute/fill players whose career stats
        are too noisy to cluster meaningfully.
    """

    def __init__(
        self,
        method: ClusterMethod = "kmeans",
        n_clusters: int = 3,
        random_state: int = 42,
        min_games: int = 5,
    ):
        self.method = method
        self.n_clusters = n_clusters
        self.random_state = random_state
        self.min_games = min_games

        self._scaler: StandardScaler | None = None
        self._clusterer: KMeans | GaussianMixture | None = None
        self._archetype_map: dict[int, str] | None = None  # cluster_id → name
        self._centroids_scaled: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Fit / predict
    # ------------------------------------------------------------------

    def fit_predict(self, player_stats_df: pd.DataFrame) -> pd.DataFrame:
        """
        Aggregate per-game stats → career averages, cluster, return results.

        Parameters
        ----------
        player_stats_df : DataFrame from player_stats.parquet

        Returns
        -------
        DataFrame with one row per player_id containing:
            player_id, archetype, archetype_id, n_games,
            + scaled career-average stat columns
        """
        career = self._aggregate_career_stats(player_stats_df)

        # Split into players with enough games and those below threshold
        eligible = career[career["n_games"] >= self.min_games].copy()
        ineligible = career[career["n_games"] < self.min_games].copy()

        X = eligible[STAT_COLS].to_numpy(dtype=float)

        # Fit scaler + clusterer on eligible players
        self._scaler = StandardScaler()
        X_scaled = self._scaler.fit_transform(X)

        self._clusterer = self._build_clusterer()
        raw_labels = self._clusterer.fit_predict(X_scaled)

        # Derive centroids for archetype naming (GMM uses means)
        if self.method == "kmeans":
            self._centroids_scaled = self._clusterer.cluster_centers_
        else:
            self._centroids_scaled = self._clusterer.means_

        self._archetype_map = _assign_archetype_names(
            self._centroids_scaled, STAT_COLS
        )

        eligible = eligible.copy()
        eligible["archetype_id"] = raw_labels
        eligible["archetype"] = eligible["archetype_id"].map(self._archetype_map)

        # Ineligible players get archetype "unknown"
        ineligible = ineligible.copy()
        ineligible["archetype_id"] = -1
        ineligible["archetype"] = "unknown"

        result = pd.concat([eligible, ineligible], ignore_index=True)
        cols = ["player_id", "archetype", "archetype_id", "n_games"] + STAT_COLS
        return result[cols]

    def predict(self, player_stats_df: pd.DataFrame) -> pd.DataFrame:
        """
        Assign archetypes to new players using a fitted model.

        Parameters
        ----------
        player_stats_df : DataFrame from player_stats.parquet

        Returns
        -------
        Same schema as fit_predict output.
        """
        if self._scaler is None or self._clusterer is None:
            raise RuntimeError("Model has not been fitted. Call fit_predict() first.")

        career = self._aggregate_career_stats(player_stats_df)
        eligible = career[career["n_games"] >= self.min_games].copy()
        ineligible = career[career["n_games"] < self.min_games].copy()

        result_rows = []

        if len(eligible) > 0:
            X_scaled = self._scaler.transform(eligible[STAT_COLS].to_numpy(dtype=float))
            raw_labels = self._clusterer.predict(X_scaled)
            eligible = eligible.copy()
            eligible["archetype_id"] = raw_labels
            eligible["archetype"] = eligible["archetype_id"].map(self._archetype_map)
            result_rows.append(eligible)

        if len(ineligible) > 0:
            ineligible = ineligible.copy()
            ineligible["archetype_id"] = -1
            ineligible["archetype"] = "unknown"
            result_rows.append(ineligible)

        result = pd.concat(result_rows, ignore_index=True) if result_rows else pd.DataFrame()
        cols = ["player_id", "archetype", "archetype_id", "n_games"] + STAT_COLS
        return result[cols]

    # ------------------------------------------------------------------
    # Evaluation helpers
    # ------------------------------------------------------------------

    def silhouette_score(self, player_stats_df: pd.DataFrame) -> float:
        """
        Compute silhouette score on the eligible (≥ min_games) players.

        Higher is better; range [-1, 1].
        """
        from sklearn.metrics import silhouette_score

        if self._scaler is None:
            raise RuntimeError("Model has not been fitted.")

        career = self._aggregate_career_stats(player_stats_df)
        eligible = career[career["n_games"] >= self.min_games]
        X_scaled = self._scaler.transform(eligible[STAT_COLS].to_numpy(dtype=float))
        labels = self._clusterer.predict(X_scaled)
        return float(silhouette_score(X_scaled, labels))

    def archetype_summary(self, archetypes_df: pd.DataFrame) -> pd.DataFrame:
        """
        Return mean career stats per archetype — useful for validation.

        Parameters
        ----------
        archetypes_df : output of fit_predict / predict
        """
        known = archetypes_df[archetypes_df["archetype"] != "unknown"]
        return known.groupby("archetype")[STAT_COLS].mean().round(3)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        if self._scaler is None:
            raise RuntimeError("Nothing to save — model has not been fitted.")
        joblib.dump(
            {
                "method": self.method,
                "n_clusters": self.n_clusters,
                "random_state": self.random_state,
                "min_games": self.min_games,
                "scaler": self._scaler,
                "clusterer": self._clusterer,
                "archetype_map": self._archetype_map,
                "centroids_scaled": self._centroids_scaled,
            },
            path,
        )

    @classmethod
    def load(cls, path: str | Path) -> "PlayerArchetypeModel":
        data = joblib.load(path)
        obj = cls(
            method=data["method"],
            n_clusters=data["n_clusters"],
            random_state=data["random_state"],
            min_games=data["min_games"],
        )
        obj._scaler = data["scaler"]
        obj._clusterer = data["clusterer"]
        obj._archetype_map = data["archetype_map"]
        obj._centroids_scaled = data["centroids_scaled"]
        return obj

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _aggregate_career_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Average each stat column per player_id; add n_games count."""
        agg = df.groupby("player_id")[STAT_COLS].mean()
        counts = df.groupby("player_id").size().rename("n_games")
        return agg.join(counts).reset_index()

    def _build_clusterer(self) -> KMeans | GaussianMixture:
        if self.method == "kmeans":
            return KMeans(
                n_clusters=self.n_clusters,
                random_state=self.random_state,
                n_init=20,
            )
        if self.method == "gmm":
            return GaussianMixture(
                n_components=self.n_clusters,
                random_state=self.random_state,
                n_init=10,
            )
        raise ValueError(f"Unknown method: {self.method!r}")


# ---------------------------------------------------------------------------
# CLI entry point — cluster, evaluate, and save
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    stats_path = Path("data/processed/player_stats.parquet")
    models_dir = Path("data/models")
    output_path = Path("data/processed/player_archetypes.parquet")
    models_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(stats_path)
    print(f"Loaded {len(df)} player-game rows ({df['player_id'].nunique()} unique players)\n")

    results = {}

    for method in ("kmeans", "gmm"):
        print(f"=== {method.upper()} ===")
        model = PlayerArchetypeModel(method=method)
        archetypes_df = model.fit_predict(df)
        sil = model.silhouette_score(df)

        dist = archetypes_df["archetype"].value_counts().to_dict()
        print(f"  Silhouette : {sil:.4f}")
        print(f"  Distribution : {dist}")
        print(f"  Archetype cluster IDs: {model._archetype_map}")
        print()
        print(model.archetype_summary(archetypes_df).to_string())
        print()

        save_path = models_dir / f"player_archetypes_{method}.pkl"
        model.save(save_path)
        print(f"  Saved → {save_path}\n")

        results[method] = {"silhouette": sil, "distribution": dist}

    # Save K-Means archetypes as the canonical output artifact
    kmeans_model = PlayerArchetypeModel(method="kmeans")
    archetypes_df = kmeans_model.fit_predict(df)
    archetypes_df.to_parquet(output_path, index=False)
    print(f"Archetypes → {output_path}")

    results_path = models_dir / "archetype_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results → {results_path}")
