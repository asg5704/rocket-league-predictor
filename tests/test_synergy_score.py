"""
tests/test_synergy_score.py

Unit tests for src/models/synergy_score.py.
All tests use small synthetic DataFrames — no file I/O except save/load.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.synergy_score import SynergyScoreModel, _build_team_trios, _attach_archetypes
from src.models.win_probability import WinProbabilityModel, FEATURE_COLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_player_stats(match_ids: list[str], trios: dict) -> pd.DataFrame:
    """
    Build a player_stats DataFrame from a mapping of
    match_id → {"blue": [p1, p2, p3], "orange": [p4, p5, p6]}.
    """
    rows = []
    for match_id in match_ids:
        for side, players in trios[match_id].items():
            for player_id in players:
                rows.append({"match_id": match_id, "player_id": player_id, "team_side": side})
    return pd.DataFrame(rows)


def _make_features(match_ids: list[str], winners: list[str], seed: int = 0) -> pd.DataFrame:
    """Build a minimal features DataFrame with valid FEATURE_COLS values."""
    rng = np.random.default_rng(seed)
    n = len(match_ids)
    data = {col: rng.normal(0, 1, size=n) for col in FEATURE_COLS}
    data["match_id"] = match_ids
    data["winner"] = winners
    return pd.DataFrame(data)


def _make_fitted_win_model(features_df: pd.DataFrame) -> WinProbabilityModel:
    """
    Return a fitted WinProbabilityModel (XGBoost, no CalibratedClassifierCV so
    no minimum-per-class-per-fold constraint).  Synergy tests care about the
    mechanics, not the model type.
    """
    model = WinProbabilityModel(model_type="xgboost")
    model.fit(features_df)
    return model


def _make_archetypes(player_ids: list[str], archetypes: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"player_id": player_ids, "archetype": archetypes})


# ---------------------------------------------------------------------------
# Fixed scenario: 3 matches, 2 trios each side
#
# Match m1: blue=(A,B,C) vs orange=(D,E,F) — blue wins
# Match m2: blue=(A,B,C) vs orange=(D,E,F) — blue wins
# Match m3: blue=(D,E,F) vs orange=(A,B,C) — blue wins → orange (A,B,C) loses
# So trio ABC: 2 wins out of 3 matches → actual_win_rate = 2/3
# ---------------------------------------------------------------------------

MATCH_IDS = ["m1", "m2", "m3"]
TRIOS = {
    "m1": {"blue": ["A", "B", "C"], "orange": ["D", "E", "F"]},
    "m2": {"blue": ["A", "B", "C"], "orange": ["D", "E", "F"]},
    "m3": {"blue": ["D", "E", "F"], "orange": ["A", "B", "C"]},
}
# ABC wins m1 (blue); loses m2 (blue, orange wins); loses m3 (orange)
# ABC win rate = 1/3; DEF win rate = 2/3
# y = [1, 0, 1] — both classes present for logistic regression
WINNERS = ["blue", "orange", "blue"]


@pytest.fixture
def basic_data():
    features_df = _make_features(MATCH_IDS, WINNERS, seed=1)
    player_stats_df = _make_player_stats(MATCH_IDS, TRIOS)
    win_model = _make_fitted_win_model(features_df)
    return features_df, player_stats_df, win_model


# ---------------------------------------------------------------------------
# _build_team_trios
# ---------------------------------------------------------------------------

class TestBuildTeamTrios:
    def test_returns_one_row_per_match_side(self):
        ps = _make_player_stats(MATCH_IDS, TRIOS)
        trios = _build_team_trios(ps)
        # 3 matches × 2 sides = 6 rows
        assert len(trios) == 6

    def test_trio_is_sorted(self):
        ps = _make_player_stats(MATCH_IDS, TRIOS)
        trios = _build_team_trios(ps)
        for trio in trios["trio"]:
            assert list(trio) == sorted(trio)

    def test_excludes_incomplete_sides(self):
        ps = _make_player_stats(MATCH_IDS, TRIOS)
        # Remove one player from m1 orange side → that side has only 2 players
        ps = ps[~((ps["match_id"] == "m1") & (ps["player_id"] == "D"))]
        trios = _build_team_trios(ps)
        # m1 orange is now excluded
        assert len(trios) == 5
        m1_orange = trios[(trios["match_id"] == "m1") & (trios["team_side"] == "orange")]
        assert len(m1_orange) == 0

    def test_correct_trio_for_known_match(self):
        ps = _make_player_stats(MATCH_IDS, TRIOS)
        trios = _build_team_trios(ps)
        m1_blue = trios[(trios["match_id"] == "m1") & (trios["team_side"] == "blue")]
        assert m1_blue["trio"].values[0] == tuple(sorted(["A", "B", "C"]))


# ---------------------------------------------------------------------------
# SynergyScoreModel.fit
# ---------------------------------------------------------------------------

class TestSynergyFit:
    def test_returns_self(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        result = model.fit(features_df, player_stats_df, win_model)
        assert result is model

    def test_results_has_expected_columns(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        required = {
            "trio", "player_a", "player_b", "player_c",
            "n_matches", "actual_win_rate", "mean_p_win", "synergy", "low_sample",
        }
        assert required.issubset(set(df.columns))

    def test_one_row_per_trio(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        assert df["trio"].nunique() == len(df)

    def test_synergy_equals_actual_minus_predicted(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        expected = (df["actual_win_rate"] - df["mean_p_win"]).round(10)
        actual = df["synergy"].round(10)
        pd.testing.assert_series_equal(expected, actual, check_names=False)

    def test_actual_win_rate_in_unit_interval(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        assert (df["actual_win_rate"] >= 0).all()
        assert (df["actual_win_rate"] <= 1).all()

    def test_mean_p_win_in_unit_interval(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        assert (df["mean_p_win"] >= 0).all()
        assert (df["mean_p_win"] <= 1).all()

    def test_results_sorted_by_synergy_descending(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        assert (df["synergy"].diff().dropna() <= 0).all()

    def test_low_sample_flag(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        # min_matches=4 → all trios (3 matches each) are low_sample
        model = SynergyScoreModel(min_matches=4)
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        assert df["low_sample"].all()

    def test_no_low_sample_when_threshold_met(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel(min_matches=3)
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        assert not df["low_sample"].any()

    def test_correct_win_count_for_known_trio(self, basic_data):
        """ABC wins m1 (blue), loses m2 (blue, orange won), loses m3 (orange). win_rate = 1/3."""
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()

        abc_trio = tuple(sorted(["A", "B", "C"]))
        abc_row = df[df["trio"] == abc_trio]
        assert len(abc_row) == 1
        assert abc_row["n_matches"].values[0] == 3
        assert abs(abc_row["actual_win_rate"].values[0] - 1 / 3) < 1e-9

    def test_p_win_perspective_flipped_for_orange(self, basic_data):
        """P(win) for an orange-side trio = 1 - P(blue wins)."""
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)

        # Compute expected mean_p_win for DEF manually:
        # m1: DEF is orange → p_win_DEF = 1 - P(blue wins m1)
        # m2: DEF is orange → p_win_DEF = 1 - P(blue wins m2)
        # m3: DEF is blue   → p_win_DEF = P(blue wins m3)
        p_blue = win_model.predict_proba(features_df)
        idx = {mid: i for i, mid in enumerate(features_df["match_id"])}
        p_def = [
            1 - p_blue[idx["m1"]],
            1 - p_blue[idx["m2"]],
            p_blue[idx["m3"]],
        ]
        expected_mean_p_win = float(np.mean(p_def))

        def_trio = tuple(sorted(["D", "E", "F"]))
        df = model.results()
        def_row = df[df["trio"] == def_trio]
        assert abs(def_row["mean_p_win"].values[0] - expected_mean_p_win) < 1e-9

    def test_null_proba_matches_excluded(self):
        """Matches where the model returns NaN P(win) should not count."""
        # 4 matches; m4 gets a NaN feature → model returns NaN → excluded from synergy
        # Non-NaN matches have y=[1,0,1] (both classes) so logistic can fit
        match_ids = ["m1", "m2", "m3", "m4"]
        trios_map = {mid: {"blue": ["A", "B", "C"], "orange": ["D", "E", "F"]} for mid in match_ids}
        winners = ["blue", "orange", "blue", "blue"]

        features_df = _make_features(match_ids, winners)
        # Inject NaN into m4 so the model returns NaN for that match
        features_df.loc[features_df["match_id"] == "m4", FEATURE_COLS[0]] = np.nan

        player_stats_df = _make_player_stats(match_ids, trios_map)
        # Fit the model only on non-NaN rows (m1, m2, m3) — y=[1,0,1] has both classes
        win_model = _make_fitted_win_model(features_df.dropna(subset=FEATURE_COLS))
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()

        abc_trio = tuple(sorted(["A", "B", "C"]))
        abc_row = df[df["trio"] == abc_trio]
        # m4 excluded (NaN) → only m1 (blue win), m2 (orange win→ABC loses), m3 (blue win→ABC wins)
        # n_matches = 3, wins = m1 + m3 = 2 → actual_win_rate = 2/3
        assert abc_row["n_matches"].values[0] == 3
        assert abs(abc_row["actual_win_rate"].values[0] - 2 / 3) < 1e-9


# ---------------------------------------------------------------------------
# Archetype attachment
# ---------------------------------------------------------------------------

class TestArchetypeAttachment:
    def test_archetype_columns_present_when_provided(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        archetypes_df = _make_archetypes(
            ["A", "B", "C", "D", "E", "F"],
            ["striker", "anchor", "flex", "striker", "anchor", "flex"],
        )
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model, archetypes_df)
        df = model.results()
        for col in ("archetype_a", "archetype_b", "archetype_c", "archetype_combo"):
            assert col in df.columns

    def test_archetype_combo_is_sorted(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        archetypes_df = _make_archetypes(
            ["A", "B", "C", "D", "E", "F"],
            ["striker", "anchor", "flex", "striker", "anchor", "flex"],
        )
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model, archetypes_df)
        df = model.results()
        for combo in df["archetype_combo"].dropna():
            parts = combo.split("+")
            assert parts == sorted(parts)

    def test_missing_player_gets_unknown_archetype(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        # Only provide archetypes for A, B, C — not D, E, F
        archetypes_df = _make_archetypes(["A", "B", "C"], ["striker", "anchor", "flex"])
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model, archetypes_df)
        df = model.results()

        def_trio = tuple(sorted(["D", "E", "F"]))
        def_row = df[df["trio"] == def_trio]
        assert def_row["archetype_combo"].values[0] == "unknown+unknown+unknown"

    def test_archetype_columns_none_when_not_provided(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        df = model.results()
        for col in ("archetype_a", "archetype_b", "archetype_c", "archetype_combo"):
            assert df[col].isna().all()


# ---------------------------------------------------------------------------
# SynergyScoreModel.score (lookup)
# ---------------------------------------------------------------------------

class TestSynergyScore:
    def test_score_known_trio(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        record = model.score(["A", "B", "C"])
        assert "synergy" in record
        assert record["n_matches"] == 3

    def test_score_order_independent(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        r1 = model.score(["A", "B", "C"])
        r2 = model.score(["C", "A", "B"])
        assert r1["synergy"] == r2["synergy"]

    def test_score_unknown_trio_raises_key_error(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        with pytest.raises(KeyError):
            model.score(["X", "Y", "Z"])

    def test_score_before_fit_raises(self):
        model = SynergyScoreModel()
        with pytest.raises(RuntimeError, match="fitted"):
            model.score(["A", "B", "C"])


# ---------------------------------------------------------------------------
# archetype_summary
# ---------------------------------------------------------------------------

class TestArchetypeSummary:
    def test_summary_before_fit_raises(self):
        model = SynergyScoreModel()
        with pytest.raises(RuntimeError, match="fitted"):
            model.archetype_summary()

    def test_summary_without_archetypes_returns_empty(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        summary = model.archetype_summary()
        assert len(summary) == 0

    def test_summary_with_archetypes(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        archetypes_df = _make_archetypes(
            ["A", "B", "C", "D", "E", "F"],
            ["striker", "anchor", "flex", "striker", "anchor", "flex"],
        )
        model = SynergyScoreModel(min_matches=1)
        model.fit(features_df, player_stats_df, win_model, archetypes_df)
        summary = model.archetype_summary()
        assert isinstance(summary, pd.DataFrame)
        assert "mean_synergy" in summary.columns
        assert "n_trios" in summary.columns


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_load_roundtrip(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)
        original = model.results()

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = Path(f.name)

        model.save(path)
        loaded = SynergyScoreModel.load(path)
        restored = loaded.results()

        pd.testing.assert_frame_equal(original.reset_index(drop=True), restored.reset_index(drop=True))
        path.unlink()

    def test_save_before_fit_raises(self):
        model = SynergyScoreModel()
        with tempfile.NamedTemporaryFile(suffix=".pkl") as f:
            with pytest.raises(RuntimeError, match="fitted"):
                model.save(f.name)

    def test_loaded_model_score_lookup_works(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel()
        model.fit(features_df, player_stats_df, win_model)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = Path(f.name)

        model.save(path)
        loaded = SynergyScoreModel.load(path)
        record = loaded.score(["A", "B", "C"])
        assert "synergy" in record
        path.unlink()

    def test_loaded_model_preserves_min_matches(self, basic_data):
        features_df, player_stats_df, win_model = basic_data
        model = SynergyScoreModel(min_matches=7)
        model.fit(features_df, player_stats_df, win_model)

        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            path = Path(f.name)

        model.save(path)
        loaded = SynergyScoreModel.load(path)
        assert loaded.min_matches == 7
        path.unlink()
