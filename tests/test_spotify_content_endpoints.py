import pytest

from src.api import spotify


class _Response:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_get_user_top_items_raises_scope_error_on_403(monkeypatch):
    monkeypatch.setattr(
        spotify,
        "_spotify_request",
        lambda *args, **kwargs: _Response(403, text="insufficient_scope"),
    )

    with pytest.raises(spotify.SpotifyScopeError) as exc:
        spotify.get_user_top_items("token", item_type="tracks", time_range="medium_term")

    assert exc.value.required_scope == "user-top-read"


def test_get_recently_played_tracks_returns_empty_on_429(monkeypatch):
    monkeypatch.setattr(
        spotify,
        "_spotify_request",
        lambda *args, **kwargs: _Response(429, text="rate_limited"),
    )

    assert spotify.get_recently_played_tracks("token") == []


def test_get_recently_played_tracks_handles_missing_fields(monkeypatch):
    payload = {
        "items": [
            {"track": {"uri": "spotify:track:1234567890123456789012", "artists": [{}]}},
            {"track": {"uri": "spotify:track:1234567890123456789012"}},
        ]
    }
    monkeypatch.setattr(
        spotify,
        "_spotify_request",
        lambda *args, **kwargs: _Response(200, payload=payload),
    )

    result = spotify.get_recently_played_tracks("token")

    assert len(result) == 1
    assert result[0]["type"] == "track"
    assert result[0]["artist"] == "Unknown Artist"


def test_search_items_caps_limit_to_ten(monkeypatch):
    observed_params = {}

    def _fake_request(*args, **kwargs):
        observed_params.update(kwargs.get("params", {}))
        return _Response(200, payload={"tracks": {"items": []}, "albums": {"items": []}, "artists": {"items": []}, "playlists": {"items": []}})

    monkeypatch.setattr(spotify, "_spotify_request", _fake_request)

    result = spotify.search_items("token", "test", limit=99)

    assert observed_params.get("limit") == 10
    assert set(result.keys()) == {"tracks", "albums", "artists", "playlists"}


def test_get_playback_queue_returns_empty_shape_on_empty_payload(monkeypatch):
    monkeypatch.setattr(
        spotify,
        "_spotify_request",
        lambda *args, **kwargs: _Response(200, payload={}),
    )

    result = spotify.get_playback_queue("token")

    assert result["queue"] == []
    assert result["total"] == 0


def test_get_playback_queue_raises_scope_error_on_403(monkeypatch):
    monkeypatch.setattr(
        spotify,
        "_spotify_request",
        lambda *args, **kwargs: _Response(403, text="insufficient_scope"),
    )

    with pytest.raises(spotify.SpotifyScopeError) as exc:
        spotify.get_playback_queue("token")

    assert exc.value.required_scope == "user-read-playback-state"
