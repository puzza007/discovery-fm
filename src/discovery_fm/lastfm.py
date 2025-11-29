"""Last.fm API interactions using pylast."""

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import NamedTuple

import pylast
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Suppress pylast rate limit warnings
logging.getLogger("pylast").setLevel(logging.ERROR)


class Track(NamedTuple):
    """A track with artist and title."""

    artist: str
    title: str

    def __hash__(self) -> int:
        return hash((self.artist.lower(), self.title.lower()))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Track):
            return NotImplemented
        return (
            self.artist.lower() == other.artist.lower()
            and self.title.lower() == other.title.lower()
        )


class LastFMClient:
    """Client for Last.fm API operations."""

    # Last.fm is generally lenient but we limit concurrent requests to be safe
    MAX_WORKERS = 5

    def __init__(self, api_key: str, api_secret: str) -> None:
        """Initialize the Last.fm client.

        Args:
            api_key: Last.fm API key.
            api_secret: Last.fm API secret.
        """
        self.network = pylast.LastFMNetwork(api_key=api_key, api_secret=api_secret)

    def get_user(self, username: str) -> pylast.User:
        """Get a Last.fm user object.

        Args:
            username: Last.fm username.

        Returns:
            pylast User object.
        """
        return self.network.get_user(username)

    def get_user_tracks(
        self,
        username: str,
        months: int = 12,
        limit: int | None = None,
        show_progress: bool = True,
    ) -> set[Track]:
        """Fetch all tracks a user has listened to in the given time period.

        Args:
            username: Last.fm username.
            months: Number of months to look back.
            limit: Optional limit on number of tracks to fetch.
            show_progress: Whether to show progress bar.

        Returns:
            Set of Track objects.
        """
        import sys

        user = self.get_user(username)
        tracks: set[Track] = set()

        # Calculate time range
        now = datetime.now()
        time_from = int((now - timedelta(days=months * 30)).timestamp())
        time_to = int(now.timestamp())

        if show_progress:
            pbar = tqdm(
                desc="   ",
                unit=" scrobbles",
                file=sys.stdout,
                dynamic_ncols=True,
                leave=True,
                mininterval=0.1,
            )

        try:
            # Use stream=True to get tracks as pages arrive (better progress)
            # pylast expects int for limit, None means fetch all
            recent = user.get_recent_tracks(
                limit=limit if limit is not None else 0,
                time_from=time_from,
                time_to=time_to,
                stream=True,
                cacheable=False,
            )

            count = 0
            for played_track in recent:
                if played_track.track:
                    artist = str(played_track.track.artist)
                    title = str(played_track.track.title)
                    tracks.add(Track(artist=artist, title=title))
                count += 1
                if show_progress:
                    pbar.update(1)
                    if count % 50 == 0:
                        pbar.set_postfix(unique=len(tracks), refresh=True)

            if show_progress:
                pbar.set_postfix(unique=len(tracks))
                pbar.close()

        except pylast.WSError as e:
            if show_progress:
                pbar.close()
                print(f"Warning: Could not fetch tracks for {username}: {e}")

        return tracks

    def get_neighbours(self, username: str, limit: int = 10) -> list[str]:
        """Get musical neighbours for a user by scraping the Last.fm website.

        Note: The Last.fm API no longer supports getting neighbours, so we
        scrape the website instead.

        Args:
            username: Last.fm username.
            limit: Maximum number of neighbours to fetch.

        Returns:
            List of neighbour usernames.
        """
        print(f"Fetching neighbours for {username}...")

        url = f"https://www.last.fm/user/{username}/neighbours"
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Warning: Could not fetch neighbours page: {e}")
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        # Find all user links that are direct /user/USERNAME (not subpaths)
        neighbours: list[str] = []
        user_link_pattern = re.compile(r"^/user/([^/]+)$")

        for link in soup.find_all("a", href=user_link_pattern):
            href = link.get("href", "")
            match = user_link_pattern.match(href)
            if match:
                neighbour = match.group(1)
                # Skip the target user themselves
                if (
                    neighbour.lower() != username.lower()
                    and neighbour not in neighbours
                ):
                    neighbours.append(neighbour)
                    if len(neighbours) >= limit:
                        break

        if not neighbours:
            print(f"Warning: No neighbours found for {username}")

        return neighbours

    def _fetch_single_neighbour_tracks(
        self, neighbour: str, months: int, pbar: tqdm | None = None
    ) -> tuple[str, set[Track]]:
        """Fetch tracks for a single neighbour (used for parallel execution).

        Args:
            neighbour: Neighbour username.
            months: Number of months to look back.
            pbar: Optional progress bar to update description.

        Returns:
            Tuple of (neighbour username, set of tracks).
        """
        try:
            if pbar:
                pbar.set_postfix_str(f"fetching {neighbour}...")
            tracks = self.get_user_tracks(
                neighbour, months=months, limit=None, show_progress=False
            )
            return (neighbour, tracks)
        except Exception:
            return (neighbour, set())

    def get_neighbour_tracks_parallel(
        self, neighbours: list[str], months: int = 12
    ) -> dict[Track, int]:
        """Fetch tracks from all neighbours and count occurrences.

        Args:
            neighbours: List of neighbour usernames.
            months: Number of months to look back.

        Returns:
            Dictionary mapping Track to number of neighbours who listened to it.
        """
        track_counts: dict[Track, int] = {}
        failed_neighbours: list[str] = []

        print(
            f"Fetching tracks from {len(neighbours)} neighbours ({months} months each)...\n"
        )

        for i, neighbour in enumerate(neighbours, 1):
            try:
                print(f"   [{i}/{len(neighbours)}] {neighbour}")
                tracks = self.get_user_tracks(
                    neighbour, months=months, limit=None, show_progress=True
                )
                if tracks:
                    for track in tracks:
                        track_counts[track] = track_counts.get(track, 0) + 1
                else:
                    failed_neighbours.append(neighbour)
            except Exception as e:
                print(f"   Failed: {e}")
                failed_neighbours.append(neighbour)

        if failed_neighbours:
            print(
                f"Warning: Could not fetch tracks for {len(failed_neighbours)} "
                f"neighbour(s): {', '.join(failed_neighbours)}"
            )

        return track_counts


def find_discovery_tracks(
    user_tracks: set[Track], neighbour_tracks: dict[Track, int]
) -> dict[Track, int]:
    """Find tracks that neighbours have listened to but the user hasn't.

    Args:
        user_tracks: Set of tracks the user has listened to.
        neighbour_tracks: Dictionary of tracks from neighbours with counts.

    Returns:
        Dictionary of discovery tracks with their neighbour counts.
    """
    discoveries = {}
    for track, count in neighbour_tracks.items():
        if track not in user_tracks:
            discoveries[track] = count
    return discoveries
