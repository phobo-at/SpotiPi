from __future__ import annotations

from pathlib import Path

from src.utils import spotify_secrets


def _bind_runtime_env(monkeypatch, env_path: Path) -> None:
    monkeypatch.setattr(spotify_secrets, "get_runtime_env_path", lambda: env_path)
    for env_key in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
                    "SPOTIFY_REFRESH_TOKEN", "SPOTIFY_USERNAME"):
        monkeypatch.delenv(env_key, raising=False)
    spotify_secrets.invalidate_spotify_secrets_cache()


def test_update_spotify_credentials_creates_runtime_env(monkeypatch, tmp_path):
    env_path = tmp_path / ".spotipi-test" / ".env"
    _bind_runtime_env(monkeypatch, env_path)

    assert spotify_secrets.update_spotify_credentials(
        {
            "client_id": "clientid12345678901234567890",
            "client_secret": "clientsecret12345678901234567890",
            "username": "spotipi-user",
        }
    )

    assert env_path.exists()
    contents = env_path.read_text(encoding="utf-8")
    assert "SPOTIFY_CLIENT_ID=clientid12345678901234567890" in contents
    assert "SPOTIFY_CLIENT_SECRET=clientsecret12345678901234567890" in contents
    assert "SPOTIFY_USERNAME=spotipi-user" in contents

    try:
        file_mode = oct(env_path.stat().st_mode & 0o777)
        assert file_mode == "0o600"
    except OSError:
        # Permission assertions can be restricted in some CI/sandbox environments.
        pass


def test_update_spotify_credentials_preserves_other_env_entries(monkeypatch, tmp_path):
    env_path = tmp_path / ".spotipi-test" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "# Keep me\nOTHER_KEY=keep\nSPOTIFY_REFRESH_TOKEN=old-token\n",
        encoding="utf-8",
    )
    _bind_runtime_env(monkeypatch, env_path)

    spotify_secrets.update_spotify_credentials({"refresh_token": "new-token"})

    contents = env_path.read_text(encoding="utf-8")
    assert "# Keep me" in contents
    assert "OTHER_KEY=keep" in contents
    assert "SPOTIFY_REFRESH_TOKEN=new-token" in contents


def test_update_spotify_credentials_can_remove_refresh_token(monkeypatch, tmp_path):
    env_path = tmp_path / ".spotipi-test" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text(
        "SPOTIFY_CLIENT_ID=abc\nSPOTIFY_REFRESH_TOKEN=to-delete\n",
        encoding="utf-8",
    )
    _bind_runtime_env(monkeypatch, env_path)

    spotify_secrets.update_spotify_credentials({"refresh_token": None})

    contents = env_path.read_text(encoding="utf-8")
    assert "SPOTIFY_CLIENT_ID=abc" in contents
    assert "SPOTIFY_REFRESH_TOKEN" not in contents


def test_get_spotify_credentials_reflects_updates_without_restart(monkeypatch, tmp_path):
    env_path = tmp_path / ".spotipi-test" / ".env"
    _bind_runtime_env(monkeypatch, env_path)

    spotify_secrets.update_spotify_credentials({"client_id": "first-client-1234567890123"})
    first_read = spotify_secrets.get_spotify_credentials(use_cache=True)
    assert first_read["client_id"] == "first-client-1234567890123"

    spotify_secrets.update_spotify_credentials({"client_id": "second-client-123456789012"})
    second_read = spotify_secrets.get_spotify_credentials(use_cache=True)
    assert second_read["client_id"] == "second-client-123456789012"


def test_build_masked_credentials_payload_hides_secrets():
    payload = spotify_secrets.build_masked_credentials_payload(
        {
            "client_id": "abcd1234efgh5678",
            "client_secret": "secretvalue1234",
            "refresh_token": "refreshvalue5678",
            "username": "demo-user",
        }
    )

    assert payload["client_id"]["set"] is True
    assert payload["client_id"]["masked"].startswith("abcd")
    assert payload["client_secret"]["masked"] != "secretvalue1234"
    assert payload["refresh_token"]["masked"] != "refreshvalue5678"
    assert payload["username"]["value"] == "demo-user"
