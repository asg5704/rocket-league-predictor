"""
Backtest team Elo vs per-player Elo on held-out later matches.

Method: fit each model on ALL matches chronologically; the per-match
`blue_elo`/`orange_elo` are pre-match snapshots, so they are already
out-of-sample predictions for that match. We score the snapshots on the last
`--holdout` fraction of matches (by date), with ratings having warmed up on the
earlier ones. Predictor: P(blue wins) = expected(blue_elo, orange_elo).

Run: PYTHONPATH=. .venv/bin/python scripts/backtest_player_elo.py
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from src.models.elo import EloModel, PlayerEloModel, _expected


def _score(y: np.ndarray, p: np.ndarray) -> dict:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return {
        "log_loss": float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))),
        "brier": float(np.mean((p - y) ** 2)),
        "accuracy": float(np.mean((p > 0.5) == (y == 1))),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", type=float, default=0.3)
    ap.add_argument("--k", type=float, nargs="+", default=[32.0])
    args = ap.parse_args()

    matches = pd.read_parquet("data/processed/matches.parquet")
    players = pd.read_parquet("data/processed/player_stats.parquet")
    matches["date"] = pd.to_datetime(matches["date"], utc=True)
    matches = matches.sort_values("date", kind="stable").reset_index(drop=True)

    cut = int(len(matches) * (1 - args.holdout))
    test_ids = matches["match_id"].iloc[cut:]
    y_all = (matches.set_index("match_id")["winner"] == "blue").astype(float)
    y = y_all.loc[test_ids].to_numpy()
    print(f"{len(matches)} matches; scoring last {len(test_ids)} "
          f"(from {matches['date'].iloc[cut].date()})")

    rows = [("coin flip (p=0.5)", _score(y, np.full(len(y), 0.5)))]
    for k in args.k:
        for name, elos in (
            (f"team Elo   K={k:g}", EloModel(k_factor=k).fit(matches).match_elos()),
            (f"player Elo K={k:g}", PlayerEloModel(k_factor=k).fit(matches, players).match_elos()),
        ):
            e = elos.set_index("match_id").loc[test_ids]
            p = _expected(e["blue_elo"].to_numpy(), e["orange_elo"].to_numpy())
            rows.append((name, _score(y, p)))

    print(pd.DataFrame({n: s for n, s in rows}).T.round(4).to_string())


if __name__ == "__main__":
    main()
