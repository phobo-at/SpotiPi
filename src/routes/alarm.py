"""
🚨 Alarm Routes Blueprint
Handles alarm configuration and status endpoints.
"""

import logging
from typing import Any, Dict

from flask import Blueprint, request

from ..config import load_config
from ..core.scheduler import AlarmTimeValidator
from ..services.service_manager import get_service
from ..utils.logger import log_structured
from ..utils.rate_limiting import rate_limit
from ..utils.translations import t_api
from .helpers import api_error_handler, api_response

alarm_bp = Blueprint("alarm", __name__)
logger = logging.getLogger(__name__)


@alarm_bp.route("/save_alarm", methods=["POST"])
@api_error_handler
@rate_limit("config_changes")
def save_alarm():
    """Save alarm settings with comprehensive input validation."""
    alarm_service = get_service("alarm")
    result = alarm_service.save_alarm_settings(request.form)

    if result.success:
        return api_response(True, data=result.data, message=t_api("alarm_settings_saved", request))

    error_code = (result.error_code or "internal_error").lower()
    message = result.message or t_api("internal_error_saving", request)

    if error_code == "time_format":
        return api_response(False, message=t_api("invalid_time_format", request), status=400, error_code="time_format")
    if error_code == "save_failed":
        return api_response(False, message=t_api("failed_save_config", request), status=500, error_code="save_failed")
    if error_code in {"alarm_time", "volume", "alarm_volume", "playlist_uri", "device_name"}:
        log_structured(logger, logging.WARNING, "Alarm validation error",
                      error_code=error_code, validation_message=message, endpoint="/save_alarm")
        return api_response(False, message=message, status=400, error_code=error_code)

    log_structured(logger, logging.ERROR, "Error saving alarm configuration via service",
                  error_message=message, endpoint="/save_alarm")
    return api_response(False, message=t_api("internal_error_saving", request), status=500, error_code="internal_error")



@alarm_bp.route("/api/alarm/execute", methods=["POST"])
@rate_limit("config_changes")
def api_alarm_execute():
    """Manually execute the alarm immediately.

    Useful for debugging on the Raspberry Pi when checking playlist/device
    configuration or verifying logging. Returns JSON with success flag.
    """
    alarm_service = get_service("alarm")
    result = alarm_service.execute_alarm_now()

    if result.success:
        return api_response(True, data={"executed": True}, message=result.message or "Alarm executed")

    log_structured(logger, logging.ERROR, "Alarm execution failed",
                  message=result.message, error_code=result.error_code,
                  endpoint="/api/alarm/execute")
    return api_response(
        False,
        data={"executed": False},
        message=result.message or "Alarm conditions not met or failed",
        status=400,
        error_code="alarm_not_executed"
    )
