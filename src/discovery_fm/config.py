"""Configuration management via environment variables."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def load_config() -> dict[str, str]:
    """Load configuration from .env file and environment variables.

    Returns:
        Dictionary with all required configuration values.

    Raises:
        SystemExit: If required environment variables are missing.
    """
    # Load .env file from current directory or parent directories
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()

    required_vars = [
        "LASTFM_API_KEY",
        "LASTFM_API_SECRET",
        "SPOTIFY_CLIENT_ID",
        "SPOTIFY_CLIENT_SECRET",
    ]

    config = {}
    missing = []

    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
        else:
            config[var] = value

    # Optional with default
    config["SPOTIFY_REDIRECT_URI"] = os.getenv(
        "SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback"
    )

    if missing:
        print(f"Error: Missing required environment variables: {', '.join(missing)}")
        print("\nPlease create a .env file with the following variables:")
        print("  LASTFM_API_KEY=your_lastfm_api_key")
        print("  LASTFM_API_SECRET=your_lastfm_api_secret")
        print("  SPOTIFY_CLIENT_ID=your_spotify_client_id")
        print("  SPOTIFY_CLIENT_SECRET=your_spotify_client_secret")
        print("  SPOTIFY_REDIRECT_URI=http://localhost:8888/callback  (optional)")
        print("\nGet Last.fm API credentials: https://www.last.fm/api/account/create")
        print("Get Spotify API credentials: https://developer.spotify.com/dashboard")
        sys.exit(1)

    return config
