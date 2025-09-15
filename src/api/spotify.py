#!/usr/bin/env python3
"""
🎵 Spotify API Integration for SpotiPi
Provides comprehensive Spotify Web API functionality including:
- Authentication and token management
- Music library access (playlists, albums, tracks, artists)  
- Playback control with device management
- Parallel data loading for performance
"""

import os
import json
import requests
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import time
from functools import lru_cache
import logging
from typing import Dict, List, Optional, Any, Union
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
import socket

# Use the new centralized config system
from ..config import load_config, save_config
# Import token caching system
from ..utils.token_cache import initialize_token_cache, get_cached_token, force_token_refresh
from ..utils.cache_migration import get_cache_migration_layer

# Use the new central#  Exportable functions - Updated for new config system
__all__ = [
    "refresh_access_token", "get_access_token", "force_refresh_token",
    "get_playlists", "get_devices", "get_device_id",
    "start_playback", "stop_playback", "resume_playback", "toggle_playback",
    "get_current_playback", "get_current_track", "get_current_spotify_volume", 
    "get_saved_albums", "get_user_saved_tracks", "get_followed_artists",
    "set_volume", "get_playback_status", "get_user_library", "get_combined_playback",
    "load_music_library_parallel", "spotify_network_health", "load_music_library_sections"
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

# ⏱️ Network timeout configuration
# Increased timeout for better reliability with unstable connections
SPOTIFY_API_TIMEOUT = 30  # seconds

# 🌍 Load environment variables
load_dotenv(dotenv_path=ENV_PATH)
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
USERNAME = os.getenv("SPOTIFY_USERNAME")

# 🔑 Token function
def refresh_access_token() -> Optional[str]:
    """Refresh Spotify access token using refresh token.
    
    Returns:
        Optional[str]: New access token if successful, None otherwise
    """
    # Optional offline short-circuit for tests or restricted environments
    if os.getenv("SPOTIPI_OFFLINE") == "1":
        return None
    try:
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN},
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=SPOTIFY_API_TIMEOUT
        )
        if r.status_code == 200:
            return r.json().get("access_token")
        else:
            logging.getLogger('spotify').error(f"❌ Token refresh failed: {r.text}")
            return None
    except Exception as e:
        logging.getLogger('spotify').exception(f"❌ Exception during token refresh: {e}")
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

# Initialize token cache when module is imported
initialize_token_cache(refresh_access_token)

# Initialize cache migration layer
cache_migration = get_cache_migration_layer()

# =============================
# 🌐 HTTP Session + Circuit Breaker
# =============================

def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=int(os.getenv('SPOTIPI_HTTP_RETRY_TOTAL', '3')),
        backoff_factor=float(os.getenv('SPOTIPI_HTTP_BACKOFF', '0.5')),
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=(
            'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'
        ),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session.mount('https://', adapter)
    session.mount('http://', adapter)
    return session

SESSION = _build_session()

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

def _spotify_request(method: str, url: str, *, headers: Dict[str, str], params: Optional[Dict[str, Any]] = None, json: Optional[Dict[str, Any]] = None, timeout: int = 10) -> requests.Response:
    if _breaker_open():
        raise RuntimeError("Spotify API temporarily unavailable (circuit breaker open)")
    try:
        resp = SESSION.request(method=method, url=url, headers=headers, params=params, json=json, timeout=timeout)
        _breaker_on_success()
        return resp
    except requests.exceptions.RequestException:
        _breaker_on_failure()
        raise

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

def get_device_id(token: str, device_name: str) -> Optional[str]:
    """Get device ID by device name.
    
    Args:
        token: Spotify access token
        device_name: Name of the device to find
        
    Returns:
        Optional[str]: Device ID if found, None otherwise
    """
    devices = get_devices(token)
    for d in devices:
        if d["name"] == device_name:
            return d["id"]
    return None

# ▶️ Playback
def start_playback(token: str, device_id: str, playlist_uri: str = "", volume_percent: int = 50, shuffle: bool = False) -> bool:
    """Start playback on specified device with optional playlist and volume
    
    Args:
        token: Spotify access token
        device_id: Target device ID
        playlist_uri: Optional playlist/album/track URI to play
        volume_percent: Volume level (0-100)
        shuffle: Enable shuffle mode
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not token or not device_id:
        logging.getLogger('spotify').error("❌ Missing token or device_id for playback")
        return False

    try:
        # 1. Transfer playback to device
        transfer_resp = _spotify_request(
            'PUT',
            "https://api.spotify.com/v1/me/player",
            json={"device_ids": [device_id], "play": False},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if transfer_resp.status_code != 204:
            logging.getLogger('spotify').warning(f"⚠️ Could not transfer playback to device: {transfer_resp.text}")

        # 2. Set volume
        try:
            vol_resp = _spotify_request(
                'PUT',
                "https://api.spotify.com/v1/me/player/volume",
                params={"volume_percent": volume_percent},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            if vol_resp.status_code != 204:
                logging.getLogger('spotify').warning(f"⚠️ Could not set volume: {vol_resp.text}")
        except Exception as e:
            logging.getLogger('spotify').exception(f"❌ Error setting volume: {e}")

        # 3. (Optional) Enable shuffle BEFORE starting playback so first track is randomized
        shuffle_enabled_before = False
        if shuffle:
            try:
                shuffle_resp = _spotify_request(
                    'PUT',
                    f"https://api.spotify.com/v1/me/player/shuffle?state=true",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=10
                )
                if shuffle_resp.status_code == 204:
                    logging.getLogger('spotify').info("🔀 Shuffle mode enabled (pre-play)")
                    shuffle_enabled_before = True
                else:
                    logging.getLogger('spotify').warning(f"⚠️ Could not enable shuffle pre-play: {shuffle_resp.text}")
            except Exception as e:
                logging.getLogger('spotify').warning(f"⚠️ Error enabling shuffle pre-play: {e}")

        # 4. Start playback (with optional random offset when shuffle active)
        if playlist_uri and playlist_uri.strip():
            if playlist_uri.startswith("spotify:track:"):
                # For individual tracks, use "uris" parameter
                payload = {"uris": [playlist_uri]}
                logging.getLogger('spotify').info(f"▶️ Starting track playback: {playlist_uri}")
            else:
                # For playlists/albums, use "context_uri" parameter
                payload = {"context_uri": playlist_uri}
                # Randomize first track if shuffle requested: pick random offset
                if shuffle and shuffle_enabled_before:
                    import random
                    try:
                        if playlist_uri.startswith("spotify:playlist:"):
                            total = _get_track_total_cached(token, playlist_uri, 'playlist')
                            if total > 1:
                                pos = random.randint(0, total - 1)
                                payload['offset'] = {"position": pos}
                                logging.getLogger('spotify').info(f"🎲 Starting at random playlist position {pos} of {total}")
                        elif playlist_uri.startswith("spotify:album:"):
                            total = _get_track_total_cached(token, playlist_uri, 'album')
                            if total > 1:
                                pos = random.randint(0, total - 1)
                                payload['offset'] = {"position": pos}
                                logging.getLogger('spotify').info(f"🎲 Starting at random album position {pos} of {total}")
                    except Exception as e:
                        logging.getLogger('spotify').warning(f"⚠️ Could not apply random offset: {e}")
                logging.getLogger('spotify').info(f"▶️ Starting context playback: {playlist_uri}")
        else:
            payload = {}
            logging.getLogger('spotify').info("▶️ Resuming playback with specified volume")
        
        play_resp = _spotify_request(
            'PUT',
            f"https://api.spotify.com/v1/me/player/play?device_id={device_id}",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if play_resp.status_code == 204:
            # Fallback: if shuffle requested but pre-play enable failed, retry once now
            if shuffle and not shuffle_enabled_before:
                try:
                    shuffle_resp = _spotify_request(
                        'PUT',
                        f"https://api.spotify.com/v1/me/player/shuffle?state=true",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10
                    )
                    if shuffle_resp.status_code == 204:
                        logging.getLogger('spotify').info("🔀 Shuffle mode enabled (post-play fallback)")
                    else:
                        logging.getLogger('spotify').warning(f"⚠️ Could not enable shuffle (fallback): {shuffle_resp.text}")
                except Exception as e:
                    logging.getLogger('spotify').warning(f"⚠️ Error enabling shuffle (fallback): {e}")
            return True
        else:
            logging.getLogger('spotify').error(f"❌ Error starting playback: {play_resp.text}")
            return False
            
    except Exception as e:
        logging.getLogger('spotify').error(f"❌ Error in start_playback: {e}")
        return False

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

def stop_playback(token: str) -> bool:
    """Stop Spotify playback.
    
    Args:
        token: Spotify access token
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        r = requests.put(
            "https://api.spotify.com/v1/me/player/pause",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 204:
            return True
        else:
            print("❌ Error stopping playback:", r.text)
            return False
    except Exception as e:
        print(f"❌ Exception stopping playback: {e}")
        return False

def resume_playback(token: str) -> bool:
    """Resume/start playback.
    
    Args:
        token: Spotify access token
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        r = requests.put(
            "https://api.spotify.com/v1/me/player/play",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 204:
            return True
        else:
            print("❌ Error resuming playback:", r.text)
            return False
    except Exception as e:
        print(f"❌ Exception resuming playback: {e}")
        return False

def toggle_playback(token: str) -> Dict[str, Union[bool, str]]:
    """Toggle between play and pause.
    
    Args:
        token: Spotify access token
        
    Returns:
        Dict[str, Union[bool, str]]: Result dictionary with action and success status
    """
    try:
        playback = get_current_playback(token)
        if playback and playback.get("is_playing", False):
            # Currently playing, so pause
            success = stop_playback(token)
            return {"action": "paused", "success": success}
        else:
            # Not playing, so resume/start
            success = resume_playback(token)
            return {"action": "playing", "success": success}
    except Exception as e:
        print(f"❌ Error toggling playback: {e}")
        return {"success": False, "error": str(e)}


def toggle_playback_fast(token: str) -> Dict[str, Union[bool, str]]:
    """Fast toggle - tries pause first, then play if that fails.
    Optimized for immediate response without status check.
    
    Args:
        token: Spotify access token
        
    Returns:
        Dict[str, Union[bool, str]]: Result dictionary with action and success status
    """
    try:
        # Try pause first (most common case when music is playing)
        try:
            pause_resp = _spotify_request(
                'PUT',
                "https://api.spotify.com/v1/me/player/pause",
                headers={"Authorization": f"Bearer {token}"},
                timeout=5
            )
            if pause_resp.status_code == 204:
                return {"action": "paused", "success": True}
            elif pause_resp.status_code == 403:
                # 403 means no active device or already paused - try play
                play_resp = _spotify_request(
                    'PUT',
                    "https://api.spotify.com/v1/me/player/play", 
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5
                )
                if play_resp.status_code == 204:
                    return {"action": "playing", "success": True}
                else:
                    return {"success": False, "error": f"Play failed: {play_resp.status_code}"}
            else:
                return {"success": False, "error": f"Pause failed: {pause_resp.status_code}"}
        except Exception as e:
            # If pause fails, try play
            try:
                play_resp = _spotify_request(
                    'PUT',
                    "https://api.spotify.com/v1/me/player/play",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=5
                )
                if play_resp.status_code == 204:
                    return {"action": "playing", "success": True}
                else:
                    return {"success": False, "error": f"Play fallback failed: {play_resp.status_code}"}
            except Exception as play_error:
                return {"success": False, "error": f"Both pause and play failed: {e}, {play_error}"}
                
    except Exception as e:
        print(f"❌ Error in fast toggle playback: {e}")
        return {"success": False, "error": str(e)}

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
    try:
        r = _spotify_request(
            'GET',
            "https://api.spotify.com/v1/me/player",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            return int(data.get("device", {}).get("volume_percent", 50))
    except Exception as e:
        print(f"⚠️ Could not get current volume: {e}")
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

def get_combined_playback(token: str) -> Optional[Dict[str, Any]]:
    """Single-call helper returning playback + simplified track + volume.

    Avoids making three separate requests (status + track + volume) since
    Spotify's /me/player already contains everything needed.
    """
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
        try:
            result = func(token)
            logger.info(f"✅ {name} loaded: {len(result)} items")
            return result
        except Exception as e:
            logger.error(f"❌ Error loading {name}: {e}")
            return []
    
    # Use ThreadPoolExecutor to load all data in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all tasks
        futures = {
            'playlists': executor.submit(load_with_error_handling, get_playlists, "Playlists"),
            'albums': executor.submit(load_with_error_handling, get_saved_albums, "Albums"),
            'tracks': executor.submit(load_with_error_handling, get_user_saved_tracks, "Saved Tracks"),
            'artists': executor.submit(load_with_error_handling, get_followed_artists, "Followed Artists")
        }
        
        # Collect results
        results = {}
        for key, future in futures.items():
            results[key] = future.result()
    
    end_time = time.time()
    total_items = sum(len(data) for data in results.values())
    logger.info(f"🎉 Parallel loading completed in {end_time - start_time:.2f} seconds - {total_items} total items")
    
    return {
        "playlists": results['playlists'],
        "albums": results['albums'], 
        "tracks": results['tracks'],
        "artists": results['artists'],
        "total": total_items
    }

# ------------------------------
# ⚡ Incremental / Section-based loading with per-section cache
# ------------------------------

# In-process cache for individual sections to accelerate partial requests.
_LIB_SECTION_CACHE: Dict[str, Dict[str, Any]] = {}

def _get_section_cache(name: str) -> Dict[str, Any]:
    if name not in _LIB_SECTION_CACHE:
        _LIB_SECTION_CACHE[name] = {"ts": 0.0, "data": []}
    return _LIB_SECTION_CACHE[name]

def load_music_library_sections(token: str, sections: List[str], force_refresh: bool = False) -> Dict[str, Any]:
    """Load only the requested music library sections with caching.

    Args:
        token: Spotify access token
        sections: List of section names to load (playlists, albums, tracks, artists)
        force_refresh: Bypass cache when True

    Returns:
        Dict[str, Any]: Partial library containing only requested sections (others empty)
    """
    valid_sections = {"playlists", "albums", "tracks", "artists"}
    wanted = [s for s in sections if s in valid_sections]
    if not wanted:
        wanted = ["playlists"]  # sensible default

    ttl = int(os.getenv('SPOTIPI_LIBRARY_SECTION_TTL', '600'))
    now = time.time()

    # Mapping from section name to loader function
    loaders = {
        "playlists": get_playlists,
        "albums": get_saved_albums,
        "tracks": get_user_saved_tracks,
        "artists": get_followed_artists,
    }

    results: Dict[str, List[Dict[str, Any]]] = {s: [] for s in valid_sections}

    def load_if_needed(name: str):
        cache = _get_section_cache(name)
        if (not force_refresh) and cache['data'] and (now - cache['ts'] < ttl):
            return cache['data']
        try:
            data = loaders[name](token)
            cache['data'] = data
            cache['ts'] = now
            return data
        except Exception as e:
            logging.getLogger('app').warning(f"⚠️ Failed loading section {name}: {e}")
            return cache['data'] or []

    # Load requested sections (in parallel to retain performance)
    with ThreadPoolExecutor(max_workers=min(len(wanted), 4)) as executor:
        future_map = {sec: executor.submit(load_if_needed, sec) for sec in wanted}
        for sec, fut in future_map.items():
            results[sec] = fut.result()

    # Compose partial result with total count for only loaded sections
    total_loaded = sum(len(results[s]) for s in wanted)

    return {
        "playlists": results["playlists"],
        "albums": results["albums"],
        "tracks": results["tracks"],
        "artists": results["artists"],
        "total": total_loaded,
        "partial": True,
        "sections": wanted,
        "cached": {s: (now - _get_section_cache(s)['ts'] < ttl) for s in wanted}
    }

# Additional functions for the new modular app.py

def set_volume(token: str, volume_percent: int) -> bool:
    """Set Spotify volume.
    
    Args:
        token: Spotify access token
        volume_percent: Volume level (0-100)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        response = requests.put(
            f"https://api.spotify.com/v1/me/player/volume?volume_percent={volume_percent}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if response.status_code == 204:
            return True
        else:
            print(f"Error setting volume: {response.status_code}")
            return False
    except Exception as e:
        print(f"Error setting volume: {str(e)}")
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
        r = requests.head(
            "https://api.spotify.com/v1",
            timeout=5,
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
