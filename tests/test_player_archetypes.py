"""
tests/test_player_archetypes.py

Unit tests for src/models/player_archetypes.py.
All tests use small synthetic DataFrames — no file I/O except save/load.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.player_archetypes import (
    STAT_COLS,
    PlayerArchetypeModel,
    _assign_archetype_names,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player_stats(n_players: int = 30, games_per_player: int = 8, seed: int = 0) -> pd.DataFrame:
    """
    Synthetic player_stats DataFrame with three distinct clusters:
      - strikers   (player_id 0..9)  : high goals/shots
      - anchors    (player_id 10..19): high saves
      - flex       (player_id 20..29): balanced
    """
    rng = np.random.default_rng(seed)
    rows = []

    for player_idx in range(n_players):
        player_id = str(player_idx)
        for _ in range(games_per_player):
            if player_idx < 10:       # striker
                goals, saves, shots = rng.normal(1.2, 0.2), rng.normal(0.5, 0.2), rng.normal(4.0, 0.3)
            elif player_idx < 20:     # anchor
                goals, saves, shots = rng.normal(0.3, 0.2), rng.normal(2.5, 0.2), rng.normal(1.5, 0.3)
            else:                     # flex
                goals, saves, shots = rng.normal(0.7, 0.2), rng.normal(1.2, 0.2), rng.normal(2.5, 0.3)

            row: dict = {
                "match_id": f"match_{rng.integers(0, 1000)}",
                "player_id": player_id,
                "team_side": rng.choice(["blue", "orange"]),
                "playlist_type": "3v3",
                "goals": max(0, goals),
                "assists": max(0, rng.normal(0.4, 0.2)),
                "saves": max(0, saves),
                "shots": max(0, shots),
                "score": max(0, rng.normal(350, 50)),
                "shooting_pct": max(0, rng.normal(20, 5)),
                "demos_inflicted": max(0, rng.normal(1, 0.3)),
                "demos_taken": max(0, rng.normal(1, 0.3)),
                "boost_avg": max(0, rng.normal(48, 3)),
                "boost_bcpm": max(0, rng.normal(430, 30)),
                "boost_amount_stolen": max(0, rng.normal(600, 80)),
                "boost_percent_zero": max(0, rng.normal(11, 2)),
                "boost_percent_full": max(0, rng.normal(10, 2)),
                "movement_avg_speed": max(0, rng.normal(1560, 50)),
                "movement_percent_supersonic": max(0, rng.normal(17, 2)),
                "movement_percent_high_air": max(0, rng.normal(8, 1)),
                "movement_percent_ground": max(0, rng.normal(53, 2)),
                "positioning_avg_dist_to_ball": max(0, rng.normal(2850, 100)),
                "positioning_percent_defensive_third": max(0, rng.normal(48, 3)),
                "positioning_percent_offensive_third": max(0, rng.normal(20, 3)),
                "positioning_percent_behind_ball": max(0, rng.normal(71, 3)),
                "positioning_percent_most_back": max(0, rng.normal(35, 3)),
            }
            rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# _assign_archetype_names
# ---------------------------------------------------------------------------

class TestAssignArchetypeNames:
    def test_basic_assignment(self):
        # 3 centroids: [goals_idx=0, saves_idx=2]
        # Cluster 0: goals high → striker
        # Cluster 1: saves high → anchor
        # Cluster 2: balanced → flex
        centroids = np.array([
            [2.0, 0, 0.5, 0],   # cluster 0: high goals
            [0.3, 0, 2.5, 0],   # cluster 1: high saves
            [0.7, 0, 1.2, 0],   # cluster 2: balanced
        ])
        feature_names = ["goals", "assists", "saves", "shots"]
        mapping = _assign_archetype_names(centroids, feature_names)

        assert mapping[0] == "striker"
        assert mapping[1] == "anchor"
        assert mapping[2] == "flex"

    def test_all_archetypes_assigned(self):
        centroids = np.array([
            [0.5, 0.5, 2.0, 0],  # anchor first
            [1.5, 0.5, 0.3, 0],  # striker second
            [0.8, 0.5, 1.0, 0],  # flex third
        ])
        mapping = _assign_archetype_names(centroids, ["goals", "assists", "saves", "shots"])
        assert set(mapping.values()) == {"striker", "anchor", "flex"}

    def test_no_duplicate_assignments(self):
        rng = np.random.default_rng(99)
        centroids = rng.standard_normal((3, len(STAT_COLS)))
        mapping = _assign_archetype_names(centroids, STAT_COLS)
        assert len(set(mapping.values())) == 3


# ---------------------------------------------------------------------------
# PlayerArchetypeModel — fit_predict
# ---------------------------------------------------------------------------

class TestFitPredict:
    def test_returns_dataframe(self):
        df = _make_player_stats()
        model = PlayerArchetypeModel(min_games=5)
        result = model.fit_predict(df)
        assert isinstance(result, pd.DataFrame)

    def test_output_columns(self):
        df = _make_player_stats()
        model = PlayerArchetypeModel(min_games=5)
        result = model.fit_predict(df)
        required = {"player_id", "archetype", "archetype_id", "n_games"} | set(STAT_COLS)
        assert required.issubset(set(result.columns))

    def test_one_row_per_player(self):
        df = _make_player_stats(n_players=30)
        model = PlayerArchetypeModel(min_games=5)
        result = model.fit_predict(df)
        assert len(result) == 30
        assert result["player_id"].nunique() == 30

    def test_archetype_values(self):
        df = _make_player_stats()
        model = PlayerArchetypeModel(min_games=5)
        result = model.fit_predict(df)
        valid = {"striker", "anchor", "flex", "unknown"}
        assert set(result["archetype"].unique()).issubset(valid)

    def test_unknown_for_low_game_players(self):
        df = _make_player_stats(n_players=30, games_per_player=8)
        # Add two 1-game players
        sparse = _make_player_stats(n_players=2, games_per_player=1, seed=99)
        sparse["player_id"] = ["sparse_a", "sparse_b"]
        combined = pd.concat([df, sparse], ignore_index=True)

        model = PlayerArchetypeModel(min_games=5)
        result = model.fit_predict(combined)
        sparse_rows = result[result["player_id"].isin(["sparse_a", "sparse_b"])]
        assert (sparse_rows["archetype"] == "unknown").all()
        assert (sparse_rows["archetype_id"] == -1).all()

    def test_stats_are_career_averages(self):
        """Each row's stat values should equal the mean over that player's games."""
        df = _make_player_stats(n_players=5, games_per_player=8)
        model = PlayerArchetypeModel(min_games=1)
        result = model.fit_predict(df)

        for pid in df["player_id"].unique():
            expected_goals = df[df["player_id"] == pid]["goals"].mean()
            actual_goals = result[result["player_id"] == pid]["goals"].values[0]
            assert abs(expected_goals - actual_goals) < 1e-9

    def test_three_distinct_clusters_recovered(self):
        """With clearly separated clusters, all three archetypes should be present."""
        df = _make_player_stats(n_players=30, games_per_player=10, seed=7)
        model = PlayerArchetypeModel(min_games=5)
        result = model.fit_predict(df)
        named = result[result["archetype"] != "unknown"]["archetype"].unique()
        assert set(named) == {"striker", "anchor", "flex"}


# ---------------------------------------------------------------------------
# PlayerArchetypeModel — predict (unseen data)
# ---------------------------------------------------------------------------

class TestPredict:
    def test_predict_before_fit_raises(self):
        model = PlayerArchetypeModel()
        df = _make_player_stats(n_players=5)
        with pytest.raises(RuntimeError, match="fitted"):
            model.predict(df)

    def test_predict_returns_same_schema(self):
        train = _make_player_stats(n_players=30, seed=0)
        test = _make_player_stats(n_players=5, seed=99)
        # Ensure different player IDs
        test["player_id"] = test["player_id"].apply(lambda x: f"new_{x}")

        model = PlayerArchetypeModel(min_games=5)
        model.fit_predict(train)
        result = model.predict(test)

        required = {"player_id", "archetype", "archetype_id", "n_games"} | set(STAT_COLS)
        assert required.issubset(set(result.columns))

    def test_predict_archetype_values(self):
        train = _make_player_stats(n_players=30, seed=0)
        test = _make_player_stats(n_players=10, seed=55)
        test["player_id"] = test["player_id"].apply(lambda x: f"t_{x}")

        model = PlayerArchetypeModel(min_games=5)
        model.fit_predict(train)
        result = model.predict(test)

        valid = {"striker", "anchor", "flex", "unknown"}
        assert set(result["archetype"].unique()).issubset(valid)


# ---------------------------------------------------------------------------
# PlayerArchetypeModel — silhouette_score
# ---------------------------------------------------------------------------

class TestSilhouetteScore:
    def test_returns_float_in_range(self):
        df = _make_player_stats(n_players=30, games_per_player=8)
        model = PlayerArchetypeModel(min_games=5)
        model.fit_predict(df)
        sil = model.silhouette_score(df)
        assert isinstance(sil, float)
        assert -1.0 <= sil <= 1.0

    def test_raises_before_fit(self):
        model = PlayerArchetypeModel()
        df = _make_player_stats()
        with pytest.raises(RuntimeError):
            model.silhouette_score(df)

    def test_separated_clusters_have_positive_silhouette(self):
        """Clearly separated clusters should yield positive silhouette."""
        df = _make_player_stats(n_players=30, games_per_player=10, seed=7)
        model = PlayerArchetypeModel(min_games=5)
        model.fit_predict(df)
        sil = model.silhouette_score(df)
        assert sil > 0


# ---------------------------------------------------------------------------
# PlayerArchetypeModel — archetype_summary
# ---------------------------------------------------------------------------

class TestArchetypeSummary:
    def test_returns_dataframe_indexed_by_archetype(self):
        df = _make_player_stats(n_players=30)
        model = PlayerArchetypeModel(min_games=5)
        arc = model.fit_predict(df)
        summary = model.archetype_summary(arc)

        assert isinstance(summary, pd.DataFrame)
        assert summary.index.name == "archetype"
        assert set(summary.columns) == set(STAT_COLS)

    def test_excludes_unknown(self):
        df = _make_player_stats(n_players=30, games_per_player=8)
        model = PlayerArchetypeModel(min_games=5)
        arc = model.fit_predict(df)
        summary = model.archetype_summary(arc)
        assert "unknown" not in summary.index


# ---------------------------------------------------------------------------
# PlayerArchetypeModel — save / load
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_load_roundtrip(self):
        df = _make_player_stats(n_players=30, games_per_player=8)
        model = PlayerArchetypeModel(min_games=5)
        original_result = model.fit_predict(df)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = Path(f.name)

        model.save(path)
        loaded = PlayerArchetypeModel.load(path)
        loaded_result = loaded.predict(df)

        # Archetype assignments should be identical
        merged = original_result.merge(loaded_result, on="player_id", suffixes=("_orig", "_load"))
        assert (merged["archetype_orig"] == merged["archetype_load"]).all()

        path.unlink()

    def test_save_before_fit_raises(self):
        model = PlayerArchetypeModel()
        with tempfile.NamedTemporaryFile(suffix=".pkl") as f:
            with pytest.raises(RuntimeError, match="fitted"):
                model.save(f.name)

    def test_loaded_model_hyperparams(self):
        df = _make_player_stats(n_players=30, games_per_player=8)
        model = PlayerArchetypeModel(method="kmeans", n_clusters=3, min_games=5)
        model.fit_predict(df)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = Path(f.name)

        model.save(path)
        loaded = PlayerArchetypeModel.load(path)

        assert loaded.method == "kmeans"
        assert loaded.n_clusters == 3
        assert loaded.min_games == 5

        path.unlink()


# ---------------------------------------------------------------------------
# GMM method
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method", ["kmeans", "gmm"])
class TestBothMethods:
    def test_fit_predict_works(self, method):
        df = _make_player_stats(n_players=30, games_per_player=8)
        model = PlayerArchetypeModel(method=method, min_games=5)
        result = model.fit_predict(df)
        assert len(result) == 30
        valid = {"striker", "anchor", "flex", "unknown"}
        assert set(result["archetype"].unique()).issubset(valid)

    def test_silhouette_score_works(self, method):
        df = _make_player_stats(n_players=30, games_per_player=8)
        model = PlayerArchetypeModel(method=method, min_games=5)
        model.fit_predict(df)
        sil = model.silhouette_score(df)
        assert -1.0 <= sil <= 1.0
