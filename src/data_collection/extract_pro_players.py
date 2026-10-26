"""
extract_pro_players.py

Discovers RLCS pro players by sampling replay groups on Ballchasing and
extracting the unique player platform IDs contained in those replays.

The script operates in two modes:

  SEARCH mode  — lists groups matching a search term so you can find group IDs.
  EXTRACT mode — samples replays from one or more group IDs and writes
                 data/players/pro_players_raw.json.

Usage
-----
  # Step 1: find group IDs for the events you want
  python src/data_collection/extract_pro_players.py --search "RLCS 2024"

  # Step 2: extract players from those groups
  python src/data_collection/extract_pro_players.py \\
      --groups <group_id_1> <group_id_2> \\
      --max-per-group 100

Output
------
  data/players/pro_players_raw.json

  Each player entry contains:
    - platform_id    : exact ID for the Ballchasing API (e.g. "steam:76561198xxxxxx")
    - display_names  : all names seen across replays (pros sometimes change IGNs)
    - replay_count   : number of replays this player appeared in
    - team_sides     : team names seen in replays (often blank, but captured when present)
    - teammates      : other players they appeared with most — helps infer org/roster

  Fields left blank for manual completion:
    - real_name, country, team_history
"""

import argparse
import json
import os
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Allow running from the project root
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from src.data_collection.ballchasing_api import BallchasingAPI


# ---------------------------------------------------------------------------
# Replay parsing
# ---------------------------------------------------------------------------

def _extract_platform_id(player: dict) -> str | None:
    """
    Pull the platform ID string out of a player object.

    Ballchasing nests it as player["id"]["id"], e.g. "steam:76561198xxxxxx".
    Guard against missing/malformed data.
    """
    try:
        return player["id"]["id"]
    except (KeyError, TypeError):
        return None


def _parse_replay_players(replay: dict) -> list[dict]:
    """
    Return a flat list of player records from a single replay.

    Each record:
      {
        "platform_id": "steam:76561198xxxxxx",
        "display_name": "jstn.",
        "team_name": "NRG" | None,   # team org name when present in replay
      }
    """
    records = []
    for side in ("blue", "orange"):
        team = replay.get(side, {})
        team_name = team.get("name")  # org name — present in some RLCS uploads
        for player in team.get("players", []):
            pid = _extract_platform_id(player)
            if not pid:
                continue
            records.append({
                "platform_id": pid,
                "display_name": player.get("name", ""),
                "team_name": team_name,
            })
    return records


# ---------------------------------------------------------------------------
# Core extraction
# ---------------------------------------------------------------------------

def extract_players_from_groups(
    client: BallchasingAPI,
    group_ids: list[str],
    max_per_group: int = 100,
    delay: float = 1.2,
) -> dict:
    """
    Sample replays from each group and build a player registry.

    Returns a dict keyed by platform_id with aggregated stats.
    """
    # platform_id → aggregated data
    players: dict[str, dict] = {}
    # platform_id → Counter of co-appearing platform_ids
    co_appearances: dict[str, Counter] = defaultdict(Counter)

    total_replays = 0

    for group_id in group_ids:
        print(f"\n--- Group: {group_id} ---")

        try:
            group_meta = client.get_group(group_id)
            group_name = group_meta.get("name", group_id)
            print(f"    Name : {group_name}")
            print(f"    Direct replays: {group_meta.get('direct_replays', '?')}")
        except Exception as e:
            print(f"    [warn] Could not fetch group metadata: {e}")
            group_name = group_id

        replays_this_group = 0
        for meta in client.iter_replays(group=group_id, max_replays=max_per_group, delay=delay):
            replay_id = meta["id"]
            try:
                replay = client.get_replay(replay_id)
            except Exception as e:
                print(f"  [error] {replay_id}: {e}")
                continue
            finally:
                # iter_replays() only delays between paginated list requests,
                # not these per-replay detail fetches — without this the loop
                # blows through the ~2 req/s rate limit in a few seconds.
                time.sleep(delay)

            records = _parse_replay_players(replay)
            if not records:
                continue

            # Update per-player aggregates
            for rec in records:
                pid = rec["platform_id"]
                if pid not in players:
                    players[pid] = {
                        "platform_id": pid,
                        "display_names": [],
                        "replay_count": 0,
                        "team_names_seen": [],
                        "source_groups": [],
                        # — filled in manually after extraction —
                        "real_name": None,
                        "country": None,
                        "team_history": [],
                    }

                entry = players[pid]
                entry["replay_count"] += 1

                name = rec["display_name"]
                if name and name not in entry["display_names"]:
                    entry["display_names"].append(name)

                if rec["team_name"] and rec["team_name"] not in entry["team_names_seen"]:
                    entry["team_names_seen"].append(rec["team_name"])

                if group_id not in entry["source_groups"]:
                    entry["source_groups"].append(group_id)

            # Track co-appearances (everyone in this replay played together)
            pids_in_replay = [r["platform_id"] for r in records]
            for pid in pids_in_replay:
                for other_pid in pids_in_replay:
                    if other_pid != pid:
                        co_appearances[pid][other_pid] += 1

            replays_this_group += 1
            total_replays += 1
            print(f"  [parsed] {replay_id}  ({replays_this_group} from this group)")

        print(f"  => {replays_this_group} replays processed from {group_name}")

    # Attach top-5 most frequent teammates to each player
    for pid, entry in players.items():
        top_teammates = []
        for teammate_pid, count in co_appearances[pid].most_common(5):
            teammate_name = players.get(teammate_pid, {}).get("display_names", [])
            top_teammates.append({
                "platform_id": teammate_pid,
                "display_name": teammate_name[0] if teammate_name else "",
                "shared_replays": count,
            })
        entry["frequent_teammates"] = top_teammates

    return players


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_registry(players: dict, group_ids: list[str], total_replays: int, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    registry = {
        "meta": {
            "extracted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source_groups": group_ids,
            "total_replays_sampled": total_replays,
            "total_players_found": len(players),
            "note": (
                "platform_id, display_names, frequent_teammates are auto-extracted. "
                "real_name, country, and team_history must be filled in manually."
            ),
        },
        "players": list(players.values()),
    }

    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"\nSaved {len(players)} players → {output_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_search(client: BallchasingAPI, term: str) -> None:
    """List groups matching a search term — use this to find group IDs."""
    print(f"\nSearching groups for: '{term}'\n")
    groups = client.list_groups(name=term, count=50)
    if not groups:
        print("No groups found.")
        return

    print(f"{'ID':<32}  {'Replays':>8}  Name")
    print("-" * 72)
    for g in groups:
        print(f"{g['id']:<32}  {g.get('direct_replays', '?'):>8}  {g.get('name', '')}")

    print(f"\n{len(groups)} groups found.")
    print("Pass one or more IDs to --groups to extract player data from them.")


def cmd_extract(client: BallchasingAPI, group_ids: list[str], max_per_group: int, delay: float) -> None:
    output_path = Path("data/players/pro_players_raw.json")

    print(f"Extracting from {len(group_ids)} group(s), up to {max_per_group} replays each.")

    players = extract_players_from_groups(
        client,
        group_ids=group_ids,
        max_per_group=max_per_group,
        delay=delay,
    )

    # Count total replays (sum of replay_count divided by players-per-replay ~6)
    total_replays = max(p["replay_count"] for p in players.values()) if players else 0

    save_registry(players, group_ids, total_replays, output_path)

    print("\nNext steps:")
    print(f"  1. Open {output_path}")
    print("  2. Fill in real_name and country for each player")
    print("  3. Use frequent_teammates to infer team rosters, then fill team_history")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract RLCS pro player IDs from Ballchasing replay groups.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--search",
        metavar="TERM",
        help='Search for groups by name (e.g. --search "RLCS 2024")',
    )
    mode.add_argument(
        "--groups",
        nargs="+",
        metavar="GROUP_ID",
        help="One or more Ballchasing group IDs to extract players from.",
    )

    parser.add_argument(
        "--max-per-group",
        type=int,
        default=100,
        metavar="N",
        help="Max replays to sample per group (default: 100).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        metavar="SEC",
        help="Seconds between API requests (default: 1.2).",
    )

    args = parser.parse_args()

    api_key = os.getenv("BALLCHASING_API_KEY")
    if not api_key:
        sys.exit("Error: BALLCHASING_API_KEY not set in environment or .env file.")

    client = BallchasingAPI(api_key)

    # Verify credentials before doing any work
    try:
        info = client.ping()
        print(f"Authenticated as: {info.get('name')} (type: {info.get('type')})")
    except Exception as e:
        sys.exit(f"Authentication failed: {e}")

    if args.search:
        cmd_search(client, args.search)
    else:
        cmd_extract(client, args.groups, args.max_per_group, args.delay)


if __name__ == "__main__":
    main()
