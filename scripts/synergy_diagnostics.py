"""
Synergy-score diagnostics: is the signal real, or noise plus team strength?

Re-run after every retrain (docs/ETL.md step 4i) to see whether more data is
making synergy more meaningful. Reports:

  1. Which team stats predict winning (same-match = descriptive only; prior
     5-match form = what a predictor could actually use).
  2. Whether playstyle similarity within a trio relates to synergy.
  3. Noise check: observed SD of synergy vs the SD if every trio were pure luck.
  4. Overlap with strength: Spearman(synergy, trio mean player Elo).

Run:  PYTHONPATH=. .venv/bin/python scripts/synergy_diagnostics.py [--json out.json]

Caveats: Elo is fit on the same matches (in-sample), so item 4 is an upper bound.
With few trios only large effects are detectable; read p-values accordingly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import roc_auc_score

STYLE_FEATURES = [
    "goals", "assists", "saves", "shots", "demos_inflicted", "boost_bcpm",
    "movement_avg_speed", "movement_percent_supersonic",
    "positioning_avg_dist_to_ball", "positioning_percent_behind_ball",
    "positioning_percent_most_back", "boost_percent_zero",
]
TEAM_STATS = [
    "demos_inflicted", "demos_taken", "shots", "saves", "boost_bcpm",
    "movement_avg_speed", "positioning_percent_behind_ball",
    "boost_amount_stolen", "goals",
]
PRIOR_STATS = ["demos_inflicted", "shots", "saves", "movement_avg_speed"]


def _blue_win(matches: pd.DataFrame) -> pd.Series:
    return (matches.set_index("match_id")["winner"] == "blue").astype(int)


def stat_vs_winning(matches: pd.DataFrame, player_stats: pd.DataFrame) -> pd.DataFrame:
    """AUC of (blue - orange) team stat sums for predicting a blue win, same match."""
    y = _blue_win(matches)
    cols = [c for c in TEAM_STATS if c in player_stats.columns]
    t = player_stats.groupby(["match_id", "team_side"])[cols].sum().unstack("team_side")
    rows = []
    for c in cols:
        d = (t[(c, "blue")] - t[(c, "orange")]).reindex(y.index)
        ok = d.notna()
        rows.append({"stat": c, "auc": roc_auc_score(y[ok], d[ok]), "n": int(ok.sum())})
    return pd.DataFrame(rows)


def prior_form_vs_winning(
    matches: pd.DataFrame, player_stats: pd.DataFrame, window: int = 5
) -> pd.DataFrame:
    """AUC of prior-`window`-match form differences (no same-match information)."""
    m = matches[["match_id", "date", "winner"]].copy()
    m["date"] = pd.to_datetime(m["date"], utc=True)
    y = _blue_win(m)
    pp = player_stats.merge(m[["match_id", "date"]], on="match_id").sort_values(
        ["player_id", "date"]
    )
    cols = [c for c in PRIOR_STATS if c in pp.columns]
    for c in cols:
        pp[c + "_prior"] = pp.groupby("player_id")[c].transform(
            lambda s: s.shift(1).rolling(window, min_periods=2).mean()
        )
    pri = pp.groupby(["match_id", "team_side"])[[c + "_prior" for c in cols]].mean()
    pri = pri.unstack("team_side")
    rows = []
    for c in cols:
        d = (pri[(c + "_prior", "blue")] - pri[(c + "_prior", "orange")]).reindex(y.index)
        ok = d.notna()
        if ok.sum() > 10 and y[ok].nunique() == 2:
            rows.append({"stat": c, "auc": roc_auc_score(y[ok], d[ok]), "n": int(ok.sum())})
    return pd.DataFrame(rows)


def style_dispersion(synergy: pd.DataFrame, player_stats: pd.DataFrame) -> pd.DataFrame:
    """Add `style_dist`: mean pairwise distance of the trio's standardized career stats."""
    feat = [c for c in STYLE_FEATURES if c in player_stats.columns]
    mu = player_stats.groupby("player_id")[feat].mean()
    z = (mu - mu.mean()) / mu.std().replace(0, 1)

    def spread(r) -> float:
        v = z.loc[[r.player_a, r.player_b, r.player_c]].to_numpy()
        return float(np.mean([np.linalg.norm(v[i] - v[j]) for i, j in ((0, 1), (0, 2), (1, 2))]))

    out = synergy.copy()
    out["style_dist"] = out.apply(spread, axis=1)
    return out


def similarity_vs_synergy(synergy_with_dist: pd.DataFrame, thresholds=(1, 5, 10)) -> list[dict]:
    rows = []
    for lo in thresholds:
        g = synergy_with_dist[synergy_with_dist["n_matches"] >= lo]
        if len(g) < 4:
            continue
        r = spearmanr(g["style_dist"], g["synergy"])
        rows.append({"min_matches": lo, "trios": len(g),
                     "spearman": float(r.statistic), "p": float(r.pvalue)})
    return rows


def noise_check(synergy: pd.DataFrame, sims: int = 2000, seed: int = 0) -> dict:
    """Observed SD of synergy vs SD if each trio's wins were Bernoulli(mean_p_win)."""
    rng = np.random.default_rng(seed)
    n = synergy["n_matches"].to_numpy()
    p = synergy["mean_p_win"].to_numpy()
    null = np.array(
        [np.std(rng.binomial(n, p) / n - p) for _ in range(sims)]
    )
    return {
        "observed_sd": float(synergy["synergy"].std()),
        "luck_sd": float(null.mean()),
        "luck_sd_95": [float(np.percentile(null, 2.5)), float(np.percentile(null, 97.5))],
        "trios": int(len(synergy)),
        "trios_le_3_matches": int((n <= 3).sum()),
        "trios_ge_10_matches": int((n >= 10).sum()),
    }


def strength_overlap(synergy: pd.DataFrame, elo_model, min_matches: int = 5) -> dict:
    s = synergy.copy()
    s["trio_elo"] = s.apply(
        lambda r: elo_model.team_rating([r.player_a, r.player_b, r.player_c]), axis=1
    )
    g = s[s["n_matches"] >= min_matches]
    if len(g) < 4:
        return {"min_matches": min_matches, "trios": len(g), "spearman": None, "p": None}
    r = spearmanr(g["trio_elo"], g["synergy"])
    return {"min_matches": min_matches, "trios": len(g),
            "spearman": float(r.statistic), "p": float(r.pvalue)}


def run(data: Path, models: Path) -> dict:
    from src.models.elo import PlayerEloModel

    matches = pd.read_parquet(data / "matches.parquet")
    players = pd.read_parquet(data / "player_stats.parquet")
    synergy = pd.read_parquet(data / "synergy_scores.parquet")
    elo = PlayerEloModel.load(models / "elo.pkl")
    return {
        "n_matches": int(len(matches)),
        "same_match_auc": stat_vs_winning(matches, players).round(4).to_dict("records"),
        "prior_form_auc": prior_form_vs_winning(matches, players).round(4).to_dict("records"),
        "similarity_vs_synergy": similarity_vs_synergy(style_dispersion(synergy, players)),
        "noise": noise_check(synergy),
        "strength_overlap": strength_overlap(synergy, elo),
    }


def _print(report: dict) -> None:
    print(f"Matches: {report['n_matches']}\n")
    print("1a. Same-match team stat diff -> blue win (descriptive; includes consequences of leading)")
    print(pd.DataFrame(report["same_match_auc"]).to_string(index=False))
    print("\n1b. Prior-form diff -> blue win (usable by a predictor)")
    print(pd.DataFrame(report["prior_form_auc"]).to_string(index=False))
    print("\n2. Trio playstyle dispersion vs synergy (Spearman)")
    print(pd.DataFrame(report["similarity_vs_synergy"]).round(3).to_string(index=False))
    n = report["noise"]
    print(f"\n3. Noise: observed synergy SD {n['observed_sd']:.3f} vs pure-luck SD "
          f"{n['luck_sd']:.3f} (95% {n['luck_sd_95'][0]:.3f}-{n['luck_sd_95'][1]:.3f}); "
          f"{n['trios_le_3_matches']}/{n['trios']} trios have <=3 matches")
    s = report["strength_overlap"]
    if s["spearman"] is not None:
        print(f"4. Synergy vs trio mean Elo (n>={s['min_matches']}, {s['trios']} trios): "
              f"spearman {s['spearman']:+.2f} (p={s['p']:.3f}); in-sample, upper bound")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=Path("data/processed"))
    ap.add_argument("--models", type=Path, default=Path("data/models"))
    ap.add_argument("--json", type=Path, help="also write the report as JSON")
    args = ap.parse_args()
    report = run(args.data, args.models)
    _print(report)
    if args.json:
        args.json.write_text(json.dumps(report, indent=2))
        print(f"\nReport -> {args.json}")


if __name__ == "__main__":
    main()
