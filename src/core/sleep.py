#!/usr/bin/env python3
"""
😴 Sleep Timer Module for SpotiPi
Provides comprehensive sleep timer functionality including:
- Timer management with persistent status tracking
- Automatic music playback and stopping
- Background monitoring with graceful shutdown
- Configuration persistence and device management
- Spotify integration for seamless sleep music experience
"""

import os
import time
import json
import logging
from threading import Thread
from typing import Dict, Any, Optional, Union
import requests

# Import from new modular structure
from ..api.spotify import (
    refresh_access_token,
    get_devices,
    start_playback,
    set_volume
)
from ..config import load_config, save_config

# Paths for status and log files - Path-agnostic
def _get_app_data_dir():
    """Get application data directory path-agnostically"""
    app_name = os.getenv("SPOTIPI_APP_NAME", "spotipi")
    return os.path.expanduser(f"~/.{app_name}")

LOG_DIR = _get_app_data_dir()
STATUS_PATH = os.path.join(LOG_DIR, "sleep_status.json")

# Ensure log directory exists
os.makedirs(LOG_DIR, exist_ok=True)

# Setup logger for sleep module
logger = logging.getLogger('sleep')

def get_sleep_status() -> Dict[str, Any]:
    """Get current sleep timer status.
    
    Returns:
        Dict[str, Any]: Sleep timer status with remaining time and activity state
    """
    try:
        if os.path.exists(STATUS_PATH):
            with open(STATUS_PATH, "r", encoding='utf-8') as f:
                data = json.load(f)
                if data.get("active", False):
                    end_time = data.get("end", 0)
                    remaining = int(end_time - time.time())
                    return {
                        "active": True,
                        "remaining_seconds": remaining,
                        "remaining_minutes": remaining // 60,
                        "end_time": end_time
                    }
        return {"active": False}
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
        logger.warning(f"Error reading sleep status: {e}")
        return {"active": False}
    except Exception as e:
        logger.exception("Unexpected error getting sleep status")
        return {"active": False}

def start_sleep_timer(duration_minutes: int, playlist_uri: str = "", device_name: str = "", volume: int = 30, shuffle: bool = False) -> bool:
    """Start sleep timer with music playback.
    
    Args:
        duration_minutes: Timer duration in minutes
        playlist_uri: Spotify playlist URI for sleep music (optional)
        device_name: Target Spotify device name (optional)
        volume: Playback volume level 0-100 (default: 30)
        
    Returns:
        bool: True if timer started successfully, False otherwise
    """
    print(f"🔥 DEBUG: start_sleep_timer called with {duration_minutes} minutes")
    try:
        if duration_minutes <= 0:
            print("🔥 DEBUG: Invalid duration for sleep timer")
            logger.warning("Invalid duration for sleep timer")
            return False
            
        end_timestamp = time.time() + duration_minutes * 60
        print(f"🔥 DEBUG: End timestamp calculated: {end_timestamp}")
        
        # Save sleep status
        sleep_data = {
            "active": True, 
            "end": end_timestamp,
            "duration_minutes": duration_minutes,
            "playlist_uri": playlist_uri,
            "device_name": device_name,
            "volume": volume
        }
        
        print(f"🔥 DEBUG: Saving sleep status to {STATUS_PATH}")
        with open(STATUS_PATH, "w", encoding='utf-8') as f:
            json.dump(sleep_data, f, indent=2)
        print("🔥 DEBUG: Sleep status saved successfully")
        
        print("🔥 DEBUG: About to log timer started message")
        logger.info(f"🕒 Sleep timer started for {duration_minutes} minutes")
        print("🔥 DEBUG: Timer started message logged")
        
        # Start music playback if specified
        if playlist_uri and device_name:
            print(f"🔥 DEBUG: Starting sleep music: {playlist_uri} on {device_name}, shuffle: {shuffle}")
            success = _start_sleep_music(playlist_uri, device_name, volume, shuffle)
            if not success:
                print("🔥 DEBUG: Failed to start sleep music")
                logger.warning("Failed to start sleep music, but timer is still active")
        else:
            print("🔥 DEBUG: No music playback requested")
        
        # Start monitoring thread
        print("🔥 DEBUG: About to create monitor thread")
        monitor_thread = Thread(target=_monitor_sleep_timer, daemon=True)
        print("🔥 DEBUG: Monitor thread created, about to start")
        monitor_thread.start()
        print("🔥 DEBUG: Monitor thread started successfully")
        
        print("🔥 DEBUG: About to log monitoring thread started message")
        logger.info(f"😴 Sleep timer started: {duration_minutes} minutes, monitoring thread started")
        print("🔥 DEBUG: All done, returning True")
        
        return True
        
    except Exception as e:
        print(f"🔥 DEBUG: Exception in start_sleep_timer: {e}")
        logger.exception("Error starting sleep timer")
        return False

def stop_sleep_timer() -> bool:
    """Stop active sleep timer.
    
    Returns:
        bool: True if stopped successfully, False otherwise
    """
    try:
        with open(STATUS_PATH, "w", encoding='utf-8') as f:
            json.dump({"active": False}, f, indent=2)
        
        logger.info("🛑 Sleep timer stopped")
        return True
        
    except Exception as e:
        logger.exception("Error stopping sleep timer")
        return False

def _start_sleep_music(playlist_uri: str, device_name: str, volume: int, shuffle: bool = False) -> bool:
    """Start sleep music playback.
    
    Args:
        playlist_uri: Spotify playlist URI
        device_name: Target device name
        volume: Playback volume (0-100)
        shuffle: Enable shuffle mode
        
    Returns:
        bool: True if playback started successfully
    """
    try:
        token = refresh_access_token()
        if not token:
            logger.warning("Failed to get Spotify token for sleep music")
            return False
            
        # Get device ID
        devices = get_devices(token)
        device_id = None
        for device in devices:
            if device.get('name') == device_name:
                device_id = device.get('id')
                break
        
        if not device_id:
            logger.warning(f"Device '{device_name}' not found for sleep music")
            return False
        
        # Start playback
        start_playback(token, device_id, playlist_uri, volume_percent=volume, shuffle=shuffle)
        logger.info(f"🎵 Started sleep music: {playlist_uri} on {device_name} at {volume}% volume, shuffle: {shuffle}")
        return True
        
    except Exception as e:
        logger.exception("Error starting sleep music")
        return False

def _monitor_sleep_timer() -> None:
    """Background thread to monitor sleep timer.
    
    Monitors the sleep timer and automatically stops music when expired.
    Runs in a daemon thread with regular status checks.
    """
    print("🔥 DEBUG MONITOR: _monitor_sleep_timer function started!")
    logger.info("😴 Sleep timer monitor thread started")
    try:
        while True:
            print("🔥 DEBUG MONITOR: Starting while loop iteration")
            status = get_sleep_status()
            print(f"🔥 DEBUG MONITOR: Got status: {status}")
            
            if not status.get("active", False):
                print("🔥 DEBUG MONITOR: Timer not active, exiting")
                logger.info("😴 Sleep timer monitor: timer not active, exiting")
                break
                
            remaining = status.get("remaining_seconds", 0)
            print(f"🔥 DEBUG MONITOR: {remaining} seconds remaining")
            logger.debug(f"😴 Sleep timer monitor: {remaining} seconds remaining")
            
            if remaining <= 0:
                # Timer expired - stop music
                print("🔥 DEBUG MONITOR: Timer expired! Stopping music...")
                logger.info("😴 Timer expired! Stopping music...")
                _stop_sleep_music()
                stop_sleep_timer()
                logger.info("😴 Sleep timer expired - stopping music")
                print("🔥 DEBUG MONITOR: Music stopped, breaking")
                break
            
            # Log remaining time every 5 minutes (300 seconds)
            if remaining % 300 == 0 and remaining > 0:
                minutes_left = remaining // 60
                logger.info(f"😴 Sleep timer: {minutes_left} minutes remaining")
            
            # Check every 30 seconds
            print("🔥 DEBUG MONITOR: Sleeping for 30 seconds")
            time.sleep(30)
            print("🔥 DEBUG MONITOR: Woke up from sleep")
            
    except Exception as e:
        print(f"🔥 DEBUG MONITOR: Exception in monitor: {e}")
        logger.exception("Error in sleep timer monitor")
    finally:
        print("🔥 DEBUG MONITOR: Monitor thread exiting")
        logger.info("😴 Sleep timer monitor thread exiting")

def _stop_sleep_music() -> bool:
    """Stop Spotify playback for sleep timer.
    
    Returns:
        bool: True if music stopped successfully
    """
    try:
        token = refresh_access_token()
        if not token:
            logger.warning("Failed to get token for stopping sleep music")
            return False
            
        # Try to pause playback
        response = requests.put(
            "https://api.spotify.com/v1/me/player/pause",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10
        )
        
        if response.status_code == 204:
            logger.info("🎵 Sleep music stopped successfully")
            return True
        else:
            logger.warning(f"Failed to stop sleep music: HTTP {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error stopping sleep music: {e}")
        return False
    except Exception as e:
        logger.exception("Unexpected error stopping sleep music")
        return False

def save_sleep_settings(settings: Dict[str, Any]) -> bool:
    """Save sleep timer settings to configuration.
    
    Args:
        settings: Dictionary containing sleep settings (volume, duration, playlist_uri, device_name)
        
    Returns:
        bool: True if settings saved successfully, False otherwise
    """
    try:
        if not isinstance(settings, dict):
            logger.warning("Invalid settings format for sleep timer")
            return False
            
        config = load_config()
        
        # Validate and set sleep settings with defaults
        config.update({
            "sleep_volume": max(0, min(100, settings.get("volume", 30))),  # Clamp to 0-100
            "sleep_default_duration": max(1, settings.get("duration", 30)),  # At least 1 minute
            "sleep_playlist_uri": settings.get("playlist_uri", ""),
            "sleep_device_name": settings.get("device_name", "")
        })
        
        success = save_config(config)
        if success:
            logger.info("💾 Sleep settings saved successfully")
        return success
        
    except Exception as e:
        logger.exception("Error saving sleep settings")
        return False

def get_sleep_settings() -> Dict[str, Any]:
    """Get current sleep timer settings from configuration.
    
    Returns:
        Dict[str, Any]: Sleep settings with defaults
    """
    try:
        config = load_config()
        return {
            "volume": config.get("sleep_volume", 30),
            "duration": config.get("sleep_default_duration", 30),
            "playlist_uri": config.get("sleep_playlist_uri", ""),
            "device_name": config.get("sleep_device_name", "")
        }
    except Exception as e:
        logger.exception("Error loading sleep settings")
        return {
            "volume": 30,
            "duration": 30,
            "playlist_uri": "",
            "device_name": ""
        }

def format_sleep_time_remaining(remaining_seconds: int) -> str:
    """Format remaining sleep time for display.
    
    Args:
        remaining_seconds: Seconds remaining on timer
        
    Returns:
        str: Formatted time string (e.g., "25m 30s", "1h 15m")
    """
    if remaining_seconds <= 0:
        return "Timer expired"
    
    hours = remaining_seconds // 3600
    minutes = (remaining_seconds % 3600) // 60
    seconds = remaining_seconds % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"
