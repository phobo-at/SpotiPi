#!/usr/bin/env python3
"""
⏰ Scheduling Logic for SpotiPi Alarms
Provides comprehensive scheduling functionality including:
- Weekday-based alarm scheduling with validation
- Time format validation and calculations
- Next alarm date calculations
- Human-readable formatting for UI display
- Robust error handling for edge cases
"""

import datetime
from typing import Dict, List, Optional, Tuple, Union

from ..utils.timezone import get_local_timezone

LOCAL_TZ = get_local_timezone()

class WeekdayScheduler:
    """Handles weekday-based alarm scheduling with comprehensive validation."""
    
    WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    SHORT_WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
    
    @staticmethod
    def is_weekday_enabled(weekdays: List[int], target_weekday: int) -> bool:
        """Check if alarm should trigger for given weekday.
        
        Args:
            weekdays: List of enabled weekdays (0=Monday, 6=Sunday)
            target_weekday: Target weekday to check (0=Monday, 6=Sunday)
            
        Returns:
            bool: True if alarm should trigger on this weekday
        """
        # Empty list means daily alarm
        if not weekdays:
            return True
            
        return target_weekday in weekdays
    
    @staticmethod
    def get_next_alarm_date(alarm_time: str, weekdays: List[int]) -> Optional[datetime.datetime]:
        """Calculate next alarm trigger date based on time and weekdays.
        
        Args:
            alarm_time: Time in "HH:MM" format
            weekdays: List of enabled weekdays (0=Monday, 6=Sunday)
            
        Returns:
            Optional[datetime.datetime]: Next datetime when alarm should trigger, or None if invalid
        """
        try:
            now = datetime.datetime.now(tz=LOCAL_TZ)
            hour, minute = map(int, alarm_time.split(":"))
            
            # Validate hour and minute ranges
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                return None
            
            # If no weekdays specified, alarm is daily
            if not weekdays:
                # Check if today's alarm time has passed
                today_alarm = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now < today_alarm:
                    return today_alarm
                else:
                    # Tomorrow
                    return today_alarm + datetime.timedelta(days=1)
            
            # Find next enabled weekday
            current_weekday = now.weekday()
            
            # Check if today's alarm is still valid
            today_alarm = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if current_weekday in weekdays and now < today_alarm:
                return today_alarm
            
            # Look for next enabled weekday (max 7 days ahead)
            for days_ahead in range(1, 8):
                check_date = now + datetime.timedelta(days=days_ahead)
                check_weekday = check_date.weekday()
                
                if check_weekday in weekdays:
                    return check_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            return None  # No valid weekday found (shouldn't happen)
            
        except (ValueError, IndexError, TypeError):
            return None
    
    @staticmethod
    def format_weekdays_display(weekdays: List[int]) -> str:
        """Format weekdays for human-readable display.
        
        Args:
            weekdays: List of weekday numbers (0=Monday, 6=Sunday)
            
        Returns:
            str: Human-readable weekday string (e.g., "Weekdays (Mon-Fri)", "Daily")
        """
        if not weekdays:
            return "Daily"
        
        if len(weekdays) == 7:
            return "Daily"
        
        # Sort weekdays and convert to names
        sorted_weekdays = sorted(weekdays)
        weekday_names = [WeekdayScheduler.WEEKDAYS[day] for day in sorted_weekdays if 0 <= day <= 6]
        
        # Handle common patterns
        if sorted_weekdays == [0, 1, 2, 3, 4]:  # Mon-Fri
            return "Weekdays (Mon-Fri)"
        elif sorted_weekdays == [5, 6]:  # Sat-Sun
            return "Weekends"
        
        # Standard list
        if len(weekday_names) <= 3:
            return ", ".join(weekday_names)
        else:
            return f"{', '.join(weekday_names[:-1])} and {weekday_names[-1]}"
    
    @staticmethod
    def format_weekdays_short(weekdays: List[int]) -> str:
        """Format weekdays in short form (Mo, Tu, We, ...).
        
        Args:
            weekdays: List of weekday numbers (0=Monday, 6=Sunday)
            
        Returns:
            str: Short-form weekday string (e.g., "Mo, Tu, We")
        """
        if not weekdays:
            return "Daily"
        
        if len(weekdays) == 7:
            return "Daily"
        
        sorted_weekdays = sorted([day for day in weekdays if 0 <= day <= 6])
        return ", ".join([WeekdayScheduler.SHORT_WEEKDAYS[day] for day in sorted_weekdays])
    
    @staticmethod
    def validate_weekdays(weekdays: List[int]) -> List[int]:
        """Validate and clean weekdays list.
        
        Args:
            weekdays: List of weekday numbers to validate
            
        Returns:
            List[int]: Cleaned list of valid weekdays (0-6), sorted and deduplicated
        """
        if not isinstance(weekdays, list):
            return []
        
        # Filter valid weekdays (0-6) and remove duplicates
        valid_weekdays = list(set([day for day in weekdays if isinstance(day, int) and 0 <= day <= 6]))
        return sorted(valid_weekdays)
    
    @staticmethod
    def get_weekday_name(weekday: int) -> str:
        """Get full weekday name from number.
        
        Args:
            weekday: Weekday number (0=Monday, 6=Sunday)
            
        Returns:
            str: Full weekday name or "Invalid" for out-of-range values
        """
        if 0 <= weekday <= 6:
            return WeekdayScheduler.WEEKDAYS[weekday]
        return "Invalid"
    
    @staticmethod
    def parse_weekday_string(weekday_str: str) -> List[int]:
        """Parse comma-separated weekday string to list of integers.
        
        Args:
            weekday_str: Comma-separated string of weekday numbers
            
        Returns:
            List[int]: List of valid weekday numbers (0-6)
        """
        try:
            if not weekday_str or not isinstance(weekday_str, str):
                return []
            
            weekdays = []
            for day in weekday_str.split(","):
                day = day.strip()
                if day.isdigit():
                    weekdays.append(int(day))
            
            return WeekdayScheduler.validate_weekdays(weekdays)
        except (ValueError, AttributeError):
            return []

class AlarmTimeValidator:
    """Validates alarm time formats and calculations with robust error handling."""
    
    @staticmethod
    def validate_time_format(time_str: str) -> bool:
        """Validate HH:MM time format.
        
        Args:
            time_str: Time string to validate
            
        Returns:
            bool: True if valid HH:MM format, False otherwise
        """
        try:
            if not isinstance(time_str, str):
                return False
            datetime.datetime.strptime(time_str, "%H:%M")
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_alarm_time_now(alarm_time: str, tolerance_minutes: float = 1.5) -> bool:
        """Check if current time matches alarm time within tolerance.
        
        Args:
            alarm_time: Target alarm time in "HH:MM" format
            tolerance_minutes: Tolerance window in minutes (default: 1.5)
            
        Returns:
            bool: True if current time is within tolerance of alarm time
        """
        try:
            if not AlarmTimeValidator.validate_time_format(alarm_time):
                return False

            now = datetime.datetime.now(tz=LOCAL_TZ)
            target_time = datetime.datetime.strptime(alarm_time, "%H:%M")
            
            target_today = now.replace(
                hour=target_time.hour,
                minute=target_time.minute,
                second=0,
                microsecond=0
            )
            
            diff_minutes = abs((now - target_today).total_seconds() / 60)
            return diff_minutes <= tolerance_minutes
            
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def format_time_until_alarm(alarm_time: str, weekdays: List[int]) -> str:
        """Format time remaining until next alarm.
        
        Args:
            alarm_time: Alarm time in "HH:MM" format
            weekdays: List of enabled weekdays (0=Monday, 6=Sunday)
            
        Returns:
            str: Human-readable time until next alarm (e.g., "in 2h 30m", "in 1 day, 3h 15m")
        """
        if not AlarmTimeValidator.validate_time_format(alarm_time):
            return "Invalid alarm time"
            
        next_alarm = WeekdayScheduler.get_next_alarm_date(alarm_time, weekdays)
        
        if not next_alarm:
            return "Invalid alarm configuration"
        
        now = datetime.datetime.now(tz=LOCAL_TZ)
        time_diff = next_alarm - now
        
        if time_diff.total_seconds() < 0:
            return "Alarm time has passed"
        
        days = time_diff.days
        hours, remainder = divmod(time_diff.seconds, 3600)
        minutes = remainder // 60
        
        if days > 0:
            return f"in {days} day{'s' if days != 1 else ''}, {hours}h {minutes}m"
        elif hours > 0:
            return f"in {hours}h {minutes}m"
        else:
            return f"in {minutes}m"
    
    @staticmethod
    def parse_time_string(time_str: str) -> Optional[Tuple[int, int]]:
        """Parse time string to hour and minute integers.
        
        Args:
            time_str: Time string in "HH:MM" format
            
        Returns:
            Optional[Tuple[int, int]]: (hour, minute) tuple or None if invalid
        """
        try:
            if not AlarmTimeValidator.validate_time_format(time_str):
                return None
            
            hour, minute = map(int, time_str.split(":"))
            return (hour, minute)
        except (ValueError, TypeError):
            return None
        
