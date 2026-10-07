"""
feature_engineer.py

Build match-level features for the Synergy Score win probability model.

Entry point
-----------
    features = build_features(matches, player_stats, rolling_window=5)
    features = build_features(matches, player_stats, elo_model=elo_model)

Returns
-------
    pd.DataFrame — one row per valid match containing:
      - match metadata (match_id, date, season, overtime, duration, winner)
      - blue_avg_{stat} / orange_avg_{stat} — team rolling stat means
      - diff_{stat} — blue minus orange for each stat
      - blue_h2h_win_rate, h2h_matches_played
      - blue_elo, orange_elo, elo_diff (if elo_model is provided)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

import pandas as pd

if TYPE_CHECKING:
    from src.models.elo import EloModel

STAT_COLS = [
    # core
    "goals",
    "assists",
    "saves",
    "shots",
    "score",
    "shooting_pct",
    # demo
    "demos_inflicted",
    "demos_taken",
    # boost
    "boost_avg",
    "boost_bcpm",
    "boost_amount_stolen",
    "boost_percent_zero",
    "boost_percent_full",
    # movement
    "movement_avg_speed",
    "movement_percent_supersonic",
    "movement_percent_high_air",
    "movement_percent_ground",
    # positioning
    "positioning_avg_dist_to_ball",
    "positioning_percent_defensive_third",
    "positioning_percent_offensive_third",
    "positioning_percent_behind_ball",
    "positioning_percent_most_back",
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _filter_valid_matches(
    matches: pd.DataFrame,
    player_stats: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop matches where either team does not have exactly 3 players."""
    player_counts = (
        player_stats.groupby(["match_id", "team_side"])
        .size()
        .reset_index(name="n")
    )
    invalid_ids = player_counts[player_counts["n"] != 3]["match_id"].unique()

    valid_matches = matches[~matches["match_id"].isin(invalid_ids)].copy()
    valid_players = player_stats[~player_stats["match_id"].isin(invalid_ids)].copy()

    n_dropped = len(invalid_ids)
    if n_dropped:
        print(f"Filtered {n_dropped} matches with non-standard player counts.")

    return valid_matches, valid_players


def _rolling_player_stats(
    player_stats: pd.DataFrame,
    matches: pd.DataFrame,
    window: int,
) -> pd.DataFrame:
    """
    Compute per-player rolling averages over the previous `window` games.

    Uses shift(1) before the rolling window so each game's feature reflects
    only matches played before it — no leakage from the current game.

    Returns player_stats with additional roll_{stat} columns.
    """
    date_map = matches.set_index("match_id")["date"]

    df = player_stats.copy()
    df["date"] = df["match_id"].map(date_map)
    df = df.sort_values(["player_id", "date"]).reset_index(drop=True)

    for stat in STAT_COLS:
        df[f"roll_{stat}"] = (
            df.groupby("player_id")[stat]
            .transform(
                lambda s: s.shift(1).rolling(window, min_periods=1).mean()
            )
        )

    return df


def _team_aggregations(rolling_df: pd.DataFrame) -> pd.DataFrame:
    """
    Average each player's rolling stats across the 3 players on each side.

    Returns one row per (match_id, team_side).
    """
    roll_cols = [f"roll_{s}" for s in STAT_COLS]
    return (
        rolling_df
        .groupby(["match_id", "team_side"])[roll_cols]
        .mean()
        .reset_index()
    )


def _pivot_to_match_level(team_agg: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot (match_id, team_side) rows into a single row per match.

    Produces blue_avg_{stat}, orange_avg_{stat}, and diff_{stat} columns
    where diff = blue - orange.
    """
    roll_cols = [f"roll_{s}" for s in STAT_COLS]

    blue = (
        team_agg[team_agg["team_side"] == "blue"]
        .set_index("match_id")[roll_cols]
        .rename(columns={c: c.replace("roll_", "blue_avg_") for c in roll_cols})
    )
    orange = (
        team_agg[team_agg["team_side"] == "orange"]
        .set_index("match_id")[roll_cols]
        .rename(columns={c: c.replace("roll_", "orange_avg_") for c in roll_cols})
    )

    merged = blue.join(orange, how="inner")

    for stat in STAT_COLS:
        merged[f"diff_{stat}"] = (
            merged[f"blue_avg_{stat}"] - merged[f"orange_avg_{stat}"]
        )

    return merged.reset_index()


def _head_to_head(matches: pd.DataFrame) -> pd.DataFrame:
    """
    Compute the blue team's historical win rate against the orange team,
    using only matches played strictly before each match.

    Defaults to 0.5 (even odds) when no prior meetings exist.

    Returns DataFrame with columns:
        match_id, blue_h2h_win_rate, h2h_matches_played
    """
    df = matches[
        ["match_id", "date", "blue_team_name", "orange_team_name", "winner"]
    ].copy().sort_values("date").reset_index(drop=True)

    records = []
    for i, row in df.iterrows():
        blue = row["blue_team_name"]
        orange = row["orange_team_name"]
        prior = df.iloc[:i]

        h2h = prior[
            (
                (prior["blue_team_name"] == blue)
                & (prior["orange_team_name"] == orange)
            )
            | (
                (prior["blue_team_name"] == orange)
                & (prior["orange_team_name"] == blue)
            )
        ]

        n = len(h2h)
        if n == 0:
            win_rate = 0.5
        else:
            blue_wins = (
                ((h2h["blue_team_name"] == blue) & (h2h["winner"] == "blue")).sum()
                + (
                    (h2h["orange_team_name"] == blue)
                    & (h2h["winner"] == "orange")
                ).sum()
            )
            win_rate = blue_wins / n

        records.append(
            {
                "match_id": row["match_id"],
                "blue_h2h_win_rate": float(win_rate),
                "h2h_matches_played": n,
            }
        )

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_features(
    matches: pd.DataFrame,
    player_stats: pd.DataFrame,
    rolling_window: int = 5,
    elo_model: Optional["EloModel"] = None,
) -> pd.DataFrame:
    """
    Build match-level features for win probability modelling.

    Parameters
    ----------
    matches        : DataFrame loaded from matches.parquet
    player_stats   : DataFrame loaded from player_stats.parquet
    rolling_window : number of prior games to average per player (default 5)
    elo_model      : Optional fitted EloModel. When provided, adds
                     blue_elo, orange_elo, and elo_diff columns.

    Returns
    -------
    DataFrame sorted by date with one row per valid match.
    """
    matches = matches.copy()
    matches["date"] = pd.to_datetime(matches["date"], utc=True)

    valid_matches, valid_players = _filter_valid_matches(matches, player_stats)

    rolling_df = _rolling_player_stats(valid_players, valid_matches, rolling_window)
    team_agg = _team_aggregations(rolling_df)
    match_features = _pivot_to_match_level(team_agg)
    h2h = _head_to_head(valid_matches)

    meta_cols = [
        "match_id", "date", "season", "overtime", "duration",
        "blue_team_name", "orange_team_name", "winner",
    ]
    features = (
        valid_matches[meta_cols]
        .merge(match_features, on="match_id", how="inner")
        .merge(h2h, on="match_id", how="left")
    )

    if elo_model is not None:
        elo_df = elo_model.match_elos()[["match_id", "blue_elo", "orange_elo", "elo_diff"]]
        features = features.merge(elo_df, on="match_id", how="left")

    return features.sort_values("date").reset_index(drop=True)


if __name__ == "__main__":
    from src.models.elo import EloModel

    matches_path = Path("data/processed/matches.parquet")
    player_stats_path = Path("data/processed/player_stats.parquet")
    elo_path = Path("data/models/elo.pkl")
    output_path = Path("data/processed/features.parquet")

    matches = pd.read_parquet(matches_path)
    player_stats = pd.read_parquet(player_stats_path)
    elo_model = EloModel.load(elo_path)
    print(f"Loaded {len(matches)} matches, {len(player_stats)} player-stat rows\n")

    features = build_features(matches, player_stats, rolling_window=5, elo_model=elo_model)
    print(f"Built {len(features)} feature rows, {features.shape[1]} columns")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_parquet(output_path, index=False)
    print(f"Features → {output_path}")
