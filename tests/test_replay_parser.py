"""
tests/test_replay_parser.py

Unit tests for src/data_collection/replay_parser.py.

All tests use inline fixture dicts that mirror the real Ballchasing API
response shape — no network calls required.
"""

import pytest

from src.data_collection.replay_parser import parse_replay


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_player(platform_id: str, name: str, goals=0, assists=0, saves=0,
                 shots=0, score=200, shooting_pct=40.0,
                 demos_inflicted=0, demos_taken=0,
                 boost_avg=45.5, boost_bcpm=200.0, boost_amount_stolen=100.0,
                 boost_percent_zero=10.0, boost_percent_full=20.0,
                 movement_avg_speed=1400.0, movement_percent_supersonic=15.0,
                 movement_percent_high_air=8.0, movement_percent_ground=65.0,
                 positioning_avg_dist_to_ball=2000.0,
                 positioning_percent_defensive_third=35.0,
                 positioning_percent_offensive_third=30.0,
                 positioning_percent_behind_ball=55.0,
                 positioning_percent_most_back=33.0) -> dict:
    """Minimal valid Ballchasing player object with all stat categories."""
    return {
        "id": {"id": f"steam:{platform_id}"},
        "name": name,
        "stats": {
            "core": {
                "goals": goals,
                "assists": assists,
                "saves": saves,
                "shots": shots,
                "score": score,
                "shooting_percentage": shooting_pct,
            },
            "boost": {
                "avg_amount": boost_avg,
                "bcpm": boost_bcpm,
                "amount_stolen": boost_amount_stolen,
                "percent_zero_boost": boost_percent_zero,
                "percent_full_boost": boost_percent_full,
            },
            "demo": {
                "inflicted": demos_inflicted,
                "taken": demos_taken,
            },
            "movement": {
                "avg_speed": movement_avg_speed,
                "percent_supersonic_speed": movement_percent_supersonic,
                "percent_high_air": movement_percent_high_air,
                "percent_ground": movement_percent_ground,
            },
            "positioning": {
                "avg_distance_to_ball": positioning_avg_dist_to_ball,
                "percent_defensive_third": positioning_percent_defensive_third,
                "percent_offensive_third": positioning_percent_offensive_third,
                "percent_behind_ball": positioning_percent_behind_ball,
                "percent_most_back": positioning_percent_most_back,
            },
        },
    }


def _make_replay(
    replay_id="abc123",
    playlist_id="tournament-standard",
    blue_goals=3,
    orange_goals=1,
    blue_name="Karmine Corp",
    orange_name="NRG",
    duration=300,
    overtime=False,
    date="2024-03-01T18:00:00Z",
    season="2023-24",
    blue_players=None,
    orange_players=None,
) -> dict:
    """Build a minimal but structurally valid Ballchasing replay dict."""
    if blue_players is None:
        blue_players = [
            _make_player("111", "vatira", goals=2, assists=1),
            _make_player("222", "Atomic", goals=1),
            _make_player("333", "rokii"),
        ]
    if orange_players is None:
        orange_players = [
            _make_player("444", "jstn.", goals=1),
            _make_player("555", "GarrettG"),
            _make_player("666", "Squishy"),
        ]

    return {
        "id": replay_id,
        "playlist_id": playlist_id,
        "date": date,
        "season": season,
        "duration": duration,
        "overtime": overtime,
        "blue": {
            "name": blue_name,
            "goals": blue_goals,
            "players": blue_players,
        },
        "orange": {
            "name": orange_name,
            "goals": orange_goals,
            "players": orange_players,
        },
    }


# ---------------------------------------------------------------------------
# parse_replay — MatchRaw fields
# ---------------------------------------------------------------------------

class TestMatchParsing:

    def test_returns_match_and_player_stats(self):
        match, stats = parse_replay(_make_replay())
        assert match is not None
        assert isinstance(stats, list)

    def test_match_id(self):
        match, _ = parse_replay(_make_replay(replay_id="xyz999"))
        assert match["match_id"] == "xyz999"

    def test_playlist_type_3v3(self):
        match, _ = parse_replay(_make_replay(playlist_id="tournament-standard"))
        assert match["playlist_type"] == "3v3"
        assert match["team_size"] == 3

    def test_playlist_type_2v2(self):
        match, _ = parse_replay(_make_replay(playlist_id="tournament-doubles"))
        assert match["playlist_type"] == "2v2"
        assert match["team_size"] == 2

    def test_goals(self):
        match, _ = parse_replay(_make_replay(blue_goals=3, orange_goals=1))
        assert match["blue_goals"] == 3
        assert match["orange_goals"] == 1

    def test_winner_blue(self):
        match, _ = parse_replay(_make_replay(blue_goals=3, orange_goals=1))
        assert match["winner"] == "blue"

    def test_winner_orange(self):
        match, _ = parse_replay(_make_replay(blue_goals=0, orange_goals=2))
        assert match["winner"] == "orange"

    def test_team_names(self):
        match, _ = parse_replay(_make_replay(blue_name="Karmine Corp", orange_name="Team Falcons"))
        assert match["blue_team_name"] == "Karmine Corp"
        assert match["orange_team_name"] == "Team Falcons"

    def test_team_name_aliases_are_canonicalised(self):
        match, _ = parse_replay(_make_replay(blue_name="NRG", orange_name="GK ESPORTS"))
        assert match["blue_team_name"] == "NRG ESPORTS"
        assert match["orange_team_name"] == "GEEKAY ESPORTS"

    def test_duration_and_overtime(self):
        match, _ = parse_replay(_make_replay(duration=315, overtime=True))
        assert match["duration"] == 315
        assert match["overtime"] is True

    def test_source_group_attached(self):
        match, _ = parse_replay(_make_replay(), source_group="rlcs-group-1")
        assert match["source_group"] == "rlcs-group-1"

    def test_source_group_none_by_default(self):
        match, _ = parse_replay(_make_replay())
        assert match["source_group"] is None

    def test_date_and_season_passthrough(self):
        match, _ = parse_replay(_make_replay(date="2024-01-15T20:00:00Z", season="2023-24"))
        assert match["date"] == "2024-01-15T20:00:00Z"
        assert match["season"] == "2023-24"


# ---------------------------------------------------------------------------
# parse_replay — irrelevant playlists
# ---------------------------------------------------------------------------

class TestIrrelevantPlaylists:

    @pytest.mark.parametrize("playlist_id", [
        "hoops",
        "rumble",
        "dropshot",
        "snow-day",
        "ranked-hoops",
        "casual",
        "",
    ])
    def test_returns_none_for_irrelevant_playlist(self, playlist_id):
        match, stats = parse_replay(_make_replay(playlist_id=playlist_id))
        assert match is None
        assert stats == []


# ---------------------------------------------------------------------------
# parse_replay — PlayerStatsRaw fields
# ---------------------------------------------------------------------------

class TestPlayerStatsParsing:

    def setup_method(self):
        self.replay = _make_replay(
            blue_players=[
                _make_player("111", "vatira", goals=2, assists=1, saves=0,
                             shots=5, score=450, demos_inflicted=1, demos_taken=0,
                             boost_avg=60.0),
            ],
            orange_players=[
                _make_player("444", "jstn.", goals=1, assists=0, saves=2,
                             shots=3, score=310, demos_inflicted=0, demos_taken=1,
                             boost_avg=38.2),
            ],
            blue_goals=2,
            orange_goals=1,
        )
        _, self.stats = parse_replay(self.replay)

    def test_player_count(self):
        assert len(self.stats) == 2

    def test_player_id_strips_platform_prefix(self):
        ids = {s["player_id"] for s in self.stats}
        assert "111" in ids
        assert "444" in ids
        # raw "steam:111" should NOT appear
        assert "steam:111" not in ids

    def test_team_side_assignment(self):
        sides = {s["player_id"]: s["team_side"] for s in self.stats}
        assert sides["111"] == "blue"
        assert sides["444"] == "orange"

    def test_core_stats(self):
        vatira = next(s for s in self.stats if s["player_id"] == "111")
        assert vatira["goals"] == 2
        assert vatira["assists"] == 1
        assert vatira["saves"] == 0
        assert vatira["shots"] == 5
        assert vatira["score"] == 450
        assert vatira["demos_inflicted"] == 1
        assert vatira["demos_taken"] == 0

    def test_boost_avg(self):
        vatira = next(s for s in self.stats if s["player_id"] == "111")
        assert vatira["boost_avg"] == pytest.approx(60.0)

    def test_new_boost_stats(self):
        vatira = next(s for s in self.stats if s["player_id"] == "111")
        assert vatira["boost_bcpm"] == pytest.approx(200.0)
        assert vatira["boost_amount_stolen"] == pytest.approx(100.0)
        assert vatira["boost_percent_zero"] == pytest.approx(10.0)
        assert vatira["boost_percent_full"] == pytest.approx(20.0)

    def test_movement_stats(self):
        vatira = next(s for s in self.stats if s["player_id"] == "111")
        assert vatira["movement_avg_speed"] == pytest.approx(1400.0)
        assert vatira["movement_percent_supersonic"] == pytest.approx(15.0)
        assert vatira["movement_percent_high_air"] == pytest.approx(8.0)
        assert vatira["movement_percent_ground"] == pytest.approx(65.0)

    def test_positioning_stats(self):
        vatira = next(s for s in self.stats if s["player_id"] == "111")
        assert vatira["positioning_avg_dist_to_ball"] == pytest.approx(2000.0)
        assert vatira["positioning_percent_defensive_third"] == pytest.approx(35.0)
        assert vatira["positioning_percent_offensive_third"] == pytest.approx(30.0)
        assert vatira["positioning_percent_behind_ball"] == pytest.approx(55.0)
        assert vatira["positioning_percent_most_back"] == pytest.approx(33.0)

    def test_shooting_pct(self):
        vatira = next(s for s in self.stats if s["player_id"] == "111")
        assert vatira["shooting_pct"] == pytest.approx(40.0)

    def test_playlist_type_on_player_stats(self):
        for s in self.stats:
            assert s["playlist_type"] == "3v3"

    def test_match_id_on_player_stats(self):
        for s in self.stats:
            assert s["match_id"] == "abc123"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def test_missing_boost_stats_returns_none(self):
        player = _make_player("111", "vatira")
        del player["stats"]["boost"]
        replay = _make_replay(blue_players=[player], orange_players=[_make_player("222", "x")])
        _, stats = parse_replay(replay)
        vatira = next(s for s in stats if s["player_id"] == "111")
        assert vatira["boost_avg"] is None
        assert vatira["boost_bcpm"] is None

    def test_missing_movement_stats_returns_none(self):
        player = _make_player("111", "vatira")
        del player["stats"]["movement"]
        replay = _make_replay(blue_players=[player], orange_players=[_make_player("222", "x")])
        _, stats = parse_replay(replay)
        vatira = next(s for s in stats if s["player_id"] == "111")
        assert vatira["movement_avg_speed"] is None
        assert vatira["movement_percent_supersonic"] is None

    def test_missing_positioning_stats_returns_none(self):
        player = _make_player("111", "vatira")
        del player["stats"]["positioning"]
        replay = _make_replay(blue_players=[player], orange_players=[_make_player("222", "x")])
        _, stats = parse_replay(replay)
        vatira = next(s for s in stats if s["player_id"] == "111")
        assert vatira["positioning_avg_dist_to_ball"] is None
        assert vatira["positioning_percent_most_back"] is None

    def test_missing_core_stats_defaults_to_zero(self):
        player = {"id": {"id": "steam:999"}, "name": "ghost", "stats": {}}
        replay = _make_replay(blue_players=[player], orange_players=[_make_player("222", "x")])
        _, stats = parse_replay(replay)
        ghost = next(s for s in stats if s["player_id"] == "999")
        assert ghost["goals"] == 0
        assert ghost["score"] == 0

    def test_goals_fallback_to_team_stats_core(self):
        """When top-level team goals key is missing, fall back to stats.core.goals."""
        replay = _make_replay(blue_goals=2, orange_goals=1)
        # Remove top-level goals, put them in stats.core instead
        del replay["blue"]["goals"]
        del replay["orange"]["goals"]
        replay["blue"]["stats"] = {"core": {"goals": 2}}
        replay["orange"]["stats"] = {"core": {"goals": 1}}
        match, _ = parse_replay(replay)
        assert match["blue_goals"] == 2
        assert match["orange_goals"] == 1

    def test_team_name_none_when_absent(self):
        replay = _make_replay()
        del replay["blue"]["name"]
        del replay["orange"]["name"]
        match, _ = parse_replay(replay)
        assert match["blue_team_name"] is None
        assert match["orange_team_name"] is None

    def test_empty_teams_produce_no_player_stats(self):
        replay = _make_replay(blue_players=[], orange_players=[])
        match, stats = parse_replay(replay)
        assert match is not None
        assert stats == []

    def test_player_id_without_platform_prefix(self):
        """Platform IDs without a colon (e.g. Epic) should be returned as-is."""
        player = _make_player("epicuser42", "EpicPlayer")
        player["id"]["id"] = "epicuser42"  # no "steam:" prefix
        replay = _make_replay(blue_players=[player], orange_players=[_make_player("222", "x")])
        _, stats = parse_replay(replay)
        epic = next(s for s in stats if s["player_id"] == "epicuser42")
        assert epic is not None
