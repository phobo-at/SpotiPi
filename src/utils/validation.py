#!/usr/bin/env python3
"""
🛡️ Input Validation Module for SpotiPi
Provides comprehensive input validation for all user inputs including:
- Volume levels (0-100)
- Time formats (HH:MM)
- Playlist URIs
- Device names
- Duration values
- Weekday selections
"""

import datetime
import re
from dataclasses import dataclass
from typing import Any, Dict, Union


@dataclass
class ValidationResult:
    """Result of input validation with value and error details."""
    is_valid: bool
    value: Any = None
    error: str = ""
    field_name: str = ""

class InputValidator:
    """Centralized input validation for all SpotiPi user inputs."""
    
    # Validation constants
    MIN_VOLUME = 0
    MAX_VOLUME = 100
    MIN_DURATION = 1
    MAX_DURATION = 480  # 8 hours max
    MAX_STRING_LENGTH = 500
    MAX_URI_LENGTH = 200
    
    # Regex patterns
    TIME_PATTERN = re.compile(r'^([0-1]?[0-9]|2[0-3]):([0-5][0-9])$')
    SPOTIFY_URI_PATTERN = re.compile(r'^spotify:(playlist|album|artist|track):[a-zA-Z0-9]{22}$')
    # Allow Unicode characters (emojis, special chars) in device names - Spotify allows them
    # Simplified: allow everything except control characters (< 0x20) and block certain dangerous chars
    # This accepts ASCII, Unicode letters/numbers, emojis, and common punctuation
    DEVICE_NAME_PATTERN = re.compile(r'^[^\x00-\x1F<>]{1,100}$', re.UNICODE)
    
    @classmethod
    def validate_volume(cls, value: Union[str, int, None], field_name: str = "volume") -> ValidationResult:
        """Validate volume input (0-100).
        
        Args:
            value: Volume value to validate
            field_name: Name of the field for error messages
            
        Returns:
            ValidationResult: Validation result with cleaned value or error
        """
        if value is None:
            return ValidationResult(False, None, f"{field_name} is required", field_name)
        
        try:
            volume = int(value)
            if volume < cls.MIN_VOLUME or volume > cls.MAX_VOLUME:
                return ValidationResult(
                    False, None, 
                    f"{field_name} must be between {cls.MIN_VOLUME} and {cls.MAX_VOLUME}", 
                    field_name
                )
            return ValidationResult(True, volume, "", field_name)
        except (ValueError, TypeError):
            return ValidationResult(
                False, None, 
                f"{field_name} must be a valid number between {cls.MIN_VOLUME} and {cls.MAX_VOLUME}", 
                field_name
            )
    
    @classmethod
    def validate_time(cls, value: Union[str, None], field_name: str = "time") -> ValidationResult:
        """Validate time format (HH:MM).
        
        Args:
            value: Time string to validate
            field_name: Name of the field for error messages
            
        Returns:
            ValidationResult: Validation result with cleaned value or error
        """
        if not value:
            return ValidationResult(False, None, f"{field_name} is required", field_name)
        
        if not isinstance(value, str):
            return ValidationResult(False, None, f"{field_name} must be a string", field_name)
        
        value = value.strip()
        if not cls.TIME_PATTERN.match(value):
            return ValidationResult(
                False, None, 
                f"{field_name} must be in HH:MM format (24-hour)", 
                field_name
            )
        
        # Additional validation - check if it's a valid time
        try:
            hour, minute = map(int, value.split(':'))
            datetime.time(hour, minute)
            return ValidationResult(True, value, "", field_name)
        except ValueError:
            return ValidationResult(
                False, None, 
                f"{field_name} contains invalid hour or minute values", 
                field_name
            )
    
    @classmethod
    def validate_duration(cls, value: Union[str, int, None], field_name: str = "duration") -> ValidationResult:
        """Validate duration in minutes.
        
        Args:
            value: Duration value to validate
            field_name: Name of the field for error messages
            
        Returns:
            ValidationResult: Validation result with cleaned value or error
        """
        if value is None:
            return ValidationResult(False, None, f"{field_name} is required", field_name)
        
        try:
            duration = int(value)
            if duration < cls.MIN_DURATION or duration > cls.MAX_DURATION:
                return ValidationResult(
                    False, None, 
                    f"{field_name} must be between {cls.MIN_DURATION} and {cls.MAX_DURATION} minutes", 
                    field_name
                )
            return ValidationResult(True, duration, "", field_name)
        except (ValueError, TypeError):
            return ValidationResult(
                False, None, 
                f"{field_name} must be a valid number between {cls.MIN_DURATION} and {cls.MAX_DURATION}", 
                field_name
            )
    
    @classmethod
    def validate_spotify_uri(cls, value: Union[str, None], field_name: str = "playlist_uri", required: bool = False) -> ValidationResult:
        """Validate Spotify URI format.
        
        Args:
            value: Spotify URI to validate
            field_name: Name of the field for error messages
            required: Whether the field is required
            
        Returns:
            ValidationResult: Validation result with cleaned value or error
        """
        if not value:
            if required:
                return ValidationResult(False, None, f"{field_name} is required", field_name)
            return ValidationResult(True, "", "", field_name)
        
        if not isinstance(value, str):
            return ValidationResult(False, None, f"{field_name} must be a string", field_name)
        
        value = value.strip()
        if len(value) > cls.MAX_URI_LENGTH:
            return ValidationResult(
                False, None, 
                f"{field_name} is too long (max {cls.MAX_URI_LENGTH} characters)", 
                field_name
            )
        
        # Allow empty for optional fields
        if not value:
            return ValidationResult(True, "", "", field_name)
        
        if not cls.SPOTIFY_URI_PATTERN.match(value):
            return ValidationResult(
                False, None, 
                f"{field_name} must be a valid Spotify URI (spotify:type:id)", 
                field_name
            )
        
        return ValidationResult(True, value, "", field_name)
    
    @classmethod
    def validate_device_name(cls, value: Union[str, None], field_name: str = "device_name", required: bool = False) -> ValidationResult:
        """Validate device name.
        
        Args:
            value: Device name to validate
            field_name: Name of the field for error messages
            required: Whether the field is required
            
        Returns:
            ValidationResult: Validation result with cleaned value or error
        """
        if not value:
            if required:
                return ValidationResult(False, None, f"{field_name} is required", field_name)
            return ValidationResult(True, "", "", field_name)
        
        if not isinstance(value, str):
            return ValidationResult(False, None, f"{field_name} must be a string", field_name)
        
        value = value.strip()
        if len(value) > 100:
            return ValidationResult(
                False, None, 
                f"{field_name} is too long (max 100 characters)", 
                field_name
            )
        
        if not cls.DEVICE_NAME_PATTERN.match(value):
            return ValidationResult(
                False, None, 
                f"{field_name} contains invalid characters", 
                field_name
            )
        
        return ValidationResult(True, value, "", field_name)
    
    @classmethod
    def validate_boolean(cls, value: Union[str, bool, None], field_name: str = "enabled") -> ValidationResult:
        """Validate boolean input.
        
        Args:
            value: Boolean value to validate
            field_name: Name of the field for error messages
            
        Returns:
            ValidationResult: Validation result with cleaned value or error
        """
        if value is None:
            return ValidationResult(True, False, "", field_name)
        
        if isinstance(value, bool):
            return ValidationResult(True, value, "", field_name)
        
        if isinstance(value, str):
            lower_value = value.lower().strip()
            if lower_value in ('true', '1', 'on', 'yes', 'enabled'):
                return ValidationResult(True, True, "", field_name)
            elif lower_value in ('false', '0', 'off', 'no', 'disabled', ''):
                return ValidationResult(True, False, "", field_name)
        
        return ValidationResult(True, bool(value), "", field_name)

class ValidationError(Exception):
    """Custom exception for validation errors."""
    
    def __init__(self, field_name: str, message: str):
        self.field_name = field_name
        self.message = message
        super().__init__(f"{field_name}: {message}")

def validate_alarm_config(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate complete alarm configuration.
    
    Args:
        form_data: Form data dictionary to validate
        
    Returns:
        Dict[str, Any]: Validated configuration
        
    Raises:
        ValidationError: If any validation fails
    """
    validated = {}
    
    # Time validation
    time_result = InputValidator.validate_time(form_data.get('time'), 'alarm_time')
    if not time_result.is_valid:
        raise ValidationError(time_result.field_name, time_result.error)
    validated['time'] = time_result.value
    
    # Volume validation
    volume_result = InputValidator.validate_volume(form_data.get('volume', 50), 'volume')
    if not volume_result.is_valid:
        raise ValidationError(volume_result.field_name, volume_result.error)
    validated['volume'] = volume_result.value
    
    # Alarm volume validation
    alarm_volume_result = InputValidator.validate_volume(form_data.get('alarm_volume', 50), 'alarm_volume')
    if not alarm_volume_result.is_valid:
        raise ValidationError(alarm_volume_result.field_name, alarm_volume_result.error)
    validated['alarm_volume'] = alarm_volume_result.value
    
    # Playlist URI validation (optional)
    uri_result = InputValidator.validate_spotify_uri(form_data.get('playlist_uri'), 'playlist_uri', required=False)
    if not uri_result.is_valid:
        raise ValidationError(uri_result.field_name, uri_result.error)
    validated['playlist_uri'] = uri_result.value
    
    # Device name validation (optional)
    device_result = InputValidator.validate_device_name(form_data.get('device_name'), 'device_name', required=False)
    if not device_result.is_valid:
        raise ValidationError(device_result.field_name, device_result.error)
    validated['device_name'] = device_result.value
    
    # Boolean fields
    for field in ['enabled', 'fade_in', 'shuffle']:
        bool_result = InputValidator.validate_boolean(form_data.get(field), field)
        validated[field] = bool_result.value
    
    return validated

def validate_sleep_config(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate sleep timer configuration.
    
    Args:
        form_data: Form data dictionary to validate
        
    Returns:
        Dict[str, Any]: Validated configuration
        
    Raises:
        ValidationError: If any validation fails
    """
    validated = {}
    
    # Duration validation
    duration_value = form_data.get('duration', '30')
    if duration_value == 'custom':
        duration_value = form_data.get('custom_duration', '30')
    
    duration_result = InputValidator.validate_duration(duration_value, 'duration')
    if not duration_result.is_valid:
        raise ValidationError(duration_result.field_name, duration_result.error)
    validated['duration_minutes'] = duration_result.value
    
    # Volume validation
    volume_result = InputValidator.validate_volume(form_data.get('sleep_volume', 30), 'sleep_volume')
    if not volume_result.is_valid:
        raise ValidationError(volume_result.field_name, volume_result.error)
    validated['volume'] = volume_result.value
    
    # Playlist URI validation (optional)
    uri_result = InputValidator.validate_spotify_uri(form_data.get('playlist_uri'), 'playlist_uri', required=False)
    if not uri_result.is_valid:
        raise ValidationError(uri_result.field_name, uri_result.error)
    validated['playlist_uri'] = uri_result.value
    
    # Device name validation (optional)
    device_result = InputValidator.validate_device_name(form_data.get('device_name'), 'device_name', required=False)
    if not device_result.is_valid:
        raise ValidationError(device_result.field_name, device_result.error)
    validated['device_name'] = device_result.value
    
    # Shuffle validation (optional, defaults to False)
    shuffle_value = form_data.get('shuffle', 'off')
    validated['shuffle'] = shuffle_value == 'on' if isinstance(shuffle_value, str) else bool(shuffle_value)
    
    return validated

def validate_volume_only(form_data: Dict[str, Any]) -> int:
    """Validate standalone volume input.
    
    Args:
        form_data: Form data dictionary containing volume
        
    Returns:
        int: Validated volume value
        
    Raises:
        ValidationError: If validation fails
    """
    volume_result = InputValidator.validate_volume(form_data.get('volume'), 'volume')
    if not volume_result.is_valid:
        raise ValidationError(volume_result.field_name, volume_result.error)
    return volume_result.value
