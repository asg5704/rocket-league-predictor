# Roster Changes

Teams in the app are derived from each player's **most recent replay
appearance**. After offseason moves that mapping is stale until new replays are
ingested. `data/players/roster_overrides.json` lets you correct it by hand in
the meantime.

## How to add a move

Edit `data/players/roster_overrides.json`:

```json
{
  "overrides": [
    {
      "player": "Oski",
      "team": "EXAMPLE TEAM",
      "effective": "2026-11-20",
      "note": "optional: source or context"
    }
  ]
}
```

| Field | Required | Notes |
|---|---|---|
| `player` | yes | Display name as shown in the app. Case-insensitive. Must match exactly one player. |
| `team` | yes | Matched case-insensitively (and through the alias map) to teams that already have an Elo, so `Wildcard` inherits `WILDCARD`'s rating. A new org starts at the default rating of 1500. |
| `effective` | yes | `YYYY-MM-DD`. If a player has several entries, the latest date wins. |
| `note` | no | Free text. Ignored by the app. |

Add one entry per player who moved. For a player who was released with no new
team, use `"team": null`: they leave their old roster and show as a free agent
(Elo starts at the default 1500 until per-player Elo exists).

## Rebrands, acquisitions and defunct teams

Team metadata lives in `data/processed/team_status.json`:

```json
{
  "NRG ESPORTS": { "country": "us", "status": "active" },
  "VIRTUS.PRO":  { "country": "ru", "status": "defunct", "note": "disbanded" }
}
```

- **Same roster continues under a new name** (a rebrand): add an alias in
  `src/data_collection/team_aliases.py` so history and Elo carry over.
- **The team's story ends** (disbanded, brand absorbed, players scattered): set
  `"status": "defunct"`. The team leaves the ranking and appears under
  "Inactive teams" on the leaderboard; its Elo stays in the model as history.
  Move its players with overrides (a new team, or `null`).
- `country` is a 2-letter ISO code (`gb` for the UK). Teams missing from the
  file are active with no flag. `tests/test_team_status.py` validates the file.

## Players with no replays yet

A player must exist in the registry before an override can move them. For
players with no Steam ID or replays, add them to `data/players/manual_players.json`:

```json
{ "players": [ { "name": "reyyn", "note": "optional" } ] }
```

They get a synthetic id (`manual:reyyn`), show up in the player picker with an
`unknown` archetype and no synergy history, and can then be used in
`roster_overrides.json` like anyone else. If the name later appears in
`player_names.json` with real data, the manual entry is ignored automatically.

## Check your edit

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_roster_overrides.py -q
```

`test_real_overrides_file_is_valid` fails on unknown or ambiguous player names,
a missing field, a bad date, duplicate entries, or the same player assigned to
two teams on the same date. At runtime an invalid entry is logged and
skipped rather than crashing the API, so run the test before you deploy.

## Deploying

The file is copied into the Docker image, so changes need a rebuild and deploy.
Restart the API locally to pick up edits.

## Caveats

- **Elo is still team-based.** A moved player takes on the Elo of the team you
  assign, so their old team's rating no longer follows them. A team whose roster
  changed keeps its old rating. Per-player Elo is the planned fix.
- **Overrides always win over replay data.** They are applied on top of the
  replay-derived team, so a stale entry will keep overriding a later real move.
  After ingesting new replays (see [ETL.md](ETL.md)), delete the entries for
  players who have since played for their new team.
- Overrides change only the team shown and used for Elo. Archetypes and synergy
  stay tied to the player's historical stats.
