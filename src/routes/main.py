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
from ..config import load_config, save_config
from ..core.scheduler import AlarmTimeValidator
from ..services.service_manager import get_service
from ..utils.cache_migration import get_cache_migration_layer
from ..utils.rate_limiting import rate_limit
from ..utils.thread_safety import invalidate_config_cache
from ..utils.translations import get_translations, get_user_language, t_api
from ..version import VERSION, get_app_info
from .helpers import api_error_handler, api_response, normalise_snapshot_meta

main_bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)

LOW_POWER_MODE = os.getenv('SPOTIPI_LOW_POWER', '').lower() in ('1', 'true', 'yes', 'on')

_dashboard_snapshot = None
_playback_snapshot = None
_devices_snapshot = None


def init_snapshots(dashboard_snapshot, playback_snapshot, devices_snapshot) -> None:
    """Initialize snapshot references from main app."""
    global _dashboard_snapshot, _playback_snapshot, _devices_snapshot
    _dashboard_snapshot = dashboard_snapshot
    _playback_snapshot = playback_snapshot
    _devices_snapshot = devices_snapshot


@main_bp.route("/")
@api_error_handler
def index():
    """Main page with alarm and sleep interface."""
    config = load_config()

    initial_volume = config.get('volume', 50)
    try:
        initial_volume = max(0, min(100, int(initial_volume)))
    except (TypeError, ValueError):
        initial_volume = 50

    devices = []
    playlists = []
    current_track = None

    next_alarm_info = ""
    if config.get('enabled') and config.get('time'):
        try:
            next_alarm_info = AlarmTimeValidator.format_time_until_alarm(config['time'])
        except Exception:
            next_alarm_info = "Next alarm calculation error"

    user_language = get_user_language(request)
    translations = get_translations(user_language)

    def template_t(key, **kwargs):
        from ..utils.translations import t
        return t(key, user_language, **kwargs)

    dashboard_snapshot, dashboard_meta = (None, {}) if _dashboard_snapshot is None else _dashboard_snapshot.snapshot()
    playback_snapshot, playback_meta = (None, {}) if _playback_snapshot is None else _playback_snapshot.snapshot()
    devices_snapshot, devices_meta = (None, {}) if _devices_snapshot is None else _devices_snapshot.snapshot()

    initial_state = {
        'dashboard': dashboard_snapshot,
        'dashboard_meta': normalise_snapshot_meta(dashboard_meta) if dashboard_meta else {},
        'playback': playback_snapshot,
        'playback_meta': normalise_snapshot_meta(playback_meta) if playback_meta else {},
        'devices': devices_snapshot,
        'devices_meta': normalise_snapshot_meta(devices_meta) if devices_meta else {}
    }

    sleep_service_index = get_service("sleep")
    sleep_status_result_index = sleep_service_index.get_sleep_status()
    if sleep_status_result_index.success:
        sleep_status_initial = (sleep_status_result_index.data or {}).get("raw_status") or sleep_status_result_index.data
    else:
        sleep_status_initial = {
            "active": False,
            "error": sleep_status_result_index.message,
            "error_code": sleep_status_result_index.error_code or "sleep_status_error"
        }

    template_data = {
        'config': config,
        'devices': devices,
        'playlists': playlists,
        'current_track': current_track,
        'next_alarm_info': next_alarm_info,
        'initial_volume': initial_volume,
        'error_message': session.pop('error_message', None),
        'success_message': session.pop('success_message', None),
        'sleep_status': sleep_status_initial,
        'now': datetime.datetime.now(),
        't': template_t,
        'lang': user_language,
        'translations': translations,
        'initial_state': initial_state,
        'low_power': LOW_POWER_MODE,
        'feature_flags': {
            'sleep_timer': config.get('feature_sleep', False),
            'music_library': config.get('feature_library', True),
        },
        'app_info': get_app_info(),
        'version': VERSION
    }

    return render_template('index.html', **template_data)


@main_bp.route("/debug/language")
def debug_language():
    """Debug endpoint to check language detection."""
    user_language = get_user_language(request)
    translations = get_translations(user_language)

    return {
        "detected_language": user_language,
        "accept_language_header": request.headers.get('Accept-Language', 'Not found'),
        "sample_translation": translations.get('app_title', 'Translation not found'),
        "all_headers": dict(request.headers)
    }


@main_bp.route("/settings")
@api_error_handler
def settings_page():
    """Settings page with feature flags and app configuration."""
    config = load_config()
    user_language = get_user_language(request)
    translations = get_translations(user_language)

    def template_t(key, **kwargs):
        from ..utils.translations import t
        return t(key, user_language, **kwargs)

    return render_template(
        "settings.html",
        config=config,
        version=VERSION,
        translations=translations,
        t=template_t,
    )


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
            "default_volume": config.get("alarm_volume", 50),
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

    config = load_config()
    updated_fields = []

    if "feature_flags" in data:
        flags = data["feature_flags"]
        if "sleep_timer" in flags:
            config["feature_sleep"] = bool(flags["sleep_timer"])
            updated_fields.append("feature_sleep")
        if "music_library" in flags:
            config["feature_library"] = bool(flags["music_library"])
            updated_fields.append("feature_library")

    if "app" in data:
        app_settings = data["app"]
        if "language" in app_settings:
            lang = app_settings["language"]
            if lang in ("de", "en"):
                config["language"] = lang
                updated_fields.append("language")
        if "default_volume" in app_settings:
            try:
                vol = max(0, min(100, int(app_settings["default_volume"])))
                config["alarm_volume"] = vol
                updated_fields.append("alarm_volume")
            except (TypeError, ValueError):
                pass
        if "debug" in app_settings:
            config["debug"] = bool(app_settings["debug"])
            updated_fields.append("debug")

    if not updated_fields:
        return api_response(False, message=t_api("no_changes", request), status=400, error_code="no_changes")

    if save_config(config):
        invalidate_config_cache()
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
