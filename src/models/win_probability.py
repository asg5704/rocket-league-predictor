"""
win_probability.py

Train and evaluate a match win-probability model for Rocket League pro matches.

Entry point
-----------
    model = WinProbabilityModel()
    model.fit(features_df)
    proba = model.predict_proba(features_df)   # P(blue wins), shape (n,)
    scores = model.cross_validate(features_df) # dict of mean ± std metrics

The model outputs P(blue wins) ∈ [0, 1]. Calibrated probabilities are
required downstream for computing Synergy Score residuals.

Model types
-----------
    "logistic"  — LogisticRegression with mean imputation (interpretable baseline)
    "xgboost"   — XGBClassifier with native NaN handling (main model)

Persistence
-----------
    model.save("data/models/win_probability.pkl")
    model = WinProbabilityModel.load("data/models/win_probability.pkl")
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

ModelType = Literal["logistic", "xgboost"]

FEATURE_COLS = [
    # core differentials
    "diff_goals",
    "diff_assists",
    "diff_saves",
    "diff_shots",
    "diff_score",
    "diff_shooting_pct",
    # demo differentials
    "diff_demos_inflicted",
    "diff_demos_taken",
    # boost differentials
    "diff_boost_avg",
    "diff_boost_bcpm",
    "diff_boost_amount_stolen",
    "diff_boost_percent_zero",
    "diff_boost_percent_full",
    # movement differentials
    "diff_movement_avg_speed",
    "diff_movement_percent_supersonic",
    "diff_movement_percent_high_air",
    # positioning differentials
    "diff_positioning_avg_dist_to_ball",
    "diff_positioning_percent_defensive_third",
    "diff_positioning_percent_behind_ball",
    # head-to-head
    "blue_h2h_win_rate",
    "h2h_matches_played",
    # elo
    "elo_diff",
]
TARGET_COL = "winner"


def _encode_target(series: pd.Series) -> np.ndarray:
    """Map 'blue' → 1, 'orange' → 0."""
    return (series == "blue").astype(int).to_numpy()


def _build_pipeline(model_type: ModelType) -> Pipeline:
    if model_type == "logistic":
        return Pipeline(
            [
                ("imputer", SimpleImputer(strategy="mean")),
                (
                    "clf",
                    CalibratedClassifierCV(
                        LogisticRegression(max_iter=1000, C=0.1),
                        cv=3,
                        method="isotonic",
                    ),
                ),
            ]
        )
    if model_type == "xgboost":
        return Pipeline(
            [
                (
                    "clf",
                    XGBClassifier(
                        n_estimators=200,
                        max_depth=3,
                        learning_rate=0.05,
                        subsample=0.8,
                        colsample_bytree=0.8,
                        eval_metric="logloss",
                        random_state=42,
                    ),
                )
            ]
        )
    raise ValueError(f"Unknown model_type: {model_type!r}")


class WinProbabilityModel:
    """
    Predicts P(blue wins) for a Rocket League pro match.

    Parameters
    ----------
    model_type : "logistic" | "xgboost"
    """

    def __init__(self, model_type: ModelType = "xgboost"):
        self.model_type = model_type
        self._pipeline: Pipeline | None = None

    # ------------------------------------------------------------------
    # Fit / predict
    # ------------------------------------------------------------------

    def fit(self, df: pd.DataFrame) -> "WinProbabilityModel":
        """
        Train on all rows in df that have non-null features and a valid winner.

        Parameters
        ----------
        df : DataFrame from features.parquet (output of build_features)
        """
        X, y = self._prepare(df)
        self._pipeline = _build_pipeline(self.model_type)
        self._pipeline.fit(X, y)
        return self

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """
        Return P(blue wins) for each row in df.

        Rows with null features are returned as NaN.
        """
        if self._pipeline is None:
            raise RuntimeError("Model has not been fitted. Call fit() first.")

        mask = df[FEATURE_COLS].notnull().all(axis=1)
        result = np.full(len(df), np.nan)

        if mask.any():
            X = df.loc[mask, FEATURE_COLS].to_numpy()
            proba = self._pipeline.predict_proba(X)
            # Column order: [P(orange), P(blue)] since label 0=orange, 1=blue
            result[mask.to_numpy()] = proba[:, 1]

        return result

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def cross_validate(
        self,
        df: pd.DataFrame,
        cv: int = 5,
        random_state: int = 42,
    ) -> dict[str, float]:
        """
        Evaluate via stratified k-fold CV on rows with complete features.

        Returns a dict with keys:
            accuracy, roc_auc, log_loss
        (each is the mean across folds; std is also included as *_std)
        """
        X, y = self._prepare(df)
        skf = StratifiedKFold(n_splits=cv, shuffle=True, random_state=random_state)
        pipeline = _build_pipeline(self.model_type)

        fold_accuracy = []
        fold_auc = []
        fold_logloss = []

        for train_idx, val_idx in skf.split(X, y):
            X_train, X_val = X[train_idx], X[val_idx]
            y_train, y_val = y[train_idx], y[val_idx]

            pipeline.fit(X_train, y_train)
            proba = pipeline.predict_proba(X_val)[:, 1]
            pred = (proba >= 0.5).astype(int)

            fold_accuracy.append((pred == y_val).mean())
            fold_auc.append(roc_auc_score(y_val, proba))
            fold_logloss.append(log_loss(y_val, proba))

        return {
            "accuracy": float(np.mean(fold_accuracy)),
            "accuracy_std": float(np.std(fold_accuracy)),
            "roc_auc": float(np.mean(fold_auc)),
            "roc_auc_std": float(np.std(fold_auc)),
            "log_loss": float(np.mean(fold_logloss)),
            "log_loss_std": float(np.std(fold_logloss)),
            "n_samples": len(y),
            "cv_folds": cv,
        }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> None:
        if self._pipeline is None:
            raise RuntimeError("Nothing to save — model has not been fitted.")
        joblib.dump({"model_type": self.model_type, "pipeline": self._pipeline}, path)

    @classmethod
    def load(cls, path: str | Path) -> "WinProbabilityModel":
        data = joblib.load(path)
        obj = cls(model_type=data["model_type"])
        obj._pipeline = data["pipeline"]
        return obj

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _prepare(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """Return (X, y) dropping rows with any null feature or missing target."""
        mask = df[FEATURE_COLS].notnull().all(axis=1) & df[TARGET_COL].notnull()
        clean = df[mask]
        X = clean[FEATURE_COLS].to_numpy()
        y = _encode_target(clean[TARGET_COL])
        return X, y


# ---------------------------------------------------------------------------
# CLI entry point — train, evaluate, and save both models
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    features_path = Path("data/processed/features.parquet")
    models_dir = Path("data/models")
    models_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_parquet(features_path)
    print(f"Loaded {len(df)} matches ({df[TARGET_COL].notnull().sum()} with labels)\n")

    results = {}

    for model_type in ("logistic", "xgboost"):
        print(f"=== {model_type.upper()} ===")
        model = WinProbabilityModel(model_type=model_type)
        scores = model.cross_validate(df)

        print(f"  Accuracy : {scores['accuracy']:.3f} ± {scores['accuracy_std']:.3f}")
        print(f"  ROC-AUC  : {scores['roc_auc']:.3f} ± {scores['roc_auc_std']:.3f}")
        print(f"  Log-Loss : {scores['log_loss']:.3f} ± {scores['log_loss_std']:.3f}")
        print(f"  Samples  : {scores['n_samples']} (after dropping NaN rows)\n")

        model.fit(df)
        save_path = models_dir / f"win_probability_{model_type}.pkl"
        model.save(save_path)
        print(f"  Saved → {save_path}\n")

        results[model_type] = scores

    # Persist CV results for reproducibility
    results_path = models_dir / "cv_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"CV results → {results_path}")
