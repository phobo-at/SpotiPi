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
from ..constants import ALARM_TRIGGER_WINDOW_MINUTES
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

def execute_alarm() -> bool:
    """Main alarm execution function.

    Returns:
        bool: True if playback was started, False otherwise
    """
    now = datetime.datetime.now()

    try:
        config = load_config()
    except Exception as e:
        logger.error(f"❌ Failed to load config: {e}")
        return False

    # Helper for conditional debug logging (only when config.debug True)
    def debug(reason: str):
        try:
            if config and config.get("debug"):
                logger.info(f"[ALARM DEBUG] {reason}")
        except Exception:
            pass

    if not config:
        debug("Config is empty or could not be loaded")
        return False

    if not config.get("enabled", False):
        debug("Alarm not enabled -> skip")
        return False

    current_weekday = now.weekday()  # 0=Mon, 6=Sun
    if not is_weekday_enabled(config, current_weekday):
        debug(f"Weekday {current_weekday} not enabled (weekdays={config.get('weekdays')})")
        return False

    # From here on we log normal info
    log("🚀 SpotiPi Wakeup started")
    log(f"👤 User: {os.getenv('USER', 'Unknown')}")
    log(f"🏠 Home directory (expanduser): {os.path.expanduser('~')}")
    log("📁 Using centralized config system")

    now_str = now.strftime("%H:%M")
    log(f"⏰ Current time: {now_str}")
    log(f"📅 Current weekday: {current_weekday} (0=Mon, 6=Sun)")
    # Log only key fields to reduce noise
    safe_cfg = {k: config.get(k) for k in ["enabled", "time", "weekdays", "device_name", "playlist_uri", "alarm_volume", "fade_in", "shuffle"]}
    log(f"📄 Loaded config (sanitized): {safe_cfg}")

    # Time check
    try:
        target_time = datetime.datetime.strptime(config["time"], "%H:%M")
    except (ValueError, KeyError) as e:
        log(f"❌ Invalid time format in config: {config.get('time')} - {e}")
        return False

    target_today = now.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0
    )
    diff_minutes = (now - target_today).total_seconds() / 60

    log(f"🎯 Target time: {config['time']}")
    log(f"📏 Time difference: {diff_minutes:.2f} minutes")

    if abs(diff_minutes) > ALARM_TRIGGER_WINDOW_MINUTES:
        debug(f"Not within trigger window (±1.5m). diff={diff_minutes:.2f}m")
        return False

    # Start playback
    try:
        token = get_access_token()
        if not token:
            log("❌ Failed to retrieve token.")
            return False

        device_name = config.get("device_name", "")
        if not device_name:
            log("❌ No device name configured.")
            return False

        device_id = get_device_id(token, device_name)
        if not device_id:
            log(f"❌ Device '{device_name}' not found.")
            return False

        target_volume = config.get("alarm_volume", 50)
        fade_in = config.get("fade_in", False)
        shuffle = config.get("shuffle", False)
        log(f"🎚️ Alarm volume: {target_volume}%, Fade-In: {fade_in}, Shuffle: {shuffle}")

        if not config.get("playlist_uri"):
            debug("No playlist_uri configured; playback may fail")

        if not fade_in:
            start_playback(
                token,
                device_id,
                config.get("playlist_uri", ""),
                volume_percent=target_volume,
                shuffle=shuffle
            )
            log(f"▶️ Playback started directly with {target_volume}% alarm volume")
        else:
            start_playback(
                token,
                device_id,
                config.get("playlist_uri", ""),
                volume_percent=5,
                shuffle=shuffle
            )
            log("▶️ Playback started at 5% volume (Fade-In to alarm volume)")
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

        log("✅ Playback started.")

        # Auto-disable alarm
        try:
            with config_transaction() as transaction:
                current_config = transaction.load()
                current_config["enabled"] = False
                transaction.save(current_config)
            log("🔄 Alarm automatically disabled after triggering (thread-safe)")
        except Exception as e:
            log(f"❌ Error disabling the alarm: {e}")

        return True

    except Exception as e:
        log(f"❌ Unexpected error during alarm execution: {e}")
        logger.exception("Full traceback for alarm error:")
        return False
    finally:
        debug("Alarm evaluation finished")


def get_weekday_name(weekday: int) -> str:
    """Get weekday name from number.
    
    Args:
        weekday: Weekday number (0=Monday, 6=Sunday)
        
    Returns:
        str: Human-readable weekday name
    """
    weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return weekdays[weekday] if 0 <= weekday <= 6 else "Unknown"

## Removed legacy validate_alarm_config (duplicated by utils.validation.validate_alarm_config)