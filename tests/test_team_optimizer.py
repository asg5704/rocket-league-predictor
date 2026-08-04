"""Tests for src/models/team_optimizer.py"""

from itertools import combinations
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.models.team_optimizer import TeamOptimizer, _ARCHETYPE_BONUS


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_archetypes(assignments: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"player_id": pid, "archetype": arch} for pid, arch in assignments.items()]
    )


def _make_player_teams(assignments: dict[str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        [{"player_id": pid, "team_name": team} for pid, team in assignments.items()]
    )


def _make_synergy_model(scores: dict[tuple, float], min_matches: int = 5):
    """Build a mock SynergyScoreModel that returns predetermined scores."""
    mock = MagicMock()

    def _score(player_ids):
        trio = tuple(sorted(player_ids))
        if trio in scores:
            return {
                "synergy": scores[trio],
                "n_matches": min_matches,
                "low_sample": False,
            }
        raise KeyError(f"Trio {trio} not found")

    mock.score.side_effect = _score
    return mock


def _make_elo_model(ratings: dict[str, float], initial: float = 1500.0):
    mock = MagicMock()
    mock.initial_rating = initial
    mock.rating.side_effect = lambda team: ratings.get(team, initial)
    return mock


# Shared fixtures
ARCHETYPES = _make_archetypes(
    {
        "A": "anchor",
        "B": "flex",
        "C": "striker",
        "D": "anchor",
        "E": "striker",
        "F": "flex",
    }
)

PLAYER_TEAMS = _make_player_teams(
    {
        "A": "TEAM_1",
        "B": "TEAM_1",
        "C": "TEAM_2",
        "D": "TEAM_2",
        "E": "TEAM_3",
        "F": "TEAM_3",
    }
)

ELO_RATINGS = {"TEAM_1": 1600.0, "TEAM_2": 1500.0, "TEAM_3": 1400.0}

SYNERGY_SCORES = {
    ("A", "B", "C"): 0.15,
    ("A", "B", "F"): 0.05,
    ("A", "C", "F"): 0.02,
    ("B", "C", "D"): -0.05,
}

POOL = ["A", "B", "C", "D", "E", "F"]


@pytest.fixture
def optimizer():
    synergy_model = _make_synergy_model(SYNERGY_SCORES)
    elo_model = _make_elo_model(ELO_RATINGS)
    return TeamOptimizer(
        synergy_model=synergy_model,
        archetypes_df=ARCHETYPES,
        player_teams_df=PLAYER_TEAMS,
        elo_model=elo_model,
    )


# ---------------------------------------------------------------------------
# optimize() — basic contract
# ---------------------------------------------------------------------------

class TestOptimizeBasics:
    def test_returns_list(self, optimizer):
        results = optimizer.optimize(POOL, top_k=3)
        assert isinstance(results, list)

    def test_top_k_respected(self, optimizer):
        results = optimizer.optimize(POOL, top_k=3)
        assert len(results) == 3

    def test_top_k_larger_than_combos(self, optimizer):
        # 4 players → C(4,3) = 4 combos; top_k=10 should return 4
        results = optimizer.optimize(["A", "B", "C", "D"], top_k=10)
        assert len(results) == 4

    def test_ranks_are_consecutive(self, optimizer):
        results = optimizer.optimize(POOL, top_k=5)
        ranks = [r["rank"] for r in results]
        assert ranks == list(range(1, len(results) + 1))

    def test_sorted_descending_by_score(self, optimizer):
        results = optimizer.optimize(POOL, top_k=6)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_players_is_sorted_tuple(self, optimizer):
        results = optimizer.optimize(POOL, top_k=5)
        for r in results:
            assert isinstance(r["players"], tuple)
            assert len(r["players"]) == 3
            assert list(r["players"]) == sorted(r["players"])

    def test_too_few_players_raises(self, optimizer):
        with pytest.raises(ValueError):
            optimizer.optimize(["A", "B"])

    def test_exactly_three_players(self, optimizer):
        results = optimizer.optimize(["A", "B", "C"], top_k=5)
        assert len(results) == 1

    def test_all_combos_evaluated(self, optimizer):
        results = optimizer.optimize(POOL, top_k=100)
        n_expected = len(list(combinations(POOL, 3)))
        assert len(results) == n_expected


# ---------------------------------------------------------------------------
# RankedLineup fields
# ---------------------------------------------------------------------------

class TestRankedLineupFields:
    def test_all_keys_present(self, optimizer):
        required = {
            "rank", "players", "score", "synergy", "archetype_combo",
            "archetype_bonus", "mean_elo", "n_matches", "low_sample",
        }
        result = optimizer.optimize(POOL, top_k=1)[0]
        assert required.issubset(result.keys())

    def test_unseen_trio_synergy_zero(self, optimizer):
        # E, F are not in any SYNERGY_SCORES entry together with D
        results = optimizer.optimize(["D", "E", "F"], top_k=1)
        assert results[0]["synergy"] == 0.0

    def test_unseen_trio_low_sample_true(self, optimizer):
        results = optimizer.optimize(["D", "E", "F"], top_k=1)
        assert results[0]["low_sample"] is True

    def test_unseen_trio_n_matches_zero(self, optimizer):
        results = optimizer.optimize(["D", "E", "F"], top_k=1)
        assert results[0]["n_matches"] == 0

    def test_known_trio_synergy_correct(self, optimizer):
        # Force the trio (A, B, C) to be top by using only those 3
        results = optimizer.optimize(["A", "B", "C"], top_k=1)
        assert results[0]["synergy"] == pytest.approx(0.15)

    def test_known_trio_low_sample_false(self, optimizer):
        results = optimizer.optimize(["A", "B", "C"], top_k=1)
        assert results[0]["low_sample"] is False


# ---------------------------------------------------------------------------
# Archetype bonus
# ---------------------------------------------------------------------------

class TestArchetypeBonus:
    def test_balanced_lineup_has_highest_bonus(self, optimizer):
        # anchor+flex+striker should get the highest bonus
        balanced = optimizer.optimize(["A", "B", "C"], top_k=1)[0]
        assert balanced["archetype_combo"] == "anchor+flex+striker"
        assert balanced["archetype_bonus"] == pytest.approx(
            _ARCHETYPE_BONUS["anchor+flex+striker"]
        )

    def test_archetype_combo_is_sorted(self, optimizer):
        results = optimizer.optimize(POOL, top_k=6)
        for r in results:
            parts = r["archetype_combo"].split("+")
            assert parts == sorted(parts)

    def test_unknown_player_gets_unknown_archetype(self):
        # Player "Z" not in archetypes_df
        archetypes = _make_archetypes({"A": "anchor", "B": "flex"})
        player_teams = _make_player_teams({"A": "T1", "B": "T1", "Z": "T1"})
        synergy = _make_synergy_model({})
        opt = TeamOptimizer(
            synergy_model=synergy,
            archetypes_df=archetypes,
            player_teams_df=player_teams,
        )
        result = opt.optimize(["A", "B", "Z"], top_k=1)[0]
        assert "unknown" in result["archetype_combo"]


# ---------------------------------------------------------------------------
# ELO integration
# ---------------------------------------------------------------------------

class TestEloIntegration:
    def test_mean_elo_computed_from_team(self, optimizer):
        # A and B are on TEAM_1 (elo 1600), C on TEAM_2 (elo 1500)
        results = optimizer.optimize(["A", "B", "C"], top_k=1)
        expected_mean = (1600 + 1600 + 1500) / 3
        assert results[0]["mean_elo"] == pytest.approx(expected_mean, abs=0.1)

    def test_no_elo_model_still_works(self):
        synergy = _make_synergy_model({})
        opt = TeamOptimizer(
            synergy_model=synergy,
            archetypes_df=ARCHETYPES,
            player_teams_df=PLAYER_TEAMS,
            elo_model=None,
        )
        results = opt.optimize(["A", "B", "C"], top_k=1)
        assert len(results) == 1

    def test_no_elo_model_mean_elo_zero(self):
        synergy = _make_synergy_model({})
        opt = TeamOptimizer(
            synergy_model=synergy,
            archetypes_df=ARCHETYPES,
            player_teams_df=PLAYER_TEAMS,
            elo_model=None,
        )
        results = opt.optimize(["A", "B", "C"], top_k=1)
        assert results[0]["mean_elo"] == pytest.approx(0.0)

    def test_unknown_team_gets_initial_rating(self):
        archetypes = _make_archetypes({"X": "flex", "Y": "flex", "Z": "flex"})
        player_teams = _make_player_teams({"X": "UNKNOWN", "Y": "UNKNOWN", "Z": "UNKNOWN"})
        synergy = _make_synergy_model({})
        elo = _make_elo_model({}, initial=1500.0)
        opt = TeamOptimizer(
            synergy_model=synergy,
            archetypes_df=archetypes,
            player_teams_df=player_teams,
            elo_model=elo,
        )
        results = opt.optimize(["X", "Y", "Z"], top_k=1)
        assert results[0]["mean_elo"] == pytest.approx(1500.0)


# ---------------------------------------------------------------------------
# Weights
# ---------------------------------------------------------------------------

class TestWeights:
    def test_zero_synergy_weight_ignores_synergy(self):
        synergy = _make_synergy_model({("A", "B", "C"): 1000.0})
        elo = _make_elo_model(ELO_RATINGS)
        opt = TeamOptimizer(
            synergy_model=synergy,
            archetypes_df=ARCHETYPES,
            player_teams_df=PLAYER_TEAMS,
            elo_model=elo,
            weights={"synergy": 0.0, "archetype": 1.0, "elo": 0.0},
        )
        results = opt.optimize(["A", "B", "C", "D"], top_k=4)
        # Score should be driven purely by archetype_bonus
        for r in results:
            assert r["score"] == pytest.approx(
                _ARCHETYPE_BONUS.get(r["archetype_combo"], 0.0)
            )

    def test_custom_weights_change_ranking(self):
        # A → ELITE (2000), B → MID (1500), C → LOW (1000), D → ELITE (2000)
        # Mean ELO: (A,B,C)=1500, (A,B,D)=1833 → D's team is elite
        # Synergy: (A,B,C)=+0.5 (good), (A,B,D)=-0.5 (bad)
        archetypes = _make_archetypes(
            {"A": "anchor", "B": "flex", "C": "striker", "D": "anchor"}
        )
        player_teams = _make_player_teams(
            {"A": "ELITE", "B": "MID", "C": "LOW", "D": "ELITE"}
        )
        synergy = _make_synergy_model(
            {("A", "B", "C"): 0.5, ("A", "B", "D"): -0.5}
        )
        elo = _make_elo_model({"ELITE": 2000, "MID": 1500, "LOW": 1000})

        opt_synergy_first = TeamOptimizer(
            synergy_model=synergy,
            archetypes_df=archetypes,
            player_teams_df=player_teams,
            elo_model=elo,
            weights={"synergy": 10.0, "archetype": 0.0, "elo": 0.0},
        )
        opt_elo_first = TeamOptimizer(
            synergy_model=synergy,
            archetypes_df=archetypes,
            player_teams_df=player_teams,
            elo_model=elo,
            weights={"synergy": 0.0, "archetype": 0.0, "elo": 10.0},
        )
        top_synergy = opt_synergy_first.optimize(["A", "B", "C", "D"], top_k=1)[0]["players"]
        top_elo = opt_elo_first.optimize(["A", "B", "C", "D"], top_k=1)[0]["players"]
        # Synergy dominance → (A,B,C) wins; ELO dominance → (A,B,D) wins
        assert top_synergy == ("A", "B", "C")
        assert top_elo == ("A", "B", "D")


# ---------------------------------------------------------------------------
# score_trio()
# ---------------------------------------------------------------------------

class TestScoreTrio:
    def test_score_trio_single_result(self, optimizer):
        result = optimizer.score_trio(["A", "B", "C"])
        assert result["rank"] == 1
        assert result["players"] == ("A", "B", "C")

    def test_score_trio_wrong_count_raises(self, optimizer):
        with pytest.raises(ValueError):
            optimizer.score_trio(["A", "B"])
        with pytest.raises(ValueError):
            optimizer.score_trio(["A", "B", "C", "D"])

    def test_score_trio_matches_optimize(self, optimizer):
        direct = optimizer.score_trio(["A", "B", "C"])
        via_opt = optimizer.optimize(["A", "B", "C"], top_k=1)[0]
        assert direct["score"] == pytest.approx(via_opt["score"])
        assert direct["synergy"] == pytest.approx(via_opt["synergy"])
