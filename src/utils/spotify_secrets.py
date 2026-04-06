"""Helpers for reading/writing Spotify credentials in the runtime .env file."""

from __future__ import annotations

import os
import re
import threading
import time
from pathlib import Path
from typing import Dict, Optional

_SPOTIFY_KEYS = {
    "client_id": "SPOTIFY_CLIENT_ID",
    "client_secret": "SPOTIFY_CLIENT_SECRET",
    "refresh_token": "SPOTIFY_REFRESH_TOKEN",
    "username": "SPOTIFY_USERNAME",
}

_SECRET_FIELDS = {"client_id", "client_secret", "refresh_token"}
_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_VALUE_PATTERN = re.compile(r"^[A-Za-z0-9._:/@+\-=]*$")

_lock = threading.RLock()
_cache: Optional[Dict[str, str]] = None
_cache_ts = 0.0


def _cache_ttl_seconds() -> float:
    raw_ttl = os.getenv("SPOTIPI_SPOTIFY_SECRETS_CACHE_TTL", "2.0")
    try:
        return max(0.2, float(raw_ttl))
    except (TypeError, ValueError):
        return 2.0


def get_runtime_env_path() -> Path:
    """Return the canonical runtime secrets path (~/.spotipi/.env by default)."""
    app_name = os.getenv("SPOTIPI_APP_NAME", "spotipi")
    return Path.home() / f".{app_name}" / ".env"


def _ensure_runtime_paths(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass

    if not path.exists():
        path.touch(exist_ok=True)

    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _strip_wrapping_quotes(value: str) -> str:
    if len(value) >= 2 and (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        return value[1:-1]
    return value


def _read_runtime_env(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    values: Dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        candidate = stripped
        if candidate.startswith("export "):
            candidate = candidate[len("export ") :].strip()

        if "=" not in candidate:
            continue

        key, raw_value = candidate.split("=", 1)
        key = key.strip()
        if key not in _SPOTIFY_KEYS.values():
            continue

        values[key] = _strip_wrapping_quotes(raw_value.strip())

    return values


def invalidate_spotify_secrets_cache() -> None:
    """Clear the in-memory credentials cache."""
    global _cache, _cache_ts
    with _lock:
        _cache = None
        _cache_ts = 0.0


def _read_runtime_env_cached(use_cache: bool = True) -> Dict[str, str]:
    global _cache, _cache_ts

    with _lock:
        now = time.monotonic()
        if use_cache and _cache is not None and (now - _cache_ts) <= _cache_ttl_seconds():
            return dict(_cache)

        path = get_runtime_env_path()
        values = _read_runtime_env(path)
        _cache = dict(values)
        _cache_ts = now
        return values


def get_spotify_credentials(use_cache: bool = True) -> Dict[str, str]:
    """Return Spotify credentials from runtime secrets, falling back to os.environ.

    The runtime .env (~/.spotipi/.env) is authoritative, but credentials may also
    be loaded into os.environ via load_dotenv() at startup (e.g. from the repo .env).
    Fall back to os.environ so existing installations don't lose visibility of
    credentials that haven't been migrated to the runtime file yet. Writes via
    update_spotify_credentials() keep os.environ in sync so explicit deletions
    (e.g. disconnect) are never masked by stale startup values.
    """
    env_values = _read_runtime_env_cached(use_cache=use_cache)
    result: Dict[str, str] = {}

    for field, env_key in _SPOTIFY_KEYS.items():
        value = (env_values.get(env_key) or "").strip()
        if not value:
            value = (os.environ.get(env_key) or "").strip()
        result[field] = value

    return result


def _encode_env_value(value: str) -> str:
    text = value.replace("\n", "").replace("\r", "")
    if _SAFE_VALUE_PATTERN.fullmatch(text):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def update_spotify_credentials(updates: Dict[str, Optional[str]]) -> bool:
    """Persist partial Spotify credential updates atomically into runtime .env."""
    global _cache, _cache_ts
    normalized_updates: Dict[str, Optional[str]] = {}
    for field, value in updates.items():
        if field not in _SPOTIFY_KEYS:
            continue

        if value is None:
            normalized_updates[_SPOTIFY_KEYS[field]] = None
        else:
            normalized_updates[_SPOTIFY_KEYS[field]] = str(value).strip()

    if not normalized_updates:
        return True

    path = get_runtime_env_path()
    with _lock:
        _ensure_runtime_paths(path)

        try:
            existing_lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        except OSError:
            existing_lines = []

        replaced = set()
        output_lines = []

        for line in existing_lines:
            candidate = line.strip()
            if candidate.startswith("export "):
                candidate = candidate[len("export ") :].strip()

            if "=" not in candidate:
                output_lines.append(line)
                continue

            key = candidate.split("=", 1)[0].strip()
            if not _KEY_PATTERN.fullmatch(key):
                output_lines.append(line)
                continue

            if key not in normalized_updates:
                output_lines.append(line)
                continue

            replaced.add(key)
            next_value = normalized_updates[key]
            if next_value is None:
                continue

            output_lines.append(f"{key}={_encode_env_value(next_value)}\n")

        for key, value in normalized_updates.items():
            if key in replaced or value is None:
                continue
            output_lines.append(f"{key}={_encode_env_value(value)}\n")

        if output_lines and not output_lines[-1].endswith("\n"):
            output_lines[-1] = output_lines[-1] + "\n"

        temp_path = path.with_suffix(".tmp")
        try:
            temp_path.write_text("".join(output_lines), encoding="utf-8")
            os.replace(temp_path, path)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

        # Keep os.environ in sync with the runtime .env so the fallback in
        # get_spotify_credentials() never serves stale values after explicit
        # updates or deletions (e.g. disconnect removes the refresh token).
        for env_key, next_value in normalized_updates.items():
            if next_value is None:
                os.environ.pop(env_key, None)
            else:
                os.environ[env_key] = next_value

        _cache = None
        _cache_ts = 0.0

    return True


def mask_secret(value: str, *, visible: int = 4) -> str:
    """Mask a value while preserving only short prefix/suffix fragments."""
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= visible * 2:
        return "*" * len(text)
    return f"{text[:visible]}...{text[-visible:]}"


def build_masked_credentials_payload(credentials: Dict[str, str]) -> Dict[str, Dict[str, str | bool]]:
    """Return UI-safe credential metadata with masked values."""
    payload: Dict[str, Dict[str, str | bool]] = {}

    for field in ("client_id", "client_secret", "refresh_token"):
        value = str(credentials.get(field, "") or "")
        payload[field] = {
            "set": bool(value),
            "masked": mask_secret(value),
        }
        if field == "client_id":
            payload[field]["value"] = value

    username_value = str(credentials.get("username", "") or "")
    payload["username"] = {
        "set": bool(username_value),
        "value": username_value,
        "masked": username_value,
    }

    return payload


def has_required_oauth_credentials(credentials: Dict[str, str]) -> bool:
    """Return True when client id + client secret are configured."""
    return bool(credentials.get("client_id") and credentials.get("client_secret"))


def credentials_need_auth(credentials: Dict[str, str]) -> bool:
    """Return True when refresh token is missing."""
    return not bool(credentials.get("refresh_token"))


def secret_field_names() -> set[str]:
    """Return field names that should never be logged in clear text."""
    return set(_SECRET_FIELDS)
