"""Smoke tests for scripts/synergy_diagnostics.py on synthetic data."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_spec = importlib.util.spec_from_file_location(
    "synergy_diagnostics",
    Path(__file__).resolve().parents[1] / "scripts" / "synergy_diagnostics.py",
)
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)


def _synergy(n_matches, wins, p=0.5):
    rows = []
    for i, (n, w) in enumerate(zip(n_matches, wins)):
        rows.append({
            "trio": (f"a{i}", f"b{i}", f"c{i}"), "n_matches": n,
            "actual_win_rate": w / n, "mean_p_win": p, "synergy": w / n - p,
            "player_a": f"a{i}", "player_b": f"b{i}", "player_c": f"c{i}",
        })
    return pd.DataFrame(rows)


def test_noise_check_pure_luck_is_within_luck_band():
    rng = np.random.default_rng(1)
    n = np.full(60, 12)
    s = _synergy(n, rng.binomial(n, 0.5))
    out = sd.noise_check(s, sims=500)
    lo, hi = out["luck_sd_95"]
    assert lo <= out["observed_sd"] <= hi * 1.1
    assert out["trios"] == 60 and out["trios_le_3_matches"] == 0


def test_noise_check_flags_real_signal():
    # half the trios always win, half always lose: SD far above luck
    n = np.full(40, 12)
    s = _synergy(n, np.array([12, 0] * 20))
    out = sd.noise_check(s, sims=500)
    assert out["observed_sd"] > out["luck_sd_95"][1]


def test_stat_vs_winning_detects_a_perfect_predictor():
    mids = [f"m{i}" for i in range(30)]
    winner = ["blue" if i % 2 else "orange" for i in range(30)]
    matches = pd.DataFrame({"match_id": mids, "winner": winner})
    rows = []
    for mid, w in zip(mids, winner):
        for side in ("blue", "orange"):
            rows.append({"match_id": mid, "team_side": side, "player_id": f"{mid}{side}",
                         "goals": 3 if side == w else 1, "demos_inflicted": 1.0})
    out = sd.stat_vs_winning(matches, pd.DataFrame(rows)).set_index("stat")["auc"]
    assert out["goals"] == pytest.approx(1.0)
    assert out["demos_inflicted"] == pytest.approx(0.5)


def test_style_dispersion_zero_for_identical_players():
    stats = pd.DataFrame({
        "player_id": ["a", "b", "c", "x", "y", "z"],
        "goals": [1.0, 1.0, 1.0, 0.0, 5.0, 9.0],
        "saves": [2.0, 2.0, 2.0, 7.0, 1.0, 4.0],
    })
    syn = pd.DataFrame([
        {"n_matches": 5, "synergy": 0.1, "player_a": "a", "player_b": "b", "player_c": "c"},
        {"n_matches": 5, "synergy": 0.0, "player_a": "x", "player_b": "y", "player_c": "z"},
    ])
    out = sd.style_dispersion(syn, stats)
    assert out.loc[0, "style_dist"] == pytest.approx(0.0)
    assert out.loc[1, "style_dist"] > 1.0
