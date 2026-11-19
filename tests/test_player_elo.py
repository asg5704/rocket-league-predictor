"""Tests for PlayerEloModel (per-player Elo)."""

import pandas as pd
import pytest

from src.models.elo import EloModel, PlayerEloModel, _expected


def _matches(rows):
    """rows: (match_id, date, blue_team, orange_team, winner)"""
    return pd.DataFrame(
        rows, columns=["match_id", "date", "blue_team_name", "orange_team_name", "winner"]
    )


def _lineups(spec):
    """spec: {match_id: (blue_players, orange_players)}"""
    rows = []
    for mid, (blue, orange) in spec.items():
        rows += [{"match_id": mid, "player_id": p, "team_side": "blue"} for p in blue]
        rows += [{"match_id": mid, "player_id": p, "team_side": "orange"} for p in orange]
    return pd.DataFrame(rows)


A = ["a1", "a2", "a3"]
B = ["b1", "b2", "b3"]
C = ["c1", "c2", "c3"]


def test_unknown_player_gets_initial_rating():
    m = PlayerEloModel(initial_rating=1500)
    m.fit(
        _matches([("m1", "2026-01-01", "A", "B", "blue")]),
        _lineups({"m1": (A, B)}),
    )
    assert m.rating("nobody") == 1500
    assert m.team_rating(["nobody", "ghost"]) == 1500


def test_unfitted_raises():
    with pytest.raises(RuntimeError):
        PlayerEloModel().match_elos()
    with pytest.raises(RuntimeError):
        PlayerEloModel().ratings_df()


def test_first_match_symmetric_update():
    m = PlayerEloModel(k_factor=32).fit(
        _matches([("m1", "2026-01-01", "A", "B", "blue")]),
        _lineups({"m1": (A, B)}),
    )
    for p in A:
        assert m.rating(p) == pytest.approx(1516)
    for p in B:
        assert m.rating(p) == pytest.approx(1484)


def test_anti_leakage_snapshot_excludes_own_match():
    matches = _matches(
        [
            ("m1", "2026-01-01", "A", "B", "blue"),
            ("m2", "2026-01-02", "A", "B", "blue"),
        ]
    )
    m = PlayerEloModel(k_factor=32).fit(matches, _lineups({"m1": (A, B), "m2": (A, B)}))
    elos = m.match_elos().set_index("match_id")
    assert elos.loc["m1", "blue_elo"] == 1500  # before m1
    assert elos.loc["m2", "blue_elo"] == pytest.approx(1516)  # after m1 only
    assert elos.loc["m1", "elo_diff"] == 0


def test_mean_preservation_matches_team_elo_when_rosters_fixed():
    """Fixed rosters: team mean must move exactly like team-level Elo."""
    matches = _matches(
        [
            ("m1", "2026-01-01", "A", "B", "blue"),
            ("m2", "2026-01-02", "B", "A", "blue"),
            ("m3", "2026-01-03", "A", "B", "orange"),
        ]
    )
    lineups = _lineups({"m1": (A, B), "m2": (B, A), "m3": (A, B)})
    pm = PlayerEloModel(k_factor=32).fit(matches, lineups).match_elos().set_index("match_id")
    tm = EloModel().fit(matches).match_elos().set_index("match_id")
    for col in ("blue_elo", "orange_elo", "elo_diff"):
        assert pm[col].tolist() == pytest.approx(tm[col].tolist())


def test_mover_carries_rating_and_old_team_drops():
    """a3 wins with A, then moves to C. Their rating travels; A (with a
    replacement) is rated without them."""
    matches = _matches(
        [
            ("m1", "2026-01-01", "A", "B", "blue"),
            ("m2", "2026-01-02", "A", "B", "blue"),
            ("m3", "2026-01-03", "C", "B", "blue"),
        ]
    )
    lineups = _lineups(
        {
            "m1": (A, B),
            "m2": (A, B),
            "m3": (["a3", "c2", "c3"], B),  # a3 joins C
        }
    )
    m = PlayerEloModel().fit(matches, lineups)
    elos = m.match_elos().set_index("match_id")

    # a3 won twice with A, so C's pre-m3 mean (a3 + two fresh 1500s) is above
    # 1500 but diluted well below a3's own rating.
    assert 1500 < elos.loc["m3", "blue_elo"] < m.rating("a3")

    # Old team without a3 is now weaker than with them
    with_a3 = m.team_rating(["a1", "a2", "a3"])
    without_a3 = m.team_rating(["a1", "a2", "new_guy"])
    assert without_a3 < with_a3


def test_order_independent_of_input_row_order():
    rows = [
        ("m1", "2026-01-01", "A", "B", "blue"),
        ("m2", "2026-01-02", "A", "B", "orange"),
        ("m3", "2026-01-03", "A", "B", "blue"),
    ]
    lineups = _lineups({"m1": (A, B), "m2": (A, B), "m3": (A, B)})
    fwd = PlayerEloModel().fit(_matches(rows), lineups)
    rev = PlayerEloModel().fit(_matches(rows[::-1]), lineups)
    assert fwd.rating("a1") == pytest.approx(rev.rating("a1"))


def test_irregular_lineup_uses_listed_players_and_zero_sum():
    # blue has a sub (4 players), orange has 2
    lineups = _lineups({"m1": (A + ["sub"], B[:2])})
    m = PlayerEloModel(k_factor=32).fit(
        _matches([("m1", "2026-01-01", "A", "B", "blue")]), lineups
    )
    assert m.rating("sub") == pytest.approx(1516)
    assert m.rating("b1") == pytest.approx(1484)


def test_empty_side_skips_update_but_keeps_snapshot_row():
    lineups = _lineups({"m1": (A, [])})
    m = PlayerEloModel().fit(_matches([("m1", "2026-01-01", "A", "B", "blue")]), lineups)
    assert len(m.match_elos()) == 1
    assert m.rating("a1") == 1500


def test_default_k_is_16():
    assert PlayerEloModel().k_factor == 16


def test_team_ratings_is_mean_of_roster_sorted_desc():
    m = PlayerEloModel(k_factor=32).fit(
        _matches([("m1", "2026-01-01", "A", "B", "blue")]), _lineups({"m1": (A, B)})
    )
    df = m.team_ratings({"B_TEAM": B, "A_TEAM": A, "NEW": ["x", "y"], "EMPTY": []})
    assert df["team_name"].tolist()[0] == "A_TEAM"
    by = df.set_index("team_name")["elo"]
    assert by["A_TEAM"] == pytest.approx(1516)
    assert by["NEW"] == 1500 and by["EMPTY"] == 1500


def test_team_rating_follows_roster_change():
    m = PlayerEloModel(k_factor=32).fit(
        _matches([("m1", "2026-01-01", "A", "B", "blue")]), _lineups({"m1": (A, B)})
    )
    before = m.team_ratings({"A_TEAM": A, "B_TEAM": B}).set_index("team_name")["elo"]
    # a1 moves from A_TEAM to B_TEAM
    after = m.team_ratings(
        {"A_TEAM": ["a2", "a3"], "B_TEAM": B + ["a1"]}
    ).set_index("team_name")["elo"]
    assert after["A_TEAM"] == pytest.approx(1516)  # a2, a3 unchanged mean
    assert after["B_TEAM"] > before["B_TEAM"]


def test_expected_scale_matches_team_elo_helper():
    m = PlayerEloModel(k_factor=32).fit(
        _matches(
            [
                ("m1", "2026-01-01", "A", "B", "blue"),
                ("m2", "2026-01-02", "A", "B", "orange"),
            ]
        ),
        _lineups({"m1": (A, B), "m2": (A, B)}),
    )
    e = _expected(1516, 1484)
    assert m.rating("a1") == pytest.approx(1516 + 32 * (0 - e))


def test_save_load_roundtrip_and_rejects_team_pickle(tmp_path):
    matches = _matches([("m1", "2026-01-01", "A", "B", "blue")])
    lineups = _lineups({"m1": (A, B)})

    pm = PlayerEloModel(k_factor=32).fit(matches, lineups)
    p = tmp_path / "player_elo.pkl"
    pm.save(p)
    loaded = PlayerEloModel.load(p)
    assert loaded.rating("a1") == pm.rating("a1")

    team = EloModel().fit(matches)
    tp = tmp_path / "team_elo.pkl"
    team.save(tp)
    with pytest.raises(ValueError, match="not a PlayerEloModel"):
        PlayerEloModel.load(tp)
