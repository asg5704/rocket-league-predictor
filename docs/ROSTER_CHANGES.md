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
| `team` | yes | Match an existing team's spelling exactly (e.g. `GENTLE MATES`) to inherit its Elo. A new name starts at the default rating of 1500. |
| `effective` | yes | `YYYY-MM-DD`. If a player has several entries, the latest date wins. |
| `note` | no | Free text. Ignored by the app. |

Add one entry per player who moved. Players who were released with no new team
are not supported yet; leave them as they are.

## Check your edit

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/test_roster_overrides.py -q
```

`test_real_overrides_file_is_valid` fails on unknown or ambiguous player names,
a missing field, or a bad date. At runtime an invalid entry is logged and
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
