# Claude Code Instructions

## Project Overview

**discovery-fm** is a CLI tool inspired by Last.fm's discontinued Discovery Radio. It finds tracks that a user's musical neighbours listen to that the user hasn't heard yet, then creates a Spotify playlist.

## Tech Stack

- Python 3.13+
- uv for dependency management
- pylast for Last.fm API
- spotipy for Spotify API
- typer for CLI
- tqdm for progress bars
- beautifulsoup4 for scraping (neighbours endpoint was deprecated)

## Project Structure

```
src/discovery_fm/
├── __init__.py      # Package init
├── cli.py           # Typer CLI entry point
├── config.py        # Environment variable loading
├── lastfm.py        # Last.fm API + scraping
└── spotify.py       # Spotify API interactions
```

## Key Commands

```bash
# Install dependencies
uv sync

# Run the tool
uv run discovery-fm USERNAME

# Run with options
uv run discovery-fm USERNAME --neighbour-months 3 --max-tracks 100
```

## Environment Variables

Required in `.env`:
- `LASTFM_API_KEY`
- `LASTFM_API_SECRET`
- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_REDIRECT_URI` (optional, defaults to `http://localhost:8888/callback`)

## Known Issues / Notes

- Last.fm deprecated the `user.getNeighbours` API, so we scrape the website instead
- Spotify rate limits are handled automatically by spotipy with retries
- Progress bars use tqdm with `stream=True` for Last.fm to show incremental progress
- User history defaults to 60 months to minimize duplicate tracks in results

## Development

- Use `uv sync` to install dependencies
- Format with black
- The entry point is defined in pyproject.toml as `discovery-fm`
