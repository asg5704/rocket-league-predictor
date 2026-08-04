"""Pydantic request/response schemas for the RLCS Team Optimizer API."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------

class PlayerOut(BaseModel):
    player_id: str
    display_name: str
    archetype: str
    team_name: str | None
    elo: float


# ---------------------------------------------------------------------------
# GET /players
# ---------------------------------------------------------------------------

class PlayersResponse(BaseModel):
    players: list[PlayerOut]
    total: int


# ---------------------------------------------------------------------------
# POST /optimize
# ---------------------------------------------------------------------------

class WeightsIn(BaseModel):
    synergy: float = Field(default=1.0, ge=0.0)
    archetype: float = Field(default=0.5, ge=0.0)
    elo: float = Field(default=0.3, ge=0.0)


class OptimizeRequest(BaseModel):
    player_ids: list[str] = Field(min_length=3, max_length=120)
    top_k: int = Field(default=5, ge=1, le=50)
    weights: WeightsIn = Field(default_factory=WeightsIn)


class LineupPlayerOut(BaseModel):
    player_id: str
    display_name: str
    archetype: str


class LineupOut(BaseModel):
    rank: int
    players: list[LineupPlayerOut]
    score: float
    synergy: float
    archetype_combo: str
    archetype_bonus: float
    mean_elo: float
    n_matches: int
    low_sample: bool


class OptimizeResponse(BaseModel):
    lineups: list[LineupOut]
    pool_size: int


# ---------------------------------------------------------------------------
# GET /elo-ratings
# ---------------------------------------------------------------------------

class EloRatingOut(BaseModel):
    rank: int
    team_name: str
    elo: float


class EloRatingsResponse(BaseModel):
    ratings: list[EloRatingOut]
    total: int
