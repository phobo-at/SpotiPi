import os

import generate_token


def test_store_refresh_token_writes_env_file_with_strict_permissions(tmp_path):
    env_path = tmp_path / ".spotipi" / ".env"

    stored_path = generate_token.store_refresh_token("refresh-token-value", env_path=env_path)

    assert stored_path == env_path
    assert env_path.read_text(encoding="utf-8") == "SPOTIFY_REFRESH_TOKEN=refresh-token-value\n"
    assert env_path.stat().st_mode & 0o777 == 0o600


def test_load_environment_reads_canonical_env_file(tmp_path, monkeypatch):
    env_path = tmp_path / ".spotipi" / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("SPOTIPI_TEST_MARKER=canonical\n", encoding="utf-8")

    monkeypatch.delenv("SPOTIPI_TEST_MARKER", raising=False)

    loaded_path = generate_token.load_environment(env_path)

    assert loaded_path == env_path
    assert os.getenv("SPOTIPI_TEST_MARKER") == "canonical"


def test_scope_configuration_contains_required_library_and_search_scopes():
    required_scopes = {
        "user-follow-read",
        "user-library-read",
        "user-top-read",
        "user-read-recently-played",
        "user-read-private",
    }
    assert required_scopes.issubset(set(generate_token.SCOPES))
