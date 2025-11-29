"""Spotify API interactions using spotipy."""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from threading import Lock
from typing import TYPE_CHECKING

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from tqdm import tqdm

# Suppress spotipy rate limit warnings
logging.getLogger("spotipy").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)

if TYPE_CHECKING:
    from discovery_fm.lastfm import Track


class RateLimiter:
    """Thread-safe rate limiter for API calls."""

    def __init__(self, calls_per_second: float = 10) -> None:
        """Initialize rate limiter.

        Args:
            calls_per_second: Maximum calls per second.
        """
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0.0
        self.lock = Lock()

    def wait(self) -> None:
        """Wait if necessary to respect rate limit."""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.time()


class SpotifyClient:
    """Client for Spotify API operations."""

    # Spotify rate limit is ~30 req/s but we're conservative
    MAX_SEARCH_WORKERS = 10
    RATE_LIMIT = 15  # calls per second
    BATCH_SIZE = 100  # Max tracks per playlist_add_items call

    def __init__(
        self, client_id: str, client_secret: str, redirect_uri: str
    ) -> None:
        """Initialize the Spotify client with OAuth.

        Args:
            client_id: Spotify client ID.
            client_secret: Spotify client secret.
            redirect_uri: OAuth redirect URI.
        """
        scope = "playlist-modify-public playlist-modify-private"
        self.sp = spotipy.Spotify(
            auth_manager=SpotifyOAuth(
                client_id=client_id,
                client_secret=client_secret,
                redirect_uri=redirect_uri,
                scope=scope,
                open_browser=True,
            )
        )
        self.rate_limiter = RateLimiter(self.RATE_LIMIT)
        self._user_id: str | None = None

    @property
    def user_id(self) -> str:
        """Get the current user's Spotify ID."""
        if self._user_id is None:
            self._user_id = self.sp.current_user()["id"]
        return self._user_id

    def _search_single_track(self, track: "Track") -> tuple["Track", str | None]:
        """Search for a single track on Spotify.

        Args:
            track: Track to search for.

        Returns:
            Tuple of (track, spotify_uri or None if not found).
        """
        self.rate_limiter.wait()

        query = f"artist:{track.artist} track:{track.title}"
        try:
            results = self.sp.search(q=query, type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            if items:
                return (track, items[0]["uri"])
        except Exception:
            pass

        # Try a more lenient search without field specifiers
        try:
            query = f"{track.artist} {track.title}"
            results = self.sp.search(q=query, type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            if items:
                return (track, items[0]["uri"])
        except Exception:
            pass

        return (track, None)

    def search_tracks_parallel(
        self, tracks: list["Track"]
    ) -> tuple[list[str], list["Track"]]:
        """Search for multiple tracks on Spotify in parallel.

        Args:
            tracks: List of tracks to search for.

        Returns:
            Tuple of (list of Spotify URIs, list of unmatched tracks).
        """
        found_uris: list[str] = []
        not_found: list["Track"] = []

        print(f"Searching for {len(tracks)} tracks on Spotify...")

        with ThreadPoolExecutor(max_workers=self.MAX_SEARCH_WORKERS) as executor:
            futures = {
                executor.submit(self._search_single_track, track): track
                for track in tracks
            }

            with tqdm(total=len(tracks), desc="Searching Spotify") as pbar:
                for future in as_completed(futures):
                    try:
                        track, uri = future.result()
                        if uri:
                            found_uris.append(uri)
                        else:
                            not_found.append(track)
                    except Exception:
                        not_found.append(futures[future])
                    pbar.update(1)

        return found_uris, not_found

    def create_playlist(
        self, name: str, description: str = "", public: bool = True
    ) -> str:
        """Create a new playlist.

        Args:
            name: Playlist name.
            description: Playlist description.
            public: Whether the playlist should be public.

        Returns:
            Playlist ID.
        """
        playlist = self.sp.user_playlist_create(
            user=self.user_id,
            name=name,
            public=public,
            description=description,
        )
        return playlist["id"]

    def add_tracks_to_playlist(
        self, playlist_id: str, track_uris: list[str], max_tracks: int = 10000
    ) -> int:
        """Add tracks to a playlist in batches.

        Args:
            playlist_id: Spotify playlist ID.
            track_uris: List of Spotify track URIs.
            max_tracks: Maximum number of tracks to add.

        Returns:
            Number of tracks actually added.
        """
        # Limit to max_tracks
        uris_to_add = track_uris[:max_tracks]
        total = len(uris_to_add)

        if total == 0:
            return 0

        print(f"Adding {total} tracks to playlist...")

        # Add in batches of 100 (Spotify's limit)
        added = 0
        with tqdm(total=total, desc="Adding tracks") as pbar:
            for i in range(0, total, self.BATCH_SIZE):
                batch = uris_to_add[i : i + self.BATCH_SIZE]
                try:
                    self.sp.playlist_add_items(playlist_id, batch)
                    added += len(batch)
                except Exception as e:
                    print(f"Warning: Failed to add batch starting at {i}: {e}")
                pbar.update(len(batch))

        return added

    def get_playlist_url(self, playlist_id: str) -> str:
        """Get the URL for a playlist.

        Args:
            playlist_id: Spotify playlist ID.

        Returns:
            Playlist URL.
        """
        return f"https://open.spotify.com/playlist/{playlist_id}"


def generate_playlist_name(custom_name: str | None = None) -> str:
    """Generate a playlist name.

    Args:
        custom_name: Optional custom name. If not provided, uses default format.

    Returns:
        Playlist name.
    """
    if custom_name:
        return custom_name
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"discovery-fm - {date_str}"
