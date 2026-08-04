import json
import os
import time
from pathlib import Path
from typing import Dict, Generator, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv()


class BallchasingAPI:
    """
    Client for the Ballchasing API, scoped to RLCS professional match data.

    Pro data is collected in two ways:
      1. Group-based: find community-uploaded RLCS tournament replay groups and
         download every replay in them (most complete, preferred).
      2. Player-based: pull replays for a list of known pro player platform IDs
         (useful for supplementing group coverage or targeting specific players).

    Rate limits (free tier): ~2 requests/second.
    Responses are cached to disk so re-runs skip already-downloaded replays.
    """

    BASE_URL = "https://ballchasing.com/api"

    def __init__(self, api_key: str) -> None:
        self.session = requests.Session()
        self.session.headers.update({"Authorization": api_key})

    # -------------------------------------------------------------------------
    # Auth
    # -------------------------------------------------------------------------

    def ping(self) -> Dict:
        """Verify the API key and return the authenticated uploader's info."""
        response = self.session.get(f"{self.BASE_URL}/")
        response.raise_for_status()
        return response.json()

    # -------------------------------------------------------------------------
    # Replay endpoints
    # -------------------------------------------------------------------------

    def get_replay(self, replay_id: str) -> Dict:
        """Fetch full statistics for a single replay."""
        response = self.session.get(f"{self.BASE_URL}/replays/{replay_id}")
        response.raise_for_status()
        return response.json()

    def iter_replays(
        self,
        group: Optional[str] = None,
        player_id: Optional[str] = None,
        player_name: Optional[str] = None,
        playlist: Optional[str] = None,
        max_replays: int = 2000,
        delay: float = 1.2,
    ) -> Generator[Dict, None, None]:
        """
        Yield replay metadata dicts, following Ballchasing's cursor pagination.

        :param group: Group ID to scope results to (e.g. an RLCS event group).
        :param player_id: Platform ID, e.g. "steam:76561198xxxxxxxxx".
        :param player_name: Display name filter (partial match supported).
        :param playlist: e.g. "tournament-standard". Pass None to include all.
        :param max_replays: Safety cap on total replays yielded.
        :param delay: Seconds to sleep between paginated requests.
        """
        params: Dict = {"count": 200}
        if group:
            params["group"] = group
        if player_id:
            params["player-id"] = player_id
        if player_name:
            params["player-name"] = player_name
        if playlist:
            params["playlist"] = playlist

        url: Optional[str] = f"{self.BASE_URL}/replays"
        yielded = 0

        while url and yielded < max_replays:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for replay in data.get("list", []):
                if yielded >= max_replays:
                    return
                yield replay
                yielded += 1

            # "next" is a full URL with cursor embedded; clear params to avoid conflicts.
            url = data.get("next")
            params = None

            if url:
                time.sleep(delay)

    # -------------------------------------------------------------------------
    # Group endpoints
    # -------------------------------------------------------------------------

    def get_group(self, group_id: str) -> Dict:
        """Fetch metadata for a specific replay group."""
        response = self.session.get(f"{self.BASE_URL}/groups/{group_id}")
        response.raise_for_status()
        return response.json()

    def list_groups(
        self,
        name: Optional[str] = None,
        creator: Optional[str] = None,
        count: int = 200,
    ) -> List[Dict]:
        """
        Search for replay groups by name or uploader.

        :param name: Partial name match, e.g. "RLCS" or "World Championship".
        :param creator: Filter by uploader's Steam/Epic ID or display name.
        :param count: Max results to return (API cap is 200).
        :return: List of group metadata dicts.
        """
        params: Dict = {"count": min(count, 200)}
        if name:
            params["name"] = name
        if creator:
            params["creator"] = creator

        response = self.session.get(f"{self.BASE_URL}/groups", params=params)
        response.raise_for_status()
        return response.json().get("list", [])

    # -------------------------------------------------------------------------
    # Download helpers
    # -------------------------------------------------------------------------

    def download_group_replays(
        self,
        group_id: str,
        output_dir: Path,
        delay: float = 1.2,
        max_replays: int = 2000,
    ) -> int:
        """
        Download all replay JSONs from a Ballchasing group (e.g. an RLCS event).
        Replays already on disk are skipped.

        :param group_id: Ballchasing group ID for the tournament/event.
        :param output_dir: Directory to write cached replay JSON files.
        :param delay: Seconds between API requests (respect rate limits).
        :param max_replays: Safety cap on total replays to process.
        :return: Number of replays newly downloaded this run.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        downloaded = 0
        for meta in self.iter_replays(group=group_id, max_replays=max_replays, delay=delay):
            replay_id = meta["id"]
            filepath = output_dir / f"{replay_id}.json"

            if filepath.exists():
                print(f"  [skip]  {replay_id}")
                continue

            try:
                replay_data = self.get_replay(replay_id)
                with open(filepath, "w") as f:
                    json.dump(replay_data, f)
                downloaded += 1
                print(f"  [saved] {replay_id}  ({downloaded} new)")
                time.sleep(delay)
            except requests.HTTPError as e:
                print(f"  [error] {replay_id}: {e}")

        print(f"\nGroup {group_id}: {downloaded} new replays saved to {output_dir}")
        return downloaded

    def download_player_replays(
        self,
        player_ids: List[str],
        output_dir: Path,
        playlist: Optional[str] = "tournament-standard",
        delay: float = 1.2,
        max_per_player: int = 500,
    ) -> int:
        """
        Download replays for a list of pro players by platform ID.
        Useful for supplementing group-based collection or targeting specific pros.

        :param player_ids: Platform IDs, e.g. ["steam:76561198xxxxxxxxx", ...].
        :param output_dir: Directory to write cached replay JSON files.
        :param playlist: Filter by playlist; None includes all. Use
                         "tournament-standard" for RLCS events.
        :param delay: Seconds between API requests.
        :param max_per_player: Cap on replays fetched per player.
        :return: Total new replays downloaded across all players.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        total = 0
        for pid in player_ids:
            print(f"\nFetching replays for: {pid}")
            for meta in self.iter_replays(
                player_id=pid,
                playlist=playlist,
                max_replays=max_per_player,
                delay=delay,
            ):
                replay_id = meta["id"]
                filepath = output_dir / f"{replay_id}.json"

                if filepath.exists():
                    continue

                try:
                    replay_data = self.get_replay(replay_id)
                    with open(filepath, "w") as f:
                        json.dump(replay_data, f)
                    total += 1
                    print(f"  [saved] {replay_id}  ({total} total)")
                    time.sleep(delay)
                except requests.HTTPError as e:
                    print(f"  [error] {replay_id}: {e}")

        print(f"\nTotal new replays downloaded: {total}")
        return total


if __name__ == "__main__":
    api_key = os.getenv("BALLCHASING_API_KEY")
    if not api_key:
        raise ValueError("BALLCHASING_API_KEY not set in environment or .env file")

    client = BallchasingAPI(api_key)

    # Verify credentials
    info = client.ping()
    print(f"Authenticated as: {info.get('name')} (Steam ID: {info.get('steam_id')})")

    # Example: search for RLCS replay groups
    groups = client.list_groups(name="RLCS")
    print(f"\nFound {len(groups)} groups matching 'RLCS':")
    for g in groups[:5]:
        print(f"  {g['id']}  {g.get('name')}  (replays: {g.get('direct_replays', '?')})")
