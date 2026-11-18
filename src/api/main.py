"""
main.py — RLCS Team Optimizer FastAPI application.

Endpoints
---------
    GET  /api/players       — All known players with archetype, team, and Elo
    POST /api/optimize      — Given a player pool, return the top-k lineups
    GET  /api/elo-ratings   — Team Elo leaderboard

All models are loaded once at startup via the lifespan context manager and
stored on app.state. No model I/O happens during request handling.

Run
---
    PYTHONPATH=. uvicorn src.api.main:app --reload
"""

from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

import pandas as pd  # used in _load_player_teams and _build_player_index
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.api.schemas import (
    EloRatingOut,
    EloRatingsResponse,
    LineupOut,
    LineupPlayerOut,
    OptimizeRequest,
    OptimizeResponse,
    PlayerOut,
    PlayersResponse,
)
from src.models.elo import EloModel
from src.models.synergy_score import SynergyScoreModel
from src.models.team_optimizer import TeamOptimizer

_ROOT = Path(__file__).resolve().parents[2]
_DATA = _ROOT / "data" / "processed"
_MODELS = _ROOT / "data" / "models"


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------

def _load_player_teams(player_stats_path: Path, matches_path: Path) -> pd.DataFrame:
    """Return DataFrame[player_id, team_name] using most recent appearance."""
    ps = pd.read_parquet(player_stats_path)[["match_id", "player_id", "team_side"]]
    matches = pd.read_parquet(matches_path)[
        ["match_id", "blue_team_name", "orange_team_name"]
    ]
    merged = ps.merge(matches, on="match_id")
    merged["team_name"] = merged.apply(
        lambda r: r["blue_team_name"] if r["team_side"] == "blue" else r["orange_team_name"],
        axis=1,
    )
    return (
        merged.sort_values("match_id")
        .groupby("player_id")["team_name"]
        .last()
        .reset_index()
    )


def _load_team_rosters(
    player_stats_path: Path,
    matches_path: Path,
    player_names: dict[str, str],
) -> dict[str, list[str]]:
    """Return team_name → display names of the lineup in the team's latest match."""
    ps = pd.read_parquet(player_stats_path)[["match_id", "player_id", "team_side"]]
    matches = pd.read_parquet(matches_path)[
        ["match_id", "date", "blue_team_name", "orange_team_name"]
    ]
    merged = ps.merge(matches, on="match_id")
    merged["date"] = pd.to_datetime(merged["date"], utc=True)
    merged["team_name"] = merged["blue_team_name"].where(
        merged["team_side"] == "blue", merged["orange_team_name"]
    )
    latest = merged.groupby("team_name")["date"].transform("max")
    current = merged[merged["date"] == latest]
    return {
        team: sorted(
            {player_names.get(pid, pid) for pid in grp["player_id"]},
            key=str.lower,
        )
        for team, grp in current.groupby("team_name")
    }


def _load_team_countries(path: Path) -> dict[str, str]:
    """Return team_name → lowercase ISO 3166-1 alpha-2 code (blank entries skipped)."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text())
    fixes = {"uk": "gb"}  # ISO 3166-1 uses "gb" for the United Kingdom
    codes = {
        team: code.strip().lower()
        for team, code in raw.items()
        if isinstance(code, str) and len(code.strip()) == 2
    }
    return {team: fixes.get(code, code) for team, code in codes.items()}


def _build_player_index(
    player_names: dict[str, str],
    archetypes_df: pd.DataFrame,
    player_teams_df: pd.DataFrame,
    elo_model: EloModel,
) -> dict[str, PlayerOut]:
    """
    Build a player_id → PlayerOut lookup used by both /players and /optimize.
    """
    archetype_map = archetypes_df.set_index("player_id")["archetype"].to_dict()
    team_map = player_teams_df.set_index("player_id")["team_name"].to_dict()

    index: dict[str, PlayerOut] = {}
    for pid, display_name in player_names.items():
        team = team_map.get(pid)
        elo = elo_model.rating(team) if team else elo_model.initial_rating
        index[pid] = PlayerOut(
            player_id=pid,
            display_name=display_name,
            archetype=archetype_map.get(pid, "unknown"),
            team_name=team,
            elo=round(elo, 2),
        )
    return index


# ---------------------------------------------------------------------------
# Lifespan — load everything once at startup
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    _DUMMY_KEYWORDS = {"referee", "admin"}
    player_names: dict[str, str] = {
        pid: name
        for pid, name in json.loads((_DATA / "player_names.json").read_text()).items()
        if not any(kw in name.lower() for kw in _DUMMY_KEYWORDS)
    }
    elo_model = EloModel.load(_MODELS / "elo.pkl")
    synergy_model = SynergyScoreModel.load(_MODELS / "synergy_score.pkl")
    archetypes_df = pd.read_parquet(_DATA / "player_archetypes.parquet")
    player_teams_df = _load_player_teams(
        _DATA / "player_stats.parquet",
        _DATA / "matches.parquet",
    )

    player_index = _build_player_index(
        player_names, archetypes_df, player_teams_df, elo_model
    )

    optimizer = TeamOptimizer(
        synergy_model=synergy_model,
        archetypes_df=archetypes_df,
        player_teams_df=player_teams_df,
        elo_model=elo_model,
    )

    app.state.player_index = player_index
    app.state.optimizer = optimizer
    app.state.elo_model = elo_model
    app.state.team_rosters = _load_team_rosters(
        _DATA / "player_stats.parquet", _DATA / "matches.parquet", player_names
    )
    app.state.team_countries = _load_team_countries(_DATA / "team_countries.json")

    yield


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

_ENV = os.getenv("APP_ENV", "development")
_DOCS_URL = "/docs" if _ENV != "production" else None
_REDOC_URL = "/redoc" if _ENV != "production" else None

_DEFAULT_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
_CORS_ORIGINS = os.getenv("CORS_ORIGINS", _DEFAULT_ORIGINS).split(",")

app = FastAPI(
    title="RLCS Team Optimizer",
    description="Rank RLCS player trios by synergy, archetype balance, and Elo.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=_DOCS_URL,
    redoc_url=_REDOC_URL,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/players", response_model=PlayersResponse)
def get_players() -> PlayersResponse:
    """Return all known players sorted by Elo descending."""
    players = sorted(
        app.state.player_index.values(),
        key=lambda p: p.elo,
        reverse=True,
    )
    return PlayersResponse(players=players, total=len(players))


@app.post("/api/optimize", response_model=OptimizeResponse)
def optimize(req: OptimizeRequest) -> OptimizeResponse:
    """
    Return the top-k lineups from the given player pool.

    Scores each C(n, 3) combo using synergy, archetype bonus, and Elo.
    Players not in the known player index are rejected with 400.
    """
    player_index: dict[str, PlayerOut] = app.state.player_index

    unknown = [pid for pid in req.player_ids if pid not in player_index]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown player_ids: {unknown}",
        )

    weights = {
        "synergy": req.weights.synergy,
        "archetype": req.weights.archetype,
        "elo": req.weights.elo,
    }

    raw_results = app.state.optimizer.optimize(
        player_pool=req.player_ids,
        top_k=req.top_k,
        weights=weights,
    )

    lineups = []
    for r in raw_results:
        lineup_players = [
            LineupPlayerOut(
                player_id=pid,
                display_name=player_index[pid].display_name,
                archetype=player_index[pid].archetype,
            )
            for pid in r["players"]
        ]
        lineups.append(
            LineupOut(
                rank=r["rank"],
                players=lineup_players,
                score=r["score"],
                synergy=r["synergy"],
                archetype_combo=r["archetype_combo"],
                archetype_bonus=r["archetype_bonus"],
                mean_elo=r["mean_elo"],
                n_matches=r["n_matches"],
                low_sample=r["low_sample"],
            )
        )

    return OptimizeResponse(lineups=lineups, pool_size=len(req.player_ids))


@app.get("/api/elo-ratings", response_model=EloRatingsResponse)
def get_elo_ratings() -> EloRatingsResponse:
    """Return all team Elo ratings sorted descending."""
    ratings_df = app.state.elo_model.ratings_df()
    rosters = app.state.team_rosters
    countries = app.state.team_countries
    ratings = [
        EloRatingOut(
            rank=i + 1,
            team_name=row["team_name"],
            elo=round(row["elo"], 2),
            country=countries.get(row["team_name"]),
            roster=rosters.get(row["team_name"], []),
        )
        for i, row in ratings_df.iterrows()
    ]
    return EloRatingsResponse(ratings=ratings, total=len(ratings))


# ---------------------------------------------------------------------------
# Static frontend — mounted last so /api/* routes above take precedence.
# Only present in the Docker image (built by the frontend stage); absent
# during local dev, where Vite's own dev server serves the SPA instead.
# ---------------------------------------------------------------------------

class SPAStaticFiles(StaticFiles):
    """StaticFiles that serves index.html for unknown client-side routes.

    TanStack Router handles paths like /about in the browser, so a direct
    visit or refresh must return the app shell instead of a 404. Missing
    files (anything with an extension, e.g. /assets/x.js) and unknown /api/*
    paths still 404 so real errors are not masked by HTML.
    """

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            is_api = path == "api" or path.startswith("api/")
            has_extension = "." in Path(path).name
            if exc.status_code == 404 and not is_api and not has_extension:
                return await super().get_response("index.html", scope)
            raise


_FRONTEND_DIST = _ROOT / "frontend_dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=_FRONTEND_DIST, html=True), name="frontend")
