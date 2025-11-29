"""CLI interface using Typer."""

import random
from enum import Enum
from typing import Annotated

import typer

from discovery_fm.config import load_config
from discovery_fm.lastfm import LastFMClient, Track, find_discovery_tracks
from discovery_fm.spotify import SpotifyClient, generate_playlist_name

app = typer.Typer(
    name="discovery-fm",
    help="Rediscover music through your Last.fm neighbours.",
    add_completion=False,
)


class OrderBy(str, Enum):
    """Track ordering options."""

    neighbour_count = "neighbour-count"
    shuffle = "shuffle"
    none = "none"


def order_tracks(
    tracks: dict[Track, int], order_by: OrderBy, max_tracks: int
) -> list[Track]:
    """Order and limit tracks based on the specified method.

    Args:
        tracks: Dictionary of tracks with neighbour counts.
        order_by: Ordering method.
        max_tracks: Maximum number of tracks to return.

    Returns:
        Ordered list of tracks.
    """
    track_list = list(tracks.keys())

    if order_by == OrderBy.neighbour_count:
        # Sort by neighbour count descending
        track_list.sort(key=lambda t: tracks[t], reverse=True)
    elif order_by == OrderBy.shuffle:
        random.shuffle(track_list)
    # OrderBy.none keeps original order

    return track_list[:max_tracks]


@app.command()
def main(
    username: Annotated[str, typer.Argument(help="Last.fm username to analyze")],
    neighbours: Annotated[
        int, typer.Option("--neighbours", "-n", help="Number of neighbours to fetch")
    ] = 10,
    user_months: Annotated[
        int,
        typer.Option(
            "--user-months", "-u",
            help="Months of YOUR history to exclude (use high value to avoid duplicates)",
        ),
    ] = 60,  # 5 years default - we want to exclude everything you've heard
    neighbour_months: Annotated[
        int | None,
        typer.Option(
            "--neighbour-months", "-m",
            help="Months of neighbour history to search (defaults to 12)",
        ),
    ] = None,
    order_by: Annotated[
        OrderBy,
        typer.Option("--order-by", "-o", help="How to order tracks in playlist"),
    ] = OrderBy.neighbour_count,
    playlist_name: Annotated[
        str | None,
        typer.Option("--playlist-name", "-p", help="Custom playlist name"),
    ] = None,
    max_tracks: Annotated[
        int, typer.Option("--max-tracks", "-t", help="Maximum tracks in playlist")
    ] = 10000,
) -> None:
    """Create a Spotify playlist from Last.fm neighbour discoveries.

    Finds tracks that your Last.fm neighbours have listened to that you haven't,
    then creates a Spotify playlist with those discoveries.
    """
    # Default neighbour_months to 12 if not specified
    if neighbour_months is None:
        neighbour_months = 12

    # Load configuration
    config = load_config()

    typer.echo(f"\n📻 discovery-fm")
    typer.echo(f"━━━━━━━━━━━━━━━━")
    typer.echo(f"Target user: {username}")
    typer.echo(f"Neighbours: {neighbours}")
    typer.echo(f"Your history: {user_months} months (to exclude)")
    typer.echo(f"Neighbour history: {neighbour_months} months (to discover)")
    typer.echo(f"Ordering: {order_by.value}")
    typer.echo(f"Max tracks: {max_tracks}\n")

    # Initialize clients
    lastfm = LastFMClient(
        api_key=config["LASTFM_API_KEY"],
        api_secret=config["LASTFM_API_SECRET"],
    )

    spotify = SpotifyClient(
        client_id=config["SPOTIFY_CLIENT_ID"],
        client_secret=config["SPOTIFY_CLIENT_SECRET"],
        redirect_uri=config["SPOTIFY_REDIRECT_URI"],
    )

    # Step 1: Fetch user's tracks
    typer.echo("📥 Step 1: Fetching your listening history...")
    user_tracks = lastfm.get_user_tracks(username, months=user_months)
    typer.echo(f"   Found {len(user_tracks)} unique tracks\n")

    # Step 2: Fetch neighbours
    typer.echo("👥 Step 2: Finding your musical neighbours...")
    neighbour_list = lastfm.get_neighbours(username, limit=neighbours)
    if not neighbour_list:
        typer.echo("Error: Could not find any neighbours. Exiting.", err=True)
        raise typer.Exit(1)
    typer.echo(f"   Found neighbours: {', '.join(neighbour_list)}\n")

    # Step 3: Fetch neighbour tracks (parallel)
    typer.echo("📥 Step 3: Fetching neighbour listening histories...")
    neighbour_tracks = lastfm.get_neighbour_tracks_parallel(
        neighbour_list, months=neighbour_months
    )
    typer.echo(f"   Found {len(neighbour_tracks)} unique tracks from neighbours\n")

    # Step 4: Find discoveries
    typer.echo("🔍 Step 4: Finding tracks you haven't heard...")
    discoveries = find_discovery_tracks(user_tracks, neighbour_tracks)
    typer.echo(f"   Found {len(discoveries)} potential discoveries\n")

    if not discoveries:
        typer.echo("No new discoveries found! Your neighbours listen to the same music.")
        raise typer.Exit(0)

    # Step 5: Order and limit tracks
    ordered_tracks = order_tracks(discoveries, order_by, max_tracks)
    typer.echo(f"📋 Will search for {len(ordered_tracks)} tracks on Spotify\n")

    # Step 6: Search Spotify (parallel)
    typer.echo("🔎 Step 5: Searching for tracks on Spotify...")
    found_uris, not_found = spotify.search_tracks_parallel(ordered_tracks)
    typer.echo(f"   Found {len(found_uris)} tracks on Spotify")
    typer.echo(f"   Could not find {len(not_found)} tracks\n")

    if not found_uris:
        typer.echo("Error: No tracks found on Spotify. Exiting.", err=True)
        raise typer.Exit(1)

    # Step 7: Create playlist and add tracks
    typer.echo("📝 Step 6: Creating Spotify playlist...")
    name = generate_playlist_name(playlist_name)
    description = (
        f"Tracks from Last.fm neighbours of {username}. "
        f"Generated from {len(neighbour_list)} neighbours' listening history."
    )

    playlist_id = spotify.create_playlist(name=name, description=description)
    added = spotify.add_tracks_to_playlist(playlist_id, found_uris, max_tracks)

    playlist_url = spotify.get_playlist_url(playlist_id)

    # Summary
    typer.echo("\n" + "━" * 50)
    typer.echo("✅ Playlist created successfully!")
    typer.echo(f"   Name: {name}")
    typer.echo(f"   Tracks added: {added}")
    typer.echo(f"   URL: {playlist_url}")

    # Report unmatched tracks
    if not_found:
        typer.echo(f"\n⚠️  {len(not_found)} tracks could not be found on Spotify:")
        # Show first 20 unmatched
        for track in not_found[:20]:
            typer.echo(f"   - {track.artist} - {track.title}")
        if len(not_found) > 20:
            typer.echo(f"   ... and {len(not_found) - 20} more")

    typer.echo()


if __name__ == "__main__":
    app()
