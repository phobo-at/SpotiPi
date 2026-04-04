#!/usr/bin/env python3
"""
Spotify token generator for SpotiPi.

Stores Spotify credentials in ~/.spotipi/.env and keeps repo-root .env
support only as a local development override when reading credentials.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyOAuth

PROJECT_ROOT = Path(__file__).resolve().parent
REDIRECT_URI = "http://127.0.0.1:8080"
SCOPES = [
    "user-read-playback-state",
    "user-modify-playback-state",
    "user-read-currently-playing",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-follow-read",
    "user-library-read",
    "user-read-private",
    "user-top-read",
    "user-read-recently-played",
]


def get_env_file_path() -> Path:
    """Return the canonical runtime env file path."""
    app_name = os.getenv("SPOTIPI_APP_NAME", "spotipi")
    return Path.home() / f".{app_name}" / ".env"


def load_environment(env_path: Path | None = None) -> Path:
    """Load runtime secrets from the canonical env file, then local overrides."""
    target = env_path or get_env_file_path()
    if target.exists():
        load_dotenv(dotenv_path=target)

    project_env = PROJECT_ROOT / ".env"
    if project_env.exists():
        load_dotenv(dotenv_path=project_env, override=True)

    return target


def mask_secret(value: str, *, visible: int = 4) -> str:
    """Mask a secret while keeping a short prefix/suffix visible."""
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= visible * 2:
        return "*" * len(text)
    return f"{text[:visible]}...{text[-visible:]}"


def ensure_env_file(env_path: Path) -> None:
    """Create the env directory/file and harden permissions."""
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.touch(exist_ok=True)
    try:
        os.chmod(env_path.parent, 0o700)
    except OSError:
        pass
    try:
        os.chmod(env_path, 0o600)
    except OSError:
        pass


def store_refresh_token(refresh_token: str, env_path: Path | None = None) -> Path:
    """Persist the Spotify refresh token to the canonical env file."""
    target = env_path or get_env_file_path()
    ensure_env_file(target)

    try:
        existing_lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        existing_lines = []

    updated_lines = []
    replaced = False
    for line in existing_lines:
        if line.startswith("SPOTIFY_REFRESH_TOKEN="):
            updated_lines.append(f"SPOTIFY_REFRESH_TOKEN={refresh_token}")
            replaced = True
        else:
            updated_lines.append(line)

    if not replaced:
        updated_lines.append(f"SPOTIFY_REFRESH_TOKEN={refresh_token}")

    tmp_path = target.with_suffix(".tmp")
    tmp_path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")
    os.replace(tmp_path, target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass

    return target


def build_oauth_client(client_id: str, client_secret: str, env_path: Path) -> SpotifyOAuth:
    """Create the Spotipy OAuth client using a cache inside ~/.spotipi."""
    cache_path = env_path.parent / ".spotify_cache"
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=REDIRECT_URI,
        scope=" ".join(SCOPES),
        cache_path=str(cache_path),
    )


def get_spotify_token() -> int:
    """Generate and store a new Spotify refresh token."""
    env_path = load_environment()
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    print("🎵 Spotify Token Generator für SpotiPi")
    print("=" * 50)
    print(f"📁 Ziel-Datei: {env_path}")

    if not client_id or not client_secret:
        print("❌ Error: SPOTIFY_CLIENT_ID und SPOTIFY_CLIENT_SECRET müssen gesetzt sein.")
        print("📝 Verwende ~/.spotipi/.env für Runtime-Secrets; eine lokale .env bleibt nur Dev-Override.")
        return 1

    sp_oauth = build_oauth_client(client_id, client_secret, env_path)

    print("🌐 Öffne Browser für Spotify Autorisierung...")
    sp_oauth.get_access_token(as_dict=False)
    token_info = sp_oauth.get_cached_token()
    if not token_info:
        print("❌ Token-Generierung fehlgeschlagen")
        return 1

    refresh_token = token_info.get("refresh_token")
    if not refresh_token:
        print("❌ Spotify hat keinen Refresh Token zurückgegeben")
        return 1

    stored_at = store_refresh_token(refresh_token, env_path)

    print("\n✅ Token erfolgreich generiert!")
    print("=" * 50)
    print(f"ACCESS_TOKEN: {mask_secret(token_info.get('access_token', ''))}")
    print(f"REFRESH_TOKEN: {mask_secret(refresh_token)}")
    print(f"EXPIRES_IN: {token_info.get('expires_in')} Sekunden")
    print(f"💾 .env Datei wurde aktualisiert: {stored_at}")
    print("🎉 SpotiPi ist jetzt bereit!")
    return 0


if __name__ == "__main__":
    raise SystemExit(get_spotify_token())
