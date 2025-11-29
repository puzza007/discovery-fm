# discovery-fm

Discover music through your Last.fm neighbours. Creates Spotify playlists from tracks they love that you haven't heard yet.

Inspired by Last.fm's discontinued Discovery Radio feature.

## Features

- Scrapes your Last.fm neighbours (since the API was deprecated)
- Fetches listening history for you and your neighbours
- Finds tracks your neighbours love that you haven't listened to
- Searches Spotify and creates a playlist with those discoveries
- Configurable time ranges, ordering, and playlist size
- Progress indicators throughout

## Prerequisites

### API Keys Required

1. **Last.fm API Key**
   - Get one at https://www.last.fm/api/account/create

2. **Spotify Developer App**
   - Create one at https://developer.spotify.com/dashboard
   - Add `http://localhost:8888/callback` as a Redirect URI in your app settings

## Installation

```bash
# Install dependencies
uv sync

# Copy example env and add your credentials
cp .env.example .env
```

Edit `.env` with your API keys:
```
LASTFM_API_KEY=your_key
LASTFM_API_SECRET=your_secret
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback
```

## Usage

```bash
# Basic usage - uses sensible defaults
uv run discovery-fm YOUR_LASTFM_USERNAME

# Shorter neighbour history for faster results
uv run discovery-fm YOUR_USERNAME --neighbour-months 3

# Custom playlist name
uv run discovery-fm YOUR_USERNAME --playlist-name "My Discovery Mix"

# Shuffle the results instead of ordering by popularity
uv run discovery-fm YOUR_USERNAME --order-by shuffle

# Limit playlist size
uv run discovery-fm YOUR_USERNAME --max-tracks 100
```

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--neighbours` | `-n` | 10 | Number of neighbours to fetch |
| `--user-months` | `-u` | 60 | Months of YOUR history to exclude (higher = fewer duplicates) |
| `--neighbour-months` | `-m` | 12 | Months of neighbour history to search for discoveries |
| `--order-by` | `-o` | neighbour-count | How to order tracks: `neighbour-count`, `shuffle`, or `none` |
| `--playlist-name` | `-p` | Auto-generated | Custom playlist name |
| `--max-tracks` | `-t` | 10000 | Maximum tracks in playlist |

## How It Works

1. **Fetch your history** - Gets all tracks you've listened to (default: 5 years) to exclude them
2. **Find neighbours** - Scrapes your Last.fm neighbours page
3. **Fetch neighbour history** - Gets recent tracks from each neighbour
4. **Find discoveries** - Filters to tracks you haven't heard
5. **Search Spotify** - Finds matching tracks on Spotify
6. **Create playlist** - Adds discovered tracks to a new playlist

## Tips

- Use a long `--user-months` (default 60) to avoid getting tracks you've already heard
- Use a shorter `--neighbour-months` (e.g., 3-6) for faster results and more recent discoveries
- The first run will open your browser for Spotify authorization; subsequent runs use cached credentials

## License

MIT
