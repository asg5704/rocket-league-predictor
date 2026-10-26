# Rocket League Predictor

## Motivation

I need a more robust Data Science-y portfolio project so I decided to take something I'm learning (Data Science & AI), and apply it to something I like (Rocket League) with skills I already have (Frontend/Full-stack)

## Getting Started

FastAPI: Added CORS middleware allowing
localhost:5173.

Vite proxy: /api/\* routes to http://localhost:8000
so no hardcoded port in frontend code.

To test it, start both servers:

# Terminal 1 — backend (from

rocket-league-predictor/)
PYTHONPATH=. uvicorn src.api.main:app --reload

# Terminal 2 — frontend (from

rocket-league-predictor/frontend/)
npm run dev

Then open http://localhost:5173.

## Docker

A single multi-stage image builds the React frontend and serves it (plus the API)
from one FastAPI/uvicorn process — no separate frontend server or CORS needed.

Build the image (from `rocket-league-predictor/`):

```
docker build -t rlcs-optimizer .
```

Run it:

```
docker run -p 8000:8000 -e APP_ENV=production rlcs-optimizer
```

Then open http://localhost:8000 — the UI and API (`/api/players`, `/api/optimize`,
`/api/elo-ratings`) are served from the same origin. The container respects a `PORT`
env var if set (defaults to 8000), which is how platforms like Railway inject their
assigned port: `docker run -e PORT=3000 -p 3000:3000 rlcs-optimizer`.
