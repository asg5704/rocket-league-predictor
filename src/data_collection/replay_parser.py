"""
replay_parser.py

Parse a raw Ballchasing replay JSON dict into typed records for storage.

Entry point
-----------
    match, player_stats = parse_replay(replay_json, source_group="rlcs-abc123")

Returns
-------
    match        : MatchRaw | None   — None if the playlist is irrelevant (e.g. hoops)
    player_stats : list[PlayerStatsRaw]  — one record per player in the match

The caller is responsible for filtering out None matches before writing to parquet.
"""

from typing import Optional

from src.data_collection.team_aliases import canonical_team
from src.data_collection.schema import (
    MatchRaw,
    PlayerStatsRaw,
    PlaylistType,
    resolve_playlist_type,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _winner(blue_goals: int, orange_goals: int) -> str:
    return "blue" if blue_goals > orange_goals else "orange"


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_player_stats(
    player: dict,
    match_id: str,
    team_side: str,
    playlist_type: PlaylistType,
) -> PlayerStatsRaw:
    """
    Extract per-player stats from a Ballchasing player object.

    Ballchasing nests stats under player["stats"]["core"] and
    player["stats"]["boost"]. Both may be absent for bot/missing players.
    """
    raw_pid = player.get("id", {}).get("id", "")
    # Strip platform prefix (e.g. "steam:76561198...") → bare numeric ID
    player_id = raw_pid.split(":", 1)[-1] if ":" in raw_pid else raw_pid

    stats = player.get("stats", {})
    core = stats.get("core", {})
    boost = stats.get("boost", {})
    demo = stats.get("demo", {})
    movement = stats.get("movement", {})
    positioning = stats.get("positioning", {})

    return PlayerStatsRaw(
        match_id=match_id,
        player_id=player_id,
        team_side=team_side,
        playlist_type=playlist_type,
        # core
        goals=_safe_int(core.get("goals")),
        assists=_safe_int(core.get("assists")),
        saves=_safe_int(core.get("saves")),
        shots=_safe_int(core.get("shots")),
        score=_safe_int(core.get("score")),
        shooting_pct=_safe_float(core.get("shooting_percentage")),
        # demo
        demos_inflicted=_safe_int(demo.get("inflicted")),
        demos_taken=_safe_int(demo.get("taken")),
        # boost
        boost_avg=_safe_float(boost.get("avg_amount")),
        boost_bcpm=_safe_float(boost.get("bcpm")),
        boost_amount_stolen=_safe_float(boost.get("amount_stolen")),
        boost_percent_zero=_safe_float(boost.get("percent_zero_boost")),
        boost_percent_full=_safe_float(boost.get("percent_full_boost")),
        # movement
        movement_avg_speed=_safe_float(movement.get("avg_speed")),
        movement_percent_supersonic=_safe_float(movement.get("percent_supersonic_speed")),
        movement_percent_high_air=_safe_float(movement.get("percent_high_air")),
        movement_percent_ground=_safe_float(movement.get("percent_ground")),
        # positioning
        positioning_avg_dist_to_ball=_safe_float(positioning.get("avg_distance_to_ball")),
        positioning_percent_defensive_third=_safe_float(positioning.get("percent_defensive_third")),
        positioning_percent_offensive_third=_safe_float(positioning.get("percent_offensive_third")),
        positioning_percent_behind_ball=_safe_float(positioning.get("percent_behind_ball")),
        positioning_percent_most_back=_safe_float(positioning.get("percent_most_back")),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_replay(
    replay: dict,
    source_group: Optional[str] = None,
) -> tuple[Optional[MatchRaw], list[PlayerStatsRaw]]:
    """
    Parse a full Ballchasing replay JSON into (MatchRaw, [PlayerStatsRaw]).

    Returns (None, []) if the replay's playlist is not relevant to the project
    (e.g. Hoops, Rumble, or any non-standard/doubles playlist).

    Parameters
    ----------
    replay      : dict  Full JSON response from GET /replays/{id}
    source_group: str   Ballchasing group ID this replay came from, if any
    """
    playlist_id = replay.get("playlist_id", "")
    playlist_type = resolve_playlist_type(playlist_id)
    if playlist_type is None:
        return None, []

    match_id: str = replay["id"]
    team_size = 3 if playlist_type == "3v3" else 2

    blue = replay.get("blue", {})
    orange = replay.get("orange", {})

    blue_goals = _safe_int(blue.get("goals"))
    orange_goals = _safe_int(orange.get("goals"))

    # Fallback: derive goals from team stats if top-level goals key is missing
    if blue_goals == 0 and orange_goals == 0:
        blue_core = blue.get("stats", {}).get("core", {})
        orange_core = orange.get("stats", {}).get("core", {})
        blue_goals = _safe_int(blue_core.get("goals"))
        orange_goals = _safe_int(orange_core.get("goals"))

    match = MatchRaw(
        match_id=match_id,
        date=replay.get("date", ""),
        playlist_type=playlist_type,
        team_size=team_size,
        blue_team_name=canonical_team(blue.get("name")),
        orange_team_name=canonical_team(orange.get("name")),
        blue_goals=blue_goals,
        orange_goals=orange_goals,
        winner=_winner(blue_goals, orange_goals),
        duration=_safe_int(replay.get("duration")),
        overtime=bool(replay.get("overtime")),
        season=replay.get("season"),
        source_group=source_group,
    )

    player_stats: list[PlayerStatsRaw] = []
    for side, team in (("blue", blue), ("orange", orange)):
        for player in team.get("players", []):
            player_stats.append(
                _parse_player_stats(player, match_id, side, playlist_type)
            )

    return match, player_stats
