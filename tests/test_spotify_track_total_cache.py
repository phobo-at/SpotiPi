"""The playlist/album track-total cache must survive Spotify token rotation."""

from __future__ import annotations

import src.api.spotify as spotify_api


class _FakeResp:
    status_code = 200

    def json(self):
        return {"tracks": {"total": 42}}


def test_track_total_cache_keyed_on_uri_not_token(monkeypatch):
    """Keying on the rotating access token re-fetched unchanged metadata each hour.

    The cache must be keyed on (uri, kind) so a token refresh does not invalidate it.
    """
    spotify_api._track_total_cache.clear()

    calls: list[tuple[str, str]] = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url))
        return _FakeResp()

    monkeypatch.setattr(spotify_api, "_spotify_request", fake_request)

    uri = "spotify:playlist:abc123"
    first = spotify_api._get_track_total_cached("token-A", uri, "playlist")
    second = spotify_api._get_track_total_cached("token-B-after-refresh", uri, "playlist")

    assert first == second == 42
    # Only one upstream fetch despite the rotated token on the second call.
    assert len(calls) == 1


def test_track_total_cache_refreshes_after_ttl(monkeypatch):
    """A bounded TTL keeps the old ~hourly refresh so a resized playlist can't pin a
    stale total forever (which would feed an out-of-range shuffle offset)."""
    spotify_api._track_total_cache.clear()

    calls: list[str] = []

    def fake_request(method, url, **kwargs):
        calls.append(url)
        return _FakeResp()

    monkeypatch.setattr(spotify_api, "_spotify_request", fake_request)

    clock = {"now": 1000.0}
    monkeypatch.setattr(spotify_api.time, "time", lambda: clock["now"])

    uri = "spotify:playlist:ttl"
    spotify_api._get_track_total_cached("tok", uri, "playlist")  # initial fetch
    spotify_api._get_track_total_cached("tok", uri, "playlist")  # within TTL -> cached
    assert len(calls) == 1

    clock["now"] += spotify_api._TRACK_TOTAL_TTL + 1  # advance past the TTL
    spotify_api._get_track_total_cached("tok", uri, "playlist")  # expired -> re-fetch
    assert len(calls) == 2
