"""
tests/test_win_probability.py

Unit tests for src/models/win_probability.py.
All tests use small synthetic DataFrames — no file I/O.
"""

import math
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.models.win_probability import (
    FEATURE_COLS,
    TARGET_COL,
    WinProbabilityModel,
    _encode_target,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_features(n: int = 40, seed: int = 0) -> pd.DataFrame:
    """
    Synthetic feature DataFrame with a learnable signal:
    positive diff_goals → blue wins, negative → orange wins.
    """
    rng = np.random.default_rng(seed)
    diff_goals = rng.normal(0, 0.5, size=n)
    winner = np.where(diff_goals > 0, "blue", "orange")

    df = pd.DataFrame(
        {
            # core
            "diff_goals": diff_goals,
            "diff_assists": rng.normal(0, 0.3, size=n),
            "diff_saves": rng.normal(0, 0.8, size=n),
            "diff_shots": rng.normal(0, 1.0, size=n),
            "diff_score": rng.normal(0, 80, size=n),
            "diff_shooting_pct": rng.normal(0, 5, size=n),
            # demo
            "diff_demos_inflicted": rng.normal(0, 0.5, size=n),
            "diff_demos_taken": rng.normal(0, 0.5, size=n),
            # boost
            "diff_boost_avg": rng.normal(0, 2.5, size=n),
            "diff_boost_bcpm": rng.normal(0, 30, size=n),
            "diff_boost_amount_stolen": rng.normal(0, 50, size=n),
            "diff_boost_percent_zero": rng.normal(0, 3, size=n),
            "diff_boost_percent_full": rng.normal(0, 3, size=n),
            # movement
            "diff_movement_avg_speed": rng.normal(0, 100, size=n),
            "diff_movement_percent_supersonic": rng.normal(0, 3, size=n),
            "diff_movement_percent_high_air": rng.normal(0, 2, size=n),
            # positioning
            "diff_positioning_avg_dist_to_ball": rng.normal(0, 200, size=n),
            "diff_positioning_percent_defensive_third": rng.normal(0, 3, size=n),
            "diff_positioning_percent_behind_ball": rng.normal(0, 3, size=n),
            # h2h
            "blue_h2h_win_rate": rng.uniform(0, 1, size=n),
            "h2h_matches_played": rng.integers(0, 10, size=n),
            # elo
            "elo_diff": rng.normal(0, 100, size=n),
            TARGET_COL: winner,
        }
    )
    return df


def _make_features_with_nulls(n: int = 50, null_frac: float = 0.1) -> pd.DataFrame:
    df = _make_features(n)
    rng = np.random.default_rng(99)
    null_mask = rng.random(size=(n, len(FEATURE_COLS))) < null_frac
    for i, col in enumerate(FEATURE_COLS):
        df.loc[null_mask[:, i], col] = np.nan
    return df


# ---------------------------------------------------------------------------
# _encode_target
# ---------------------------------------------------------------------------

class TestEncodeTarget:
    def test_blue_is_one(self):
        s = pd.Series(["blue", "orange", "blue"])
        assert list(_encode_target(s)) == [1, 0, 1]

    def test_all_orange(self):
        s = pd.Series(["orange", "orange"])
        assert list(_encode_target(s)) == [0, 0]


# ---------------------------------------------------------------------------
# WinProbabilityModel.fit / predict_proba
# ---------------------------------------------------------------------------

class TestFitPredict:
    @pytest.fixture(params=["logistic", "xgboost"])
    def model(self, request):
        m = WinProbabilityModel(model_type=request.param)
        m.fit(_make_features(60))
        return m

    def test_predict_proba_shape(self, model):
        df = _make_features(10)
        proba = model.predict_proba(df)
        assert proba.shape == (10,)

    def test_predict_proba_range(self, model):
        df = _make_features(20)
        proba = model.predict_proba(df)
        assert np.all((proba >= 0) & (proba <= 1))

    def test_predict_proba_null_rows_are_nan(self, model):
        df = _make_features(5)
        df.loc[2, "diff_goals"] = np.nan
        proba = model.predict_proba(df)
        assert math.isnan(proba[2])
        assert not math.isnan(proba[0])

    def test_raises_if_not_fitted(self):
        model = WinProbabilityModel()
        with pytest.raises(RuntimeError, match="not been fitted"):
            model.predict_proba(_make_features(5))

    def test_higher_diff_goals_predicts_blue(self):
        """With a learnable dataset, strong positive diff_goals should → blue."""
        df = _make_features(80, seed=1)
        model = WinProbabilityModel(model_type="logistic")
        model.fit(df)

        strong_blue = _make_features(5)
        strong_blue["diff_goals"] = 2.0   # clear blue advantage
        strong_orange = _make_features(5)
        strong_orange["diff_goals"] = -2.0  # clear orange advantage

        assert model.predict_proba(strong_blue).mean() > 0.5
        assert model.predict_proba(strong_orange).mean() < 0.5


# ---------------------------------------------------------------------------
# WinProbabilityModel.cross_validate
# ---------------------------------------------------------------------------

class TestCrossValidate:
    @pytest.fixture(params=["logistic", "xgboost"])
    def scores(self, request):
        model = WinProbabilityModel(model_type=request.param)
        return model.cross_validate(_make_features(80), cv=3)

    def test_returns_expected_keys(self, scores):
        expected = {
            "accuracy", "accuracy_std",
            "roc_auc", "roc_auc_std",
            "log_loss", "log_loss_std",
            "n_samples", "cv_folds",
        }
        assert set(scores.keys()) == expected

    def test_accuracy_in_valid_range(self, scores):
        assert 0.0 <= scores["accuracy"] <= 1.0

    def test_roc_auc_in_valid_range(self, scores):
        assert 0.0 <= scores["roc_auc"] <= 1.0

    def test_log_loss_positive(self, scores):
        assert scores["log_loss"] > 0

    def test_n_samples_matches_non_null_rows(self):
        df = _make_features_with_nulls(300)
        model = WinProbabilityModel(model_type="logistic")
        scores = model.cross_validate(df, cv=3)
        expected_n = df[FEATURE_COLS].notnull().all(axis=1).sum()
        assert scores["n_samples"] == expected_n

    def test_cv_folds_recorded(self, scores):
        assert scores["cv_folds"] == 3


# ---------------------------------------------------------------------------
# WinProbabilityModel.save / load
# ---------------------------------------------------------------------------

class TestSaveLoad:
    @pytest.fixture(params=["logistic", "xgboost"])
    def fitted_model(self, request):
        m = WinProbabilityModel(model_type=request.param)
        m.fit(_make_features(40))
        return m

    def test_save_load_roundtrip(self, fitted_model, tmp_path):
        path = tmp_path / "model.pkl"
        fitted_model.save(path)

        loaded = WinProbabilityModel.load(path)
        assert loaded.model_type == fitted_model.model_type

        df = _make_features(10)
        original_proba = fitted_model.predict_proba(df)
        loaded_proba = loaded.predict_proba(df)
        np.testing.assert_allclose(original_proba, loaded_proba)

    def test_save_raises_if_not_fitted(self, tmp_path):
        model = WinProbabilityModel()
        with pytest.raises(RuntimeError, match="not been fitted"):
            model.save(tmp_path / "model.pkl")

    def test_load_preserves_model_type(self, fitted_model, tmp_path):
        path = tmp_path / "model.pkl"
        fitted_model.save(path)
        loaded = WinProbabilityModel.load(path)
        assert loaded.model_type == fitted_model.model_type
