"""
tests/test_batch_downloader.py

Unit tests for src/data_collection/batch_downloader.py.

All tests use temp directories and mocked API calls — no network or disk I/O
outside of the temp dirs managed by pytest's tmp_path fixture.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.data_collection.batch_downloader import BatchDownloader


# ---------------------------------------------------------------------------
# Helpers shared with test_replay_parser — kept inline to avoid coupling
# ---------------------------------------------------------------------------

def _make_player(
    platform_id: str,
    name: str,
    goals=1,
    assists=0,
    saves=1,
    shots=2,
    score=250,
    demos_inflicted=0,
    demos_taken=0,
    boost_avg=40.0,
) -> dict:
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
                "shooting_percentage": 50.0,
            },
            "boost": {
                "avg_amount": boost_avg,
                "bcpm": 200.0,
                "amount_stolen": 100.0,
                "percent_zero_boost": 10.0,
                "percent_full_boost": 20.0,
            },
            "demo": {
                "inflicted": demos_inflicted,
                "taken": demos_taken,
            },
            "movement": {
                "avg_speed": 1400.0,
                "percent_supersonic_speed": 15.0,
                "percent_high_air": 8.0,
                "percent_ground": 65.0,
            },
            "positioning": {
                "avg_distance_to_ball": 2000.0,
                "percent_defensive_third": 35.0,
                "percent_offensive_third": 30.0,
                "percent_behind_ball": 55.0,
                "percent_most_back": 33.0,
            },
        },
    }


def _make_replay(
    replay_id="abc123",
    playlist_id="tournament-standard",
    blue_goals=2,
    orange_goals=1,
    blue_name="Karmine Corp",
    orange_name="NRG",
    duration=300,
    overtime=False,
    date="2024-03-01T18:00:00Z",
    season="2023-24",
    group_id=None,
    blue_players=None,
    orange_players=None,
) -> dict:
    if blue_players is None:
        blue_players = [
            _make_player("p1", "vatira", goals=1),
            _make_player("p2", "zen", assists=1),
            _make_player("p3", "monkey moon", saves=2),
        ]
    if orange_players is None:
        orange_players = [
            _make_player("p4", "jstn", goals=1),
            _make_player("p5", "garrettg"),
            _make_player("p6", "chicago"),
        ]

    replay = {
        "id": replay_id,
        "playlist_id": playlist_id,
        "date": date,
        "season": season,
        "duration": duration,
        "overtime": overtime,
        "blue": {"name": blue_name, "goals": blue_goals, "players": blue_players},
        "orange": {"name": orange_name, "goals": orange_goals, "players": orange_players},
    }
    if group_id:
        replay["group"] = {"id": group_id}
    return replay


def _write_replay_json(directory: Path, replay: dict) -> Path:
    path = directory / f"{replay['id']}.json"
    path.write_text(json.dumps(replay))
    return path


def _make_api_mock() -> MagicMock:
    api = MagicMock()
    api.download_group_replays.return_value = 0
    api.download_player_replays.return_value = 0
    return api


# ---------------------------------------------------------------------------
# BatchDownloader construction
# ---------------------------------------------------------------------------

class TestBatchDownloaderInit:
    def test_creates_directories(self, tmp_path):
        raw_dir = tmp_path / "raw"
        out_dir = tmp_path / "processed"
        assert not raw_dir.exists()
        assert not out_dir.exists()

        BatchDownloader(api=_make_api_mock(), raw_dir=raw_dir, output_dir=out_dir)

        assert raw_dir.is_dir()
        assert out_dir.is_dir()


# ---------------------------------------------------------------------------
# download_groups / download_players — delegate to the API client
# ---------------------------------------------------------------------------

class TestDownloadDelegation:
    def test_download_groups_calls_api_for_each_group(self, tmp_path):
        api = _make_api_mock()
        api.download_group_replays.side_effect = [3, 5]
        dl = BatchDownloader(api, tmp_path / "raw", tmp_path / "out")

        result = dl.download_groups(["group-a", "group-b"], delay=0)

        assert api.download_group_replays.call_count == 2
        calls = api.download_group_replays.call_args_list
        assert calls[0][0][0] == "group-a"
        assert calls[1][0][0] == "group-b"
        assert result == 8  # 3 + 5

    def test_download_groups_empty_list(self, tmp_path):
        api = _make_api_mock()
        dl = BatchDownloader(api, tmp_path / "raw", tmp_path / "out")

        result = dl.download_groups([])
        assert result == 0
        api.download_group_replays.assert_not_called()

    def test_download_players_delegates(self, tmp_path):
        api = _make_api_mock()
        api.download_player_replays.return_value = 7
        dl = BatchDownloader(api, tmp_path / "raw", tmp_path / "out")

        result = dl.download_players(["steam:111", "steam:222"], playlist="tournament-standard")

        api.download_player_replays.assert_called_once()
        call_kwargs = api.download_player_replays.call_args
        assert call_kwargs[0][0] == ["steam:111", "steam:222"]
        assert result == 7


# ---------------------------------------------------------------------------
# parse_all
# ---------------------------------------------------------------------------

class TestParseAll:
    def test_parses_valid_replay_json(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        replay = _make_replay(replay_id="r1")
        _write_replay_json(raw_dir, replay)

        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        matches, stats = dl.parse_all()

        assert len(matches) == 1
        assert matches[0]["match_id"] == "r1"
        assert len(stats) == 6  # 3 blue + 3 orange

    def test_skips_irrelevant_playlist(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        replay = _make_replay(replay_id="r1", playlist_id="hoops")
        _write_replay_json(raw_dir, replay)

        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        matches, stats = dl.parse_all()

        assert matches == []
        assert stats == []

    def test_deduplicates_same_match_id(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        # Write the same replay twice under different filenames — simulate the
        # edge case where a replay appears in two group downloads.
        replay = _make_replay(replay_id="dup")
        (raw_dir / "dup.json").write_text(json.dumps(replay))
        # Overwrite with same content (same match_id after parse)
        (raw_dir / "dup.json").write_text(json.dumps(replay))

        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        matches, stats = dl.parse_all()

        assert len(matches) == 1

    def test_skips_malformed_json(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        (raw_dir / "bad.json").write_text("{not valid json")
        valid = _make_replay(replay_id="good")
        _write_replay_json(raw_dir, valid)

        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        matches, stats = dl.parse_all()

        assert len(matches) == 1
        assert matches[0]["match_id"] == "good"

    def test_empty_raw_dir_returns_empty(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        matches, stats = dl.parse_all()
        assert matches == []
        assert stats == []

    def test_parses_multiple_replays(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        for rid in ["r1", "r2", "r3"]:
            _write_replay_json(raw_dir, _make_replay(replay_id=rid))

        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        matches, stats = dl.parse_all()

        assert len(matches) == 3
        assert len(stats) == 18  # 6 players × 3 replays

    def test_extracts_source_group_from_replay_json(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        replay = _make_replay(replay_id="g1", group_id="rlcs-spring-2024")
        _write_replay_json(raw_dir, replay)

        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        matches, _ = dl.parse_all()

        assert matches[0]["source_group"] == "rlcs-spring-2024"

    def test_source_group_none_when_absent(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        replay = _make_replay(replay_id="ng1")  # no group_id
        _write_replay_json(raw_dir, replay)

        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        matches, _ = dl.parse_all()

        assert matches[0]["source_group"] is None

    def test_player_ids_strip_steam_prefix(self, tmp_path):
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        _write_replay_json(raw_dir, _make_replay(replay_id="r1"))

        dl = BatchDownloader(_make_api_mock(), raw_dir, tmp_path / "out")
        _, stats = dl.parse_all()

        for s in stats:
            assert ":" not in s["player_id"], f"Unexpected prefix in: {s['player_id']}"


# ---------------------------------------------------------------------------
# write_parquet
# ---------------------------------------------------------------------------

class TestWriteParquet:
    def _make_dl(self, tmp_path):
        return BatchDownloader(_make_api_mock(), tmp_path / "raw", tmp_path / "out")

    def test_writes_both_parquet_files(self, tmp_path):
        dl = self._make_dl(tmp_path)
        replay = _make_replay(replay_id="r1")
        raw_dir = tmp_path / "raw"
        _write_replay_json(raw_dir, replay)
        matches, stats = dl.parse_all()

        dl.write_parquet(matches, stats)

        assert (tmp_path / "out" / "matches.parquet").exists()
        assert (tmp_path / "out" / "player_stats.parquet").exists()

    def test_parquet_content_correct(self, tmp_path):
        dl = self._make_dl(tmp_path)
        raw_dir = tmp_path / "raw"
        _write_replay_json(raw_dir, _make_replay(replay_id="r1"))
        matches, stats = dl.parse_all()
        dl.write_parquet(matches, stats)

        df_m = pd.read_parquet(tmp_path / "out" / "matches.parquet")
        df_s = pd.read_parquet(tmp_path / "out" / "player_stats.parquet")

        assert list(df_m["match_id"]) == ["r1"]
        assert len(df_s) == 6
        assert set(df_s["match_id"]) == {"r1"}

    def test_incremental_update_merges_new_records(self, tmp_path):
        dl = self._make_dl(tmp_path)
        raw_dir = tmp_path / "raw"

        # First batch
        _write_replay_json(raw_dir, _make_replay(replay_id="r1"))
        m1, s1 = dl.parse_all()
        dl.write_parquet(m1, s1)

        # Second batch — new replay only
        for f in raw_dir.glob("*.json"):
            f.unlink()
        _write_replay_json(raw_dir, _make_replay(replay_id="r2"))
        m2, s2 = dl.parse_all()
        dl.write_parquet(m2, s2)

        df_m = pd.read_parquet(tmp_path / "out" / "matches.parquet")
        df_s = pd.read_parquet(tmp_path / "out" / "player_stats.parquet")

        assert set(df_m["match_id"]) == {"r1", "r2"}
        assert len(df_s) == 12  # 6 players × 2 replays

    def test_incremental_update_deduplicates_existing(self, tmp_path):
        dl = self._make_dl(tmp_path)
        raw_dir = tmp_path / "raw"

        # Same replay written twice → should not double-count
        _write_replay_json(raw_dir, _make_replay(replay_id="r1"))
        m1, s1 = dl.parse_all()
        dl.write_parquet(m1, s1)

        m2, s2 = dl.parse_all()
        dl.write_parquet(m2, s2)

        df_m = pd.read_parquet(tmp_path / "out" / "matches.parquet")
        assert len(df_m) == 1

    def test_no_write_on_empty_input(self, tmp_path):
        dl = self._make_dl(tmp_path)
        dl.write_parquet([], [])

        assert not (tmp_path / "out" / "matches.parquet").exists()
        assert not (tmp_path / "out" / "player_stats.parquet").exists()


# ---------------------------------------------------------------------------
# run — end-to-end orchestration
# ---------------------------------------------------------------------------

class TestRun:
    def test_run_raises_if_no_ids_given(self, tmp_path):
        dl = BatchDownloader(_make_api_mock(), tmp_path / "raw", tmp_path / "out")
        with pytest.raises(ValueError, match="Provide at least one"):
            dl.run()

    def test_run_calls_download_groups_and_writes_parquet(self, tmp_path):
        api = _make_api_mock()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()
        # Simulate the API "downloading" a file into raw_dir
        def fake_group_download(group_id, output_dir, delay, max_replays):
            _write_replay_json(Path(output_dir), _make_replay(replay_id="r1"))
            return 1
        api.download_group_replays.side_effect = fake_group_download

        dl = BatchDownloader(api, raw_dir, tmp_path / "out")
        dl.run(group_ids=["rlcs-spring"], delay=0)

        assert (tmp_path / "out" / "matches.parquet").exists()
        df = pd.read_parquet(tmp_path / "out" / "matches.parquet")
        assert len(df) == 1

    def test_run_calls_download_players_and_writes_parquet(self, tmp_path):
        api = _make_api_mock()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        def fake_player_download(player_ids, output_dir, playlist, delay, max_per_player):
            _write_replay_json(Path(output_dir), _make_replay(replay_id="r1"))
            return 1
        api.download_player_replays.side_effect = fake_player_download

        dl = BatchDownloader(api, raw_dir, tmp_path / "out")
        dl.run(player_ids=["steam:111", "steam:222"], delay=0)

        assert (tmp_path / "out" / "matches.parquet").exists()

    def test_run_no_relevant_matches_skips_write(self, tmp_path):
        api = _make_api_mock()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        def fake_group_download(group_id, output_dir, delay, max_replays):
            # Write a hoops replay — parse_all will skip it
            _write_replay_json(Path(output_dir), _make_replay(replay_id="h1", playlist_id="hoops"))
            return 1
        api.download_group_replays.side_effect = fake_group_download

        dl = BatchDownloader(api, raw_dir, tmp_path / "out")
        dl.run(group_ids=["some-group"], delay=0)

        assert not (tmp_path / "out" / "matches.parquet").exists()

    def test_run_combines_groups_and_players(self, tmp_path):
        api = _make_api_mock()
        raw_dir = tmp_path / "raw"
        raw_dir.mkdir()

        def fake_group_download(group_id, output_dir, delay, max_replays):
            _write_replay_json(Path(output_dir), _make_replay(replay_id="g1"))
            return 1

        def fake_player_download(player_ids, output_dir, playlist, delay, max_per_player):
            _write_replay_json(Path(output_dir), _make_replay(replay_id="p1"))
            return 1

        api.download_group_replays.side_effect = fake_group_download
        api.download_player_replays.side_effect = fake_player_download

        dl = BatchDownloader(api, raw_dir, tmp_path / "out")
        dl.run(group_ids=["g"], player_ids=["steam:111"], delay=0)

        df = pd.read_parquet(tmp_path / "out" / "matches.parquet")
        assert set(df["match_id"]) == {"g1", "p1"}
