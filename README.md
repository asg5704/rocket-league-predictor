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
