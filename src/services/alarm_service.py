"""
⏰ Alarm Service - Business Logic for Alarm Management
=====================================================

Handles all alarm-related business logic including scheduling,
validation, execution, and status management.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from . import BaseService, ServiceResult
from ..config import load_config, save_config
from ..core.alarm import execute_alarm
from ..core.scheduler import WeekdayScheduler, AlarmTimeValidator
from ..utils.validation import validate_alarm_config, ValidationError

@dataclass
class AlarmInfo:
    """Structured alarm information."""
    enabled: bool
    time: Optional[str]
    weekdays: List[int]
    device_name: Optional[str]
    device_id: Optional[str]
    playlist_uri: Optional[str]
    volume: int
    next_execution: Optional[datetime]
    is_scheduled: bool

class AlarmService(BaseService):
    """Service for managing alarms and scheduling."""
    
    def __init__(self):
        super().__init__("alarm")
        self.scheduler = WeekdayScheduler()
        self.validator = AlarmTimeValidator()
    
    def get_alarm_status(self) -> ServiceResult:
        """Get comprehensive alarm status information."""
        try:
            config = load_config()
            
            # Calculate next alarm execution
            next_alarm = None
            is_scheduled = False
            
            if config.get("enabled") and config.get("time"):
                weekdays = config.get("weekdays", [])
                if weekdays:
                    next_alarm = self.scheduler.get_next_alarm_date(
                        config["time"], weekdays
                    )
                    is_scheduled = True
            
            alarm_info = AlarmInfo(
                enabled=config.get("enabled", False),
                time=config.get("time"),
                weekdays=config.get("weekdays", []),
                device_name=config.get("device_name"),
                device_id=config.get("device_id"),
                playlist_uri=config.get("playlist_uri"),
                volume=config.get("volume", 50),
                next_execution=next_alarm,
                is_scheduled=is_scheduled
            )
            
            return self._success_result(
                data=alarm_info.__dict__,
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
            if validated_data.get("time"):
                if not self.validator.validate_time_format(validated_data["time"]):
                    return self._error_result(
                        "Invalid time format. Please use HH:MM format.",
                        error_code="INVALID_TIME_FORMAT"
                    )
            
            # Load current config and update
            config = load_config()
            config.update(validated_data)
            
            # Save configuration
            save_config(config)
            
            # Get updated status for response
            status_result = self.get_alarm_status()
            
            return self._success_result(
                data=status_result.data if status_result.success else None,
                message="Alarm settings saved successfully"
            )
            
        except ValidationError as e:
            return self._error_result(
                str(e),
                error_code="VALIDATION_ERROR"
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
            success = execute_alarm()
            
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
    
    def get_next_alarms(self, days: int = 7) -> ServiceResult:
        """Get next scheduled alarms for the specified number of days."""
        try:
            config = load_config()
            
            if not config.get("enabled") or not config.get("time"):
                return self._success_result(
                    data=[],
                    message="No alarms scheduled"
                )
            
            weekdays = config.get("weekdays", [])
            if not weekdays:
                return self._success_result(
                    data=[],
                    message="No weekdays selected for alarm"
                )
            
            next_alarms = []
            current_date = datetime.now().date()
            
            for i in range(days):
                check_date = current_date + timedelta(days=i)
                weekday_index = check_date.weekday()

                if weekday_index in weekdays:
                    alarm_datetime = self.scheduler.get_next_alarm_date(
                        config["time"], [weekday_index]
                    )
                    if alarm_datetime:
                        next_alarms.append({
                            "date": check_date.isoformat(),
                            "weekday": WeekdayScheduler.get_weekday_name(weekday_index),
                            "time": config["time"],
                            "datetime": alarm_datetime.isoformat()
                        })
            
            return self._success_result(
                data=next_alarms,
                message=f"Found {len(next_alarms)} scheduled alarms in the next {days} days"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_next_alarms")
    
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
            
            if not config.get("weekdays"):
                return self._error_result(
                    "Cannot enable alarm: No weekdays selected",
                    error_code="MISSING_WEEKDAYS"
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
            
            # Check scheduler
            scheduler_ok = self.scheduler is not None
            validator_ok = self.validator is not None
            
            # Check config accessibility
            config = load_config()
            config_ok = config is not None
            
            health_data = {
                "service": "alarm",
                "status": "healthy" if all([scheduler_ok, validator_ok, config_ok]) else "degraded",
                "components": {
                    "scheduler": "ok" if scheduler_ok else "error",
                    "validator": "ok" if validator_ok else "error",
                    "config": "ok" if config_ok else "error"
                }
            }
            
            return self._success_result(
                data=health_data,
                message="Alarm service health check completed"
            )
            
        except Exception as e:
            return self._handle_error(e, "health_check")
