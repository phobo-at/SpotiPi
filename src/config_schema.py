"""
Pydantic models for SpotiPi configuration validation

This module provides type-safe configuration schemas with automatic validation,
preventing runtime errors from malformed config files.

Since v1.3.8 - Part of config-schema-validation improvements
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class AlarmConfig(BaseModel):
    """Alarm-specific configuration settings."""
    
    enabled: bool = Field(default=False, description="Whether the alarm is enabled")
    time: str = Field(default="07:00", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Alarm time in HH:MM format")
    playlist_uri: str = Field(default="", description="Spotify URI for alarm playlist/album/track")
    device_name: str = Field(default="", description="Target Spotify device name")
    alarm_volume: int = Field(default=50, ge=0, le=100, description="Playback volume (0-100)")
    fade_in: bool = Field(default=False, description="Enable gradual volume fade-in")
    shuffle: bool = Field(default=False, description="Enable shuffle playback")
    weekdays: Optional[list[int]] = Field(default=None, description="Days of week (0=Monday, 6=Sunday). None = daily")
    
    @field_validator('weekdays')
    @classmethod
    def validate_weekdays(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        """Validate weekdays are in 0-6 range."""
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("weekdays must be a list")
        for day in v:
            if not isinstance(day, int) or day < 0 or day > 6:
                raise ValueError(f"Invalid weekday value: {day}. Must be 0-6 (0=Monday, 6=Sunday)")
        return sorted(set(v))  # Remove duplicates and sort


class SleepTimerConfig(BaseModel):
    """Sleep timer configuration settings."""
    
    sleep_volume: int = Field(default=30, ge=0, le=100, description="Sleep timer volume (0-100)")
    sleep_default_duration: int = Field(default=30, ge=1, le=240, description="Default duration in minutes")
    sleep_playlist_uri: str = Field(default="", description="Spotify URI for sleep playlist")
    sleep_device_name: str = Field(default="", description="Target device for sleep timer")


class RuntimeConfig(BaseModel):
    """Runtime/deployment configuration."""
    
    environment: str = Field(default="development", description="Runtime environment (development/production)")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$", description="Logging level")
    timezone: str = Field(default="Europe/Vienna", description="Timezone for alarm scheduling")
    
    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string."""
        try:
            ZoneInfo(v)
            return v
        except ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {v}")


class DeviceCacheConfig(BaseModel):
    """Device cache for faster lookups."""
    
    last_known_devices: Dict[str, Any] = Field(default_factory=dict, description="Cached Spotify devices")


class SpotiPiConfig(BaseModel):
    """Complete SpotiPi configuration schema.
    
    This is the master schema that validates all configuration files.
    Any config loaded must conform to this schema, preventing runtime errors
    from malformed or incomplete configurations.
    
    Example:
        >>> config_dict = json.load(open("config/production.json"))
        >>> validated_config = SpotiPiConfig(**config_dict)
        >>> print(validated_config.alarm_volume)  # Type-safe access
        50
    """
    
    # Alarm settings
    enabled: bool = Field(default=False, description="Whether the alarm is enabled")
    time: str = Field(default="07:00", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$", description="Alarm time in HH:MM format")
    playlist_uri: str = Field(default="", description="Spotify URI for alarm playlist/album/track")
    device_name: str = Field(default="", description="Target Spotify device name")
    alarm_volume: int = Field(default=50, ge=0, le=100, description="Playback volume (0-100)")
    fade_in: bool = Field(default=False, description="Enable gradual volume fade-in")
    shuffle: bool = Field(default=False, description="Enable shuffle playback")
    weekdays: Optional[list[int]] = Field(default=None, description="Days of week (0=Monday, 6=Sunday). None = daily")
    
    # Sleep timer settings
    sleep_volume: int = Field(default=30, ge=0, le=100, description="Sleep timer volume (0-100)")
    sleep_default_duration: int = Field(default=30, ge=1, le=240, description="Default duration in minutes")
    sleep_playlist_uri: str = Field(default="", description="Spotify URI for sleep playlist")
    sleep_device_name: str = Field(default="", description="Target device for sleep timer")
    
    # Runtime settings
    environment: str = Field(default="development", description="Runtime environment")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", pattern=r"^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$", description="Logging level")
    timezone: str = Field(default="Europe/Vienna", description="Timezone for alarm scheduling")
    
    # Device cache
    last_known_devices: Dict[str, Any] = Field(default_factory=dict, description="Cached Spotify devices")
    
    # Runtime metadata (not saved to file)
    _runtime: Optional[Dict[str, Any]] = None
    
    model_config = {
        "extra": "allow",  # Allow extra fields for forward compatibility
        "str_strip_whitespace": True,  # Auto-trim strings
        "validate_assignment": True,  # Validate on attribute assignment
    }
    
    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string."""
        try:
            ZoneInfo(v)
            return v
        except ZoneInfoNotFoundError:
            raise ValueError(f"Invalid timezone: {v}. Must be a valid IANA timezone (e.g., 'Europe/Vienna')")
    
    @field_validator('weekdays')
    @classmethod
    def validate_weekdays(cls, v: Optional[list[int]]) -> Optional[list[int]]:
        """Validate weekdays are in 0-6 range."""
        if v is None:
            return None
        if not isinstance(v, list):
            raise ValueError("weekdays must be a list of integers")
        for day in v:
            if not isinstance(day, int) or day < 0 or day > 6:
                raise ValueError(f"Invalid weekday value: {day}. Must be 0-6 (0=Monday, 6=Sunday)")
        return sorted(set(v))  # Remove duplicates and sort
    
    @model_validator(mode='after')
    def validate_alarm_settings(self) -> 'SpotiPiConfig':
        """Cross-field validation for alarm settings."""
        if self.enabled:
            # Warn if alarm is enabled without playlist
            if not self.playlist_uri:
                # Don't raise error, just use default
                pass
            
            # Warn if alarm is enabled without device
            if not self.device_name and not self.last_known_devices:
                # Don't raise error, device will be selected at runtime
                pass
        
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values and private fields."""
        return self.model_dump(
            exclude_none=False,
            exclude={'_runtime'},
            mode='json'
        )
    
    def to_json_safe(self) -> Dict[str, Any]:
        """Convert to JSON-safe dictionary (for saving to file)."""
        data = self.to_dict()
        # Remove runtime-only fields that shouldn't be persisted
        data.pop('_runtime', None)
        return data


def validate_config_dict(config_dict: Dict[str, Any]) -> tuple[SpotiPiConfig, list[str]]:
    """Validate a config dictionary against the schema.
    
    Args:
        config_dict: Raw configuration dictionary from JSON
    
    Returns:
        Tuple of (validated_config, warnings_list)
        
    Raises:
        ValueError: If config is invalid with detailed error messages
    """
    warnings = []
    
    try:
        validated = SpotiPiConfig(**config_dict)
        
        # Check for deprecated fields (for future migrations)
        # Example: if 'old_field' in config_dict:
        #     warnings.append("Field 'old_field' is deprecated, use 'new_field' instead")
        
        return validated, warnings
        
    except Exception as e:
        raise ValueError(f"Configuration validation failed: {str(e)}")


def migrate_legacy_config(config_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate legacy config formats to current schema.
    
    Args:
        config_dict: Raw config dictionary (potentially legacy format)
    
    Returns:
        Migrated config dictionary
    """
    migrated = config_dict.copy()
    
    # Add future migrations here
    # Example:
    # if 'old_alarm_time' in migrated:
    #     migrated['time'] = migrated.pop('old_alarm_time')
    
    return migrated
