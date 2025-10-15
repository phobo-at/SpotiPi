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
from typing import Any, Dict, List, Optional

from ..api.spotify import get_access_token, get_device_id, start_playback, set_volume
from ..constants import ALARM_TRIGGER_WINDOW_MINUTES
from ..config import load_config, save_config
from ..utils.logger import setup_logger
from ..utils.thread_safety import config_transaction
from ..utils.timezone import get_local_timezone

# Get logger for alarm module
logger = setup_logger(__name__)
LOCAL_TZ = get_local_timezone()

def log(message: str) -> None:
    """Log message using centralized logger.
    
    Args:
        message: Message to log
    """
    logger.info(message)

def execute_alarm(*, force: bool = False) -> bool:
    """Main alarm execution function.

    Args:
        force: Skip enable/time window guards (used for manual triggers).

    Returns:
        bool: True if playback was started, False otherwise
    """
    now = datetime.datetime.now(tz=LOCAL_TZ)

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

    if not config.get("enabled", False) and not force:
        debug("Alarm not enabled -> skip")
        return False

    # From here on we log normal info
    log("🚀 SpotiPi Wakeup started")
    log(f"👤 User: {os.getenv('USER', 'Unknown')}")
    log(f"🏠 Home directory (expanduser): {os.path.expanduser('~')}")
    log("📁 Using centralized config system")

    now_str = now.strftime("%H:%M")
    log(f"⏰ Current time: {now_str}")
    # Log only key fields to reduce noise
    safe_cfg = {
        k: config.get(k)
        for k in ["enabled", "time", "device_name", "playlist_uri", "alarm_volume", "fade_in", "shuffle"]
    }
    safe_cfg["has_cached_device"] = bool(config.get("last_known_devices"))
    log(f"📄 Loaded config (sanitized): {safe_cfg}")

    # Time check
    try:
        time_str = config["time"]
        target_time = datetime.datetime.strptime(time_str, "%H:%M")
    except (ValueError, KeyError) as e:
        if not force:
            logger.error(f"❌ Invalid time format in config: {config.get('time')} - {e}")
            return False
        debug(f"Invalid or missing time '{config.get('time')}' – forcing execution anyway")
        target_time = now

    target_today = now.replace(
        hour=target_time.hour,
        minute=target_time.minute,
        second=0,
        microsecond=0
    )
    diff_minutes = (now - target_today).total_seconds() / 60

    log(f"🎯 Target time: {config.get('time', 'unset')}")
    log(f"📏 Time difference: {diff_minutes:.2f} minutes")

    if diff_minutes < 0 and not force:
        debug(f"Not yet within trigger window. diff={diff_minutes:.2f}m")
        return False

    if diff_minutes > ALARM_TRIGGER_WINDOW_MINUTES and not force:
        debug(f"Not within trigger window (+{ALARM_TRIGGER_WINDOW_MINUTES}m). diff={diff_minutes:.2f}m")
        return False

    # Start playback
    try:
        token = get_access_token()
        if not token:
            logger.warning("❌ Failed to retrieve token for alarm execution.")
            return False

        device_name = config.get("device_name", "")
        if not device_name:
            logger.warning("❌ No device name configured for the alarm.")
            return False

        device_id = get_device_id(token, device_name)
        if not device_id:
            logger.warning(f"❌ Device '{device_name}' not found.")
            return False

        target_volume = config.get("alarm_volume", 50)
        fade_in = config.get("fade_in", False)
        shuffle = config.get("shuffle", False)
        log(f"🎚️ Alarm volume: {target_volume}%, Fade-In: {fade_in}, Shuffle: {shuffle}")

        if not config.get("playlist_uri"):
            debug("No playlist_uri configured; playback may fail")

        initial_volume = 0 if fade_in else target_volume

        preset_success = False
        try:
            preset_success = set_volume(token, initial_volume, device_id)
        except Exception as preset_err:
            logger.warning(f"⚠️ Error presetting volume: {preset_err}")

        if not preset_success:
            logger.warning(f"⚠️ Could not preset volume to {initial_volume}% before playback")
            if fade_in:
                fade_in = False
                initial_volume = target_volume
                logger.warning("⚠️ Fade-in disabled because initial volume could not be set safely")

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
                volume_percent=initial_volume,
                shuffle=shuffle
            )
            log("▶️ Playback started at 0% volume (Fade-In active)")
            try:
                if target_volume > 0:
                    fade_step = max(1, min(5, target_volume))
                    volumes: List[int] = []
                    current = fade_step
                    while current < target_volume:
                        volumes.append(current)
                        current += fade_step
                    volumes.append(target_volume)

                    for idx, v in enumerate(volumes):
                        time.sleep(1 if idx == 0 else 5)
                        if set_volume(token, v, device_id):
                            log(f"🎚️ Volume increased to {v}%")
                        else:
                            log(f"⚠️ Volume set attempt to {v}% - Spotify API refused value")
            except Exception as e:
                log(f"❌ Error during fade-in: {e}")

        log("✅ Playback started.")

        # Auto-disable alarm
        if not force:
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
