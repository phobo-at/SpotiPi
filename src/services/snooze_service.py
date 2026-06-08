"""
💤 Snooze Service - Business Logic for Snooze-on-Pause
=====================================================

Thin service wrapper around :mod:`src.core.snooze` so route handlers stay
HTTP-only. Exposes the snooze session status and an explicit dismiss action.
"""

from typing import Any, Dict

from ..core.snooze import get_snooze_status, stop_snooze_session
from . import BaseService, ServiceResult


class SnoozeService(BaseService):
    """Service for the snooze-on-pause session."""

    def __init__(self):
        super().__init__("snooze")

    def get_snooze_status(self) -> ServiceResult:
        """Get the current snooze session status."""
        try:
            status: Dict[str, Any] = get_snooze_status()
            return self._success_result(
                data={**status, "raw_status": status},
                message="Snooze status retrieved successfully"
            )
        except Exception as e:
            return self._handle_error(e, "get_snooze_status")

    def stop_snooze(self) -> ServiceResult:
        """Dismiss the active snooze session."""
        try:
            current = get_snooze_status()
            if not current.get("active"):
                return self._error_result(
                    "No active snooze session to stop",
                    error_code="NO_ACTIVE_SNOOZE"
                )

            if stop_snooze_session():
                return self._success_result(message="Snooze session stopped successfully")

            return self._error_result(
                "Failed to stop snooze session",
                error_code="STOP_FAILED"
            )
        except Exception as e:
            return self._handle_error(e, "stop_snooze")

    def health_check(self) -> ServiceResult:
        """Perform snooze service health check."""
        try:
            base_health = super().health_check()
            if not base_health.success:
                return base_health

            status_result = self.get_snooze_status()
            status_ok = status_result.success

            health_data = {
                "service": "snooze",
                "status": "healthy" if status_ok else "degraded",
                "components": {
                    "status_tracking": "ok" if status_ok else "error",
                },
                "active_session": status_result.data.get("active", False) if status_result.success else None
            }

            return self._success_result(
                data=health_data,
                message="Snooze service health check completed"
            )
        except Exception as e:
            return self._handle_error(e, "health_check")
