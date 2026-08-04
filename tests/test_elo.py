"""Tests for src/models/elo.py"""

import math
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.models.elo import EloModel, _expected


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_matches(rows: list[dict]) -> pd.DataFrame:
    """Minimal matches DataFrame for testing."""
    defaults = {
        "playlist_type": "3v3",
        "team_size": 3,
        "blue_goals": 2,
        "orange_goals": 1,
        "duration": 300,
        "overtime": False,
        "season": 21,
        "source_group": None,
    }
    records = []
    for i, row in enumerate(rows):
        r = dict(defaults)
        r["match_id"] = row.get("match_id", f"match_{i}")
        r["date"] = row["date"]
        r["blue_team_name"] = row["blue_team_name"]
        r["orange_team_name"] = row["orange_team_name"]
        r["winner"] = row["winner"]
        records.append(r)
    return pd.DataFrame(records)


@pytest.fixture
def three_matches():
    """Three matches: A beats B, B beats C, A beats C."""
    return _make_matches(
        [
            {
                "match_id": "m1",
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "TEAM_A",
                "orange_team_name": "TEAM_B",
                "winner": "blue",
            },
            {
                "match_id": "m2",
                "date": "2025-01-02T00:00:00Z",
                "blue_team_name": "TEAM_B",
                "orange_team_name": "TEAM_C",
                "winner": "blue",
            },
            {
                "match_id": "m3",
                "date": "2025-01-03T00:00:00Z",
                "blue_team_name": "TEAM_A",
                "orange_team_name": "TEAM_C",
                "winner": "blue",
            },
        ]
    )


# ---------------------------------------------------------------------------
# _expected formula
# ---------------------------------------------------------------------------

def test_expected_equal_ratings():
    assert _expected(1500, 1500) == pytest.approx(0.5)


def test_expected_higher_rated_favored():
    assert _expected(1600, 1400) > 0.5


def test_expected_lower_rated_underdog():
    assert _expected(1400, 1600) < 0.5


def test_expected_symmetry():
    e = _expected(1600, 1400)
    assert _expected(1400, 1600) == pytest.approx(1.0 - e)


def test_expected_400_point_gap():
    # 400-point gap → exactly 10:1 odds → E = 10/11 ≈ 0.909
    e = _expected(1900, 1500)
    assert e == pytest.approx(10 / 11, rel=1e-6)


# ---------------------------------------------------------------------------
# Fit basics
# ---------------------------------------------------------------------------

def test_fit_returns_self(three_matches):
    model = EloModel()
    result = model.fit(three_matches)
    assert result is model


def test_unfitted_rating_returns_initial():
    model = EloModel(initial_rating=1500)
    assert model.rating("UNKNOWN_TEAM") == 1500.0


def test_unfitted_match_elos_raises():
    model = EloModel()
    with pytest.raises(RuntimeError):
        model.match_elos()


def test_unfitted_ratings_df_raises():
    model = EloModel()
    with pytest.raises(RuntimeError):
        model.ratings_df()


# ---------------------------------------------------------------------------
# Rating updates
# ---------------------------------------------------------------------------

def test_winner_gains_loser_loses():
    matches = _make_matches(
        [
            {
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "A",
                "orange_team_name": "B",
                "winner": "blue",
            }
        ]
    )
    model = EloModel(k_factor=32, initial_rating=1500)
    model.fit(matches)

    assert model.rating("A") > 1500.0
    assert model.rating("B") < 1500.0


def test_rating_update_is_symmetric():
    """When ratings start equal, winner gains exactly what loser loses."""
    matches = _make_matches(
        [
            {
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "A",
                "orange_team_name": "B",
                "winner": "blue",
            }
        ]
    )
    model = EloModel(k_factor=32, initial_rating=1500)
    model.fit(matches)

    gain = model.rating("A") - 1500.0
    loss = 1500.0 - model.rating("B")
    assert gain == pytest.approx(loss, rel=1e-9)


def test_rating_update_exact_value():
    """With equal ratings and K=32, winner gains K/2 = 16 points."""
    matches = _make_matches(
        [
            {
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "A",
                "orange_team_name": "B",
                "winner": "blue",
            }
        ]
    )
    model = EloModel(k_factor=32, initial_rating=1500)
    model.fit(matches)
    # E=0.5 for equal ratings; gain = K*(1 - 0.5) = 16
    assert model.rating("A") == pytest.approx(1516.0)
    assert model.rating("B") == pytest.approx(1484.0)


def test_upset_yields_bigger_gain():
    """Underdog beating a higher-rated opponent gains more than K/2."""
    matches = _make_matches(
        [
            {
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "UNDERDOG",
                "orange_team_name": "FAVORITE",
                "winner": "blue",
            }
        ]
    )
    # Give FAVORITE a 200-point head start
    model = EloModel(k_factor=32, initial_rating=1500)
    # Pre-seed by fitting a prior win for FAVORITE
    setup = _make_matches(
        [
            {
                "match_id": "setup",
                "date": "2024-12-31T00:00:00Z",
                "blue_team_name": "FAVORITE",
                "orange_team_name": "DUMMY",
                "winner": "blue",
            }
        ]
        * 7  # enough matches to build a lead
    )
    # Easier: just test that a 100-point underdog gains more than 16
    matches2 = _make_matches(
        [
            {
                "match_id": "s1",
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "FAVORITE",
                "orange_team_name": "UNDERDOG",
                "winner": "blue",  # FAVORITE wins first (expected)
            },
            {
                "match_id": "s2",
                "date": "2025-01-02T00:00:00Z",
                "blue_team_name": "UNDERDOG",
                "orange_team_name": "FAVORITE",
                "winner": "blue",  # upset!
            },
        ]
    )
    model.fit(matches2)
    # After match 1: FAVORITE > 1500, UNDERDOG < 1500
    # In match 2 (upset), UNDERDOG was the underdog → gains > K/2
    # Both should end up near 1500 (swapped and cancelled), but UNDERDOG
    # ends higher because it won more when behind
    assert model.rating("UNDERDOG") > 1500.0


def test_k_factor_scales_updates():
    """Doubling K-factor doubles the rating change."""
    matches = _make_matches(
        [
            {
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "A",
                "orange_team_name": "B",
                "winner": "blue",
            }
        ]
    )
    m32 = EloModel(k_factor=32, initial_rating=1500).fit(matches)
    m64 = EloModel(k_factor=64, initial_rating=1500).fit(matches)

    delta32 = m32.rating("A") - 1500.0
    delta64 = m64.rating("A") - 1500.0
    assert delta64 == pytest.approx(2 * delta32, rel=1e-9)


# ---------------------------------------------------------------------------
# Chronological ordering
# ---------------------------------------------------------------------------

def test_chronological_order_enforced():
    """Matches passed out of order must produce the same result as in-order."""
    in_order = _make_matches(
        [
            {
                "match_id": "early",
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "A",
                "orange_team_name": "B",
                "winner": "blue",
            },
            {
                "match_id": "late",
                "date": "2025-02-01T00:00:00Z",
                "blue_team_name": "A",
                "orange_team_name": "B",
                "winner": "orange",
            },
        ]
    )
    out_of_order = in_order.iloc[::-1].reset_index(drop=True)

    m1 = EloModel().fit(in_order)
    m2 = EloModel().fit(out_of_order)

    assert m1.rating("A") == pytest.approx(m2.rating("A"))
    assert m1.rating("B") == pytest.approx(m2.rating("B"))


# ---------------------------------------------------------------------------
# match_elos()
# ---------------------------------------------------------------------------

def test_match_elos_shape(three_matches):
    model = EloModel().fit(three_matches)
    elos = model.match_elos()
    assert len(elos) == 3
    assert set(elos.columns) >= {"match_id", "blue_elo", "orange_elo", "elo_diff"}


def test_match_elos_elo_diff_correct(three_matches):
    model = EloModel().fit(three_matches)
    elos = model.match_elos()
    # elo_diff must equal blue_elo - orange_elo for every row
    expected_diff = elos["blue_elo"] - elos["orange_elo"]
    pd.testing.assert_series_equal(
        elos["elo_diff"].reset_index(drop=True),
        expected_diff.reset_index(drop=True),
        check_names=False,
    )


def test_match_elos_first_match_starts_at_initial():
    """First time two teams meet, both have initial_rating."""
    matches = _make_matches(
        [
            {
                "date": "2025-01-01T00:00:00Z",
                "blue_team_name": "NEW_A",
                "orange_team_name": "NEW_B",
                "winner": "blue",
            }
        ]
    )
    model = EloModel(initial_rating=1500).fit(matches)
    elos = model.match_elos()
    assert elos.iloc[0]["blue_elo"] == 1500.0
    assert elos.iloc[0]["orange_elo"] == 1500.0
    assert elos.iloc[0]["elo_diff"] == 0.0


def test_match_elos_is_pre_match_snapshot(three_matches):
    """The elo stored for a match must be the rating *before* that match."""
    model = EloModel(k_factor=32, initial_rating=1500).fit(three_matches)
    elos = model.match_elos().set_index("match_id")

    # m1: A vs B — both brand new, both should be 1500
    assert elos.loc["m1", "blue_elo"] == pytest.approx(1500.0)
    assert elos.loc["m1", "orange_elo"] == pytest.approx(1500.0)

    # m2: B vs C — B's rating has changed after m1; C is still 1500
    assert elos.loc["m2", "orange_elo"] == pytest.approx(1500.0)  # C never played
    assert elos.loc["m2", "blue_elo"] != pytest.approx(1500.0)    # B played in m1


# ---------------------------------------------------------------------------
# ratings_df()
# ---------------------------------------------------------------------------

def test_ratings_df_columns(three_matches):
    model = EloModel().fit(three_matches)
    df = model.ratings_df()
    assert list(df.columns) == ["team_name", "elo"]


def test_ratings_df_sorted_descending(three_matches):
    model = EloModel().fit(three_matches)
    df = model.ratings_df()
    assert df["elo"].is_monotonic_decreasing


def test_ratings_df_all_teams_present(three_matches):
    model = EloModel().fit(three_matches)
    df = model.ratings_df()
    assert set(df["team_name"]) == {"TEAM_A", "TEAM_B", "TEAM_C"}


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_save_load_roundtrip(three_matches, tmp_path):
    model = EloModel(k_factor=24, initial_rating=1400).fit(three_matches)
    path = tmp_path / "elo.pkl"
    model.save(path)

    loaded = EloModel.load(path)
    assert loaded.k_factor == 24
    assert loaded.initial_rating == 1400

    for team in ("TEAM_A", "TEAM_B", "TEAM_C"):
        assert loaded.rating(team) == pytest.approx(model.rating(team))

    pd.testing.assert_frame_equal(
        loaded.match_elos().reset_index(drop=True),
        model.match_elos().reset_index(drop=True),
    )


def test_save_unfitted_raises(tmp_path):
    model = EloModel()
    with pytest.raises(RuntimeError):
        model.save(tmp_path / "elo.pkl")


# ---------------------------------------------------------------------------
# Unknown team at inference time
# ---------------------------------------------------------------------------

def test_unknown_team_gets_initial_rating(three_matches):
    model = EloModel(initial_rating=1500).fit(three_matches)
    assert model.rating("BRAND_NEW_TEAM") == 1500.0
