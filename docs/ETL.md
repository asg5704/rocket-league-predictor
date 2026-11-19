# ETL — Adding New Data & Retraining

Reusable checklist for pulling in a new Ballchasing group and retraining every
downstream model. Run all commands from the `rocket-league-predictor/` project
root with the venv active:

```bash
source .venv/bin/activate   # or prefix commands with .venv/bin/python
```

`BALLCHASING_API_KEY` must be set in `.env` (already configured if you've run
the pipeline before).

---

## 1. Find a new group ID on ballchasing.com

1. Go to ballchasing.com and use group search — terms like `"RLCS 2026"`,
   `"RLCS major"`, or a specific event name surface community-uploaded groups.
2. Open the group and sanity-check it before using it: replay count, date
   range, and recognizable team names.
3. The group ID is the slug at the end of the URL, e.g.
   `ballchasing.com/group/rlcs-2026-major-2-lan-xxxxxxxxxx` → ID is
   `rlcs-2026-major-2-lan-xxxxxxxxxx`.

Only 3v3/2v2 tournament lobbies are useful — this project scopes to pro RLCS
matches only, not ranked.

---

## 2. Download + parse the new group (incremental)

```bash
python -m src.data_collection.batch_downloader --groups <new_group_id>
```

- Pass **only the new group ID(s)** — replays already cached in
  `data/raw/replays/` are skipped automatically, and `matches.parquet` /
  `player_stats.parquet` are merged with existing rows (dedup by `match_id`,
  last write wins). No need to re-pass old group IDs.
- You can pass multiple new groups at once: `--groups id1 id2 id3`.
- Check the printed summary — if it reports 0 valid matches for an
  all-new playlist type, see the `PLAYLIST_MAP` note at the bottom of this doc.

---

## 3. (Optional) Enrich the player registry

If the new group introduces players not already in
`data/players/pro_players_raw.json`, extract and manually enrich them:

```bash
python src/data_collection/extract_pro_players.py --groups <new_group_id>
```

This auto-extracts `platform_id`, `display_names`, and `frequent_teammates`
for new players. Cross-reference each new player on Liquipedia and manually
fill in `real_name`, `country`, and `team_history` (org + date range) in the
registry file.

This step is **not required** for retraining — the model pipeline runs
directly off `player_stats.parquet` / `matches.parquet` and doesn't depend on
the registry. Only do this if you want the roster/team-optimizer UI to show
correct names for the new players.

---

## 4. Retrain the pipeline, in order

Each step reads the previous step's output. Run them in this exact order —
later steps depend on artifacts written by earlier ones.

### 4-pre. Check team-name aliases

Ballchasing team names are free text, so one org can show up under several
spellings. After a download, list the distinct names
(`pd.read_parquet("data/processed/matches.parquet")` → union of
`blue_team_name` / `orange_team_name`) and look for near-duplicates (e.g.
"NRG" vs "NRG ESPORTS"). Add any to `ALIASES` in
`src/data_collection/team_aliases.py` (alias → canonical full name), then run
`python -m src.data_collection.team_aliases` to rewrite the existing parquet.
New downloads are canonicalised automatically at parse time. Also add any new
team to `data/processed/team_status.json` (country, and `"status": "defunct"` if it has ended).

### 4a. Elo ratings

```bash
python -m src.models.elo
```

Fits per-player Elo (K=16) from `data/processed/matches.parquet` and
`player_stats.parquet` → writes `data/processed/elo_ratings.parquet` (per-match
pre-match snapshots) and `data/models/elo.pkl` (a `PlayerEloModel`; the old
team-level pickle will not load). The team leaderboard is not stored: the API
derives it at startup from current rosters.

Optional: `PYTHONPATH=. python scripts/backtest_player_elo.py --k 16 24 32`
compares team vs player Elo on held-out matches.

### 4b. Rebuild features

```bash
python -m src.features.feature_engineer
```

Reads `data/processed/matches.parquet`, `player_stats.parquet`, and
`data/models/elo.pkl` (a player-level model; must exist — run step 4a first) → writes
`data/processed/features.parquet`.

### 4c. Win probability model

```bash
python -m src.models.win_probability
```

Reads `data/processed/features.parquet` → writes
`data/models/win_probability_logistic.pkl`, `win_probability_xgboost.pkl`,
and `data/models/cv_results.json` (check accuracy/ROC-AUC here for regressions).

### 4d. Player archetypes

```bash
python -m src.models.player_archetypes
```

Reads `data/processed/player_stats.parquet` → writes
`data/processed/player_archetypes.parquet`,
`data/models/player_archetypes_kmeans.pkl`, `player_archetypes_gmm.pkl`,
and `archetype_results.json`.

### 4e. Synergy score

```bash
python -m src.models.synergy_score
```

Reads `features.parquet`, `player_stats.parquet`, `player_archetypes.parquet`,
and `win_probability_logistic.pkl` → writes
`data/processed/synergy_scores.parquet` and `data/models/synergy_score.pkl`.

### 4f. (Optional) Sanity-check the team optimizer

```bash
python -m src.models.team_optimizer
```

Not a required artifact-producing step (the API imports `TeamOptimizer`
directly) — just prints top-10 lineups from the current player pool as a
smoke test.

### 4g. Export the archetype cluster visualization

```bash
python -m src.models.export_archetype_viz
```

Reads `data/processed/player_archetypes.parquet`,
`data/models/player_archetypes_kmeans.pkl`, and
`data/processed/player_names.json` (must exist — run step 4d first) → writes
`frontend/src/data/archetype_clusters.json`, the static PCA-projected 2D
points the About page scatter plot imports. Visualization only; it doesn't
affect the model or archetype assignments. After re-running, check the About
page text (silhouette score, cluster descriptions) still matches the new
results in `archetype_results.json`.

### 4h. Log the snapshot in the About page changelog

Add a new entry at the **top** of `frontend/src/data/model_changelog.json`
(date, event name, match/player/team counts, XGBoost accuracy + ROC-AUC from
`cv_results.json`, silhouette from `archetype_results.json`, and the new top 3).
The About page renders it automatically. Also update the hardcoded counts in
`frontend/src/routes/about.tsx` (matches, players, teams, silhouette).

### 4i. (Optional) Synergy diagnostics

```bash
PYTHONPATH=. python scripts/synergy_diagnostics.py --json /tmp/synergy_diagnostics.json
```

Reads `matches.parquet`, `player_stats.parquet`, `synergy_scores.parquet`, and
`data/models/elo.pkl`. Reports which team stats predict winning, whether playstyle
similarity relates to synergy, whether synergy's spread exceeds pure luck, and how
much synergy overlaps with team strength. Re-run after each retrain: the numbers
that matter are the noise check (observed SD vs the pure-luck band) and the Elo
overlap. Elo overlap is in-sample, so read it as an upper bound.

---

## 5. What the API actually loads

After retraining, the FastAPI backend (`src/api/main.py`) reads these files
at startup — confirm they're all fresh before restarting the server:

- `data/models/elo.pkl`
- `data/models/synergy_score.pkl`
- `data/processed/player_archetypes.parquet`
- `data/processed/player_stats.parquet`
- `data/processed/matches.parquet`

Restart the backend (or redeploy) to pick up the new artifacts.

---

## 6. Verify

```bash
python -m pytest tests/ --cov=src --cov-report=term-missing
```

Tests use fixtures, not the real data, so they won't catch data regressions —
but they will catch a broken pipeline. Also worth eyeballing:

- `data/models/cv_results.json` — did accuracy/ROC-AUC move a lot?
- The `n_matches` / team counts printed by each step — did the new group
  actually add rows, or get silently filtered?

---

## Known gotchas

- **New playlist IDs get silently filtered.** RLCS group replays have shown
  up tagged `tournament-standard`, `private`, and `local-lobby` depending on
  who uploaded them — never a consistent value. If `batch_downloader` reports
  0 valid matches after downloading, inspect a raw JSON in
  `data/raw/replays/` for its actual `playlist_id` and add it to
  `PLAYLIST_MAP` in `src/data_collection/schema.py`.
- **Substitute players / corrupted replays.** `build_features` drops any
  match where either team doesn't have exactly 3 players — expect the row
  count after step 4b to be slightly below the raw match count.
- **Run order matters.** `build_features` (4b) needs `elo.pkl`, and
  `synergy_score` (4e) needs both `features.parquet` and
  `win_probability_logistic.pkl` — skipping ahead will throw a
  file-not-found error.

### Top 10 from previous iteration

> Pre-10/5/2026

1. Gentlemates
2. Team Vitality
3. Wildcard
4. Team Falcons
5. Made in Brazil (MiB)
6. Delacruz
7. NRG Esports
8. Pioneers
9. Chromax
10. Karmine Corp

> Past 10/6/2026

1. Gentlemates
2. Team Falcons
3. Wildcard
4. Shopify Rebellion
5. Made in Brazil
6. Team Vitality
7. Delacruz
8. NRG Esports
9. Pioneeers
10. Chromax

## Dependency audit

```bash
pip install pip-audit
pip-audit -r requirements.txt --no-deps --disable-pip
pip-audit -r requirements-prod.txt --no-deps --disable-pip
```

Also runs in CI (`.github/workflows/pip-audit.yml`) on requirements changes and
weekly. When it flags a package, bump the pin in `requirements.txt` (and
`requirements-prod.txt` if it's a runtime dep), then re-run the tests.
