import json
import pytest
import requests

from src.api import spotify


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Avoid real sleeping inside spotify module during tests."""
    monkeypatch.setattr(spotify.time, "sleep", lambda _: None)


@pytest.fixture
def temp_token_path(tmp_path, monkeypatch):
    """Redirect token persistence to a temporary path."""
    token_path = tmp_path / "token_state.json"
    monkeypatch.setattr(spotify, "TOKEN_STATE_PATH", token_path)
    return token_path


def test_refresh_access_token_retries_success(monkeypatch, temp_token_path):
    """Refresh should retry on timeouts and eventually succeed."""
    attempts = []

    def fake_post(*args, **kwargs):
        attempt = len(attempts) + 1
        attempts.append(attempt)
        if attempt < 3:
            raise requests.exceptions.ReadTimeout("timeout")

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"access_token": "token123", "expires_in": 3600}

        return _Resp()

    monkeypatch.setattr(spotify, "CLIENT_ID", "client")
    monkeypatch.setattr(spotify, "CLIENT_SECRET", "secret")
    monkeypatch.setattr(spotify, "REFRESH_TOKEN", "refresh")
    monkeypatch.setattr(spotify.SESSION, "post", fake_post)

    token = spotify.refresh_access_token(with_retries=True)

    assert token == "token123"
    assert len(attempts) == 3
    saved = json.loads(temp_token_path.read_text(encoding="utf-8"))
    assert saved["access_token"] == "token123"


def test_ensure_token_valid_triggers_cache_refresh(monkeypatch):
    """ensure_token_valid should delegate to cache when refresh is needed."""
    windows = []

    def fake_token_needs_refresh(window):
        windows.append(window)
        return True

    def fake_cache_ensure(window):
        windows.append(f"ensure:{window}")
        return "fresh-token"

    monkeypatch.setattr(spotify, "token_needs_refresh", fake_token_needs_refresh)
    monkeypatch.setattr(spotify, "cache_ensure_token_valid", fake_cache_ensure)

    result = spotify.ensure_token_valid(180)

    assert result == "fresh-token"
    assert windows == [180, "ensure:180"]


def test_play_with_retry_uses_fallback_device(monkeypatch):
    """When primary device fails, fallback device should be attempted."""
    attempts = []

    def fake_start(token, device_id, playlist_uri, volume_percent, shuffle):
        attempts.append(device_id)
        return device_id != "primary"

    def fake_verify(token, device_id, playlist_uri, attempts=2, wait_seconds=0.5):
        return device_id == "fallback"

    monkeypatch.setattr(spotify, "_start_playback_on_device", fake_start)
    monkeypatch.setattr(spotify, "_verify_playback_state", fake_verify)
    monkeypatch.setattr(spotify, "ensure_token_valid", lambda *args, **kwargs: "token")
    monkeypatch.setattr(spotify, "get_device_id", lambda token, name: "fallback")
    monkeypatch.setattr(spotify, "PLAYER_MAX_ATTEMPTS", 1)

    success = spotify.play_with_retry(
        "token",
        "primary",
        playlist_uri="spotify:playlist:abc",
        volume_percent=40,
        shuffle=False,
        fallback_device="FallbackDevice",
    )

    assert success is True
    assert attempts == ["primary", "fallback"]
