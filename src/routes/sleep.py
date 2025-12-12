"""
😴 Sleep Timer Routes Blueprint
Handles sleep timer start, stop, and status endpoints.
"""

import logging

from flask import Blueprint, redirect, request, session, url_for

from ..services.service_manager import get_service
from ..utils.rate_limiting import rate_limit
from ..utils.translations import t_api
from .helpers import api_error_handler, api_response

sleep_bp = Blueprint("sleep", __name__)
logger = logging.getLogger(__name__)


@sleep_bp.route("/sleep_status")
@api_error_handler
@rate_limit("status_check")
def sleep_status_api():
    """Get sleep timer status - supports both basic and advanced modes."""
    advanced_mode = request.args.get('advanced', 'false').lower() == 'true'

    sleep_service = get_service("sleep")
    result = sleep_service.get_sleep_status()

    if not result.success:
        logger.error("Failed to load sleep status via service: %s", result.message)
        return api_response(
            False,
            message=result.message or t_api("sleep_status_error", request),
            status=500,
            error_code=result.error_code or "sleep_status_error"
        )

    if advanced_mode:
        return api_response(True, data={
            "timestamp": result.timestamp.isoformat(),
            "sleep": {k: v for k, v in (result.data or {}).items() if k != "raw_status"},
            "mode": "advanced"
        })

    legacy_payload = (result.data or {}).get("raw_status")
    if legacy_payload is None:
        legacy_payload = result.data
    return api_response(True, data=legacy_payload or {})


@sleep_bp.route("/sleep", methods=["POST"])
@api_error_handler
@rate_limit("config_changes")
def start_sleep():
    """Start sleep timer with comprehensive input validation."""
    sleep_service = get_service("sleep")
    result = sleep_service.start_sleep_timer(request.form)

    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
        request.headers.get('Accept', '').find('application/json') != -1
    )
    
    if request.is_json or is_ajax:
        if result.success:
            return api_response(True, message=result.message or "Sleep timer started")

        error_code = (result.error_code or "sleep_start_failed")
        status = 400 if error_code in {"duration", "sleep_volume", "playlist_uri", "device_name"} else 500
        message = result.message or t_api("failed_start_sleep", request)
        return api_response(False, message=message, status=status, error_code=error_code)

    if result.success:
        session['success_message'] = result.message or "Sleep timer started"
    else:
        session['error_message'] = result.message or "Failed to start sleep timer"
    return redirect(url_for('main.index'))


@sleep_bp.route("/stop_sleep", methods=["POST"])
@api_error_handler
@rate_limit("api_general")
def stop_sleep():
    """Stop active sleep timer."""
    sleep_service = get_service("sleep")
    result = sleep_service.stop_sleep_timer()
    success = result.success

    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
        request.headers.get('Accept', '').find('application/json') != -1
    )
    
    if request.is_json or is_ajax:
        message = t_api("sleep_stopped", request) if success else (result.message or "Failed to stop sleep timer")
        return api_response(
            success,
            message=message,
            status=200 if success else 500,
            error_code=None if success else (result.error_code or "sleep_stop_failed")
        )

    if success:
        session['success_message'] = result.message or "Sleep timer stopped"
    else:
        session['error_message'] = result.message or "Failed to stop sleep timer"
    return redirect(url_for('main.index'))
