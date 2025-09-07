#!/usr/bin/env python3
"""
🚨 Alarm Execution Logic for SpotiPi
Handles alarm triggering, weekday scheduling, and playback management with:
- Precise time-based triggering
- Weekday scheduling support  
- Volume fade-in functionality
- Automatic alarm disable after triggering
- Comprehensive error handling and logging
"""

import os
import datetime
import time
import requests
from typing import Optional, List, Dict, Any

from ..api.spotify import (
    get_access_token,
    get_device_id,
    start_playback
)
from ..config import load_config, save_config
from ..utils.logger import setup_logger
from ..utils.thread_safety import config_transaction

# Get logger for alarm module
logger = setup_logger(__name__)

def log(message: str) -> None:
    """Log message using centralized logger.
    
    Args:
        message: Message to log
    """
    logger.info(message)

def is_weekday_enabled(config: Dict[str, Any], current_weekday: int) -> bool:
    """Check if alarm should trigger for current weekday.
    
    Args:
        config: Alarm configuration dictionary
        current_weekday: Current weekday (0=Monday, 6=Sunday)
    
    Returns:
        bool: True if alarm should trigger today, False otherwise
    """
    weekdays = config.get("weekdays", [])
    
    # If no specific weekdays set, alarm triggers daily
    if not weekdays:
        return True
    
    # Check if current weekday is in enabled list
    return current_weekday in weekdays

def execute_alarm() -> None:
    """Main alarm execution function with comprehensive error handling."""
    # ✅ CHECK FIRST, THEN LOG - saves 99% of SD access
    now = datetime.datetime.now()
    
    try:
        config = load_config()
    except Exception as e:
        logger.error(f"❌ Failed to load config: {e}")
        return

    # 🔇 Silent exit if alarm is disabled – NO LOGS!
    if not config:
        return

    if not config.get("enabled", False):
        return

    # Check weekday scheduling
    current_weekday = now.weekday()  # 0=Monday, 6=Sunday
    if not is_weekday_enabled(config, current_weekday):
        return

    # ✅ From here on, log only if alarm is ACTIVE
    log("🚀 SpotiPi Wakeup started")
    log(f"👤 User: {os.getenv('USER', 'Unknown')}")
    log(f"🏠 Home directory (expanduser): {os.path.expanduser('~')}")
    log("📁 Using centralized config system")

    now_str = now.strftime("%H:%M")
    log(f"⏰ Current time: {now_str}")
    log(f"📅 Current weekday: {current_weekday} (0=Mon, 6=Sun)")
    log(f"📄 Loaded config: {config}")

    # 🎯 Time check
    try:
        target_time = datetime.datetime.strptime(config["time"], "%H:%M")
    except (ValueError, KeyError) as e:
        log(f"❌ Invalid time format in config: {config.get('time')} - {e}")
        return

    target_today = now.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0
    )
    diff_minutes = (now - target_today).total_seconds() / 60

    log(f"🎯 Target time: {config['time']}")
    log(f"📏 Time difference: {diff_minutes:.2f} minutes")

    if abs(diff_minutes) > 1.5:
        log("⏳ Not time yet.")
        return

    # ▶️ Start playback
    try:
        token = get_access_token()
        if not token:
            log("❌ Failed to retrieve token.")
            return

        device_name = config.get("device_name", "")
        if not device_name:
            log("❌ No device name configured.")
            return

        device_id = get_device_id(token, device_name)
        if not device_id:
            log(f"❌ Device '{device_name}' not found.")
            return

        # 🎚️ Target volume and Fade-In
        # Use alarm_volume if available, otherwise fallback to volume
        target_volume = config.get("alarm_volume", config.get("volume", 50))
        fade_in = config.get("fade_in", False)
        log(f"🎚️ Alarm volume: {target_volume}%, Fade-In: {fade_in}")

        if not fade_in:
            # Direct start with saved alarm volume
            start_playback(
                token,
                device_id,
                config.get("playlist_uri", ""),
                volume_percent=target_volume
            )
            log(f"▶️ Playback started directly with {target_volume}% alarm volume")
        else:
            # Gentle start at 5%, then ramp fade-in to saved alarm volume
            start_playback(
                token,
                device_id,
                config.get("playlist_uri", ""),
                volume_percent=5
            )
            log("▶️ Playback started at 5% volume (Fade-In to alarm volume)")
            
            # Fade-in with better error handling
            try:
                for v in range(10, target_volume + 1, 5):
                    time.sleep(5)
                    r = requests.put(
                        "https://api.spotify.com/v1/me/player/volume",
                        params={"volume_percent": v},
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10
                    )
                    if r.status_code == 204:
                        log(f"🎚️ Volume increased to {v}%")
                    else:
                        log(f"⚠️ Volume set to {v}% - Status: {r.status_code}")
            except requests.exceptions.RequestException as e:
                log(f"❌ Network error during fade-in: {e}")
            except Exception as e:
                log(f"❌ Error during fade-in: {e}")

        # After successful playback:
        log("✅ Playback started.")

        # 🔄 Automatically disable alarm after triggering (THREAD-SAFE)
        try:
            with config_transaction() as transaction:
                current_config = transaction.load()
                current_config["enabled"] = False
                transaction.save(current_config)
            log("🔄 Alarm automatically disabled after triggering (thread-safe)")
        except Exception as e:
            log(f"❌ Error disabling the alarm: {e}")

    except Exception as e:
        log(f"❌ Unexpected error during alarm execution: {e}")
        logger.exception("Full traceback for alarm error:")

        log("🏁 Alarm execution finished")

if __name__ == "__main__":
    execute_alarm()

def get_weekday_name(weekday: int) -> str:
    """Get weekday name from number.
    
    Args:
        weekday: Weekday number (0=Monday, 6=Sunday)
        
    Returns:
        str: Human-readable weekday name
    """
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return weekdays[weekday] if 0 <= weekday <= 6 else "Unknown"

def validate_alarm_config(config: Dict[str, Any]) -> bool:
    """Validate alarm configuration completeness.
    
    Args:
        config: Alarm configuration dictionary
        
    Returns:
        bool: True if configuration is valid, False otherwise
    """
    required_fields = ["time", "device_name"]
    
    for field in required_fields:
        if not config.get(field):
            logger.warning(f"⚠️ Missing required alarm config field: {field}")
            return False
    
    # Validate time format
    try:
        datetime.datetime.strptime(config["time"], "%H:%M")
    except (ValueError, TypeError):
        logger.warning(f"⚠️ Invalid time format: {config.get('time')}")
        return False
    
    return True

if __name__ == "__main__":
    execute_alarm()