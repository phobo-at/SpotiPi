"""
🩺 Health & Status Routes Blueprint
Handles health checks, metrics, and status endpoints.
"""

import datetime
import logging
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request

from ..api.spotify import get_access_token
from ..config import load_config
from ..core.scheduler import AlarmTimeValidator
from ..services.service_manager import get_service
from ..utils.cache_migration import get_cache_migration_layer
from ..utils.rate_limiting import get_rate_limiter, rate_limit
from ..utils.thread_safety import get_config_stats, invalidate_config_cache
from ..utils.token_cache import get_token_cache_info, log_token_cache_performance
from ..utils.translations import t_api
from ..version import VERSION
from .helpers import api_error_handler, api_response, normalise_snapshot_meta, _iso_timestamp_now

health_bp = Blueprint("health", __name__)
logger = logging.getLogger(__name__)

# Snapshot instances will be injected from app.py
_dashboard_snapshot = None
_playback_snapshot = None
_devices_snapshot = None


def init_snapshots(dashboard_snapshot, playback_snapshot, devices_snapshot):
    """Initialize snapshot references from main app."""
    global _dashboard_snapshot, _playback_snapshot, _devices_snapshot
    _dashboard_snapshot = dashboard_snapshot
    _playback_snapshot = playback_snapshot
    _devices_snapshot = devices_snapshot


def _build_playback_snapshot(token: Optional[str], *, timestamp: Optional[str] = None) -> Dict[str, Any]:
    """Build a playback snapshot payload."""
    from ..api.spotify import get_combined_playback
    snapshot_ts = timestamp or _iso_timestamp_now()
    if not token:
        return {
            "status": "auth_required",
            "playback": None,
            "fetched_at": snapshot_ts
        }
    try:
        playback = get_combined_playback(token)
        status = "ok" if playback else "empty"
        return {
            "status": status,
            "playback": playback,
            "fetched_at": snapshot_ts
        }
    except Exception as exc:
        logger.debug("Playback snapshot error: %s", exc)
        return {
            "status": "error",
            "playback": None,
            "error": str(exc),
            "fetched_at": snapshot_ts
        }


def _build_devices_snapshot(token: Optional[str], *, timestamp: Optional[str] = None) -> Dict[str, Any]:
    """Build a devices snapshot payload."""
    from ..api.spotify import get_devices
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


def _refresh_playback_snapshot() -> Dict[str, Any]:
    """Refresh the playback snapshot."""
    token = get_access_token()
    payload = _build_playback_snapshot(token)
    if _playback_snapshot and payload.get("status") == "ok":
        _playback_snapshot.set(payload)
    return payload


def _refresh_devices_snapshot() -> Dict[str, Any]:
    """Refresh the devices snapshot."""
    token = get_access_token()
    payload = _build_devices_snapshot(token)
    if _devices_snapshot and payload.get("status") in {"ok", "empty"}:
        _devices_snapshot.set(payload)
    return payload


def _refresh_dashboard_snapshot() -> Dict[str, Any]:
    """Refresh the combined dashboard snapshot."""
    token = get_access_token()
    snapshot_ts = _iso_timestamp_now()
    playback_payload = _build_playback_snapshot(token, timestamp=snapshot_ts)
    devices_payload = _build_devices_snapshot(token, timestamp=snapshot_ts)
    if _playback_snapshot and playback_payload.get("status") in {"ok", "empty"}:
        _playback_snapshot.set(playback_payload)
    if _devices_snapshot and devices_payload.get("status") in {"ok", "empty"}:
        _devices_snapshot.set(devices_payload)
    return {
        "playback": playback_payload,
        "devices": devices_payload,
        "fetched_at": snapshot_ts
    }


@health_bp.route("/healthz")
def healthz():
    """Basic health check endpoint."""
    return jsonify({"ok": True, "version": str(VERSION)})


@health_bp.route("/readyz")
def readyz():
    """Readiness check endpoint."""
    try:
        # Basic checks: config loaded, rate limiter running
        _ = load_config()
        rate_limiter = get_rate_limiter()
        stats = rate_limiter.get_statistics()
        return jsonify({
            "ok": True,
            "rate_limiter": {"total_requests": stats.get('global_stats', {}).get('total_requests', 0)}
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@health_bp.route("/metrics")
def metrics():
    """Minimal Prometheus-style metrics exposition."""
    try:
        rate_limiter = get_rate_limiter()
        stats = rate_limiter.get_statistics()
        cache_info = get_token_cache_info()
        lines = []
        lines.append("# HELP spotipi_requests_total Total requests seen by rate limiter")
        lines.append("# TYPE spotipi_requests_total counter")
        lines.append(f"spotipi_requests_total {stats.get('global_stats', {}).get('total_requests', 0)}")
        lines.append("# HELP spotipi_cache_hits Token cache hits")
        lines.append("# TYPE spotipi_cache_hits counter")
        hits = cache_info.get('cache_metrics', {}).get('cache_hits', 0) if isinstance(cache_info, dict) else 0
        lines.append(f"spotipi_cache_hits {hits}")
        lines.append("# HELP spotipi_cache_misses Token cache misses")
        lines.append("# TYPE spotipi_cache_misses counter")
        misses = cache_info.get('cache_metrics', {}).get('cache_misses', 0) if isinstance(cache_info, dict) else 0
        lines.append(f"spotipi_cache_misses {misses}")
        return ("\n".join(lines) + "\n", 200, {"Content-Type": "text/plain; version=0.0.4"})
    except Exception:
        return ("spotipi_up 0\n", 200, {"Content-Type": "text/plain; version=0.0.4"})


@health_bp.route("/api/dashboard/status")
@api_error_handler
@rate_limit("status_check")
def api_dashboard_status():
    """Aggregate dashboard status (alarm, sleep, playback) in a single response."""
    if _dashboard_snapshot is None or _playback_snapshot is None or _devices_snapshot is None:
        return api_response(False, message="Snapshots not initialized", status=500, error_code="init_error")
    
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')
    if force_refresh:
        _dashboard_snapshot.mark_stale()
        _playback_snapshot.mark_stale()
        _devices_snapshot.mark_stale()

    dashboard_data, dashboard_meta = _dashboard_snapshot.snapshot()
    playback_data, playback_meta = _playback_snapshot.snapshot()
    devices_data, devices_meta = _devices_snapshot.snapshot()

    if force_refresh or dashboard_meta["pending"]:
        _dashboard_snapshot.schedule_refresh(
            _refresh_dashboard_snapshot,
            force=force_refresh,
            reason="api.dashboard"
        )

    # Only trigger dedicated snapshot refreshers if the combined dashboard one is not already running.
    if (force_refresh or playback_meta["pending"]) and not dashboard_meta.get("refreshing"):
        _playback_snapshot.schedule_refresh(
            _refresh_playback_snapshot,
            force=force_refresh,
            reason="api.dashboard.playback"
        )
    if (force_refresh or devices_meta["pending"]) and not dashboard_meta.get("refreshing"):
        _devices_snapshot.schedule_refresh(
            _refresh_devices_snapshot,
            force=force_refresh,
            reason="api.dashboard.devices"
        )

    config = load_config()
    next_alarm_time = ""
    if config.get("enabled") and config.get("time"):
        try:
            next_alarm_time = AlarmTimeValidator.format_time_until_alarm(config["time"])
        except Exception:
            next_alarm_time = "Next alarm calculation error"

    alarm_payload = {
        "enabled": config.get("enabled", False),
        "time": config.get("time", "07:00"),
        "alarm_volume": config.get("alarm_volume", 50),
        "next_alarm": next_alarm_time,
        "playlist_uri": config.get("playlist_uri", ""),
        "device_name": config.get("device_name", "")
    }

    sleep_service = get_service("sleep")
    sleep_result = sleep_service.get_sleep_status()
    if sleep_result.success:
        sleep_payload = (sleep_result.data or {}).get("raw_status") or sleep_result.data
    else:
        sleep_payload = {
            "active": False,
            "error": sleep_result.message,
            "error_code": sleep_result.error_code or "sleep_status_error"
        }

    playback_payload = {}
    playback_status = "pending"
    playback_error = None
    if playback_data:
        playback_payload = playback_data.get("playback") or {}
        playback_status = playback_data.get("status", "unknown")
        playback_error = playback_data.get("error")
    elif dashboard_data:
        dash_playback = dashboard_data.get("playback", {})
        if isinstance(dash_playback, dict):
            playback_payload = dash_playback.get("playback") or {}
            playback_status = dash_playback.get("status", playback_status)
            playback_error = dash_playback.get("error")

    devices_payload = []
    devices_status = "pending"
    devices_cache = {}
    if devices_data:
        devices_payload = devices_data.get("devices") or []
        devices_status = devices_data.get("status", "unknown")
        devices_cache = devices_data.get("cache") or {}
    elif dashboard_data:
        dash_devices = dashboard_data.get("devices", {})
        if isinstance(dash_devices, dict):
            devices_payload = dash_devices.get("devices") or []
            devices_status = dash_devices.get("status", devices_status)
            devices_cache = dash_devices.get("cache") or {}

    hydration_meta = {
        "dashboard": normalise_snapshot_meta(dashboard_meta),
        "playback": normalise_snapshot_meta(playback_meta),
        "devices": normalise_snapshot_meta(devices_meta),
    }

    response_payload = {
        "timestamp": _iso_timestamp_now(),
        "alarm": alarm_payload,
        "sleep": sleep_payload,
        "playback": playback_payload or {},
        "playback_status": playback_status,
        "devices": devices_payload,
        "devices_meta": {
            "status": devices_status,
            "cache": devices_cache,
            "fetched_at": devices_data.get("fetched_at") if devices_data else None
        },
        "hydration": hydration_meta
    }

    if playback_error:
        response_payload["playback_error"] = playback_error

    # Determine a meaningful HTTP status: pending requests should return 202 to indicate work in progress.
    status_code = 200
    if hydration_meta["playback"]["pending"] or hydration_meta["devices"]["pending"]:
        status_code = 202
    elif playback_status == "error":
        status_code = 503

    return api_response(True, data=response_payload, status=status_code)


@health_bp.route("/playback_status")
@api_error_handler
@rate_limit("spotify_api")
def playback_status():
    """Get current Spotify playback status."""
    if _playback_snapshot is None:
        return api_response(False, message="Playback snapshot not initialized", status=500, error_code="init_error")
    
    force_refresh = request.args.get('refresh') in ('1', 'true', 'yes')
    if force_refresh:
        _playback_snapshot.mark_stale()

    playback_data, meta = _playback_snapshot.snapshot()

    if force_refresh or meta["pending"]:
        _playback_snapshot.schedule_refresh(
            _refresh_playback_snapshot,
            force=force_refresh,
            reason="api.playback"
        )

    payload = playback_data.get("playback") if playback_data else {}
    status_flag = playback_data.get("status") if playback_data else "pending"
    response_payload = {
        "timestamp": _iso_timestamp_now(),
        "playback": payload or {},
        "status": status_flag,
        "hydration": normalise_snapshot_meta(meta)
    }
    if playback_data and playback_data.get("error"):
        response_payload["error"] = playback_data["error"]

    status_code = 200
    if response_payload["hydration"]["pending"] or status_flag in {"pending", "auth_required"}:
        status_code = 202
    elif status_flag == "error":
        status_code = 503

    return api_response(True, data=response_payload, status=status_code)


@health_bp.route("/api/token-cache/status")
@rate_limit("status_check")
def get_token_cache_status():
    """📊 Get token cache performance and status information."""
    try:
        cache_info = get_token_cache_info()
        return api_response(True, data={"cache_info": cache_info})
    except Exception as e:
        logger.error(f"❌ Error getting token cache status: {e}")
        return api_response(False, message=f"Error getting cache status: {str(e)}", status=500, error_code="cache_status_error")


@health_bp.route("/api/thread-safety/status")
@rate_limit("status_check")
def get_thread_safety_status():
    """📊 Get thread safety status and statistics."""
    try:
        stats = get_config_stats()
        return api_response(True, data={"thread_safety_stats": stats})
    except Exception as e:
        logger.error(f"❌ Error getting thread safety status: {e}")
        return api_response(False, message=f"Error getting thread safety status: {str(e)}", status=500, error_code="thread_safety_error")


@health_bp.route("/api/thread-safety/invalidate-cache", methods=["POST"])
def invalidate_thread_safe_cache():
    """🗑️ Force invalidation of thread-safe config cache."""
    try:
        invalidate_config_cache()
        return jsonify({
            "success": True,
            "message": "Config cache invalidated successfully"
        })
    except Exception as e:
        logger.error(f"❌ Error invalidating cache: {e}")
        return jsonify({
            "success": False,
            "message": f"Error invalidating cache: {str(e)}"
        }), 500


@health_bp.route("/api/token-cache/performance")
def log_token_performance():
    """📈 Log token cache performance summary."""
    try:
        log_token_cache_performance()
        return jsonify({
            "success": True,
            "message": "Performance summary logged to console"
        })
    except Exception as e:
        logger.error(f"❌ Error logging token performance: {e}")
        return jsonify({
            "success": False,
            "message": f"Error logging performance: {str(e)}"
        }), 500


@health_bp.route("/api/spotify/health")
@rate_limit("status_check")
def api_spotify_health():
    """Quick health check for Spotify connectivity (DNS, TLS reachability)."""
    try:
        from ..api.spotify import spotify_network_health
        health = spotify_network_health()
        http_code = 200 if health.get("ok") else 503
        return api_response(
            health.get("ok", False),
            data=health,
            status=http_code,
            message=t_api("ok", request) if health.get("ok") else "degraded",
            error_code=None if health.get("ok") else "spotify_degraded"
        )
    except Exception as e:
        logger.exception("Error running Spotify health check")
        return jsonify({
            "ok": False,
            "error": "HEALTH_CHECK_FAILED",
            "message": str(e)
        }), 500


@health_bp.route("/api/spotify/auth-status")
@rate_limit("spotify_api")
def api_spotify_auth_status():
    """🎵 Get Spotify authentication status via service layer."""
    try:
        spotify_service = get_service("spotify")
        result = spotify_service.get_authentication_status()
        
        if result.success:
            return api_response(True, data={"timestamp": result.timestamp.isoformat(), "spotify": result.data})
        else:
            return api_response(
                False,
                message=result.message,
                status=401 if result.error_code == "AUTH_REQUIRED" else 500,
                error_code=result.error_code or "spotify_auth_error"
            )
            
    except Exception as e:
        logger.error(f"Error getting Spotify auth status: {e}")
        return api_response(False, message=str(e), status=500, error_code="spotify_auth_exception")
