# Routes Overview

This directory contains the Flask blueprints for SpotiPi. `src/app.py` registers all blueprints and injects snapshot dependencies for `health`, `devices`, and `main`.

## Blueprints
- `alarm.py`: Alarm settings, status, and manual execute endpoints.
- `cache.py`: Cache status and invalidation endpoints.
- `devices.py`: Cached device snapshots, Spotify device listing, and refresh endpoints.
- `errors.py`: Global 404/500 handlers with API JSON responses.
- `health.py`: Health checks, metrics, dashboard status, playback status, auth status, and token/cache utilities.
- `main.py`: Index page, settings UI, settings APIs, cache clear, debug language, and profile endpoints.
- `music.py`: Music library page and API endpoints, artist top tracks.
- `playback.py`: Playback controls, volume, and next/previous track endpoints.
- `services.py`: Service health, diagnostics, performance, perf metrics, rate limiting status/reset.
- `sleep.py`: Sleep timer start/stop/status endpoints.

## Snapshot Dependencies
- `devices.py` uses `_playback_snapshot` and `_devices_snapshot`.
- `health.py` uses `_dashboard_snapshot`, `_playback_snapshot`, and `_devices_snapshot`.
- `main.py` uses `_dashboard_snapshot`, `_playback_snapshot`, and `_devices_snapshot` for server-rendered hydration.

These are wired by `init_snapshots(...)` calls in `src/app.py`.
