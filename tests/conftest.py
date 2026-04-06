"""Shared pytest fixtures for the SpotiPi test suite."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from src.app import create_app
from src.utils import spotify_secrets

# Env keys that get_spotify_credentials() reads as a fallback. Tests that bind
# a temporary runtime .env must clear these so real credentials loaded via
# load_dotenv() at startup don't leak into the test.
_SPOTIFY_ENV_KEYS = (
    "SPOTIFY_CLIENT_ID",
    "SPOTIFY_CLIENT_SECRET",
    "SPOTIFY_REFRESH_TOKEN",
    "SPOTIFY_USERNAME",
)


@pytest.fixture(scope="session")
def app():
    """Create a Flask app instance for the test session."""
    flask_app = create_app(start_warmup=False)
    flask_app.config.update({"TESTING": True})
    return flask_app


@pytest.fixture
def client(app):
    """Provide a fresh Flask test client for each test."""
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def bind_spotify_runtime_env(monkeypatch) -> Callable[[Path], None]:
    """Return a helper that binds a temporary runtime .env path for tests.

    Also clears the Spotify env keys from os.environ so the fallback in
    get_spotify_credentials() can't leak real credentials into the test,
    and invalidates the credentials cache.
    """

    def _bind(env_path: Path) -> None:
        monkeypatch.setattr(spotify_secrets, "get_runtime_env_path", lambda: env_path)
        for env_key in _SPOTIFY_ENV_KEYS:
            monkeypatch.delenv(env_key, raising=False)
        spotify_secrets.invalidate_spotify_secrets_cache()

    return _bind
