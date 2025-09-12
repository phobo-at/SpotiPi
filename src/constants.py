"""Central constants for SpotiPi (light‑weight and local-use oriented).

Only put small, stable primitives here – avoid runtime/config dependent values.
"""

# Alarm trigger window (minutes) – tolerance around the configured HH:MM
ALARM_TRIGGER_WINDOW_MINUTES: float = 1.5

# Fields allowed when slimming music library payloads for basic mode
MUSIC_LIBRARY_BASIC_FIELDS = {"uri", "name", "image_url", "track_count", "type", "artist"}
