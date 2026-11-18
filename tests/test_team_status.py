"""Tests for team status/country metadata and the leaderboard split."""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.team_status import TeamInfo, load_team_info, validate_team_info
from src.models.elo import EloModel

ROOT = Path(__file__).resolve().parents[1]


def test_missing_file_means_empty(tmp_path):
    assert load_team_info(tmp_path / "none.json") == {}


def test_load_normalises_country_and_status(tmp_path):
    f = tmp_path / "t.json"
    f.write_text(json.dumps({
        "A": {"country": "UK", "status": "defunct"},
        "B": {"country": "", "status": "bogus"},
        "C": {"country": "fr"},
    }))
    info = load_team_info(f)
    assert info["A"] == TeamInfo(country="gb", status="defunct")
    assert info["B"] == TeamInfo(country=None, status="active")
    assert info["C"] == TeamInfo(country="fr", status="active")


def test_validate_reports_problems():
    raw = {
        "A": {"country": "usa"},
        "B": {"status": "gone"},
        "Ghost": {"country": "us"},
        "D": "us",
    }
    problems = validate_team_info(raw, known_teams={"A", "B", "D"})
    assert len(problems) == 4


def test_real_team_status_file_is_valid():
    raw = json.loads((ROOT / "data" / "processed" / "team_status.json").read_text())
    known = set(EloModel.load(ROOT / "data" / "models" / "elo.pkl").ratings_df()["team_name"])
    assert validate_team_info(raw, known) == []


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_leaderboard_ranks_active_and_lists_defunct_last(client):
    body = client.get("/api/elo-ratings").json()
    ratings = body["ratings"]
    active = [r for r in ratings if r["status"] == "active"]
    defunct = [r for r in ratings if r["status"] == "defunct"]
    assert body["total"] == len(active)
    assert [r["rank"] for r in active] == list(range(1, len(active) + 1))
    assert all(r["rank"] is None for r in defunct)
    assert ratings[: len(active)] == active  # defunct strictly after active
