"""
🏠 Main Routes Blueprint
Handles index, settings, debug, and profile endpoints.
"""

from __future__ import annotations

import datetime
import logging
import os

from flask import Blueprint, render_template, request, session

from ..api.spotify import get_access_token
from ..config import load_config
from ..config_schema import DEFAULT_VOLUME
from ..core.scheduler import AlarmTimeValidator
from ..services.service_manager import get_service
from ..utils.cache_migration import get_cache_migration_layer
from ..utils.rate_limiting import rate_limit
from ..utils.thread_safety import invalidate_config_cache, update_config_atomic
from ..utils.translations import get_translations, get_user_language, t_api
from ..version import VERSION, get_app_info
from .helpers import api_error_handler, api_response, normalise_snapshot_meta

main_bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)

LOW_POWER_MODE = os.getenv('SPOTIPI_LOW_POWER', '').lower() in ('1', 'true', 'yes', 'on')
DEBUG_ROUTES_ENABLED = os.getenv("SPOTIPI_ENABLE_DEBUG_ROUTES", "0").lower() in ("1", "true", "yes", "on")
DEBUG_HEADER_WHITELIST = (
    "Accept-Language",
    "User-Agent",
    "Host",
    "X-Forwarded-For",
    "X-Forwarded-Proto",
)
_VALID_INITIAL_SURFACES = {"home", "settings"}

_dashboard_snapshot = None
_playback_snapshot = None
_devices_snapshot = None


def init_snapshots(dashboard_snapshot, playback_snapshot, devices_snapshot) -> None:
    """Initialize snapshot references from main app."""
    global _dashboard_snapshot, _playback_snapshot, _devices_snapshot
    _dashboard_snapshot = dashboard_snapshot
    _playback_snapshot = playback_snapshot
    _devices_snapshot = devices_snapshot


def _resolve_initial_surface(raw_value: str | None) -> str:
    """Return a valid initial surface name for the frontend shell."""
    value = (raw_value or "home").strip().lower()
    return value if value in _VALID_INITIAL_SURFACES else "home"


def _build_settings_payload(config: dict) -> dict:
    """Create the initial settings payload used by the frontend shell."""
    return {
        "feature_flags": {
            "sleep_timer": config.get("feature_sleep", False),
            "music_library": config.get("feature_library", True),
        },
        "app": {
            "language": config.get("language", "de"),
            "default_volume": config.get("alarm_volume", DEFAULT_VOLUME),
            "debug": config.get("debug", False),
        },
        "environment": config.get("_runtime", {}).get("environment", "unknown"),
    }


def _build_sleep_defaults(config: dict) -> dict:
    """Return persisted sleep defaults for first render hydration."""
    duration = config.get("sleep_default_duration", 30)
    volume = config.get("sleep_volume", 30)

    try:
        duration = max(1, min(480, int(duration)))
    except (TypeError, ValueError):
        duration = 30

    try:
        volume = max(0, min(100, int(volume)))
    except (TypeError, ValueError):
        volume = 30

    return {
        "duration": duration,
        "volume": volume,
        "playlist_uri": config.get("sleep_playlist_uri", ""),
        "device_name": config.get("sleep_device_name", ""),
        "shuffle": bool(config.get("shuffle", False)),
    }


def _build_dashboard_payload(
    config: dict,
    sleep_status_payload: dict,
    dashboard_snapshot: dict | None,
    dashboard_meta: dict,
    playback_snapshot: dict | None,
    playback_meta: dict,
    devices_snapshot: dict | None,
    devices_meta: dict,
) -> dict:
    """Build the same dashboard shape used by /api/dashboard/status for hydration."""
    next_alarm_time = ""
    if config.get("enabled") and config.get("time"):
        try:
            next_alarm_time = AlarmTimeValidator.format_time_until_alarm(config["time"])
        except Exception:
            next_alarm_time = "Next alarm calculation error"

    alarm_payload = {
        "enabled": config.get("enabled", False),
        "time": config.get("time", "07:00"),
        "alarm_volume": config.get("alarm_volume", DEFAULT_VOLUME),
        "next_alarm": next_alarm_time,
        "playlist_uri": config.get("playlist_uri", ""),
        "device_name": config.get("device_name", ""),
        "fade_in": config.get("fade_in", False),
        "shuffle": config.get("shuffle", False),
    }

    playback_payload: dict = {}
    playback_status = "pending"
    playback_error = None
    if playback_snapshot:
        playback_payload = playback_snapshot.get("playback") or {}
        playback_status = playback_snapshot.get("status", "unknown")
        playback_error = playback_snapshot.get("error")
    elif dashboard_snapshot:
        dash_playback = dashboard_snapshot.get("playback", {})
        if isinstance(dash_playback, dict):
            playback_payload = dash_playback.get("playback") or {}
            playback_status = dash_playback.get("status", playback_status)
            playback_error = dash_playback.get("error")

    devices_payload = []
    devices_status = "pending"
    devices_cache = {}
    if devices_snapshot:
        devices_payload = devices_snapshot.get("devices") or []
        devices_status = devices_snapshot.get("status", "unknown")
        devices_cache = devices_snapshot.get("cache") or {}
    elif dashboard_snapshot:
        dash_devices = dashboard_snapshot.get("devices", {})
        if isinstance(dash_devices, dict):
            devices_payload = dash_devices.get("devices") or []
            devices_status = dash_devices.get("status", devices_status)
            devices_cache = dash_devices.get("cache") or {}

    payload = {
        "timestamp": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "alarm": alarm_payload,
        "sleep": sleep_status_payload,
        "playback": playback_payload or {},
        "playback_status": playback_status,
        "devices": devices_payload,
        "devices_meta": {
            "status": devices_status,
            "cache": devices_cache,
            "fetched_at": devices_snapshot.get("fetched_at") if devices_snapshot else None,
        },
        "hydration": {
            "dashboard": normalise_snapshot_meta(dashboard_meta),
            "playback": normalise_snapshot_meta(playback_meta),
            "devices": normalise_snapshot_meta(devices_meta),
        },
    }

    if playback_error:
        payload["playback_error"] = playback_error

    return payload


def _build_index_template_data(*, initial_surface: str = "home") -> dict:
    """Build the shared template payload for the new frontend shell."""
    config = load_config()

    user_language = get_user_language(request)
    translations = get_translations(user_language)

    dashboard_snapshot, dashboard_meta = (None, {}) if _dashboard_snapshot is None else _dashboard_snapshot.snapshot()
    playback_snapshot, playback_meta = (None, {}) if _playback_snapshot is None else _playback_snapshot.snapshot()
    devices_snapshot, devices_meta = (None, {}) if _devices_snapshot is None else _devices_snapshot.snapshot()

    sleep_service_index = get_service("sleep")
    sleep_status_result_index = sleep_service_index.get_sleep_status()
    if sleep_status_result_index.success:
        sleep_status_initial = (sleep_status_result_index.data or {}).get("raw_status") or sleep_status_result_index.data
    else:
        sleep_status_initial = {
            "active": False,
            "error": sleep_status_result_index.message,
            "error_code": sleep_status_result_index.error_code or "sleep_status_error",
        }

    notifications = []
    success_message = session.pop("success_message", None)
    error_message = session.pop("error_message", None)
    if success_message:
        notifications.append({"type": "success", "message": success_message})
    if error_message:
        notifications.append({"type": "error", "message": error_message})

    bootstrap = {
        "language": user_language,
        "translations": translations,
        "low_power": LOW_POWER_MODE,
        "app": {
            "version": VERSION,
            "info": get_app_info(),
            "initial_surface": _resolve_initial_surface(initial_surface),
            "now_iso": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        },
        "dashboard": _build_dashboard_payload(
            config,
            sleep_status_initial,
            dashboard_snapshot,
            dashboard_meta,
            playback_snapshot,
            playback_meta,
            devices_snapshot,
            devices_meta,
        ),
        "settings": _build_settings_payload(config),
        "sleep_defaults": _build_sleep_defaults(config),
        "notifications": notifications,
    }

    return {
        "lang": user_language,
        "bootstrap": bootstrap,
        "app_info": get_app_info(),
        "version": VERSION,
    }


@main_bp.route("/")
@api_error_handler
def index():
    """Main page with alarm and sleep interface."""
    initial_surface = _resolve_initial_surface(request.args.get("surface"))
    return render_template("index.html", **_build_index_template_data(initial_surface=initial_surface))


@main_bp.route("/debug/language")
def debug_language():
    """Debug endpoint to check language detection."""
    if not DEBUG_ROUTES_ENABLED:
        return api_response(False, message="Not Found", status=404, error_code="not_found")

    user_language = get_user_language(request)
    translations = get_translations(user_language)
    visible_headers = {
        header: request.headers.get(header, "Not found")
        for header in DEBUG_HEADER_WHITELIST
    }

    return api_response(True, data={
        "detected_language": user_language,
        "accept_language_header": request.headers.get('Accept-Language', 'Not found'),
        "sample_translation": translations.get('app_title', 'Translation not found'),
        "request_headers": visible_headers,
    })


@main_bp.route("/settings")
@api_error_handler
def settings_page():
    """Render the main app shell with the settings surface opened."""
    return render_template("index.html", **_build_index_template_data(initial_surface="settings"))


@main_bp.route("/api/settings", methods=["GET"])
@api_error_handler
@rate_limit("default")
def api_get_settings():
    """Get current application settings including feature flags."""
    config = load_config()

    settings = {
        "feature_flags": {
            "sleep_timer": config.get("feature_sleep", False),
            "music_library": config.get("feature_library", True),
        },
        "app": {
            "language": config.get("language", "de"),
            "default_volume": config.get("alarm_volume", DEFAULT_VOLUME),
            "debug": config.get("debug", False),
        },
        "environment": config.get("_runtime", {}).get("environment", "unknown"),
    }

    return api_response(True, data=settings)


@main_bp.route("/api/settings", methods=["POST", "PATCH"])
@api_error_handler
@rate_limit("default")
def api_update_settings():
    """Update application settings."""
    data = request.get_json(silent=True) or {}

    if not data:
        return api_response(False, message=t_api("invalid_request", request), status=400, error_code="invalid_request")

    updates = {}

    if "feature_flags" in data:
        flags = data["feature_flags"]
        if "sleep_timer" in flags:
            updates["feature_sleep"] = bool(flags["sleep_timer"])
        if "music_library" in flags:
            updates["feature_library"] = bool(flags["music_library"])

    if "app" in data:
        app_settings = data["app"]
        if "language" in app_settings:
            lang = app_settings["language"]
            if lang in ("de", "en"):
                updates["language"] = lang
        if "default_volume" in app_settings:
            try:
                vol = max(0, min(100, int(app_settings["default_volume"])))
                updates["alarm_volume"] = vol
            except (TypeError, ValueError):
                pass
        if "debug" in app_settings:
            updates["debug"] = bool(app_settings["debug"])

    updated_fields = sorted(updates.keys())

    if not updated_fields:
        return api_response(False, message=t_api("no_changes", request), status=400, error_code="no_changes")

    if update_config_atomic(lambda config: {**config, **updates}):
        logger.info("⚙️ Settings updated: %s", ", ".join(updated_fields))
        return api_response(True, message=t_api("settings_saved", request), data={"updated": updated_fields})

    return api_response(False, message=t_api("settings_save_error", request), status=500, error_code="save_error")


@main_bp.route("/api/settings/feature-flags", methods=["GET"])
@api_error_handler
@rate_limit("default")
def api_get_feature_flags():
    """Get only the feature flags (for lightweight requests from index.html)."""
    config = load_config()
    flags = {
        "sleep_timer": config.get("feature_sleep", False),
        "music_library": config.get("feature_library", True),
    }
    return api_response(True, data=flags)


@main_bp.route("/api/spotify/profile", methods=["GET"])
@api_error_handler
@rate_limit("spotify_api")
def api_spotify_profile():
    """Get the connected Spotify user's profile."""
    from ..api.spotify import get_user_profile
    token = get_access_token()
    if not token:
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")

    profile = get_user_profile(token)
    if profile:
        return api_response(True, data=profile)
    return api_response(False, message=t_api("spotify_profile_error", request), status=503, error_code="profile_error")


@main_bp.route("/api/settings/cache/clear", methods=["POST"])
@api_error_handler
@rate_limit("default")
def api_clear_cache():
    """Clear all application caches."""
    try:
        cache_migration = get_cache_migration_layer()
        cache_migration.invalidate_music_library()
        cache_migration.invalidate_devices()
        invalidate_config_cache()

        if _dashboard_snapshot:
            _dashboard_snapshot.mark_stale()
        if _playback_snapshot:
            _playback_snapshot.mark_stale()
        if _devices_snapshot:
            _devices_snapshot.mark_stale()

        logger.info("🗑️ All caches cleared via settings")
        return api_response(True, message=t_api("cache_cleared", request))
    except Exception as e:
        logger.error("❌ Error clearing cache: %s", e)
        return api_response(False, message=str(e), status=500, error_code="cache_clear_error")
