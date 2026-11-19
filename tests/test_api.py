"""
tests/test_api.py

Integration tests for the FastAPI application.
Uses the real trained models and data — tests exercise the full stack
from HTTP request to model inference and response serialization.
"""

import json

import pytest
from fastapi.testclient import TestClient

from src.api.main import _DATA, _ROOT, app
from src.api.roster_overrides import load_manual_players

# ---------------------------------------------------------------------------
# Client fixture — shared across all tests; lifespan runs once per session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# GET /players
# ---------------------------------------------------------------------------

class TestGetPlayers:
    def test_status_ok(self, client):
        resp = client.get("/api/players")
        assert resp.status_code == 200

    def test_response_has_players_and_total(self, client):
        body = client.get("/api/players").json()
        assert "players" in body
        assert "total" in body

    def test_total_matches_players_list_length(self, client):
        body = client.get("/api/players").json()
        assert body["total"] == len(body["players"])

    def test_returns_all_registered_players(self, client):
        # Every entry in player_names.json except RLCS referee/admin dummies.
        names = json.loads((_DATA / "player_names.json").read_text())
        names.update(
            load_manual_players(_ROOT / "data" / "players" / "manual_players.json", names)
        )
        expected = [
            n for n in names.values()
            if not any(kw in n.lower() for kw in ("referee", "admin"))
        ]
        body = client.get("/api/players").json()
        assert body["total"] == len(expected)

    def test_player_has_required_fields(self, client):
        player = client.get("/api/players").json()["players"][0]
        assert "player_id" in player
        assert "display_name" in player
        assert "archetype" in player
        assert "team_name" in player
        assert "elo" in player

    def test_display_names_are_strings(self, client):
        players = client.get("/api/players").json()["players"]
        for p in players:
            assert isinstance(p["display_name"], str)
            assert len(p["display_name"]) > 0

    def test_archetypes_are_valid(self, client):
        valid = {"striker", "anchor", "flex", "unknown"}
        players = client.get("/api/players").json()["players"]
        for p in players:
            assert p["archetype"] in valid

    def test_elo_values_are_positive_floats(self, client):
        players = client.get("/api/players").json()["players"]
        for p in players:
            assert isinstance(p["elo"], float)
            assert p["elo"] > 0

    def test_sorted_by_elo_descending(self, client):
        players = client.get("/api/players").json()["players"]
        elos = [p["elo"] for p in players]
        assert elos == sorted(elos, reverse=True)


# ---------------------------------------------------------------------------
# GET /elo-ratings
# ---------------------------------------------------------------------------

class TestGetEloRatings:
    def test_status_ok(self, client):
        resp = client.get("/api/elo-ratings")
        assert resp.status_code == 200

    def test_has_ratings_and_total(self, client):
        body = client.get("/api/elo-ratings").json()
        assert "ratings" in body
        assert "total" in body

    def test_total_matches_ratings_length(self, client):
        body = client.get("/api/elo-ratings").json()
        # total counts ranked (active) teams; defunct teams follow, unranked
        ranked = [r for r in body["ratings"] if r["rank"] is not None]
        assert body["total"] == len(ranked)

    def test_rating_has_required_fields(self, client):
        rating = client.get("/api/elo-ratings").json()["ratings"][0]
        assert "rank" in rating
        assert "team_name" in rating
        assert "elo" in rating

    def test_ranks_are_consecutive_from_one(self, client):
        ratings = client.get("/api/elo-ratings").json()["ratings"]
        ranks = [r["rank"] for r in ratings if r["rank"] is not None]
        assert ranks == list(range(1, len(ranks) + 1))

    def test_sorted_by_elo_descending(self, client):
        ratings = client.get("/api/elo-ratings").json()["ratings"]
        for group in ([r for r in ratings if r["rank"] is not None],
                      [r for r in ratings if r["rank"] is None]):
            elos = [r["elo"] for r in group]
            assert elos == sorted(elos, reverse=True)

    def test_top_team_is_rank_one_and_highest_rated_active(self, client):
        # Which team leads changes with every retrain, so assert structure, not a name.
        ratings = client.get("/api/elo-ratings").json()["ratings"]
        active = [r for r in ratings if r["rank"] is not None]
        assert active[0]["rank"] == 1
        assert active[0]["elo"] == max(r["elo"] for r in active)

    def test_elo_values_around_1500(self, client):
        # All ratings should be in a reasonable range around the 1500 baseline
        ratings = client.get("/api/elo-ratings").json()["ratings"]
        for r in ratings:
            assert 1000 < r["elo"] < 2500


# ---------------------------------------------------------------------------
# POST /optimize
# ---------------------------------------------------------------------------

def _get_some_player_ids(client, n: int) -> list[str]:
    """Helper: grab the first n player IDs from /players."""
    players = client.get("/api/players").json()["players"]
    return [p["player_id"] for p in players[:n]]


class TestOptimize:
    def test_status_ok(self, client):
        ids = _get_some_player_ids(client, 6)
        resp = client.post("/api/optimize", json={"player_ids": ids})
        assert resp.status_code == 200

    def test_default_top_k_is_five(self, client):
        ids = _get_some_player_ids(client, 10)
        body = client.post("/api/optimize", json={"player_ids": ids}).json()
        assert len(body["lineups"]) == 5

    def test_top_k_respected(self, client):
        ids = _get_some_player_ids(client, 10)
        body = client.post(
            "/api/optimize", json={"player_ids": ids, "top_k": 3}
        ).json()
        assert len(body["lineups"]) == 3

    def test_pool_size_in_response(self, client):
        ids = _get_some_player_ids(client, 7)
        body = client.post("/api/optimize", json={"player_ids": ids}).json()
        assert body["pool_size"] == 7

    def test_lineups_sorted_by_score_descending(self, client):
        ids = _get_some_player_ids(client, 10)
        lineups = client.post("/api/optimize", json={"player_ids": ids}).json()["lineups"]
        scores = [l["score"] for l in lineups]
        assert scores == sorted(scores, reverse=True)

    def test_ranks_are_consecutive(self, client):
        ids = _get_some_player_ids(client, 10)
        lineups = client.post("/api/optimize", json={"player_ids": ids}).json()["lineups"]
        ranks = [l["rank"] for l in lineups]
        assert ranks == list(range(1, len(lineups) + 1))

    def test_each_lineup_has_three_players(self, client):
        ids = _get_some_player_ids(client, 6)
        lineups = client.post("/api/optimize", json={"player_ids": ids}).json()["lineups"]
        for lineup in lineups:
            assert len(lineup["players"]) == 3

    def test_lineup_players_have_display_names(self, client):
        ids = _get_some_player_ids(client, 6)
        lineups = client.post("/api/optimize", json={"player_ids": ids}).json()["lineups"]
        for lineup in lineups:
            for player in lineup["players"]:
                assert isinstance(player["display_name"], str)
                assert len(player["display_name"]) > 0

    def test_lineup_players_all_from_pool(self, client):
        ids = _get_some_player_ids(client, 6)
        id_set = set(ids)
        lineups = client.post("/api/optimize", json={"player_ids": ids}).json()["lineups"]
        for lineup in lineups:
            for player in lineup["players"]:
                assert player["player_id"] in id_set

    def test_lineup_has_required_fields(self, client):
        ids = _get_some_player_ids(client, 6)
        lineup = client.post("/api/optimize", json={"player_ids": ids}).json()["lineups"][0]
        for field in ("rank", "players", "score", "synergy", "archetype_combo",
                      "archetype_bonus", "mean_elo", "n_matches", "low_sample"):
            assert field in lineup

    def test_exactly_three_players_in_pool(self, client):
        ids = _get_some_player_ids(client, 3)
        body = client.post(
            "/api/optimize", json={"player_ids": ids, "top_k": 10}
        ).json()
        assert len(body["lineups"]) == 1

    def test_unknown_player_id_returns_400(self, client):
        ids = _get_some_player_ids(client, 3)
        ids[0] = "FAKE_STEAM_ID_99999"
        resp = client.post("/api/optimize", json={"player_ids": ids})
        assert resp.status_code == 400

    def test_fewer_than_three_players_returns_422(self, client):
        ids = _get_some_player_ids(client, 2)
        resp = client.post("/api/optimize", json={"player_ids": ids})
        assert resp.status_code == 422

    def test_custom_weights_accepted(self, client):
        ids = _get_some_player_ids(client, 6)
        body = client.post(
            "/api/optimize",
            json={
                "player_ids": ids,
                "top_k": 3,
                "weights": {"synergy": 2.0, "archetype": 0.0, "elo": 0.0},
            },
        ).json()
        assert len(body["lineups"]) == 3

    def test_zero_weights_all_scores_equal(self, client):
        # With all weights = 0, every trio scores 0.0
        ids = _get_some_player_ids(client, 4)
        lineups = client.post(
            "/api/optimize",
            json={
                "player_ids": ids,
                "top_k": 4,
                "weights": {"synergy": 0.0, "archetype": 0.0, "elo": 0.0},
            },
        ).json()["lineups"]
        scores = [l["score"] for l in lineups]
        assert all(s == pytest.approx(0.0) for s in scores)

    def test_archetype_combo_is_sorted_string(self, client):
        ids = _get_some_player_ids(client, 6)
        lineups = client.post("/api/optimize", json={"player_ids": ids}).json()["lineups"]
        for lineup in lineups:
            parts = lineup["archetype_combo"].split("+")
            assert parts == sorted(parts)

    def test_top_k_capped_by_available_combos(self, client):
        # 3 players → only 1 possible trio; top_k=50 should still return 1
        ids = _get_some_player_ids(client, 3)
        body = client.post(
            "/api/optimize", json={"player_ids": ids, "top_k": 50}
        ).json()
        assert len(body["lineups"]) == 1

    def test_negative_weights_rejected(self, client):
        ids = _get_some_player_ids(client, 4)
        resp = client.post(
            "/api/optimize",
            json={
                "player_ids": ids,
                "weights": {"synergy": -1.0, "archetype": 0.5, "elo": 0.3},
            },
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# SPA static fallback
# ---------------------------------------------------------------------------

class TestSPAStaticFiles:
    @pytest.fixture()
    def spa_client(self, tmp_path):
        from fastapi import FastAPI

        from src.api.main import SPAStaticFiles

        (tmp_path / "index.html").write_text("<html>app shell</html>")
        (tmp_path / "assets").mkdir()
        (tmp_path / "assets" / "app.js").write_text("console.log(1)")
        spa = FastAPI()
        spa.mount("/", SPAStaticFiles(directory=tmp_path, html=True))
        return TestClient(spa)

    def test_root_serves_index(self, spa_client):
        assert "app shell" in spa_client.get("/").text

    def test_unknown_route_falls_back_to_index(self, spa_client):
        resp = spa_client.get("/about")
        assert resp.status_code == 200
        assert "app shell" in resp.text

    def test_existing_asset_served(self, spa_client):
        assert spa_client.get("/assets/app.js").text == "console.log(1)"

    def test_missing_asset_is_404(self, spa_client):
        assert spa_client.get("/assets/missing.js").status_code == 404

    def test_unknown_api_path_is_404(self, spa_client):
        assert spa_client.get("/api/nope").status_code == 404
