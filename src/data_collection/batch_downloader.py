"""
batch_downloader.py

Downloads replay JSONs for RLCS groups or pro players, parses them into typed
records, and writes consolidated parquet files.

Usage
-----
    # Group-based collection (preferred — most complete):
    python -m src.data_collection.batch_downloader \\
        --groups rlcs-2024-spring rlcs-2024-fall \\
        --raw-dir data/raw/replays \\
        --output-dir data/processed

    # Player-based collection (supplements gaps in group coverage):
    python -m src.data_collection.batch_downloader \\
        --registry data/players/pro_players_raw.json \\
        --raw-dir data/raw/replays \\
        --output-dir data/processed

Pipeline
--------
    1. Download raw replay JSONs to ``raw_dir`` (existing files are skipped).
    2. Parse every JSON through ``parse_replay()`` → MatchRaw + PlayerStatsRaw.
    3. Deduplicate by match_id.
    4. Merge with any existing parquet files (incremental update).
    5. Write ``matches.parquet`` and ``player_stats.parquet``.
"""

import argparse
import json
import os
from pathlib import Path
from typing import Optional

import pandas as pd
from dotenv import load_dotenv

from src.data_collection.ballchasing_api import BallchasingAPI
from src.data_collection.player_registry import PlayerRegistry
from src.data_collection.replay_parser import parse_replay
from src.data_collection.schema import MatchRaw, PlayerStatsRaw

load_dotenv()


class BatchDownloader:
    """
    Orchestrates RLCS replay collection and parquet export.

    Parameters
    ----------
    api         : Authenticated BallchasingAPI client.
    raw_dir     : Directory for cached replay JSON files.
    output_dir  : Directory for output parquet files.
    """

    def __init__(
        self,
        api: BallchasingAPI,
        raw_dir: Path,
        output_dir: Path,
    ) -> None:
        self.api = api
        self.raw_dir = Path(raw_dir)
        self.output_dir = Path(output_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_groups(
        self,
        group_ids: list[str],
        delay: float = 1.2,
        max_replays: int = 2000,
    ) -> int:
        """
        Download all replays from each Ballchasing group ID.

        Returns the total number of newly downloaded files.
        """
        total = 0
        for gid in group_ids:
            print(f"\n=== Group: {gid} ===")
            total += self.api.download_group_replays(
                gid, self.raw_dir, delay=delay, max_replays=max_replays
            )
        return total

    def download_players(
        self,
        player_ids: list[str],
        playlist: Optional[str] = "tournament-standard",
        delay: float = 1.2,
        max_per_player: int = 500,
    ) -> int:
        """
        Download replays for a list of platform IDs.

        Returns the total number of newly downloaded files.
        """
        return self.api.download_player_replays(
            player_ids,
            self.raw_dir,
            playlist=playlist,
            delay=delay,
            max_per_player=max_per_player,
        )

    # ------------------------------------------------------------------
    # Parse
    # ------------------------------------------------------------------

    def parse_all(self) -> tuple[list[MatchRaw], list[PlayerStatsRaw]]:
        """
        Parse every ``.json`` file in ``raw_dir`` through ``parse_replay()``.

        Returns deduplicated (matches, player_stats). The source_group field
        on each MatchRaw is derived from the filename (the replay ID) — it will
        be None unless the file was downloaded via ``download_groups()``, in
        which case the API embeds the group ID in the replay JSON itself.

        Deduplication strategy: last write wins on duplicate match_id, which
        handles the case where the same replay appears in multiple groups.
        """
        json_files = sorted(self.raw_dir.glob("*.json"))
        print(f"\nParsing {len(json_files)} cached replay files...")

        matches: dict[str, MatchRaw] = {}
        player_stats: dict[tuple[str, str], PlayerStatsRaw] = {}
        skipped = 0

        for path in json_files:
            try:
                with open(path) as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  [warn] {path.name}: {e}")
                skipped += 1
                continue

            # source_group is stored in the replay JSON by the Ballchasing API
            # when retrieved via a group filter; fall back to None.
            source_group = data.get("group", {}).get("id") if isinstance(data.get("group"), dict) else None

            match, stats = parse_replay(data, source_group=source_group)
            if match is None:
                skipped += 1
                continue

            mid = match["match_id"]
            matches[mid] = match
            for s in stats:
                player_stats[(mid, s["player_id"])] = s

        print(f"  {len(matches)} unique matches, {len(player_stats)} player-stat rows.")
        if skipped:
            print(f"  {skipped} files skipped (irrelevant playlist or parse error).")

        return list(matches.values()), list(player_stats.values())

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def write_parquet(
        self,
        matches: list[MatchRaw],
        player_stats: list[PlayerStatsRaw],
    ) -> None:
        """
        Merge new records with any existing parquet files and rewrite them.

        Deduplication keys:
          - matches     → match_id
          - player_stats → (match_id, player_id)

        "Last write wins" keeps the freshest data when the same replay appears
        in both the existing parquet and the new batch.
        """
        matches_path = self.output_dir / "matches.parquet"
        stats_path = self.output_dir / "player_stats.parquet"

        new_matches_df = pd.DataFrame(matches)
        new_stats_df = pd.DataFrame(player_stats)

        if matches_path.exists() and not new_matches_df.empty:
            existing = pd.read_parquet(matches_path)
            new_matches_df = (
                pd.concat([existing, new_matches_df], ignore_index=True)
                .drop_duplicates(subset=["match_id"], keep="last")
                .reset_index(drop=True)
            )

        if stats_path.exists() and not new_stats_df.empty:
            existing = pd.read_parquet(stats_path)
            new_stats_df = (
                pd.concat([existing, new_stats_df], ignore_index=True)
                .drop_duplicates(subset=["match_id", "player_id"], keep="last")
                .reset_index(drop=True)
            )

        if not new_matches_df.empty:
            new_matches_df.to_parquet(matches_path, index=False)
            print(f"\nWrote {len(new_matches_df)} matches → {matches_path}")
        else:
            print("\nNo match records to write.")

        if not new_stats_df.empty:
            new_stats_df.to_parquet(stats_path, index=False)
            print(f"Wrote {len(new_stats_df)} player-stat rows → {stats_path}")
        else:
            print("No player-stat records to write.")

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    def run(
        self,
        group_ids: Optional[list[str]] = None,
        player_ids: Optional[list[str]] = None,
        playlist: Optional[str] = "tournament-standard",
        delay: float = 1.2,
    ) -> None:
        """
        Full pipeline: download → parse → write parquet.

        At least one of ``group_ids`` or ``player_ids`` must be provided.
        Both can be supplied to combine group and player-based collection.
        """
        if not group_ids and not player_ids:
            raise ValueError("Provide at least one group_id or player_id.")

        if group_ids:
            self.download_groups(group_ids, delay=delay)

        if player_ids:
            self.download_players(player_ids, playlist=playlist, delay=delay)

        matches, stats = self.parse_all()

        if not matches:
            print("No relevant matches found. Nothing written.")
            return

        self.write_parquet(matches, stats)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download RLCS replays and export to parquet.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--groups",
        nargs="+",
        metavar="GROUP_ID",
        help="One or more Ballchasing group IDs (e.g. RLCS event groups).",
    )
    parser.add_argument(
        "--registry",
        metavar="PATH",
        help="Path to pro_players_raw.json; enables player-based collection.",
    )
    parser.add_argument(
        "--playlist",
        default="tournament-standard",
        help="Playlist filter for player-based collection.",
    )
    parser.add_argument(
        "--raw-dir",
        default="data/raw/replays",
        metavar="DIR",
        help="Directory for cached raw replay JSON files.",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed",
        metavar="DIR",
        help="Directory for output parquet files.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.2,
        help="Seconds to sleep between API requests.",
    )
    parser.add_argument(
        "--max-replays",
        type=int,
        default=2000,
        help="Safety cap on replays per group.",
    )
    parser.add_argument(
        "--max-per-player",
        type=int,
        default=500,
        help="Safety cap on replays per player.",
    )
    return parser


def main() -> None:
    args = _build_parser().parse_args()

    if not args.groups and not args.registry:
        print("Error: provide --groups and/or --registry.")
        raise SystemExit(1)

    api_key = os.getenv("BALLCHASING_API_KEY")
    if not api_key:
        raise ValueError("BALLCHASING_API_KEY not set in .env or environment.")

    api = BallchasingAPI(api_key)

    player_ids: Optional[list[str]] = None
    if args.registry:
        registry = PlayerRegistry.load(args.registry)
        player_ids = registry.all_api_player_ids()
        print(f"Loaded {len(player_ids)} player IDs from registry.")

    downloader = BatchDownloader(
        api=api,
        raw_dir=Path(args.raw_dir),
        output_dir=Path(args.output_dir),
    )
    downloader.run(
        group_ids=args.groups,
        player_ids=player_ids,
        playlist=args.playlist,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
