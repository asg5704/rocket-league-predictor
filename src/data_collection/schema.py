"""
schema.py

TypedDict definitions for the raw data produced by the Phase 1 pipeline.

Two canonical record types:

  MatchRaw       — one row per match (replay), stored in matches.parquet
  PlayerStatsRaw — one row per player per match, stored in player_stats.parquet

playlist_type is required on both so that the feature engineering and model
steps always know which format (2v2 or 3v3) a record belongs to.
"""

from typing import Literal, Optional, TypedDict

# ---------------------------------------------------------------------------
# Playlist type
# ---------------------------------------------------------------------------

PlaylistType = Literal["2v2", "3v3"]

# Maps Ballchasing playlist_id values to our internal PlaylistType.
# Only tournament and ranked standard/doubles are relevant for pro data.
PLAYLIST_MAP: dict[str, PlaylistType] = {
    "tournament-standard": "3v3",
    "ranked-standard": "3v3",
    "tournament-doubles": "2v2",
    "ranked-doubles": "2v2",
    # RLCS pro replays are uploaded as private or local-lobby lobbies
    "private": "3v3",
    "local-lobby": "3v3",
}


def resolve_playlist_type(playlist_id: str) -> Optional[PlaylistType]:
    """
    Map a Ballchasing playlist_id to our PlaylistType.
    Returns None if the playlist is not relevant (e.g. rumble, hoops).
    """
    return PLAYLIST_MAP.get(playlist_id)


# ---------------------------------------------------------------------------
# Match record  (one per replay)
# ---------------------------------------------------------------------------

class MatchRaw(TypedDict):
    match_id: str                   # Ballchasing replay ID
    date: str                       # ISO 8601, e.g. "2024-03-01T18:00:00Z"
    playlist_type: PlaylistType     # "3v3" | "2v2"
    team_size: int                  # 2 | 3  (derived from playlist_type)
    blue_team_name: Optional[str]   # org name from replay, may be None
    orange_team_name: Optional[str]
    blue_goals: int
    orange_goals: int
    winner: Literal["blue", "orange"]
    duration: int                   # seconds
    overtime: bool
    season: Optional[str]           # RLCS season label, e.g. "2023-24" (from registry lookup)
    source_group: Optional[str]     # Ballchasing group ID the replay came from


# ---------------------------------------------------------------------------
# Per-player stats record  (one per player per replay)
# ---------------------------------------------------------------------------

class PlayerStatsRaw(TypedDict):
    match_id: str                   # FK → MatchRaw.match_id
    player_id: str                  # platform_id without steam: prefix
    team_side: Literal["blue", "orange"]
    playlist_type: PlaylistType     # duplicated from match for convenience in queries
    # --- core ---
    goals: int
    assists: int
    saves: int
    shots: int
    score: int
    shooting_pct: Optional[float]   # shooting_percentage from core stats
    # --- demo ---
    demos_inflicted: int
    demos_taken: int
    # --- boost ---
    boost_avg: Optional[float]      # avg_amount
    boost_bcpm: Optional[float]     # boost collected per minute (efficiency)
    boost_amount_stolen: Optional[float]   # boost pads stolen from opponents
    boost_percent_zero: Optional[float]    # % of match spent with 0 boost
    boost_percent_full: Optional[float]    # % of match at full boost
    # --- movement ---
    movement_avg_speed: Optional[float]          # average speed (uu/s)
    movement_percent_supersonic: Optional[float] # % time at supersonic speed
    movement_percent_high_air: Optional[float]   # % time in high air (aerials)
    movement_percent_ground: Optional[float]     # % time on the ground
    # --- positioning ---
    positioning_avg_dist_to_ball: Optional[float]       # avg distance to ball
    positioning_percent_defensive_third: Optional[float]
    positioning_percent_offensive_third: Optional[float]
    positioning_percent_behind_ball: Optional[float]    # rotation discipline
    positioning_percent_most_back: Optional[float]      # last defender tendency
