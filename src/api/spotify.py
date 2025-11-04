#!/usr/bin/env python3
"""
🎵 Spotify API Integration for SpotiPi
Provides comprehensive Spotify Web API functionality including:
- Authentication and token management
- Music library access (playlists, albums, tracks, artists)  
- Playback control with device management
- Parallel data loading for performance
"""

import copy
import json
import logging
import os
import random
import re
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
from dotenv import load_dotenv

# Use the new centralized config system
from ..config import load_config
from ..utils.cache_migration import get_cache_migration_layer
from ..utils.library_utils import compute_library_hash
from ..utils.perf_monitor import perf_monitor
from ..utils.thread_safety import config_transaction, load_config_safe
# Import token caching system
from ..utils.token_cache import TokenResponse
from ..utils.token_cache import ensure_token_valid as cache_ensure_token_valid
from ..utils.token_cache import (force_token_refresh, get_cached_token,
                                 initialize_token_cache,
                                 invalidate_token_cache, seed_token_cache,
                                 token_needs_refresh)
from .http import DEFAULT_TIMEOUT, SESSION

# Use the new central#  Exportable functions - Updated for new config system
__all__ = [
    "refresh_access_token", "ensure_token_valid", "get_access_token", "force_refresh_token",
    "get_playlists", "get_devices", "get_device_id",
    "start_playback", "play_with_retry", "stop_playback", "resume_playback", "toggle_playback",
    "get_current_playback", "get_current_track", "get_current_spotify_volume", 
    "get_saved_albums", "get_user_saved_tracks", "get_followed_artists",
    "set_volume", "get_playback_status", "get_user_library", "get_combined_playback",
    "load_music_library_parallel", "spotify_network_health"
]

# 🔧 File paths - Use path-agnostic configuration
def _get_app_config_dir():
    """Get application configuration directory path-agnostically"""
    app_name = os.getenv("SPOTIPI_APP_NAME", "spotipi")
    return os.path.expanduser(f"~/.{app_name}")

def _get_env_path():
    """Get environment file path dynamically"""
    return os.path.join(_get_app_config_dir(), ".env")

ENV_PATH = _get_env_path()

# 🌍 Load environment variables
if os.path.exists(ENV_PATH):
    load_dotenv(dotenv_path=ENV_PATH)
# Also allow project-root .env to supply overrides (common in dev setups)
load_dotenv()
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
USERNAME = os.getenv("SPOTIFY_USERNAME")
_LOW_POWER_MODE = os.getenv('SPOTIPI_LOW_POWER', '').lower() in ('1', 'true', 'yes', 'on')

TOKEN_STATE_PATH = Path(_get_app_config_dir()) / "spotify_token.json"


def _coerce_float(value: Optional[str], default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


DEFAULT_CONNECT_TIMEOUT, DEFAULT_READ_TIMEOUT = DEFAULT_TIMEOUT
DEFAULT_HTTP_TIMEOUT = _coerce_float(os.getenv('SPOTIPI_HTTP_TIMEOUT'), DEFAULT_READ_TIMEOUT)
LONG_HTTP_TIMEOUT = _coerce_float(
    os.getenv('SPOTIPI_HTTP_LONG_TIMEOUT'),
    max(DEFAULT_HTTP_TIMEOUT * 1.5, DEFAULT_READ_TIMEOUT * 1.5, 20.0)
)
SPOTIFY_API_TIMEOUT = max(DEFAULT_HTTP_TIMEOUT, LONG_HTTP_TIMEOUT, DEFAULT_READ_TIMEOUT)

TOKEN_REFRESH_MAX_ATTEMPTS = max(1, int(os.getenv('SPOTIPI_TOKEN_REFRESH_ATTEMPTS', '3')))
TOKEN_REFRESH_BACKOFF_BASE = _coerce_float(os.getenv('SPOTIPI_TOKEN_REFRESH_BACKOFF', None), 0.5)
TOKEN_REFRESH_BACKOFF_JITTER = _coerce_float(os.getenv('SPOTIPI_TOKEN_REFRESH_JITTER', None), 0.4)
TOKEN_SAFETY_WINDOW = max(30, int(os.getenv('SPOTIPI_TOKEN_SAFETY_WINDOW', '120')))
PREWARM_SECONDS = max(30, int(os.getenv('SPOTIPI_PREWARM_SECONDS', str(TOKEN_SAFETY_WINDOW))))

PLAYER_MAX_ATTEMPTS = max(1, int(os.getenv('SPOTIPI_PLAYER_RETRIES', '3')))
PLAYER_BACKOFF_BASE = _coerce_float(os.getenv('SPOTIPI_PLAYER_BACKOFF', None), 1.0)
PLAYER_BACKOFF_JITTER = _coerce_float(os.getenv('SPOTIPI_PLAYER_JITTER', None), 0.35)
FALLBACK_DEVICE_NAME = os.getenv('SPOTIPI_FALLBACK_DEVICE')

PLAYBACK_VERIFY_ATTEMPTS = max(2, int(os.getenv('SPOTIPI_PLAYBACK_VERIFY_ATTEMPTS', '6')))
PLAYBACK_VERIFY_WAIT = max(0.2, _coerce_float(os.getenv('SPOTIPI_PLAYBACK_VERIFY_WAIT', None), 1.0))
SHUFFLE_RETRY_ATTEMPTS = max(1, int(os.getenv('SPOTIPI_SHUFFLE_RETRY_ATTEMPTS', '2')))
SHUFFLE_RETRY_DELAY = max(0.2, _coerce_float(os.getenv('SPOTIPI_SHUFFLE_RETRY_DELAY', None), 0.75))

def _max_concurrency() -> int:
    override = os.getenv('SPOTIPI_MAX_CONCURRENCY')
    if override:
        try:
            value = max(1, int(override))
            return value
        except ValueError:
            logging.getLogger('spotify').warning(
                "Invalid SPOTIPI_MAX_CONCURRENCY=%s; using safe default",
                override
            )
    return 2 if _LOW_POWER_MODE else 3


MAX_CONCURRENCY = _max_concurrency()
_REQUEST_SEMAPHORE = threading.Semaphore(MAX_CONCURRENCY)
_SINGLE_FLIGHT_LOCK = threading.Lock()
_IN_FLIGHT: Dict[Tuple[str, str, Tuple[Any, ...]], "_SingleFlight"] = {}


def _coerce_timeout(value: Optional[Union[int, float, Tuple[float, float]]]) -> Optional[Union[float, Tuple[float, float]]]:
    if value is None:
        return None
    if isinstance(value, tuple):
        try:
            connect = max(0.2, float(value[0]))
            read = max(0.2, float(value[1]))
            return connect, read
        except (TypeError, ValueError, IndexError):
            return None
    try:
        return max(0.2, float(value))
    except (TypeError, ValueError):
        return None


def _get_library_worker_limit() -> int:
    """Determine how many worker threads to use for library fetches."""
    override = os.getenv('SPOTIPI_LIBRARY_WORKERS')
    if override:
        try:
            value = max(1, int(override))
            return value
        except ValueError:
            logging.getLogger('spotify').warning(
                "Invalid SPOTIPI_LIBRARY_WORKERS=%s; falling back to default",
                override
            )
    base = 2 if _LOW_POWER_MODE else 3
    return max(1, min(base, MAX_CONCURRENCY))


def _compute_backoff(base: float, attempt: int, jitter: float, cap: float = 15.0) -> float:
    """Compute exponential backoff with jitter."""
    delay = base * (2 ** max(attempt - 1, 0))
    jitter_value = random.uniform(0, delay * max(jitter, 0.0))
    return min(delay + jitter_value, cap)


def _save_token_atomically(payload: Dict[str, Any]) -> None:
    """Persist token payload atomically to avoid corruption."""
    try:
        TOKEN_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = TOKEN_STATE_PATH.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, TOKEN_STATE_PATH)
    except Exception as exc:
        logging.getLogger('spotify').warning("Failed to persist token payload: %s", exc)


def _load_persisted_token() -> Optional[TokenResponse]:
    """Load persisted token data from disk if available and not expired."""
    try:
        if not TOKEN_STATE_PATH.exists():
            return None
        with TOKEN_STATE_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)

        access_token = data.get("access_token")
        expires_at = float(data.get("expires_at", 0))
        received_at = float(data.get("received_at", data.get("created_at", time.time())))
        refresh_token = data.get("refresh_token")
        scope = data.get("scope")
        token_type = data.get("token_type")

        if not access_token or not expires_at:
            return None
        if expires_at <= time.time():
            return None

        expires_in = int(max(60, expires_at - received_at))
        return TokenResponse(
            access_token=access_token,
            expires_in=expires_in,
            refresh_token=refresh_token,
            scope=scope,
            token_type=token_type,
            received_at=received_at,
        )
    except Exception as exc:
        logging.getLogger('spotify').debug("Could not load persisted token: %s", exc)
        return None

# 🔑 Token functions
_TOKEN_ENDPOINT = "https://accounts.spotify.com/api/token"


def _refresh_access_token_impl(with_retries: bool = True) -> Optional[TokenResponse]:
    """Internal helper performing the token refresh with retries and persistence."""
    logger = logging.getLogger('spotify')

    if os.getenv("SPOTIPI_OFFLINE") == "1":
        logger.debug("token.refresh.skip_offline")
        return None

    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        raise RuntimeError("Spotify credentials missing for token refresh")

    attempts = 0
    last_exc: Optional[Exception] = None

    while True:
        attempts += 1
        start = time.perf_counter()

        try:
            with _REQUEST_SEMAPHORE:
                response = SESSION.post(
                    _TOKEN_ENDPOINT,
                    data={"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN},
                    auth=(CLIENT_ID, CLIENT_SECRET),
                    timeout=SPOTIFY_API_TIMEOUT,
                )

            elapsed = time.perf_counter() - start
            status = response.status_code

            if status in (429, 500, 502, 503, 504):
                raise requests.HTTPError(f"retryable status {status}", response=response)

            response.raise_for_status()
            payload = response.json()
            token = payload.get("access_token")
            if not token:
                raise RuntimeError("Token response missing access_token")

            expires_in = int(payload.get("expires_in", 3600))

            token_response = TokenResponse(
                access_token=token,
                expires_in=expires_in,
                refresh_token=payload.get("refresh_token"),
                scope=payload.get("scope"),
                token_type=payload.get("token_type"),
                received_at=time.time(),
            )

            persist_payload = dict(payload)
            persist_payload["received_at"] = token_response.received_at
            persist_payload["expires_at"] = token_response.received_at + expires_in
            if REFRESH_TOKEN and "refresh_token" not in persist_payload:
                persist_payload["refresh_token"] = REFRESH_TOKEN

            _save_token_atomically(persist_payload)

            logger.info(
                "token.refresh.ok",
                extra={"attempts": attempts, "elapsed": round(elapsed, 3)},
            )
            return token_response

        except (requests.ReadTimeout, requests.ConnectionError) as exc:
            last_exc = exc
            elapsed = time.perf_counter() - start
            logger.warning(
                "token.refresh.retry",
                extra={
                    "attempt": attempts,
                    "elapsed": round(elapsed, 3),
                    "reason": exc.__class__.__name__,
                },
            )

        except requests.HTTPError as exc:
            last_exc = exc
            status_code = exc.response.status_code if exc.response is not None else None
            elapsed = time.perf_counter() - start
            retryable = status_code in (429, 500, 502, 503, 504)
            level = logging.WARNING if retryable else logging.ERROR
            logger.log(
                level,
                "token.refresh.http_error",
                extra={
                    "attempt": attempts,
                    "status": status_code,
                    "elapsed": round(elapsed, 3),
                },
            )
            if not retryable:
                raise

        except (ValueError, json.JSONDecodeError, RuntimeError) as exc:
            last_exc = exc
            logger.error(
                "token.refresh.parse_error",
                extra={"attempt": attempts, "cause": str(exc)},
            )
            raise

        if not with_retries or attempts >= TOKEN_REFRESH_MAX_ATTEMPTS:
            break

        delay = _compute_backoff(TOKEN_REFRESH_BACKOFF_BASE, attempts, TOKEN_REFRESH_BACKOFF_JITTER)
        time.sleep(delay)

    if last_exc:
        logger.error(
            "token.refresh.fail",
            extra={"attempts": attempts, "error": str(last_exc)},
        )
        raise last_exc

    raise RuntimeError("Token refresh failed without specific error")


def refresh_access_token(with_retries: bool = True) -> Optional[str]:
    """Public wrapper returning the raw token string for legacy callers."""
    try:
        token_response = _refresh_access_token_impl(with_retries=with_retries)
        return token_response.access_token if token_response else None
    except Exception as exc:
        logging.getLogger('spotify').debug("token.refresh.wrapper_failure: %s", exc)
        return None

# 🎟️ Cached token functions
def get_access_token() -> Optional[str]:
    """Get a valid access token using the cache system.
    
    Returns:
        Optional[str]: Valid access token or None if unavailable
    """
    return get_cached_token()

def force_refresh_token() -> Optional[str]:
    """Force refresh the access token bypassing cache.
    
    Returns:
        Optional[str]: New access token or None if refresh fails
    """
    return force_token_refresh()


def ensure_token_valid(min_ttl: int = TOKEN_SAFETY_WINDOW) -> Optional[str]:
    """Ensure the cached token remains valid for at least ``min_ttl`` seconds."""
    window = max(30, min_ttl)
    try:
        if token_needs_refresh(window):
            logging.getLogger('spotify').info(
                "token.refresh.prewarm",
                extra={"window": window},
            )
        return cache_ensure_token_valid(window)
    except Exception as exc:
        logging.getLogger('spotify').error(
            "token.refresh.ensure_failed",
            extra={"error": str(exc)},
        )
        return None

# Initialize token cache when module is imported
initialize_token_cache(lambda: _refresh_access_token_impl(with_retries=True))
_persisted = _load_persisted_token()
if _persisted:
    seed_token_cache(_persisted)
    logging.getLogger('spotify').debug(
        "token.cache.seeded",
        extra={"expires_in": _persisted.expires_in, "received_at": _persisted.received_at},
    )

# Initialize cache migration layer
cache_migration = get_cache_migration_layer()

class _SingleFlight:
    """Track in-flight GET requests to deduplicate identical calls."""

    __slots__ = ("event", "response", "error")

    def __init__(self) -> None:
        self.event = threading.Event()
        self.response: Optional[requests.Response] = None
        self.error: Optional[Exception] = None


def _freeze_value(value: Any) -> Any:
    if isinstance(value, dict):
        return tuple(sorted((k, _freeze_value(v)) for k, v in value.items()))
    if isinstance(value, (list, tuple, set)):
        return tuple(_freeze_value(v) for v in value)
    return str(value)


def _build_singleflight_key(method: str, url: str, params: Optional[Any]) -> Tuple[str, str, Tuple[Any, ...]]:
    if not params:
        frozen: Tuple[Any, ...] = tuple()
    elif isinstance(params, dict):
        frozen = tuple(sorted((k, _freeze_value(v)) for k, v in params.items()))
    else:
        try:
            frozen = tuple((str(k), _freeze_value(v)) for k, v in params)  # type: ignore[assignment]
        except Exception:
            frozen = (_freeze_value(params),)
    return method.upper(), url, frozen


def _claim_singleflight(key: Tuple[str, str, Tuple[Any, ...]]) -> Tuple[_SingleFlight, bool]:
    with _SINGLE_FLIGHT_LOCK:
        slot = _IN_FLIGHT.get(key)
        if slot:
            return slot, False
        slot = _SingleFlight()
        _IN_FLIGHT[key] = slot
        return slot, True


def _release_singleflight(key: Tuple[str, str, Tuple[Any, ...]]) -> None:
    with _SINGLE_FLIGHT_LOCK:
        _IN_FLIGHT.pop(key, None)


_PLAYBACK_CACHE: Dict[str, Any] | None = None
_PLAYBACK_CACHE_EXPIRY: float = 0.0


def _invalidate_playback_cache() -> None:
    global _PLAYBACK_CACHE, _PLAYBACK_CACHE_EXPIRY
    _PLAYBACK_CACHE = None
    _PLAYBACK_CACHE_EXPIRY = 0.0

_BREAKER = {
    'consecutive_failures': 0,
    'open_until': 0.0,
    'threshold': int(os.getenv('SPOTIPI_BREAKER_THRESHOLD', '3')),
    'cooldown': int(os.getenv('SPOTIPI_BREAKER_COOLDOWN', '30')),
}

def _breaker_open() -> bool:
    return time.time() < _BREAKER['open_until']

def _breaker_on_success() -> None:
    _BREAKER['consecutive_failures'] = 0
    _BREAKER['open_until'] = 0.0

def _breaker_on_failure() -> None:
    _BREAKER['consecutive_failures'] += 1
    if _BREAKER['consecutive_failures'] >= _BREAKER['threshold']:
        _BREAKER['open_until'] = time.time() + _BREAKER['cooldown']

def _spotify_request(
    method: str,
    url: str,
    *,
    headers: Dict[str, str],
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    timeout: Optional[Union[int, float, Tuple[float, float]]] = None
) -> requests.Response:
    if _breaker_open():
        raise RuntimeError("Spotify API temporarily unavailable (circuit breaker open)")

    method_upper = method.upper()
    request_timeout = _coerce_timeout(timeout)

    sf_key: Optional[Tuple[str, str, Tuple]] = None
    sf_slot: Optional[_SingleFlight] = None
    is_leader = False

    if method_upper == 'GET':
        sf_key = _build_singleflight_key(method_upper, url, params)
        sf_slot, is_leader = _claim_singleflight(sf_key)
        if not is_leader:
            sf_slot.event.wait()
            if sf_slot.error:
                raise sf_slot.error
            if sf_slot.response is None:
                raise RuntimeError("Single-flight response missing")
            return sf_slot.response

    path_fragment = url.split("/v1/")[-1].split("?")[0]
    metric_label = f"spotify.http.{method_upper.lower()}.{path_fragment.replace('/', '.') or 'root'}"

    request_params: Dict[str, Any] = {
        "method": method_upper,
        "url": url,
        "headers": headers,
        "params": params,
        "json": json,
    }
    if request_timeout is not None:
        request_params["timeout"] = request_timeout

    start = time.perf_counter()

    try:
        with _REQUEST_SEMAPHORE:
            with perf_monitor.time_block(metric_label):
                resp = SESSION.request(**request_params)
        _breaker_on_success()
        if method_upper == 'GET' and is_leader and sf_slot:
            sf_slot.response = resp
        return resp
    except requests.exceptions.RequestException as exc:
        _breaker_on_failure()
        elapsed = time.perf_counter() - start
        logging.getLogger('spotify').warning(
            "spotify.request.error",
            extra={
                "method": method_upper,
                "url": url,
                "elapsed": round(elapsed, 3),
                "error": exc.__class__.__name__,
            },
        )
        if method_upper == 'GET' and is_leader and sf_slot:
            sf_slot.error = exc
        raise
    finally:
        if method_upper == 'GET' and sf_slot and is_leader:
            sf_slot.event.set()
            if sf_key is not None:
                _release_singleflight(sf_key)

# 🎵 Spotify API
def get_playlists(token: str) -> List[Dict[str, Any]]:
    """Fetch user's playlists from Spotify API.
    
    Args:
        token: Spotify access token
        
    Returns:
        List[Dict[str, Any]]: List of playlist dictionaries
    """
    logger = logging.getLogger('app')  # Use same logger as app.py
    playlists = []
    url = (
        "https://api.spotify.com/v1/me/playlists?limit=50&fields="
        "items(name,uri,images,owner(display_name),tracks(total)),next"
    )
    headers = {"Authorization": f"Bearer {token}"}
    
    while url:
        try:
            r = _spotify_request('GET', url, headers=headers, timeout=10)
            if r.status_code == 200:
                for item in r.json().get("items", []):
                    # Filter out playlists whose name starts with [Felix] (optional, personal setting)
                    playlist_name = item.get("name", "")
                    if playlist_name.startswith("[Felix]"):
                        logger.debug(f"⏭️  Skipping playlist '{playlist_name}' - filtered out (Felix playlist)")
                        continue
                        
                    # Get the best available image (prefer medium size)
                    images = item.get("images", [])
                    image_url = None
                    if images:
                        # Sort by size and pick medium sized image (around 300px)
                        # If no medium, pick the first available
                        for img in images:
                            width = img.get("width")
                            if width and width <= 300 and width >= 200:
                                image_url = img.get("url")
                                break
                        if not image_url and images:
                            image_url = images[0].get("url")
                            
                    # Skip playlists without cover images (usually local files)
                    if not image_url:
                        logger.debug(f"⏭️  Skipping playlist '{item['name']}' - no cover image (likely local files)")
                        continue
                        
                    # Determine creator display name
                    owner_display_name = item.get("owner", {}).get("display_name", "Spotify")
                    if owner_display_name == USERNAME:
                        creator = "Eigene Playlist"
                    elif owner_display_name == "Spotify":
                        creator = "Spotify"
                    else:
                        creator = owner_display_name
                        
                    playlists.append({
                        "name": item["name"], 
                        "artist": creator,  # Playlist creator as artist
                        "uri": item["uri"],
                        "image_url": image_url,
                        "track_count": item.get("tracks", {}).get("total", 0),
                        "type": "playlist"  # Marking as Playlist
                    })
                url = r.json().get("next")
            else:
                logger.error(f"❌ Error fetching playlists: {r.text}")
                break
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error fetching playlists: {e}")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching playlists: {e}")
            break
            
    playlists.sort(key=lambda p: p["name"].lower())
    return playlists

def get_saved_albums(token: str) -> List[Dict[str, Any]]:
    """Fetch the user's saved albums from Spotify.
    
    Args:
        token: Spotify access token
        
    Returns:
        List[Dict[str, Any]]: List of album dictionaries
    """
    logger = logging.getLogger('app')
    albums = []
    url = (
        "https://api.spotify.com/v1/me/albums?limit=50&fields="
        "items(album(name,uri,images,artists(name),total_tracks)),next"
    )
    headers = {"Authorization": f"Bearer {token}"}
    
    while url:
        try:
            r = _spotify_request('GET', url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                for item in data.get("items", []):
                    album = item.get("album", {})
                    if album:
                        # Get the best available image (prefer medium size)
                        images = album.get("images", [])
                        image_url = None
                        if images:
                            # Sort by size and pick medium sized image (around 300px)
                            for img in images:
                                width = img.get("width")
                                if width and width <= 300 and width >= 200:
                                    image_url = img.get("url")
                                    break
                            if not image_url and images:
                                image_url = images[0].get("url")
                        
                        # Format artist names
                        artists = album.get("artists", [])
                        artist_names = [artist.get("name", "") for artist in artists]
                        artist_string = ", ".join(artist_names) if artist_names else "Unknown Artist"
                        
                        albums.append({
                            "name": album.get('name', 'Unknown Album'),
                            "artist": artist_string,  # Separate Artist field for UI
                            "uri": album.get("uri", ""),
                            "image_url": image_url,
                            "track_count": album.get("total_tracks", 0),
                            "type": "album"  # Marking as Album
                        })
                
                url = data.get("next")
            else:
                logger.error(f"❌ Error fetching albums: {r.text}")
                break
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Network error fetching albums: {e}")
            break
        except Exception as e:
            logger.error(f"❌ Unexpected error fetching albums: {e}")
            break

    # Sort albums alphabetically
    albums.sort(key=lambda a: a["name"].lower())
    return albums

def get_user_saved_tracks(token: str) -> List[Dict[str, Any]]:
    """Holt die gespeicherten Songs (Liked Songs) des Benutzers von Spotify.
    
    Args:
        token: Spotify access token
        
    Returns:
        List[Dict[str, Any]]: List of saved track dictionaries
    """
    logger = logging.getLogger('app')
    tracks = []
    
    try:
        url = "https://api.spotify.com/v1/me/tracks?limit=50"
        headers = {"Authorization": f"Bearer {token}"}
        
        while url:
            r = _spotify_request('GET', url, headers=headers, timeout=10)
            
            if r.status_code == 200:
                data = r.json()
                for item in data.get("items", []):
                    track = item.get("track", {})
                    if track:
                        # Get the best available image from album
                        album = track.get("album", {})
                        images = album.get("images", [])
                        image_url = None
                        if images:
                            # Prefer medium size (around 300px)
                            for img in images:
                                width = img.get("width")
                                if width and width <= 300 and width >= 200:
                                    image_url = img.get("url")
                                    break
                            if not image_url and images:
                                image_url = images[0].get("url")
                        
                        # Format artist names
                        artists = track.get("artists", [])
                        artist_names = [artist.get("name", "") for artist in artists]
                        artist_string = ", ".join(artist_names) if artist_names else "Unknown Artist"
                        
                        tracks.append({
                            "name": track.get('name', 'Unknown Song'),
                            "artist": artist_string,  # Separate Artist field for UI
                            "uri": track.get("uri", ""),
                            "image_url": image_url,
                            "track_count": 1,  # Single song
                            "type": "track",
                            "album": album.get("name", ""),
                            "duration_ms": track.get("duration_ms", 0)
                        })
                
                url = data.get("next")
            else:
                logger.error(f"❌ Error fetching saved songs: {r.status_code} - {r.text}")
                break
                
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error fetching saved songs: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching saved songs: {e}")

    # Sort tracks alphabetically
    tracks.sort(key=lambda t: t["name"].lower())
    logger.info(f"💚 Total {len(tracks)} saved songs found")
    return tracks

def get_artist_top_tracks(token: str, artist_id: str, market: str = "US") -> List[Dict[str, Any]]:
    """Get an artist's top tracks.
    
    Args:
        token: Spotify access token
        artist_id: Spotify artist ID (extracted from URI)
        market: Country market (default: US)
        
    Returns:
        List[Dict[str, Any]]: List of top tracks
    """
    logger = logging.getLogger('app')
    url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"market": market}
    
    try:
        r = _spotify_request('GET', url, headers=headers, params=params, timeout=SPOTIFY_API_TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            tracks = []
            
            for track in data.get("tracks", []):
                # Get image from album
                image_url = None
                images = track.get("album", {}).get("images", [])
                if images:
                    # Prefer medium-sized images (around 300px)
                    for img in images:
                        width = img.get("width")
                        if width and width <= 300 and width >= 200:
                            image_url = img.get("url")
                            break
                    if not image_url:
                        image_url = images[0].get("url")
                
                # Format artists
                artists = track.get("artists", [])
                artist_names = [artist.get("name", "") for artist in artists]
                artist_string = ", ".join(artist_names) if artist_names else "Unknown Artist"
                
                tracks.append({
                    "name": track.get("name", "Unknown Track"),
                    "artist": artist_string,
                    "uri": track.get("uri", ""),
                    "image_url": image_url,
                    "track_count": 1,  # Each track is 1 track
                    "type": "track",
                    "duration_ms": track.get("duration_ms", 0),
                    "popularity": track.get("popularity", 0)
                })
            
            logger.info(f"✅ Artist top tracks loaded: {len(tracks)} tracks")
            return tracks
        else:
            logger.error(f"❌ Error fetching artist top tracks: {r.text}")
            return []
    except Exception as e:
        logger.error(f"❌ Exception fetching artist top tracks: {e}")
        return []


def get_followed_artists(token: str) -> List[Dict[str, Any]]:
    """Fetches the user's followed artists from Spotify.
    
    Args:
        token: Spotify access token
        
    Returns:
        List[Dict[str, Any]]: List of followed artist dictionaries
    """
    logger = logging.getLogger('app')
    artists = []
    url = "https://api.spotify.com/v1/me/following?type=artist&limit=50"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        while url:
            r = _spotify_request('GET', url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                artists_data = data.get("artists", {})
                
                for item in artists_data.get("items", []):
                    # Get the best available image (prefer medium size)
                    images = item.get("images", [])
                    image_url = None
                    if images:
                        # Sort by size and pick medium sized image (around 300px)
                        for img in images:
                            width = img.get("width")
                            if width and width <= 300 and width >= 200:
                                image_url = img.get("url")
                                break
                        if not image_url and images:
                            image_url = images[0].get("url")
                    
                    # Skip artists without images
                    if not image_url:
                        logger.debug(f"⏭️  Skipping artist '{item['name']}' - no image available")
                        continue
                    
                    artists.append({
                        "name": item.get("name", "Unknown Artist"),
                        "artist": f"{item.get('followers', {}).get('total', 0):,} Follower",  # Follower as additional info
                        "uri": item.get("uri", ""),
                        "artist_id": item.get("id", ""),  # Artist ID for top tracks API
                        "image_url": image_url,
                        "track_count": None,  # Artists have no direct track count
                        "type": "artist"  # Marking as Artist
                    })
                
                # Check for next page
                url = artists_data.get("next")
            else:
                logger.error(f"❌ Error fetching followed artists: {r.status_code} - {r.text}")
                break
                
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Network error fetching followed artists: {e}")
    except Exception as e:
        logger.error(f"❌ Unexpected error fetching followed artists: {e}")
    
    # Sort artists alphabetically
    artists.sort(key=lambda a: a["name"].lower())
    logger.info(f"🎤 Total {len(artists)} followed artists found")
    return artists

def get_devices(token: str) -> List[Dict[str, Any]]:
    """Get available Spotify devices with unified caching.
    
    Args:
        token: Spotify access token
        
    Returns:
        List[Dict[str, Any]]: List of available devices
    """
    def load_devices_from_api(token: str) -> List[Dict[str, Any]]:
        """Load devices directly from Spotify API."""
        try:
            with perf_monitor.time_block("spotify.devices.api_call"):
                r = _spotify_request(
                    'GET',
                    "https://api.spotify.com/v1/me/player/devices",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=8
                )
            if r.status_code == 200:
                devices = r.json().get("devices", [])
                return devices
            else:
                logging.getLogger('spotify').error(f"❌ Error fetching devices: {r.text}")
                return []
        except Exception as e:
            logging.getLogger('spotify').exception(f"❌ Exception while fetching devices: {e}")
            return []
    
    # Use unified cache system for devices
    return cache_migration.get_devices_cached(token, load_devices_from_api)


_DEVICE_WHITESPACE_RE = re.compile(r"\s+")
_MAX_CACHED_DEVICES = 8


def _remember_device_mapping(requested_name: str, actual_name: str, device_id: Optional[str]) -> None:
    if not device_id:
        return
    normalized_key = _normalize_device_name(actual_name or requested_name)
    if not normalized_key:
        return
    try:
        with config_transaction() as transaction:
            cfg = transaction.load()
            cache = cfg.get("last_known_devices")
            if not isinstance(cache, dict):
                cache = {}
            cache[normalized_key] = {
                "id": device_id,
                "name": actual_name or requested_name,
                "requested_name": requested_name,
                "updated_at": time.time(),
            }
            if len(cache) > _MAX_CACHED_DEVICES:
                sorted_items = sorted(
                    cache.items(),
                    key=lambda item: item[1].get("updated_at", 0.0),
                    reverse=True,
                )[:_MAX_CACHED_DEVICES]
                cache = {key: value for key, value in sorted_items}
            cfg["last_known_devices"] = cache
            transaction.save(cfg)
    except Exception as exc:  # pragma: no cover - fallback on best-effort cache
        logging.getLogger('spotify').debug("device.cache.store_failed %s", exc)


def _load_cached_device_mapping(device_name: str) -> Optional[Dict[str, Any]]:
    normalized_key = _normalize_device_name(device_name)
    if not normalized_key:
        return None
    try:
        cfg = load_config_safe()
    except Exception:
        try:
            cfg = load_config()
        except Exception:
            return None
    cache = cfg.get("last_known_devices")
    if not isinstance(cache, dict):
        return None
    entry = cache.get(normalized_key)
    if isinstance(entry, dict) and entry.get("id"):
        return entry
    return None


def _normalize_device_name(value: Any) -> str:
    """Normalize device names for robust comparison."""
    if not isinstance(value, str):
        return ""
    collapsed = _DEVICE_WHITESPACE_RE.sub(" ", value).strip()
    return collapsed.casefold()


def _pick_device_by_name(
    devices: List[Dict[str, Any]],
    normalized_target: str,
    *,
    allow_partial: bool = False,
) -> Optional[Dict[str, Any]]:
    """Find a device by normalized name, optionally allowing partial matches."""
    for device in devices:
        if _normalize_device_name(device.get("name")) == normalized_target:
            return device

    if not allow_partial or not normalized_target:
        return None

    candidates: List[Tuple[Tuple[int, int], Dict[str, Any]]] = []
    for device in devices:
        normalized_name = _normalize_device_name(device.get("name"))
        if not normalized_name:
            continue
        if normalized_target in normalized_name or normalized_name in normalized_target:
            weight = (
                0 if device.get("is_active") else 1,
                abs(len(normalized_name) - len(normalized_target)),
            )
            candidates.append((weight, device))

    if not candidates:
        return None

    candidates.sort(key=lambda entry: entry[0])
    return candidates[0][1]


def get_device_id(token: str, device_name: str) -> Optional[str]:
    """Get device ID by device name.
    
    Args:
        token: Spotify access token
        device_name: Name of the device to find
        
    Returns:
        Optional[str]: Device ID if found, None otherwise
    """
    logger = logging.getLogger('spotify')
    normalized_requested = _normalize_device_name(device_name)
    if not normalized_requested:
        return None

    devices = get_devices(token)
    device = _pick_device_by_name(devices, normalized_requested)

    if device is None:
        try:
            cache_migration.invalidate_devices()
        except Exception as exc:
            logger.debug(
                "spotify.device.cache_invalidate_failed",
                extra={"error": str(exc)},
            )
        devices = get_devices(token)
        device = _pick_device_by_name(devices, normalized_requested)

    if device is None:
        device = _pick_device_by_name(devices, normalized_requested, allow_partial=True)

    if device:
        matched_name = device.get("name", "")
        device_id = device.get("id")
        if not device_id:
            logger.warning(
                "spotify.device.missing_id",
                extra={"requested": device_name, "matched": matched_name},
            )
            return None
        if _normalize_device_name(matched_name) != normalized_requested:
            logger.warning(
                "spotify.device.partial_match",
                extra={"requested": device_name, "matched": matched_name, "device_id": device_id},
            )
        _remember_device_mapping(device_name, matched_name or device_name, device_id)
        return device_id

    cached_entry = _load_cached_device_mapping(device_name)
    if cached_entry:
        cached_id = cached_entry.get("id")
        cached_name = cached_entry.get("name", device_name)
        if cached_id:
            logger.info(
                "spotify.device.cached_id_used",
                extra={"requested": device_name, "cached_name": cached_name, "device_id": cached_id},
            )
            return cached_id

    available_names = [
        d.get("name") for d in devices if isinstance(d.get("name"), str)
    ]
    logger.warning(
        "spotify.device.not_found",
        extra={
            "requested": device_name,
            "available": available_names[:8],
            "total_devices": len(available_names),
        },
    )
    return None

# ▶️ Playback
def _start_playback_on_device(
    token: str,
    device_id: str,
    playlist_uri: str,
    volume_percent: int,
    shuffle: bool,
) -> bool:
    """Issue the sequence of Spotify API calls to start playback on a device."""
    logger = logging.getLogger('spotify')
    headers = {"Authorization": f"Bearer {token}"}

    try:
        transfer_resp = _spotify_request(
            'PUT',
            "https://api.spotify.com/v1/me/player",
            json={"device_ids": [device_id], "play": False},
            headers=headers,
            timeout=10,
        )
        if transfer_resp.status_code not in (200, 202, 204):
            logger.warning("⚠️ Transfer playback failed: %s", transfer_resp.text)
    except requests.exceptions.RequestException:
        raise

    try:
        if not set_volume(token, volume_percent, device_id):
            logger.warning("⚠️ Could not preset volume to %s%%", volume_percent)
    except Exception as exc:
        logger.warning("⚠️ Error setting volume: %s", exc)

    payload: Dict[str, Any] = {}
    playlist_uri = playlist_uri.strip()
    if playlist_uri:
        if playlist_uri.startswith("spotify:track:"):
            payload["uris"] = [playlist_uri]
            logger.info("▶️ Starting track playback: %s", playlist_uri)
        else:
            payload["context_uri"] = playlist_uri
            if shuffle:
                try:
                    total = 0
                    if playlist_uri.startswith("spotify:playlist:"):
                        total = _get_track_total_cached(token, playlist_uri, 'playlist')
                    elif playlist_uri.startswith("spotify:album:"):
                        total = _get_track_total_cached(token, playlist_uri, 'album')
                    if total > 1:
                        pos = random.randint(0, total - 1)
                        payload["offset"] = {"position": pos}
                        logger.info("🎲 Randomised offset %s/%s", pos, total)
                except Exception as exc:
                    logger.debug("Shuffle offset calculation failed: %s", exc)
            logger.info("▶️ Starting context playback: %s", playlist_uri)
    else:
        logger.info("▶️ Resuming playback without context URI")

    try:
        play_resp = _spotify_request(
            'PUT',
            f"https://api.spotify.com/v1/me/player/play?device_id={device_id}",
            json=payload if payload else None,
            headers=headers,
            timeout=LONG_HTTP_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        raise

    if play_resp.status_code not in (200, 202, 204):
        logger.warning("❌ Error starting playback: %s", play_resp.text)
        _invalidate_playback_cache()
        return False

    _invalidate_playback_cache()
    return True


def _set_shuffle_state(token: str, state: bool, *, retries: int = SHUFFLE_RETRY_ATTEMPTS, delay: float = SHUFFLE_RETRY_DELAY) -> bool:
    """Attempt to toggle Spotify shuffle state with small retries."""
    logger = logging.getLogger('spotify')
    headers = {"Authorization": f"Bearer {token}"}
    target = "true" if state else "false"

    for attempt in range(1, retries + 1):
        try:
            resp = _spotify_request(
                'PUT',
                "https://api.spotify.com/v1/me/player/shuffle",
                headers=headers,
                params={"state": target},
                timeout=10,
            )
            if resp.status_code == 204:
                if attempt > 1:
                    logger.debug(
                        "shuffle.state.ok_after_retry",
                        extra={"attempt": attempt},
                    )
                return True
            logger.debug(
                "shuffle.state.failed",
                extra={"status": resp.status_code, "attempt": attempt, "body": resp.text[:120]},
            )
        except requests.exceptions.RequestException as exc:
            logger.debug(
                "shuffle.state.error",
                extra={"error": exc.__class__.__name__, "attempt": attempt},
            )
        if attempt < retries:
            time.sleep(delay)
    return False


def _verify_playback_state(
    token: str,
    expected_device_id: str,
    playlist_uri: str,
    attempts: int = PLAYBACK_VERIFY_ATTEMPTS,
    wait_seconds: float = PLAYBACK_VERIFY_WAIT,
) -> bool:
    """Poll the player API to ensure playback is active on the expected device."""
    logger = logging.getLogger('spotify')
    context_uri_expected = playlist_uri if playlist_uri and not playlist_uri.startswith("spotify:track:") else None

    for attempt in range(max(1, attempts)):
        try:
            playback = get_current_playback(token)
        except Exception as exc:
            logger.debug("verify_playback fetch failed: %s", exc)
            playback = None

        if playback:
            device_info = playback.get("device") or {}
            active_device_id = device_info.get("id")
            item = playback.get("item") or {}
            item_uri = item.get("uri")
            is_playing = bool(playback.get("is_playing"))
            progress_ms = playback.get("progress_ms") or 0
            if expected_device_id and active_device_id != expected_device_id:
                logger.debug(
                    "Playback active on unexpected device %s (expected %s)",
                    active_device_id,
                    expected_device_id,
                )
            else:
                matched = False
                if context_uri_expected:
                    context_uri = (playback.get("context") or {}).get("uri")
                    if context_uri and context_uri == context_uri_expected:
                        matched = True
                    elif context_uri:
                        logger.debug("Playback context mismatch (got %s)", context_uri)
                elif playlist_uri.startswith("spotify:track:"):
                    matched = item_uri == playlist_uri
                else:
                    matched = bool(item_uri)

                if matched and (is_playing or progress_ms > 0):
                    return True

        if attempt + 1 < attempts:
            time.sleep(wait_seconds)

    return False


def play_with_retry(
    token: str,
    device_id: str,
    playlist_uri: str = "",
    volume_percent: int = 50,
    shuffle: bool = False,
    *,
    fallback_device: Optional[str] = None,
) -> bool:
    """Start playback with retries, verification, and optional fallback device."""
    logger = logging.getLogger('spotify')

    if not token or not device_id:
        logger.error("❌ Missing token or device_id for playback")
        return False

    fallback_name = fallback_device or FALLBACK_DEVICE_NAME
    targets: List[Tuple[str, bool]] = [(device_id, False)]
    fallback_attempted = False
    total_attempts = 0
    idx = 0

    while idx < len(targets):
        target_device_id, is_fallback = targets[idx]
        idx += 1

        for attempt in range(1, PLAYER_MAX_ATTEMPTS + 1):
            total_attempts += 1

            refreshed = ensure_token_valid()
            if refreshed:
                token = refreshed

            logger.info(
                "alarm.start.attempt",
                extra={
                    "device": target_device_id,
                    "attempt": attempt,
                    "fallback": is_fallback,
                },
            )

            start_time = time.perf_counter()

            try:
                started = _start_playback_on_device(
                    token,
                    target_device_id,
                    playlist_uri,
                    volume_percent,
                    shuffle,
                )
                if not started:
                    raise RuntimeError("playback_start_failed")

                if _verify_playback_state(token, target_device_id, playlist_uri):
                    elapsed = time.perf_counter() - start_time
                    try:
                        if not set_volume(token, volume_percent, target_device_id):
                            logger.debug(
                                "alarm.start.volume_postcheck_failed",
                                extra={"device": target_device_id, "volume": volume_percent},
                            )
                    except Exception as exc:
                        logger.debug(
                            "alarm.start.volume_postcheck_error",
                            extra={"device": target_device_id, "error": str(exc)},
                        )
                    if shuffle:
                        shuffle_ok = _set_shuffle_state(token, True)
                        if not shuffle_ok:
                            logger.debug(
                                "shuffle.state.final_failed",
                                extra={"device": target_device_id},
                            )
                    logger.info(
                        "alarm.start.ok",
                        extra={
                            "attempts": total_attempts,
                            "device": target_device_id,
                            "fallback": is_fallback,
                            "elapsed": round(elapsed, 3),
                        },
                    )
                    return True

                logger.warning(
                    "alarm.start.unverified",
                    extra={
                        "device": target_device_id,
                        "attempt": attempt,
                        "waited_seconds": round(PLAYBACK_VERIFY_ATTEMPTS * PLAYBACK_VERIFY_WAIT, 2),
                    },
                )
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else None
                if status not in (429, 500, 502, 503, 504):
                    raise
                logger.warning(
                    "alarm.start.retry",
                    extra={
                        "device": target_device_id,
                        "attempt": attempt,
                        "status": status,
                    },
                )
            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "alarm.start.retry",
                    extra={
                        "device": target_device_id,
                        "attempt": attempt,
                        "error": exc.__class__.__name__,
                    },
                )
            except Exception as exc:
                logger.warning(
                    "alarm.start.retry",
                    extra={
                        "device": target_device_id,
                        "attempt": attempt,
                        "error": str(exc),
                    },
                )

            delay = _compute_backoff(PLAYER_BACKOFF_BASE, attempt, PLAYER_BACKOFF_JITTER, cap=10.0)
            time.sleep(delay)

        if not fallback_attempted and fallback_name:
            fallback_attempted = True
            try:
                fallback_id = get_device_id(token, fallback_name)
            except Exception as exc:
                logger.warning(
                    "alarm.start.fallback_lookup_failed",
                    extra={"device": fallback_name, "error": str(exc)},
                )
                fallback_id = None

            existing_ids = {d for d, _ in targets}
            if fallback_id and fallback_id not in existing_ids:
                logger.warning(
                    "alarm.start.fallback_activate",
                    extra={"device": fallback_name, "device_id": fallback_id},
                )
                targets.append((fallback_id, True))

    logger.error(
        "alarm.start.fail",
        extra={
            "attempts": total_attempts,
            "device": device_id,
            "fallback": fallback_name,
        },
    )
    return False


def start_playback(
    token: str,
    device_id: str,
    playlist_uri: str = "",
    volume_percent: int = 50,
    shuffle: bool = False,
) -> bool:
    """Backward-compatible wrapper that delegates to play_with_retry."""
    return play_with_retry(
        token,
        device_id,
        playlist_uri=playlist_uri,
        volume_percent=volume_percent,
        shuffle=shuffle,
    )

# --- Track count caching for random offset (playlist/album) ---
@lru_cache(maxsize=256)
def _get_track_total_cached(token: str, uri: str, kind: str) -> int:
    try:
        if kind == 'playlist':
            playlist_id = uri.split(":")[-1]
            meta_resp = _spotify_request(
                'GET',
                f"https://api.spotify.com/v1/playlists/{playlist_id}?fields=tracks.total",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8
            )
        else:
            album_id = uri.split(":")[-1]
            meta_resp = _spotify_request(
                'GET',
                f"https://api.spotify.com/v1/albums/{album_id}?fields=tracks.total",
                headers={"Authorization": f"Bearer {token}"},
                timeout=8
            )
        if meta_resp.status_code == 200:
            return meta_resp.json().get('tracks', {}).get('total', 0)
    except Exception:
        pass
    return 0

def stop_playback(token: str, device_id: Optional[str] = None) -> bool:
    """Stop Spotify playback.
    
    Args:
        token: Spotify access token
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger('spotify')
    try:
        params: Dict[str, Any] = {}
        if device_id:
            params["device_id"] = device_id

        response = _spotify_request(
            'PUT',
            "https://api.spotify.com/v1/me/player/pause",
            headers={"Authorization": f"Bearer {token}"},
            params=params if params else None,
            timeout=DEFAULT_HTTP_TIMEOUT
        )
    except requests.exceptions.RequestException as exc:
        logger.error(
            "spotify.playback.stop.request_error",
            extra={"error": str(exc)},
        )
        if getattr(exc, "response", None) is not None and exc.response.status_code == 401:  # type: ignore[attr-defined]
            invalidate_token_cache()
        return False
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.exception("spotify.playback.stop.unexpected", extra={"error": str(exc)})
        return False
    finally:
        _invalidate_playback_cache()

    if 200 <= response.status_code < 300:
        return True

    if response.status_code == 401:
        invalidate_token_cache()

    logger.warning(
        "spotify.playback.stop.failed status=%s body=%s",
        response.status_code,
        response.text[:200],
    )
    return False

def resume_playback(token: str, device_id: Optional[str] = None) -> bool:
    """Resume/start playback.
    
    Args:
        token: Spotify access token
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger('spotify')
    try:
        params: Dict[str, Any] = {}
        if device_id:
            params["device_id"] = device_id

        response = _spotify_request(
            'PUT',
            "https://api.spotify.com/v1/me/player/play",
            headers={"Authorization": f"Bearer {token}"},
            params=params if params else None,
            timeout=DEFAULT_HTTP_TIMEOUT
        )
    except requests.exceptions.RequestException as exc:
        logger.error(
            "spotify.playback.resume.request_error",
            extra={"error": str(exc)},
        )
        if getattr(exc, "response", None) is not None and exc.response.status_code == 401:  # type: ignore[attr-defined]
            invalidate_token_cache()
        return False
    except Exception as exc:  # pragma: no cover
        logger.exception("spotify.playback.resume.unexpected", extra={"error": str(exc)})
        return False
    finally:
        _invalidate_playback_cache()

    if 200 <= response.status_code < 300:
        return True

    if response.status_code == 401:
        invalidate_token_cache()

    logger.warning(
        "spotify.playback.resume.failed status=%s body=%s",
        response.status_code,
        response.text[:200],
    )
    return False

def toggle_playback(token: str) -> Dict[str, Union[bool, str]]:
    """Toggle between play and pause.
    
    Args:
        token: Spotify access token
        
    Returns:
        Dict[str, Union[bool, str]]: Result dictionary with action and success status
    """
    logger = logging.getLogger('spotify')
    try:
        playback = get_current_playback(token)
    except Exception as exc:
        logger.error("spotify.playback.toggle.status_failed", extra={"error": str(exc)})
        return {"success": False, "error": str(exc)}

    device_id = None
    if playback and isinstance(playback, dict):
        device = playback.get("device")
        if isinstance(device, dict):
            device_id = device.get("id")

    try:
        if playback and playback.get("is_playing", False):
            success = stop_playback(token, device_id=device_id)
            return {"action": "paused", "success": success}
        success = resume_playback(token, device_id=device_id)
        return {"action": "playing", "success": success}
    except Exception as exc:  # pragma: no cover
        logger.exception("spotify.playback.toggle.unexpected", extra={"error": str(exc)})
        return {"success": False, "error": str(exc)}


def toggle_playback_fast(token: str) -> Dict[str, Union[bool, str]]:
    """Fast toggle - tries pause first, then play if that fails.
    Optimized for immediate response without status check.
    
    Args:
        token: Spotify access token
        
    Returns:
        Dict[str, Union[bool, str]]: Result dictionary with action and success status
    """
    return toggle_playback(token)

#  Exportable functions - Updated for new config system
__all__ = [
    "refresh_access_token", 
    "get_playlists", "get_devices", "get_device_id",
    "start_playback", "stop_playback", "resume_playback", "toggle_playback",
    "get_current_playback", "get_current_track", "get_current_spotify_volume", 
    "get_saved_albums", "get_user_saved_tracks", "get_followed_artists", "get_artist_top_tracks",
    "set_volume", "get_playback_status", "get_user_library",
    "load_music_library_parallel"
]

def get_current_spotify_volume(token: str) -> int:
    """Get current Spotify volume.
    
    Args:
        token: Spotify access token
        
    Returns:
        int: Current volume percentage (0-100), defaults to 50
    """
    logger = logging.getLogger('spotify')
    try:
        response = _spotify_request(
            'GET',
            "https://api.spotify.com/v1/me/player",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
    except requests.exceptions.RequestException as exc:
        logger.warning("spotify.volume.request_error", extra={"error": str(exc)})
        if getattr(exc, "response", None) is not None and exc.response.status_code == 401:  # type: ignore[attr-defined]
            invalidate_token_cache()
        return 50
    except Exception as exc:  # pragma: no cover
        logger.exception("spotify.volume.unexpected", extra={"error": str(exc)})
        return 50

    if response.status_code == 200:
        try:
            data = response.json()
            return int(data.get("device", {}).get("volume_percent", 50))
        except (ValueError, TypeError):
            logger.debug("spotify.volume.invalid_payload")
            return 50

    if response.status_code == 401:
        invalidate_token_cache()

    logger.debug(
        "spotify.volume.fallback",
        extra={"status": response.status_code, "body_preview": response.text[:200]},
    )
    return 50

def get_current_playback(token: str, device_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Retrieves the current playback status.
    
    Args:
        token: Spotify access token
        device_id: Optional device ID to query
        
    Returns:
        Optional[Dict[str, Any]]: Playback status JSON or None if no active player
        
    Raises:
        RuntimeError: If API returns an error status
    """
    params = {}
    if device_id:
        params["device_id"] = device_id
        
    try:
        r = _spotify_request(
            'GET',
            "https://api.spotify.com/v1/me/player",
            params=params,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 200:
            return r.json()
        elif r.status_code == 204:
            # 204 No Content - no active player, this is normal
            return None
        else:
            raise RuntimeError(f"Error retrieving playback status: {r.status_code} - {r.text}")
    except requests.exceptions.RequestException as e:
        # Let callers turn this into a 503 so UI can degrade gracefully
        raise RuntimeError(f"Network error retrieving playback status: {e}")

def get_current_track(token: str) -> Optional[Dict[str, Any]]:
    """Get current playing track information for Now Playing display.
    
    Args:
        token: Spotify access token
        
    Returns:
        Optional[Dict[str, Any]]: Track info with name, artist, album, image or None
    """
    try:
        playback = get_current_playback(token)
        if not playback or not playback.get("item"):
            return None
            
        track = playback["item"]
        artists = track.get("artists", [])
        album = track.get("album", {})
        images = album.get("images", [])
        
        return {
            "name": track.get("name"),
            "artist": ", ".join([artist.get("name", "") for artist in artists]),
            "album": album.get("name"),
            "album_image": images[0]["url"] if images else None,
            "is_playing": playback.get("is_playing", False),
            "uri": track.get("uri")
        }
    except Exception as e:
        logging.error(f"Error getting current track: {e}")
        return None

def _playback_cache_ttl() -> float:
    """Get playback cache TTL with adaptive defaults.
    
    Longer TTL on Pi Zero W to reduce API calls - playback state doesn't 
    change frequently when track is playing (only on skip/pause/volume change).
    """
    default_ttl = 5.0 if _LOW_POWER_MODE else 1.5
    ttl_env = os.getenv('SPOTIPI_PLAYBACK_CACHE_TTL', str(default_ttl))
    try:
        ttl = float(ttl_env)
    except (TypeError, ValueError):
        ttl = default_ttl
    return max(0.0, ttl)


def get_combined_playback(token: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """Single-call helper returning playback + simplified track + volume.

    Avoids making three separate requests (status + track + volume) since
    Spotify's /me/player already contains everything needed.
    """
    global _PLAYBACK_CACHE, _PLAYBACK_CACHE_EXPIRY

    ttl = _playback_cache_ttl()
    now = time.time()

    if not force_refresh and ttl > 0 and _PLAYBACK_CACHE and now < _PLAYBACK_CACHE_EXPIRY:
        return copy.deepcopy(_PLAYBACK_CACHE)

    try:
        playback = get_current_playback(token)
        if not playback:
            return None
        item = playback.get("item")
        track = None
        if item:
            album = item.get("album", {})
            images = album.get("images", [])
            artists = item.get("artists", [])
            track = {
                "name": item.get("name"),
                "artist": ", ".join([a.get("name", "") for a in artists]),
                "album": album.get("name"),
                "album_image": images[0]["url"] if images else None,
                "is_playing": playback.get("is_playing", False),
                "uri": item.get("uri")
            }
        volume = int(playback.get("device", {}).get("volume_percent", 50))
        combined = {
            "is_playing": playback.get("is_playing", False),
            "device": playback.get("device"),
            "progress_ms": playback.get("progress_ms"),
            "shuffle_state": playback.get("shuffle_state"),
            "repeat_state": playback.get("repeat_state"),
            "current_track": track,
            "volume": volume
        }
        if ttl > 0:
            _PLAYBACK_CACHE = copy.deepcopy(combined)
            _PLAYBACK_CACHE_EXPIRY = now + ttl
        return combined
    except Exception as e:
        logging.getLogger('spotify').debug(f"Combined playback fetch failed: {e}")
        return None

def load_music_library_parallel(token: str) -> Dict[str, Any]:
    """Load playlists, albums, tracks, and artists in parallel for better performance.
    
    Args:
        token: Spotify access token
        
    Returns:
        Dict[str, Any]: Dictionary containing all music library data
    """
    logger = logging.getLogger('app')  # Use same logger as app.py
    start_time = time.time()
    logger.info("🚀 Starting parallel music library loading...")
    
    def load_with_error_handling(func, name: str) -> List[Dict[str, Any]]:
        """Helper function to load data with error handling.
        
        Args:
            func: Function to call for loading data
            name: Name for logging purposes
            
        Returns:
            List[Dict[str, Any]]: Loaded data or empty list on error
        """
        label = name.lower().replace(' ', '_')
        try:
            with perf_monitor.time_block(f"spotify.library.{label}"):
                result = func(token)
            logger.info(f"✅ {name} loaded: {len(result)} items")
            return result
        except Exception as e:
            logger.error(f"❌ Error loading {name}: {e}")
            return []
    
    section_funcs = {
        'playlists': (get_playlists, "Playlists"),
        'albums': (get_saved_albums, "Albums"),
        'tracks': (get_user_saved_tracks, "Saved Tracks"),
        'artists': (get_followed_artists, "Followed Artists")
    }
    max_workers = max(1, min(len(section_funcs), _get_library_worker_limit()))

    if max_workers == 1:
        results = {
            name: load_with_error_handling(func, label)
            for name, (func, label) in section_funcs.items()
        }
    else:
        # Use timeout to prevent indefinite blocking on Pi Zero W with poor network
        timeout_seconds = float(os.getenv('SPOTIPI_LIBRARY_LOAD_TIMEOUT', '20.0'))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                name: executor.submit(load_with_error_handling, func, label)
                for name, (func, label) in section_funcs.items()
            }
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result(timeout=timeout_seconds)
                except TimeoutError:
                    logger.error(f"❌ {key} timed out after {timeout_seconds}s, using empty fallback")
                    results[key] = []
                except Exception as e:
                    logger.error(f"❌ {key} failed with error: {e}")
                    results[key] = []
    
    end_time = time.time()
    total_items = sum(len(data) for data in results.values())
    logger.info(f"🎉 Parallel loading completed in {end_time - start_time:.2f} seconds - {total_items} total items")
    
    payload = {
        "playlists": results['playlists'],
        "albums": results['albums'], 
        "tracks": results['tracks'],
        "artists": results['artists'],
        "total": total_items
    }
    payload["hash"] = compute_library_hash(payload)
    return payload

# Additional functions for the new modular app.py

def set_volume(token: str, volume_percent: int, device_id: Optional[str] = None) -> bool:
    """Set Spotify volume.
    
    Args:
        token: Spotify access token
        volume_percent: Volume level (0-100)
        device_id: Optional specific device ID to target
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger = logging.getLogger('spotify')
    try:
        params: Dict[str, Any] = {"volume_percent": int(volume_percent)}
        if device_id:
            params["device_id"] = device_id

        response = _spotify_request(
            'PUT',
            "https://api.spotify.com/v1/me/player/volume",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=10
        )
        
        if response.status_code == 204:
            return True
        logger.warning(
            "spotify.volume.failed",
            extra={
                "status": response.status_code,
                "device_id": device_id,
                "requested_volume": params["volume_percent"],
            },
        )
        if response.status_code == 404 and device_id:
            try:
                cache_migration.invalidate_devices()
            except Exception as exc:
                logger.debug(
                    "spotify.device.cache_invalidate_failed",
                    extra={"error": str(exc)},
                )
        return False
    except Exception as exc:
        logger.warning(
            "spotify.volume.exception",
            extra={"error": str(exc), "device_id": device_id},
        )
        return False

def get_playback_status(token: str) -> Optional[Dict[str, Any]]:
    """Get current playback status.
    
    Args:
        token: Spotify access token
        
    Returns:
        Optional[Dict[str, Any]]: Current playback status or None
    """
    return get_current_playback(token)

def get_user_library(token: str) -> Dict[str, Any]:
    """Get comprehensive user library.
    
    Args:
        token: Spotify access token
        
    Returns:
        Dict[str, Any]: Complete user library data
    """
    return load_music_library_parallel(token)

def spotify_network_health() -> Dict[str, Any]:
    """Basic connectivity diagnostics to Spotify API.

    Returns:
        Dict with ok flag, DNS/IPs, TLS reachability, and error info.
    """
    info: Dict[str, Any] = {
        "ok": False,
        "dns": {},
        "tls": {},
    }

    host = "api.spotify.com"

    # DNS resolution
    try:
        addrs = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        ips = sorted({ai[4][0] for ai in addrs})
        info["dns"] = {"resolved": True, "ips": ips}
    except Exception as e:
        info["dns"] = {"resolved": False, "error": str(e)}

    # TLS reachability (HEAD to a harmless endpoint)
    try:
        with _REQUEST_SEMAPHORE:
            r = SESSION.head(
                "https://api.spotify.com/v1",
                timeout=_coerce_timeout(5)
            )
        info["tls"] = {
            "reachable": True,
            "status": r.status_code,
        }
        info["ok"] = True
    except requests.exceptions.SSLError as e:
        info["tls"] = {"reachable": False, "type": "SSLError", "error": str(e)}
    except requests.exceptions.RequestException as e:
        info["tls"] = {"reachable": False, "type": "RequestException", "error": str(e)}

    return info
