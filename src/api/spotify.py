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
import logging
from typing import Dict, List, Optional, Any, Union

# Use the new centralized config system
from ..config import load_config, save_config
# Import token caching system
from ..utils.token_cache import initialize_token_cache, get_cached_token, force_token_refresh

# Use the new central#  Exportable functions - Updated for new config system
__all__ = [
    "refresh_access_token", "get_access_token", "force_refresh_token",
    "get_playlists", "get_devices", "get_device_id",
    "start_playback", "stop_playback", "resume_playback", "toggle_playback",
    "get_current_playback", "get_current_track", "get_current_spotify_volume", 
    "get_saved_albums", "get_user_saved_tracks", "get_followed_artists",
    "set_volume", "get_playback_status", "get_user_library",
    "load_music_library_parallel"
]

# 🔧 File paths
ENV_PATH = os.path.expanduser("~/.spotify_wakeup/.env")

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
    try:
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "refresh_token", "refresh_token": REFRESH_TOKEN},
            auth=(CLIENT_ID, CLIENT_SECRET),
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get("access_token")
        else:
            print("❌ Token refresh failed:", r.text)
            return None
    except Exception as e:
        print("❌ Exception during token refresh:", e)
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
    url = "https://api.spotify.com/v1/me/playlists?limit=50"
    headers = {"Authorization": f"Bearer {token}"}
    
    while url:
        try:
            r = requests.get(url, headers=headers, timeout=10)
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
    url = "https://api.spotify.com/v1/me/albums?limit=50"
    headers = {"Authorization": f"Bearer {token}"}
    
    while url:
        try:
            r = requests.get(url, headers=headers, timeout=10)
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
            r = requests.get(url, headers=headers, timeout=10)
            
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
            r = requests.get(url, headers=headers, timeout=10)
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
    """Get available Spotify devices.
    
    Args:
        token: Spotify access token
        
    Returns:
        List[Dict[str, Any]]: List of available devices
    """
    try:
        r = requests.get(
            "https://api.spotify.com/v1/me/player/devices",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if r.status_code == 200:
            return r.json().get("devices", [])
        else:
            print("❌ Error fetching devices:", r.text)
            return []
    except Exception as e:
        print("❌ Exception while fetching devices:", e)
        return []

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
def start_playback(token: str, device_id: str, playlist_uri: str = "", volume_percent: int = 50) -> None:
    """Start Spotify playback with specified parameters.
    
    Args:
        token: Spotify access token
        device_id: Target device ID
        playlist_uri: Playlist URI to play (optional)
        volume_percent: Volume level (0-100)
    """
    logger = logging.getLogger('app')
    
    # 1. Load configuration using centralized config system
    config = load_config()

    # 2. Set shuffle only when needed with detailed message
    shuffle_state = config.get("shuffle", False)
    logger.info(f"🔀 Shuffle mode: {'enabled' if shuffle_state else 'disabled'}")
    
    try:
        shuffle_resp = requests.put(
            "https://api.spotify.com/v1/me/player/shuffle",
            params={"state": shuffle_state, "device_id": device_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        # ✅ Status 200 and 204 as success
        if shuffle_resp.status_code in [200, 204]: 
            if shuffle_state:
                logger.info("✅ Shuffle successfully enabled")
            else:
                logger.info("✅ Shuffle successfully disabled")
        else:
            action = "enable" if shuffle_state else "disable"
            logger.warning(f"⚠️ Could not {action} shuffle: Status {shuffle_resp.status_code}")
            if shuffle_resp.text:
                logger.warning(f"   API response: {shuffle_resp.text}")
    except Exception as e:
        action = "enable" if shuffle_state else "disable"
        logger.error(f"❌ Error {action}ing shuffle: {e}")

    # 3. Set volume
    try:
        vol_resp = requests.put(
            "https://api.spotify.com/v1/me/player/volume",
            params={"volume_percent": volume_percent, "device_id": device_id},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if vol_resp.status_code != 204:
            logger.warning(f"⚠️ Could not set volume: {vol_resp.text}")
    except Exception as e:
        logger.error(f"❌ Error setting volume: {e}")

    # 4. Start playback
    # If playlist_uri is empty, just resume without context (continues last music)
    if playlist_uri and playlist_uri.strip():
        payload = {"context_uri": playlist_uri}
        logger.info(f"▶️ Starting playback with playlist: {playlist_uri}")
    else:
        payload = {}
        logger.info("▶️ Playback started directly with alarm volume")
    
    try:
        play_resp = requests.put(
            f"https://api.spotify.com/v1/me/player/play?device_id={device_id}",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        if play_resp.status_code != 204:
            logger.error(f"❌ Error starting playbook: {play_resp.text}")
    except Exception as e:
        logger.error(f"❌ Error starting playback: {e}")

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

#  Exportable functions - Updated for new config system
__all__ = [
    "refresh_access_token", 
    "get_playlists", "get_devices", "get_device_id",
    "start_playback", "stop_playback", "resume_playback", "toggle_playback",
    "get_current_playback", "get_current_track", "get_current_spotify_volume", 
    "get_saved_albums", "get_user_saved_tracks", "get_followed_artists",
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
        r = requests.get(
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
        r = requests.get(
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