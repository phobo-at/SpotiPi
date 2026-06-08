"""
💤 Snooze Routes Blueprint
Handles dismissing an active snooze-on-pause session.
"""

import logging

from flask import Blueprint, redirect, request, session, url_for

from ..services.service_manager import get_service
from ..utils.rate_limiting import rate_limit
from .helpers import api_error_handler, api_response

snooze_bp = Blueprint("snooze", __name__)
logger = logging.getLogger(__name__)


@snooze_bp.route("/api/snooze/stop", methods=["POST"])
@api_error_handler
@rate_limit("api_general")
def stop_snooze():
    """Dismiss the active snooze session."""
    snooze_service = get_service("snooze")
    result = snooze_service.stop_snooze()
    success = result.success

    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.headers.get('Accept', '').find('application/json') != -1
    )

    if request.is_json or is_ajax:
        return api_response(
            success,
            data={"active": False} if success else None,
            message=result.message or ("Snooze stopped" if success else "Failed to stop snooze"),
            status=200 if success else (400 if result.error_code == "NO_ACTIVE_SNOOZE" else 500),
            error_code=None if success else (result.error_code or "snooze_stop_failed")
        )

    if success:
        session['success_message'] = result.message or "Snooze stopped"
    else:
        session['error_message'] = result.message or "Failed to stop snooze"
    return redirect(url_for('main.index'))
