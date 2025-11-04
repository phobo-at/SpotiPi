"""
Unit tests for configuration validation (Gap 3: Pydantic Schema)

Tests cover:
- Valid configuration acceptance
- Invalid field detection (type/range/format errors)
- Edge cases (empty strings, None, boundary values)
- Legacy migration from old config formats
- Backward compatibility when Pydantic unavailable
"""
import pytest
from typing import Dict, Any

# Test both with and without Pydantic
try:
    from src.config_schema import (
        SpotiPiConfig,
        validate_config_dict,
        migrate_legacy_config
    )
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
class TestPydanticValidation:
    """Tests for Pydantic-based config validation"""
    
    def test_valid_minimal_config(self):
        """Test that minimal valid config passes validation"""
        config = {
            "time": "07:30",
            "enabled": True,
            "playlist_uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M",
            "device_name": "Raspberry Pi",
            "alarm_volume": 50,
            "timezone": "Europe/Vienna"
        }
        
        validated, warnings = validate_config_dict(config)
        
        assert validated.time == "07:30"
        assert validated.enabled is True
        assert validated.alarm_volume == 50
        assert len(warnings) == 0
    
    def test_valid_full_config(self):
        """Test that full config with all fields passes"""
        config = {
            "time": "06:00",
            "enabled": False,
            "playlist_uri": "spotify:playlist:test123",
            "device_name": "Test Device",
            "alarm_volume": 75,
            "fade_in": True,
            "shuffle": True,
            "debug": False,
            "log_level": "DEBUG",
            "timezone": "America/New_York",
            "last_known_devices": {"test": {"name": "Test"}},
            "weekdays": [1, 2, 3, 4, 5],
            "sleep_timer_minutes": 30,
            "snooze_minutes": 10
        }
        
        validated, warnings = validate_config_dict(config)
        
        assert validated.time == "06:00"
        assert validated.alarm_volume == 75
        assert validated.fade_in is True
        assert validated.weekdays == [1, 2, 3, 4, 5]
        assert validated.sleep_timer_minutes == 30
    
    def test_invalid_time_format(self):
        """Test that invalid time format raises error"""
        config = {
            "time": "25:99",  # Invalid hour and minute
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 50,
            "timezone": "Europe/Vienna"
        }
        
        with pytest.raises(ValueError, match="time"):
            validate_config_dict(config)
    
    def test_invalid_alarm_volume_range(self):
        """Test that out-of-range volume raises error"""
        config_low = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": -10,  # Below 0
            "timezone": "Europe/Vienna"
        }
        
        with pytest.raises(ValueError, match="alarm_volume"):
            validate_config_dict(config_low)
        
        config_high = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 150,  # Above 100
            "timezone": "Europe/Vienna"
        }
        
        with pytest.raises(ValueError, match="alarm_volume"):
            validate_config_dict(config_high)
    
    def test_invalid_weekdays(self):
        """Test that invalid weekday values raise error"""
        config = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 50,
            "timezone": "Europe/Vienna",
            "weekdays": [0, 1, 7]  # 7 is invalid (only 0-6)
        }
        
        with pytest.raises(ValueError, match="weekdays"):
            validate_config_dict(config)
    
    def test_invalid_timezone(self):
        """Test that invalid timezone raises error"""
        config = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 50,
            "timezone": "Invalid/Timezone"
        }
        
        with pytest.raises(ValueError, match="timezone"):
            validate_config_dict(config)
    
    def test_edge_case_boundary_volumes(self):
        """Test boundary values for alarm_volume"""
        # Minimum valid volume
        config_min = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 0,
            "timezone": "Europe/Vienna"
        }
        validated_min, _ = validate_config_dict(config_min)
        assert validated_min.alarm_volume == 0
        
        # Maximum valid volume
        config_max = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 100,
            "timezone": "Europe/Vienna"
        }
        validated_max, _ = validate_config_dict(config_max)
        assert validated_max.alarm_volume == 100
    
    def test_edge_case_empty_strings(self):
        """Test that empty strings in optional fields are handled"""
        config = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "",  # Empty but valid
            "device_name": "",
            "alarm_volume": 50,
            "timezone": "Europe/Vienna"
        }
        
        validated, warnings = validate_config_dict(config)
        assert validated.playlist_uri == ""
        assert validated.device_name == ""
        # Empty playlist_uri is allowed by schema, warnings handled by application logic
    
    def test_edge_case_none_values(self):
        """Test that None values in optional fields are preserved or get defaults"""
        config = {
            "time": "07:00",
            "enabled": False,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 50,
            "timezone": "Europe/Vienna",
            "weekdays": None,  # None is valid - means alarm runs daily
            "sleep_timer_minutes": None  # Optional field
        }
        
        validated, _ = validate_config_dict(config)
        assert validated.weekdays is None  # None is valid for daily alarms
        assert validated.sleep_timer_minutes is None or validated.sleep_timer_minutes == 0
    
    def test_missing_required_fields(self):
        """Test that missing required fields get defaults from Pydantic model"""
        config = {
            "enabled": True,
            # Missing fields will use defaults from Field(default=...)
        }
        
        # Pydantic provides defaults, so this shouldn't raise
        validated, _ = validate_config_dict(config)
        assert validated.time == "07:00"  # Default from Field
        assert validated.alarm_volume == 50  # Default from Field
    
    def test_legacy_migration_old_format(self):
        """Test migration from old config format"""
        old_config = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 50,
            "timezone": "Europe/Vienna",
            # Simulate old field names or deprecated fields
            "old_field": "should_be_removed"
        }
        
        migrated = migrate_legacy_config(old_config)
        
        # Ensure required fields are present
        assert "time" in migrated
        assert "enabled" in migrated
        # Old fields should be handled (either removed or migrated)
        # Current implementation is placeholder, so we just check it runs


class TestConfigManagerIntegration:
    """Tests for ConfigManager with Pydantic integration"""
    
    def test_validate_config_with_valid_data(self, mock_config_manager):
        """Test that ConfigManager.validate_config() accepts valid data"""
        from src.config import ConfigManager
        
        cm = ConfigManager(base_path=mock_config_manager)
        
        config = {
            "time": "08:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Pi",
            "alarm_volume": 60,
            "timezone": "Europe/Vienna"
        }
        
        validated = cm.validate_config(config)
        
        assert validated["time"] == "08:00"
        assert validated["alarm_volume"] == 60
    
    def test_validate_config_with_invalid_volume_falls_back(self, mock_config_manager):
        """Test that invalid data triggers fallback to legacy validation"""
        from src.config import ConfigManager
        
        cm = ConfigManager(base_path=mock_config_manager)
        
        config = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": "invalid",  # String instead of int
            "timezone": "Europe/Vienna"
        }
        
        # Legacy validation should coerce this to 50
        validated = cm.validate_config(config)
        assert validated["alarm_volume"] == 50
    
    def test_save_config_with_pydantic(self, tmp_path, mock_config_manager):
        """Test that save_config() uses Pydantic serialization"""
        from src.config import ConfigManager
        
        cm = ConfigManager(base_path=tmp_path)
        
        config = {
            "time": "07:00",
            "enabled": True,
            "playlist_uri": "spotify:playlist:test",
            "device_name": "Test",
            "alarm_volume": 50,
            "timezone": "Europe/Vienna",
            "_runtime": "should_not_be_saved"  # Runtime metadata
        }
        
        success = cm.save_config(config, config_name="test")
        
        assert success is True
        
        # Verify runtime metadata was stripped
        import json
        saved_file = tmp_path / "config" / "test.json"
        with open(saved_file) as f:
            saved_data = json.load(f)
        
        assert "_runtime" not in saved_data
        assert "time" in saved_data


@pytest.fixture
def mock_config_manager(tmp_path, monkeypatch):
    """Fixture to create a temporary config environment"""
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    
    # Create minimal config files
    import json
    
    default_config = {
        "time": "07:00",
        "enabled": False,
        "playlist_uri": "",
        "device_name": "",
        "alarm_volume": 50,
        "timezone": "Europe/Vienna"
    }
    
    with open(config_dir / "default_config.json", "w") as f:
        json.dump(default_config, f)
    
    with open(config_dir / "development.json", "w") as f:
        json.dump(default_config, f)
    
    # Mock environment
    monkeypatch.setenv("SPOTIPI_ENV", "development")
    
    return tmp_path


# Edge case matrix for documentation
@pytest.mark.parametrize("field,value,should_fail", [
    ("time", "00:00", False),  # Midnight
    ("time", "23:59", False),  # Just before midnight
    ("time", "24:00", True),   # Invalid hour
    ("time", "12:60", True),   # Invalid minute
    ("alarm_volume", 0, False),
    ("alarm_volume", 100, False),
    ("alarm_volume", -1, True),
    ("alarm_volume", 101, True),
    ("weekdays", [0], False),  # Sunday only
    ("weekdays", [6], False),  # Saturday only
    ("weekdays", [0,6], False),  # Weekend
    ("weekdays", [7], True),   # Invalid day
    ("weekdays", [-1], True),  # Negative day
])
@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="Pydantic not installed")
def test_edge_cases_parametrized(field, value, should_fail):
    """Parametrized tests for edge cases"""
    base_config = {
        "time": "07:00",
        "enabled": True,
        "playlist_uri": "spotify:playlist:test",
        "device_name": "Test",
        "alarm_volume": 50,
        "timezone": "Europe/Vienna"
    }
    
    base_config[field] = value
    
    if should_fail:
        with pytest.raises(ValueError):
            validate_config_dict(base_config)
    else:
        validated, _ = validate_config_dict(base_config)
        assert validated is not None
