"""
▶️ Playback Routes Blueprint
Handles playback control endpoints (play, pause, volume).
"""

import logging

from flask import Blueprint, request

from ..services.service_manager import get_service
from ..utils.rate_limiting import rate_limit
from ..utils.translations import t_api
from .helpers import api_error_handler, api_response

playback_bp = Blueprint("playback", __name__)
logger = logging.getLogger(__name__)


@playback_bp.route("/toggle_play_pause", methods=["POST"])
@api_error_handler
def toggle_play_pause():
    """Toggle Spotify play/pause - optimized for immediate response."""
    spotify_service = get_service("spotify")
    result = spotify_service.toggle_playback_fast()

    if result.success:
        return api_response(True, data=result.data, message=t_api("ok", request))

    error_code = result.error_code or "playback_toggle_failed"
    status = 503 if error_code == "playback_toggle_failed" else 500
    message = result.message or "Playback toggle failed"

    if error_code == "auth_required":
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")

    payload = result.data if isinstance(result.data, dict) else {"result": result.data}
    return api_response(False, data=payload, message=message, status=status, error_code=error_code)


@playback_bp.route("/volume", methods=["POST"])
@api_error_handler
def volume_endpoint():
    """Volume endpoint - only sets Spotify volume (no config save)."""
    spotify_service = get_service("spotify")
    result = spotify_service.set_volume_from_form(request.form)

    if result.success:
        volume = (result.data or {}).get("volume")
        message = f"Volume set to {volume}" if volume is not None else t_api("ok", request)
        return api_response(True, data=result.data, message=message)

    error_code = result.error_code or "volume_set_failed"
    message = result.message or t_api("volume_set_failed", request)

    if error_code == "auth_required":
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    if error_code == "volume":
        logger.warning("Volume validation error: %s", message)
        return api_response(False, message=message, status=400, error_code="volume")

    return api_response(False, message=t_api("volume_set_failed", request), status=500, error_code=error_code)


@playback_bp.route("/play", methods=["POST"])
@api_error_handler
def play_endpoint():
    """Unified playback endpoint - supports both JSON and form data."""
    spotify_service = get_service("spotify")

    if request.is_json:
        payload = request.get_json(silent=True) or {}
        result = spotify_service.start_playback_from_payload(payload, payload_type="json")
    else:
        result = spotify_service.start_playback_from_payload(request.form, payload_type="form")

    if result.success:
        return api_response(True, message=t_api("playback_started", request))

    error_code = (result.error_code or "playback_start_failed")
    message = result.message or t_api("failed_start_playback", request)

    if error_code == "auth_required":
        return api_response(False, message=t_api("auth_required", request), status=401, error_code="auth_required")
    if error_code in {"missing_context_uri", "missing_uri", "missing_device"}:
        translations = {
            "missing_context_uri": t_api("missing_context_uri", request),
            "missing_uri": t_api("missing_uri", request),
            "missing_device": t_api("missing_device", request)
        }
        return api_response(False, message=translations[error_code], status=400, error_code=error_code)
    if error_code == "no_devices":
        return api_response(False, message=t_api("no_devices", request), status=404, error_code="no_devices")
    if error_code == "device_not_found":
        device_name = ""
        if isinstance(result.data, dict):
            device_name = result.data.get("device_name", "")
        return api_response(False, message=t_api("device_not_found", request, name=device_name), status=404, error_code="device_not_found")

    status = 503 if error_code == "playlists_unavailable" else 500
    return api_response(False, message=message, status=status, error_code=error_code)
