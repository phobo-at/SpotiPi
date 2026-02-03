"""
🛠️ Route Helpers
Shared utilities for all route blueprints.
"""

import datetime
import logging
import uuid
from functools import wraps
from typing import Any, Callable, Optional, Union

from flask import Response, jsonify, redirect, request, session, url_for

from ..utils.translations import t_api

logger = logging.getLogger(__name__)


def _iso_timestamp_now() -> str:
    """Return ISO 8601 timestamp in UTC with a trailing Z."""
    now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
    return now_utc.isoformat(timespec="microseconds").replace("+00:00", "Z")


def api_response(
    success: bool,
    *,
    data: Optional[Any] = None,
    message: str = "",
    status: int = 200,
    error_code: Optional[str] = None
) -> Response:
    """Create a standardized API response with consistent envelope.
    
    Args:
        success: Whether the operation succeeded
        data: Optional response data
        message: Optional message string
        status: HTTP status code (default 200)
        error_code: Optional error code for failures
        
    Returns:
        Flask Response object with JSON payload
    """
    req_id = str(uuid.uuid4())
    timestamp = _iso_timestamp_now()
    payload = {
        "success": success,
        "timestamp": timestamp,
        "request_id": req_id
    }
    if message:
        payload["message"] = message
    if data is not None:
        payload["data"] = data
    if error_code:
        payload["error_code"] = error_code
    resp = jsonify(payload)
    resp.status_code = status
    # Correlation headers
    resp.headers['X-Request-ID'] = req_id
    resp.headers['X-Response-Timestamp'] = timestamp
    return resp


def api_error(
    message: str,
    *,
    status: int = 400,
    error_code: Optional[str] = None,
    data: Optional[Any] = None,
) -> Response:
    """Convenience wrapper for standardized error responses."""
    return api_response(
        False,
        data=data,
        message=message,
        status=status,
        error_code=error_code,
    )


def api_error_handler(func: Callable) -> Callable:
    """Decorator for consistent API error handling.
    
    Catches exceptions and returns standardized error responses.
    For API endpoints, returns JSON; for web pages, redirects.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logging.exception(f"Error in {func.__name__}")
            if request.is_json or request.path.startswith('/api/'):
                return api_error(
                    t_api("an_internal_error_occurred", request),
                    status=500,
                    error_code="unhandled_exception",
                )
            session['error_message'] = str(e)
            return redirect(url_for('main.index'))
    return wrapper


def normalise_snapshot_meta(meta: dict) -> dict:
    """Normalize snapshot metadata for API responses.
    
    Args:
        meta: Raw snapshot metadata dictionary
        
    Returns:
        Normalized metadata dictionary
    """
    return {
        "fresh": bool(meta.get("fresh")),
        "pending": bool(meta.get("pending")),
        "refreshing": bool(meta.get("refreshing")),
        "has_data": bool(meta.get("has_data")),
        "last_refresh": meta.get("last_refresh"),
        "last_error": meta.get("last_error"),
        "last_error_at": meta.get("last_error_at"),
        "pending_reason": meta.get("pending_reason"),
        "ttl": meta.get("ttl"),
    }
