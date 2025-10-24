"""
⏰ Alarm Service - Business Logic for Alarm Management
=====================================================

Handles all alarm-related business logic including scheduling,
validation, execution, and status management.
"""

from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

from . import BaseService, ServiceResult
from ..config import load_config, save_config
from ..core.alarm import execute_alarm
from ..core.scheduler import AlarmTimeValidator
from ..utils.validation import validate_alarm_config, ValidationError

@dataclass
class AlarmInfo:
    """Structured alarm information."""

    enabled: bool
    time: Optional[str]
    device_name: Optional[str]
    playlist_uri: Optional[str]
    volume: int
    next_execution: Optional[datetime]
    is_scheduled: bool
    next_alarm_text: Optional[str]
    next_execution_iso: Optional[str]

class AlarmService(BaseService):
    """Service for managing alarms and scheduling."""
    
    def __init__(self):
        super().__init__("alarm")
        self.validator = AlarmTimeValidator()
    
    def get_alarm_status(self) -> ServiceResult:
        """Get comprehensive alarm status information."""
        try:
            config = load_config()
            
            # Calculate next alarm execution
            next_alarm = None
            is_scheduled = False
            if config.get("enabled") and config.get("time"):
                next_alarm = AlarmTimeValidator.get_next_alarm_date(config["time"])
                is_scheduled = next_alarm is not None

            next_alarm_text = ""
            next_execution_iso = None
            if config.get("enabled") and config.get("time"):
                try:
                    next_alarm_text = AlarmTimeValidator.format_time_until_alarm(config["time"])
                except Exception:
                    next_alarm_text = "Next alarm calculation error"

            if next_alarm:
                try:
                    next_execution_iso = next_alarm.isoformat()
                except Exception:
                    next_execution_iso = None

            alarm_info = AlarmInfo(
                enabled=config.get("enabled", False),
                time=config.get("time"),
                device_name=config.get("device_name"),
                playlist_uri=config.get("playlist_uri"),
                volume=config.get("alarm_volume", 50),
                next_execution=next_alarm,
                is_scheduled=is_scheduled,
                next_alarm_text=next_alarm_text,
                next_execution_iso=next_execution_iso
            )

            data = {
                **alarm_info.__dict__,
                "next_alarm": next_alarm_text,
                "alarm_volume": alarm_info.volume,
            }

            return self._success_result(
                data=data,
                message="Alarm status retrieved successfully"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_alarm_status")
    
    def save_alarm_settings(self, form_data: Dict[str, Any]) -> ServiceResult:
        """Save and validate alarm settings."""
        try:
            # Validate input data
            validated_data = validate_alarm_config(form_data)

            # Additional business logic validation
            configured_time = validated_data.get("time")
            if configured_time and not self.validator.validate_time_format(configured_time):
                return self._error_result(
                    "Invalid time format. Please use HH:MM format.",
                    error_code="time_format"
                )

            # Load current config and update
            config = load_config()
            config.update(validated_data)

            # Persist configuration atomically
            if not save_config(config):
                return self._error_result(
                    "Failed to save alarm configuration",
                    error_code="save_failed"
                )

            self.logger.info(
                "Alarm settings saved: Active=%s Time=%s Volume=%s%% Device=%s",
                config.get("enabled"),
                config.get("time"),
                config.get("alarm_volume"),
                config.get("device_name", "")
            )

            # Compute next alarm human readable text
            next_alarm_text = ""
            if config.get("enabled") and config.get("time"):
                try:
                    next_alarm_text = AlarmTimeValidator.format_time_until_alarm(config["time"])
                except Exception:
                    next_alarm_text = "Next alarm calculation error"

            payload = {
                "enabled": config.get("enabled", False),
                "time": config.get("time"),
                "alarm_volume": config.get("alarm_volume", 50),
                "next_alarm": next_alarm_text,
                "playlist_uri": config.get("playlist_uri", ""),
                "device_name": config.get("device_name", "")
            }

            return self._success_result(
                data=payload,
                message="Alarm settings saved successfully"
            )

        except ValidationError as e:
            return self._error_result(
                f"Invalid {e.field_name}: {e.message}",
                error_code=e.field_name
            )
        except Exception as e:
            return self._handle_error(e, "save_alarm_settings")
    
    def execute_alarm_now(self) -> ServiceResult:
        """Execute alarm immediately for testing."""
        try:
            config = load_config()
            
            if not (config.get("device_name") or config.get("device_id")) or not config.get("playlist_uri"):
                return self._error_result(
                    "Alarm not fully configured. Missing device or playlist.",
                    error_code="INCOMPLETE_CONFIG"
                )
            
            # Execute the alarm
            success = execute_alarm(force=True)
            
            if success:
                return self._success_result(
                    message="Alarm executed successfully"
                )
            else:
                return self._error_result(
                    "Failed to execute alarm",
                    error_code="EXECUTION_FAILED"
                )
                
        except Exception as e:
            return self._handle_error(e, "execute_alarm_now")
    
    def validate_alarm_time(self, time_str: str) -> ServiceResult:
        """Validate alarm time format and constraints."""
        try:
            is_valid = self.validator.validate_time_format(time_str)
            
            if not is_valid:
                return self._error_result(
                    "Invalid time format. Please use HH:MM format (24-hour).",
                    error_code="INVALID_TIME_FORMAT"
                )
            
            # Additional business rules
            hour, minute = map(int, time_str.split(':'))
            
            if hour < 5 or hour > 23:
                return self._error_result(
                    "Alarm time should be between 05:00 and 23:59 for practical use.",
                    error_code="TIME_OUT_OF_RANGE"
                )
            
            return self._success_result(
                data={"time": time_str, "valid": True},
                message="Time format is valid"
            )
            
        except Exception as e:
            return self._handle_error(e, "validate_alarm_time")
    
    def disable_alarm(self) -> ServiceResult:
        """Disable the alarm system."""
        try:
            config = load_config()
            config["enabled"] = False
            save_config(config)
            
            return self._success_result(
                message="Alarm disabled successfully"
            )
            
        except Exception as e:
            return self._handle_error(e, "disable_alarm")
    
    def enable_alarm(self) -> ServiceResult:
        """Enable the alarm system."""
        try:
            config = load_config()
            
            # Validate that alarm is properly configured
            if not config.get("time"):
                return self._error_result(
                    "Cannot enable alarm: No time configured",
                    error_code="MISSING_TIME"
                )
            
            if not (config.get("device_name") or config.get("device_id")):
                return self._error_result(
                    "Cannot enable alarm: No Spotify device selected",
                    error_code="MISSING_DEVICE"
                )
            
            config["enabled"] = True
            save_config(config)
            
            # Get next alarm info
            status_result = self.get_alarm_status()
            
            return self._success_result(
                data=status_result.data if status_result.success else None,
                message="Alarm enabled successfully"
            )
            
        except Exception as e:
            return self._handle_error(e, "enable_alarm")
    
    def health_check(self) -> ServiceResult:
        """Perform alarm service health check."""
        try:
            base_health = super().health_check()
            if not base_health.success:
                return base_health
            
            config = load_config()
            config_ok = config is not None
            time_ok = False
            if config_ok:
                time_value = config.get("time")
                time_ok = bool(time_value) and self.validator.validate_time_format(time_value)
            
            health_data = {
                "service": "alarm",
                "status": "healthy" if all([config_ok, time_ok]) else "degraded",
                "components": {
                    "config": "ok" if config_ok else "error",
                    "time_format": "ok" if time_ok else "error",
                }
            }
            
            return self._success_result(
                data=health_data,
                message="Alarm service health check completed"
            )
            
        except Exception as e:
            return self._handle_error(e, "health_check")
