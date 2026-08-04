"""
tests/test_feature_engineer.py

Unit tests for src/features/feature_engineer.py.

All tests use small inline DataFrames — no file I/O.
"""

import math

import pandas as pd
import pytest

from src.features.feature_engineer import (
    STAT_COLS,
    _filter_valid_matches,
    _rolling_player_stats,
    _team_aggregations,
    _pivot_to_match_level,
    _head_to_head,
    build_features,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_matches(*rows) -> pd.DataFrame:
    """
    Each row: (match_id, date_str, blue_team, orange_team, winner, season).
    """
    records = [
        {
            "match_id": r[0],
            "date": r[1],
            "blue_team_name": r[2],
            "orange_team_name": r[3],
            "winner": r[4],
            "season": r[5],
            "overtime": False,
            "duration": 300,
            "playlist_type": "3v3",
            "team_size": 3,
            "blue_goals": 2,
            "orange_goals": 1,
            "source_group": None,
        }
        for r in rows
    ]
    return pd.DataFrame(records)


_NEW_STAT_DEFAULTS = {
    "shooting_pct": 40.0,
    "boost_bcpm": 200.0,
    "boost_amount_stolen": 100.0,
    "boost_percent_zero": 10.0,
    "boost_percent_full": 20.0,
    "movement_avg_speed": 1400.0,
    "movement_percent_supersonic": 15.0,
    "movement_percent_high_air": 8.0,
    "movement_percent_ground": 65.0,
    "positioning_avg_dist_to_ball": 2000.0,
    "positioning_percent_defensive_third": 35.0,
    "positioning_percent_offensive_third": 30.0,
    "positioning_percent_behind_ball": 55.0,
    "positioning_percent_most_back": 33.0,
}


def _make_players(match_id: str, blue_ids, orange_ids, goals=1) -> list[dict]:
    rows = []
    for pid in blue_ids:
        rows.append(
            {
                "match_id": match_id,
                "player_id": pid,
                "team_side": "blue",
                "playlist_type": "3v3",
                "goals": goals,
                "assists": 0,
                "saves": 1,
                "shots": 2,
                "score": 200,
                "demos_inflicted": 1,
                "demos_taken": 0,
                "boost_avg": 45.0,
                **_NEW_STAT_DEFAULTS,
            }
        )
    for pid in orange_ids:
        rows.append(
            {
                "match_id": match_id,
                "player_id": pid,
                "team_side": "orange",
                "playlist_type": "3v3",
                "goals": 0,
                "assists": 1,
                "saves": 2,
                "shots": 3,
                "score": 300,
                "demos_inflicted": 0,
                "demos_taken": 1,
                "boost_avg": 50.0,
                **_NEW_STAT_DEFAULTS,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# _filter_valid_matches
# ---------------------------------------------------------------------------

class TestFilterValidMatches:
    def setup_method(self):
        self.matches = _make_matches(
            ("m1", "2025-01-01", "A", "B", "blue", 21),
            ("m2", "2025-01-02", "A", "C", "orange", 21),
        )
        rows = (
            _make_players("m1", ["p1", "p2", "p3"], ["p4", "p5", "p6"])
            + _make_players("m2", ["p1", "p2", "p3"], ["p4", "p5", "p6"])
        )
        self.players = pd.DataFrame(rows)

    def test_keeps_valid_matches(self):
        vm, vp = _filter_valid_matches(self.matches, self.players)
        assert len(vm) == 2
        assert len(vp) == 12

    def test_drops_match_with_extra_player(self):
        extra = self.players.copy()
        extra_row = extra[extra["match_id"] == "m1"].iloc[:1].copy()
        extra_row["player_id"] = "p7"
        extra_row["team_side"] = "blue"
        extra = pd.concat([extra, extra_row], ignore_index=True)

        vm, vp = _filter_valid_matches(self.matches, extra)
        assert set(vm["match_id"]) == {"m2"}

    def test_drops_corrupted_match(self):
        # Only 1 player in m1
        sparse = self.players[
            ~((self.players["match_id"] == "m1") & (self.players["player_id"] != "p1"))
        ].copy()
        vm, vp = _filter_valid_matches(self.matches, sparse)
        assert set(vm["match_id"]) == {"m2"}


# ---------------------------------------------------------------------------
# _rolling_player_stats
# ---------------------------------------------------------------------------

class TestRollingPlayerStats:
    def _build(self, window=3):
        matches = _make_matches(
            ("m1", "2025-01-01", "A", "B", "blue", 21),
            ("m2", "2025-01-02", "A", "B", "blue", 21),
            ("m3", "2025-01-03", "A", "B", "blue", 21),
            ("m4", "2025-01-04", "A", "B", "blue", 21),
        )
        rows = []
        for mid in ["m1", "m2", "m3", "m4"]:
            rows += _make_players(mid, ["p1", "p2", "p3"], ["p4", "p5", "p6"])
        players = pd.DataFrame(rows)
        matches["date"] = pd.to_datetime(matches["date"], utc=True)
        return _rolling_player_stats(players, matches, window)

    def test_roll_columns_added(self):
        result = self._build()
        for stat in STAT_COLS:
            assert f"roll_{stat}" in result.columns

    def test_first_game_is_nan(self):
        result = self._build()
        p1_rows = result[result["player_id"] == "p1"].sort_values("date")
        # First game has no prior history → NaN
        assert math.isnan(p1_rows.iloc[0]["roll_goals"])

    def test_second_game_equals_first_game_value(self):
        result = self._build()
        p1_rows = result[result["player_id"] == "p1"].sort_values("date")
        # Second game rolling avg = first game's actual goals value
        assert p1_rows.iloc[1]["roll_goals"] == pytest.approx(
            p1_rows.iloc[0]["goals"]
        )

    def test_window_limits_lookback(self):
        result = self._build(window=2)
        p1_rows = result[result["player_id"] == "p1"].sort_values("date")
        # Fourth game: rolling(2).mean() over games 2 and 3 (goals=1 both)
        assert p1_rows.iloc[3]["roll_goals"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# _team_aggregations
# ---------------------------------------------------------------------------

class TestTeamAggregations:
    def test_averages_across_three_players(self):
        rows = _make_players("m1", ["p1", "p2", "p3"], ["p4", "p5", "p6"])
        df = pd.DataFrame(rows)
        for stat in STAT_COLS:
            df[f"roll_{stat}"] = df[stat].astype(float)

        agg = _team_aggregations(df)
        blue_row = agg[agg["team_side"] == "blue"].iloc[0]
        # All blue players have goals=1 → avg should be 1.0
        assert blue_row["roll_goals"] == pytest.approx(1.0)
        # All orange players have goals=0 → avg should be 0.0
        orange_row = agg[agg["team_side"] == "orange"].iloc[0]
        assert orange_row["roll_goals"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# _pivot_to_match_level
# ---------------------------------------------------------------------------

class TestPivotToMatchLevel:
    def _build_agg(self):
        rows = _make_players("m1", ["p1", "p2", "p3"], ["p4", "p5", "p6"])
        df = pd.DataFrame(rows)
        for stat in STAT_COLS:
            df[f"roll_{stat}"] = df[stat].astype(float)
        return _team_aggregations(df)

    def test_produces_one_row_per_match(self):
        agg = self._build_agg()
        result = _pivot_to_match_level(agg)
        assert len(result) == 1

    def test_blue_orange_columns_present(self):
        agg = self._build_agg()
        result = _pivot_to_match_level(agg)
        for stat in STAT_COLS:
            assert f"blue_avg_{stat}" in result.columns
            assert f"orange_avg_{stat}" in result.columns
            assert f"diff_{stat}" in result.columns

    def test_diff_is_blue_minus_orange(self):
        agg = self._build_agg()
        result = _pivot_to_match_level(agg)
        # blue goals=1, orange goals=0 → diff=1.0
        assert result.iloc[0]["diff_goals"] == pytest.approx(1.0)
        # blue saves=1, orange saves=2 → diff=-1.0
        assert result.iloc[0]["diff_saves"] == pytest.approx(-1.0)


# ---------------------------------------------------------------------------
# _head_to_head
# ---------------------------------------------------------------------------

class TestHeadToHead:
    def test_no_prior_history_defaults_to_half(self):
        matches = _make_matches(
            ("m1", "2025-01-01", "A", "B", "blue", 21),
        )
        matches["date"] = pd.to_datetime(matches["date"], utc=True)
        h2h = _head_to_head(matches)
        assert h2h.iloc[0]["blue_h2h_win_rate"] == pytest.approx(0.5)
        assert h2h.iloc[0]["h2h_matches_played"] == 0

    def test_prior_win_counted(self):
        matches = _make_matches(
            ("m1", "2025-01-01", "A", "B", "blue", 21),
            ("m2", "2025-01-02", "A", "B", "blue", 21),
        )
        matches["date"] = pd.to_datetime(matches["date"], utc=True)
        h2h = _head_to_head(matches)
        # For m2: 1 prior match, A (blue) won → win_rate = 1.0
        row = h2h[h2h["match_id"] == "m2"].iloc[0]
        assert row["blue_h2h_win_rate"] == pytest.approx(1.0)
        assert row["h2h_matches_played"] == 1

    def test_reversed_sides_counted(self):
        # m1: A=blue wins; m2: B=blue vs A=orange (A won as orange in m1)
        matches = _make_matches(
            ("m1", "2025-01-01", "A", "B", "blue", 21),
            ("m2", "2025-01-02", "B", "A", "blue", 21),
        )
        matches["date"] = pd.to_datetime(matches["date"], utc=True)
        h2h = _head_to_head(matches)
        # For m2: 1 prior match where B lost → B win_rate = 0.0
        row = h2h[h2h["match_id"] == "m2"].iloc[0]
        assert row["blue_h2h_win_rate"] == pytest.approx(0.0)

    def test_win_rate_over_multiple_matches(self):
        matches = _make_matches(
            ("m1", "2025-01-01", "A", "B", "blue", 21),   # A wins
            ("m2", "2025-01-02", "A", "B", "orange", 21), # B wins
            ("m3", "2025-01-03", "A", "B", "blue", 21),   # A wins
            ("m4", "2025-01-04", "A", "B", "blue", 21),   # use as query
        )
        matches["date"] = pd.to_datetime(matches["date"], utc=True)
        h2h = _head_to_head(matches)
        # For m4: 3 prior, A won 2 → 2/3
        row = h2h[h2h["match_id"] == "m4"].iloc[0]
        assert row["blue_h2h_win_rate"] == pytest.approx(2 / 3)
        assert row["h2h_matches_played"] == 3


# ---------------------------------------------------------------------------
# build_features (integration)
# ---------------------------------------------------------------------------

class TestBuildFeatures:
    def _make_dataset(self):
        matches = _make_matches(
            ("m1", "2025-01-01", "A", "B", "blue", 21),
            ("m2", "2025-01-02", "A", "B", "orange", 21),
            ("m3", "2025-01-03", "A", "B", "blue", 21),
        )
        rows = []
        for mid in ["m1", "m2", "m3"]:
            rows += _make_players(mid, ["p1", "p2", "p3"], ["p4", "p5", "p6"])
        players = pd.DataFrame(rows)
        return matches, players

    def test_output_has_one_row_per_valid_match(self):
        matches, players = self._make_dataset()
        features = build_features(matches, players)
        assert len(features) == 3

    def test_output_sorted_by_date(self):
        matches, players = self._make_dataset()
        features = build_features(matches, players)
        assert list(features["match_id"]) == ["m1", "m2", "m3"]

    def test_expected_columns_present(self):
        matches, players = self._make_dataset()
        features = build_features(matches, players)
        for stat in STAT_COLS:
            assert f"blue_avg_{stat}" in features.columns
            assert f"orange_avg_{stat}" in features.columns
            assert f"diff_{stat}" in features.columns
        assert "blue_h2h_win_rate" in features.columns
        assert "h2h_matches_played" in features.columns

    def test_filters_invalid_match(self):
        matches, players = self._make_dataset()
        # Add an extra player to m2 to make it invalid
        extra = players[
            (players["match_id"] == "m2") & (players["player_id"] == "p1")
        ].copy()
        extra["player_id"] = "p_sub"
        players = pd.concat([players, extra], ignore_index=True)

        features = build_features(matches, players)
        assert len(features) == 2
        assert "m2" not in features["match_id"].values

    def test_winner_column_preserved(self):
        matches, players = self._make_dataset()
        features = build_features(matches, players)
        assert set(features["winner"].unique()).issubset({"blue", "orange"})
