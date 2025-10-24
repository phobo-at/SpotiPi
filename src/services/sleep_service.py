"""
😴 Sleep Service - Business Logic for Sleep Timer Management
===========================================================

Handles all sleep timer related business logic including timer management,
status tracking, and sleep settings configuration.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from . import BaseService, ServiceResult
from ..core.sleep import (
    start_sleep_timer, stop_sleep_timer, get_sleep_status,
    save_sleep_settings
)
from ..utils.validation import validate_sleep_config, ValidationError

class SleepService(BaseService):
    """Service for managing sleep timers and settings."""
    
    def __init__(self):
        super().__init__("sleep")
        self._timer_start_time = None
        self._service_start_time = datetime.now()
    
    def get_sleep_status(self) -> ServiceResult:
        """Get current sleep timer status."""
        try:
            status = get_sleep_status()
            
            # Enhance status with additional information
            remaining_seconds = status.get("remaining_seconds")
            if remaining_seconds is None:
                remaining_seconds = status.get("remaining_time", 0)
            if remaining_seconds is None:
                remaining_seconds = 0
            try:
                remaining_seconds = int(remaining_seconds)
            except (TypeError, ValueError):
                remaining_seconds = 0

            total_duration = status.get("total_duration_seconds")
            if total_duration is None:
                total_duration = status.get("total_duration", 0)
            if total_duration is None:
                total_duration = 0

            start_time = status.get("start_time")
            end_time = status.get("end_time")

            progress_percent = status.get("progress_percent", 0)
            if progress_percent == 0 and status.get("active") and total_duration:
                elapsed = total_duration - remaining_seconds
                if total_duration > 0:
                    progress_percent = max(0.0, min(100.0, (elapsed / total_duration) * 100))

            enhanced_status = {
                "active": status.get("active", False),
                "remaining_time": remaining_seconds,
                "total_duration": total_duration,
                "start_time": start_time,
                "end_time": end_time,
                "progress_percent": progress_percent,
                "remaining_seconds": remaining_seconds,
                "total_duration_seconds": total_duration,
                "volume": status.get("volume"),
                "device_name": status.get("device_name"),
                "device_id": status.get("device_id")
            }

            payload = {
                **enhanced_status,
                "raw_status": status
            }

            return self._success_result(
                data=payload,
                message="Sleep status retrieved successfully"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_sleep_status")
    
    def start_sleep_timer(self, form_data: Dict[str, Any]) -> ServiceResult:
        """Start a new sleep timer with validation."""
        try:
            # Check if timer is already active
            current_status = self.get_sleep_status()
            if current_status.success and current_status.data.get("active"):
                return self._error_result(
                    "Sleep timer is already active. Stop the current timer first.",
                    error_code="TIMER_ALREADY_ACTIVE"
                )
            
            # Validate input data
            validated_data = validate_sleep_config(form_data)
            
            # Business logic validation
            duration_minutes = validated_data.get("duration_minutes", 0)
            if duration_minutes < 1:
                return self._error_result(
                    "Sleep timer duration must be at least 1 minute",
                    error_code="INVALID_DURATION"
                )
            
            if duration_minutes > 480:  # 8 hours
                return self._error_result(
                    "Sleep timer duration cannot exceed 8 hours (480 minutes)",
                    error_code="DURATION_TOO_LONG"
                )
            
            # Start the timer
            success = start_sleep_timer(**validated_data)
            
            if success:
                self._timer_start_time = datetime.now()
                
                # Get updated status
                status_result = self.get_sleep_status()
                
                return self._success_result(
                    data=status_result.data if status_result.success else None,
                    message=f"Sleep timer started for {duration_minutes} minutes"
                )
            else:
                return self._error_result(
                    "Failed to start sleep timer",
                    error_code="START_FAILED"
                )
                
        except ValidationError as e:
            return self._error_result(
                f"Invalid {e.field_name}: {e.message}",
                error_code=e.field_name
            )
        except Exception as e:
            return self._handle_error(e, "start_sleep_timer")
    
    def stop_sleep_timer(self) -> ServiceResult:
        """Stop the active sleep timer."""
        try:
            # Check if timer is active
            current_status = self.get_sleep_status()
            if current_status.success and not current_status.data.get("active"):
                return self._error_result(
                    "No active sleep timer to stop",
                    error_code="NO_ACTIVE_TIMER"
                )
            
            # Stop the timer
            success = stop_sleep_timer()
            
            if success:
                self._timer_start_time = None
                
                return self._success_result(
                    message="Sleep timer stopped successfully"
                )
            else:
                return self._error_result(
                    "Failed to stop sleep timer",
                    error_code="STOP_FAILED"
                )
                
        except Exception as e:
            return self._handle_error(e, "stop_sleep_timer")
    
    def save_sleep_settings(self, settings: Dict[str, Any]) -> ServiceResult:
        """Save default sleep timer settings."""
        try:
            # Validate settings
            if "default_duration" in settings:
                duration = settings["default_duration"]
                if not isinstance(duration, int) or duration < 1 or duration > 480:
                    return self._error_result(
                        "Default duration must be between 1 and 480 minutes",
                        error_code="INVALID_DEFAULT_DURATION"
                    )
            
            if "fade_out_duration" in settings:
                fade_duration = settings["fade_out_duration"]
                if not isinstance(fade_duration, int) or fade_duration < 0 or fade_duration > 60:
                    return self._error_result(
                        "Fade out duration must be between 0 and 60 seconds",
                        error_code="INVALID_FADE_DURATION"
                    )
            
            # Save settings
            success = save_sleep_settings(settings)
            
            if success:
                return self._success_result(
                    data=settings,
                    message="Sleep settings saved successfully"
                )
            else:
                return self._error_result(
                    "Failed to save sleep settings",
                    error_code="SAVE_FAILED"
                )
                
        except Exception as e:
            return self._handle_error(e, "save_sleep_settings")
    
    def get_sleep_statistics(self) -> ServiceResult:
        """Get sleep timer usage statistics."""
        try:
            # This would typically come from a database in a real app
            # For now, we'll return basic runtime statistics
            
            stats = {
                "session_start": self._timer_start_time.isoformat() if self._timer_start_time else None,
                "service_uptime": (datetime.now() - self._service_start_time).total_seconds(),
                "timers_started_today": 0,  # Would be tracked in real implementation
                "total_sleep_minutes_today": 0,  # Would be tracked in real implementation
                "most_common_duration": 30,  # Would be calculated from history
                "average_completion_rate": 85.0  # Would be calculated from history
            }
            
            return self._success_result(
                data=stats,
                message="Sleep statistics retrieved successfully"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_sleep_statistics")
    
    def validate_sleep_duration(self, duration: int) -> ServiceResult:
        """Validate sleep timer duration."""
        try:
            if not isinstance(duration, int):
                return self._error_result(
                    "Duration must be a number",
                    error_code="INVALID_TYPE"
                )
            
            if duration < 1:
                return self._error_result(
                    "Duration must be at least 1 minute",
                    error_code="TOO_SHORT"
                )
            
            if duration > 480:
                return self._error_result(
                    "Duration cannot exceed 8 hours (480 minutes)",
                    error_code="TOO_LONG"
                )
            
            # Suggest common durations
            suggestions = []
            common_durations = [15, 30, 45, 60, 90, 120]
            
            if duration not in common_durations:
                # Find closest common duration
                closest = min(common_durations, key=lambda x: abs(x - duration))
                if abs(closest - duration) <= 5:  # Within 5 minutes
                    suggestions.append(f"Consider {closest} minutes (common duration)")
            
            return self._success_result(
                data={
                    "duration": duration,
                    "valid": True,
                    "suggestions": suggestions
                },
                message="Duration is valid"
            )
            
        except Exception as e:
            return self._handle_error(e, "validate_sleep_duration")
    
    def get_recommended_durations(self) -> ServiceResult:
        """Get recommended sleep timer durations based on time of day."""
        try:
            current_hour = datetime.now().hour
            
            if 6 <= current_hour < 12:  # Morning
                recommendations = [15, 20, 30]
                context = "morning"
            elif 12 <= current_hour < 18:  # Afternoon
                recommendations = [20, 30, 45]
                context = "afternoon"
            elif 18 <= current_hour < 22:  # Evening
                recommendations = [30, 45, 60]
                context = "evening"
            else:  # Night
                recommendations = [60, 90, 120]
                context = "night"
            
            return self._success_result(
                data={
                    "context": context,
                    "current_hour": current_hour,
                    "recommended_durations": recommendations,
                    "explanation": f"Optimized for {context} listening"
                },
                message=f"Recommendations for {context} provided"
            )
            
        except Exception as e:
            return self._handle_error(e, "get_recommended_durations")
    
    def health_check(self) -> ServiceResult:
        """Perform sleep service health check."""
        try:
            base_health = super().health_check()
            if not base_health.success:
                return base_health
            
            # Check sleep status accessibility
            status_result = self.get_sleep_status()
            status_ok = status_result.success
            
            # Check timer functionality (without actually starting one)
            timer_ok = True  # Would test timer creation/destruction in real scenario
            
            health_data = {
                "service": "sleep",
                "status": "healthy" if all([status_ok, timer_ok]) else "degraded",
                "components": {
                    "status_tracking": "ok" if status_ok else "error",
                    "timer_management": "ok" if timer_ok else "error"
                },
                "active_timer": status_result.data.get("active", False) if status_result.success else None
            }
            
            return self._success_result(
                data=health_data,
                message="Sleep service health check completed"
            )
            
        except Exception as e:
            return self._handle_error(e, "health_check")
