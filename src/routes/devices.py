"""
📱 Device Routes Blueprint
Handles Spotify device listing and refresh endpoints.
"""

import datetime
import logging
import time
from typing import Any, Dict, Optional

from flask import Blueprint, request

from ..api.spotify import get_access_token, get_devices
from ..utils.cache_migration import get_cache_migration_layer
from ..utils.rate_limiting import rate_limit
from ..utils.translations import t_api
from .helpers import api_error_handler, api_response, normalise_snapshot_meta, _iso_timestamp_now

devices_bp = Blueprint("devices", __name__)
logger = logging.getLogger(__name__)


# Snapshot instances will be injected from app.py
_playback_snapshot = None
_devices_snapshot = None


def init_snapshots(playback_snapshot, devices_snapshot):
    """Initialize snapshot references from main app."""
    global _playback_snapshot, _devices_snapshot
    _playback_snapshot = playback_snapshot
    _devices_snapshot = devices_snapshot


def _build_devices_snapshot(token: Optional[str], *, timestamp: Optional[str] = None) -> Dict[str, Any]:
    """Build a devices snapshot payload."""
    cache_migration = get_cache_migration_layer()
    snapshot_ts = timestamp or _iso_timestamp_now()
    if not token:
        return {
            "status": "auth_required",
            "devices": [],
            "cache": {},
            "fetched_at": snapshot_ts
        }
    try:
        devices = get_devices(token) or []
        cache_info = cache_migration.get_device_cache_info(token) or {}
        return {
            "status": "ok" if devices else "empty",
            "devices": devices,
            "cache": cache_info,
            "fetched_at": snapshot_ts
        }
    except Exception as exc:
        logger.debug("Device snapshot error: %s", exc)
        return {
            "status": "error",
            "devices": [],
            "error": str(exc),
            "cache": {},
            "fetched_at": snapshot_ts
        }


def _refresh_devices_snapshot() -> Dict[str, Any]:
    """Refresh the devices snapshot."""
    token = get_access_token()
    payload = _build_devices_snapshot(token)
    if _devices_snapshot and payload.get("status") in {"ok", "empty"}:
        _devices_snapshot.set(payload)
    return payload


@devices_bp.route("/api/devices")
@api_error_handler
@rate_limit("status_check")
def api_devices():
    """Return cached Spotify devices without blocking on network calls."""
    if _devices_snapshot is None:
        return api_response(False, message="Device snapshot not initialized", status=500, error_code="init_error")
    
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')
    if force_refresh:
        _devices_snapshot.mark_stale()

    devices_data, meta = _devices_snapshot.snapshot()

    if force_refresh or meta["pending"]:
        _devices_snapshot.schedule_refresh(
            _refresh_devices_snapshot,
            force=force_refresh,
            reason="api.devices"
        )

    payload = {
        "timestamp": _iso_timestamp_now(),
        "devices": devices_data.get("devices") if devices_data else [],
        "status": devices_data.get("status") if devices_data else "pending",
        "cache": devices_data.get("cache") if devices_data else {},
        "hydration": normalise_snapshot_meta(meta)
    }
    if devices_data and devices_data.get("error"):
        payload["error"] = devices_data["error"]

    status_code = 200
    if payload["hydration"]["pending"] or payload["status"] in {"pending", "auth_required"}:
        status_code = 202
    elif payload["status"] == "error":
        status_code = 503

    return api_response(True, data=payload, status=status_code)


@devices_bp.route("/api/spotify/devices")
@api_error_handler
@rate_limit("spotify_api")
def api_spotify_devices():
    """API endpoint for getting available Spotify devices."""
    if _devices_snapshot is None:
        return api_response(False, message="Device snapshot not initialized", status=500, error_code="init_error")
    
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')
    if force_refresh:
        _devices_snapshot.mark_stale()

    devices_data, meta = _devices_snapshot.snapshot()
    if force_refresh or meta["pending"]:
        _devices_snapshot.schedule_refresh(
            _refresh_devices_snapshot,
            force=force_refresh,
            reason="api.spotify.devices"
        )

    cache_info = devices_data.get("cache") if devices_data else {}
    ts_value = cache_info.get('timestamp') if isinstance(cache_info, dict) else None
    last_updated_iso = None
    if ts_value:
        try:
            last_updated_iso = datetime.datetime.fromtimestamp(
                float(ts_value),
                tz=datetime.timezone.utc
            ).isoformat()
        except (TypeError, ValueError, OSError):
            last_updated_iso = None
    elif devices_data and devices_data.get("fetched_at"):
        last_updated_iso = devices_data["fetched_at"]

    payload = {
        "devices": devices_data.get("devices") if devices_data else [],
        "cache": cache_info or {},
        "lastUpdated": ts_value,
        "lastUpdatedIso": last_updated_iso,
        "status": devices_data.get("status") if devices_data else "pending",
        "hydration": normalise_snapshot_meta(meta)
    }

    status_code = 200
    if payload["hydration"]["pending"] or payload["status"] in {"pending", "auth_required"}:
        status_code = 202
    elif payload["status"] == "error":
        status_code = 503

    return api_response(True, data=payload, status=status_code)


@devices_bp.route("/api/devices/refresh")
@api_error_handler
def api_devices_refresh():
    """Fast device refresh endpoint - bypasses cache for immediate updates."""
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    
    cache_migration = get_cache_migration_layer()
    
    try:
        cache_migration.invalidate_devices()
        devices = get_devices(token)
        cache_info = cache_migration.get_device_cache_info(token)
        payload = {
            "devices": devices if devices else [],
            "cache": cache_info or {},
            "lastUpdated": cache_info.get('timestamp') if cache_info else None,
            "stale": bool(cache_info.get('stale')) if cache_info else False,
            "timestamp": time.time()
        }
        if cache_info and cache_info.get('timestamp'):
            try:
                payload['lastUpdatedIso'] = datetime.datetime.fromtimestamp(
                    cache_info['timestamp'], tz=datetime.timezone.utc
                ).isoformat()
            except (TypeError, ValueError, OSError):
                pass
        logger.info(f"🔄 Fast device refresh: {len(payload['devices'])} devices loaded")

        if _devices_snapshot:
            snapshot_payload = {
                "status": "ok" if payload["devices"] else "empty",
                "devices": payload["devices"],
                "cache": cache_info or {},
                "fetched_at": _iso_timestamp_now()
            }
            _devices_snapshot.set(snapshot_payload)

        return api_response(True, data=payload)
    except Exception as e:
        logger.error(f"❌ Error in device refresh: {e}")
        return api_response(False, message=str(e), status=503, error_code="device_refresh_error")
