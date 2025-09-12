#!/usr/bin/env python3
"""
Script to replace hardcoded messages in app.py with translation calls
"""

import re
import sys

def replace_messages_in_file(filepath):
    """Replace hardcoded messages with translation calls"""
    
    # Mapping of hardcoded strings to translation keys
    replacements = [
        (r'message="Spotify authentication required"', r'message=t_api("auth_required", request)'),
        (r'message="Authentication required"', r'message=t_api("auth_required", request)'),
        (r'message="Spotify unavailable: failed to load music library"', r'message=t_api("spotify_unavailable", request)'),
        (r'message="served offline cache \(spotify issue\)"', r'message=t_api("served_offline_cache", request)'),
        (r'message="ok \(partial\)"', r'message=t_api("ok_partial", request)'),
        (r'message="ok"', r'message=t_api("ok", request)'),
        (r'message="degraded"', r'message=t_api("degraded", request)'),
        (r'message="No active playback"', r'message=t_api("no_active_playback", request)'),
        (r'message="Failed to start playback"', r'message=t_api("failed_start_playback", request)'),
        (r'message="Playback started"', r'message=t_api("playback_started", request)'),
        (r'message="Missing context_uri"', r'message=t_api("missing_context_uri", request)'),
        (r'message="Missing URI"', r'message=t_api("missing_uri", request)'),
        (r'message="Missing device name"', r'message=t_api("missing_device", request)'),
        (r'message="No devices available"', r'message=t_api("no_devices", request)'),
        (r'message=f"Device \'([^\']+)\' not found"', r'message=t_api("device_not_found", request, name=r"\1")'),
        (r'message="Failed to set volume"', r'message=t_api("volume_set_failed", request)'),
        (r'message="Volume saved"', r'message=t_api("volume_saved", request)'),
        (r'message="Failed to save volume"', r'message=t_api("failed_save_volume", request)'),
        (r'message="Failed to start sleep timer"', r'message=t_api("failed_start_sleep", request)'),
        (r'message="Sleep timer stopped"', r'message=t_api("sleep_stopped", request)'),
        (r'message="Failed to stop sleep timer"', r'message=t_api("failed_stop_sleep", request)'),
    ]
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Apply replacements
        for pattern, replacement in replacements:
            content = re.sub(pattern, replacement, content)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"✅ Successfully updated {filepath}")
        
    except Exception as e:
        print(f"❌ Error processing {filepath}: {e}")

if __name__ == "__main__":
    filepath = "/Users/michi/spotipi-dev/spotify_wakeup/src/app.py"
    replace_messages_in_file(filepath)