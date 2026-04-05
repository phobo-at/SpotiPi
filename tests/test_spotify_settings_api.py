from __future__ import annotations

from pathlib import Path

import pytest

from src.api import spotify as spotify_api
from src.utils import spotify_secrets


def _bind_runtime_env(monkeypatch, env_path: Path) -> None:
    monkeypatch.setattr(spotify_secrets, "get_runtime_env_path", lambda: env_path)
    # Clear env vars so os.environ fallback doesn't leak real credentials into tests
    for env_key in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
                    "SPOTIFY_REFRESH_TOKEN", "SPOTIFY_USERNAME"):
        monkeypatch.delenv(env_key, raising=False)
    spotify_secrets.invalidate_spotify_secrets_cache()


@pytest.fixture
def runtime_paths(monkeypatch, tmp_path):
    env_path = tmp_path / ".spotipi-test" / ".env"
    token_state_path = tmp_path / "spotify_token.json"

    _bind_runtime_env(monkeypatch, env_path)
    monkeypatch.setattr(spotify_api, "TOKEN_STATE_PATH", token_state_path)
    return env_path, token_state_path


def test_get_spotify_settings_reports_missing_credentials(client, runtime_paths):
    response = client.get("/api/settings/spotify")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["connection"]["status"] == "missing_credentials"
    assert data["credentials"]["client_id"]["set"] is False
    assert data["credentials"]["client_secret"]["set"] is False


def test_patch_spotify_settings_updates_runtime_env_and_masks(client, runtime_paths):
    env_path, _ = runtime_paths

    response = client.patch(
        "/api/settings/spotify",
        json={
            "credentials": {
                "client_id": "clientid12345678901234567890",
                "client_secret": "secret12345678901234567890",
                "username": "demo-user",
            }
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert sorted(payload["data"]["updated"]) == ["client_id", "client_secret", "username"]

    spotify_data = payload["data"]["spotify"]
    assert spotify_data["connection"]["status"] == "auth_required"
    assert spotify_data["credentials"]["username"]["value"] == "demo-user"
    assert spotify_data["credentials"]["client_secret"]["masked"] != "secret12345678901234567890"

    env_contents = env_path.read_text(encoding="utf-8")
    assert "SPOTIFY_CLIENT_ID=clientid12345678901234567890" in env_contents
    assert "SPOTIFY_CLIENT_SECRET=secret12345678901234567890" in env_contents
    assert "SPOTIFY_USERNAME=demo-user" in env_contents


def test_patch_spotify_settings_rejects_invalid_payload(client, runtime_paths):
    response = client.patch(
        "/api/settings/spotify",
        json={
            "credentials": {
                "client_id": "invalid id with spaces",
            }
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert payload["error_code"] == "validation_error"
    assert "client_id" in payload["data"]["fields"]


def test_disconnect_spotify_removes_refresh_token_and_token_state(client, runtime_paths):
    env_path, token_state_path = runtime_paths

    spotify_secrets.update_spotify_credentials(
        {
            "client_id": "clientid12345678901234567890",
            "client_secret": "secret12345678901234567890",
            "refresh_token": "refresh12345678901234567890",
            "username": "demo-user",
        }
    )
    token_state_path.write_text("{}", encoding="utf-8")

    response = client.post("/api/settings/spotify/disconnect")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["data"]["spotify"]["credentials"]["refresh_token"]["set"] is False

    env_contents = env_path.read_text(encoding="utf-8")
    assert "SPOTIFY_REFRESH_TOKEN" not in env_contents
    assert not token_state_path.exists()


def test_refresh_access_token_uses_updated_credentials_without_restart(monkeypatch, runtime_paths):
    env_path, _ = runtime_paths
    monkeypatch.setenv("SPOTIPI_TOKEN_PLAINTEXT", "1")

    spotify_secrets.update_spotify_credentials(
        {
            "client_id": "clientidAAAAAA1111111111111111",
            "client_secret": "secretAAAAAA1111111111111111",
            "refresh_token": "refreshAAAAAA1111111111111111",
        }
    )

    auth_log: list[tuple[str, str]] = []

    class FakeResponse:
        status_code = 200
        text = ""

        @staticmethod
        def raise_for_status() -> None:
            return None

        @staticmethod
        def json() -> dict:
            return {
                "access_token": "test-access-token",
                "expires_in": 3600,
            }

    def fake_post(*args, **kwargs):
        auth_log.append(kwargs.get("auth"))
        return FakeResponse()

    monkeypatch.setattr(spotify_api.SESSION, "post", fake_post)

    first_token = spotify_api.refresh_access_token(with_retries=False)
    assert first_token == "test-access-token"
    assert auth_log[-1] == ("clientidAAAAAA1111111111111111", "secretAAAAAA1111111111111111")

    spotify_secrets.update_spotify_credentials(
        {
            "client_id": "clientidBBBBBB2222222222222222",
            "client_secret": "secretBBBBBB2222222222222222",
            "refresh_token": "refreshBBBBBB2222222222222222",
        }
    )

    second_token = spotify_api.refresh_access_token(with_retries=False)
    assert second_token == "test-access-token"
    assert auth_log[-1] == ("clientidBBBBBB2222222222222222", "secretBBBBBB2222222222222222")

    env_contents = env_path.read_text(encoding="utf-8")
    assert "SPOTIFY_CLIENT_ID=clientidBBBBBB2222222222222222" in env_contents
