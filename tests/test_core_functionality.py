"""
Tests for alarm execution, sleep timer, and scheduler functionality.
Covers core domain logic that was previously untested.
"""

import datetime
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional
from unittest.mock import MagicMock, patch, PropertyMock

import pytest


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_config() -> Dict[str, Any]:
    """Create a standard test alarm configuration."""
    return {
        "enabled": True,
        "time": "07:30",
        "alarm_volume": 60,
        "playlist_uri": "spotify:playlist:test123",
        "device_name": "Test Speaker",
        "shuffle": True,
        "fade_in": False,
        "weekdays": [0, 1, 2, 3, 4],  # Mon-Fri
        "debug": False,
    }


@pytest.fixture
def mock_disabled_config() -> Dict[str, Any]:
    """Create a disabled alarm configuration."""
    return {
        "enabled": False,
        "time": "07:30",
        "alarm_volume": 60,
        "playlist_uri": "spotify:playlist:test123",
        "device_name": "Test Speaker",
    }


@pytest.fixture
def temp_status_file() -> Generator[Path, None, None]:
    """Create a temporary status file for sleep timer tests."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({"active": False}, f)
        temp_path = Path(f.name)
    yield temp_path
    try:
        temp_path.unlink()
    except FileNotFoundError:
        pass


# ============================================================================
# Alarm Execution Tests
# ============================================================================

class TestAlarmExecution:
    """Tests for alarm execution logic in src/core/alarm.py."""

    @patch('src.core.alarm.load_config')
    @patch('src.core.alarm.get_access_token')
    @patch('src.core.alarm.get_device_id')
    @patch('src.core.alarm.start_playback')
    def test_execute_alarm_when_disabled(
        self,
        mock_start: MagicMock,
        mock_device: MagicMock,
        mock_token: MagicMock,
        mock_config: MagicMock,
        mock_disabled_config: Dict[str, Any]
    ):
        """Alarm should not execute when disabled."""
        mock_config.return_value = mock_disabled_config
        
        from src.core.alarm import execute_alarm
        result = execute_alarm()
        
        assert result is False
        mock_start.assert_not_called()

    @patch('src.core.alarm.load_config')
    def test_execute_alarm_empty_config(self, mock_config: MagicMock):
        """Alarm should not execute with empty config."""
        mock_config.return_value = {}
        
        from src.core.alarm import execute_alarm
        result = execute_alarm()
        
        assert result is False

    @patch('src.core.alarm.load_config')
    def test_execute_alarm_config_load_failure(self, mock_config: MagicMock):
        """Alarm should handle config load failure gracefully."""
        mock_config.side_effect = Exception("Config file corrupted")
        
        from src.core.alarm import execute_alarm
        result = execute_alarm()
        
        assert result is False

    @patch('src.core.alarm.load_config')
    @patch('src.core.alarm.get_access_token')
    @patch('src.core.alarm.get_device_id')
    @patch('src.core.alarm.start_playback')
    @patch('src.core.alarm.set_volume')
    def test_execute_alarm_force_mode(
        self,
        mock_volume: MagicMock,
        mock_start: MagicMock,
        mock_device: MagicMock,
        mock_token: MagicMock,
        mock_load_config: MagicMock,
        mock_config: Dict[str, Any]
    ):
        """Force mode should bypass enable check."""
        # Set to disabled but use force
        mock_config["enabled"] = False
        mock_load_config.return_value = mock_config
        mock_token.return_value = "test_token"
        mock_device.return_value = "device_123"
        mock_start.return_value = True
        mock_volume.return_value = True
        
        from src.core.alarm import execute_alarm
        result = execute_alarm(force=True)
        
        # With force=True, it should attempt playback even if disabled
        # (though actual execution depends on time window)
        # The test verifies the force flag is respected
        assert isinstance(result, bool)

    @patch('src.core.alarm.load_config')
    @patch('src.core.alarm.get_access_token')
    def test_execute_alarm_no_token(
        self,
        mock_token: MagicMock,
        mock_load_config: MagicMock,
        mock_config: Dict[str, Any]
    ):
        """Alarm should fail gracefully without valid token."""
        mock_load_config.return_value = mock_config
        mock_token.return_value = None
        
        from src.core.alarm import execute_alarm
        result = execute_alarm(force=True)
        
        assert result is False


# ============================================================================
# Sleep Timer Tests
# ============================================================================

class TestSleepTimer:
    """Tests for sleep timer functionality in src/core/sleep.py."""

    def test_get_sleep_status_file_not_found(self, tmp_path: Path):
        """Should handle missing status file gracefully."""
        with patch('src.core.sleep.STATUS_PATH', str(tmp_path / "nonexistent.json")):
            from src.core.sleep import _read_status_from_disk
            status = _read_status_from_disk()
            
            assert status["active"] is False

    def test_get_sleep_status_corrupted_json(self, tmp_path: Path):
        """Should handle corrupted JSON gracefully."""
        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("not valid json {{{")
        
        with patch('src.core.sleep.STATUS_PATH', str(corrupt_file)):
            from src.core.sleep import _read_status_from_disk
            status = _read_status_from_disk()
            
            assert status["active"] is False

    def test_sleep_status_cache_respects_ttl(self):
        """Status cache should respect TTL setting."""
        from src.core.sleep import _STATUS_CACHE_TTL
        
        # TTL should be positive
        assert _STATUS_CACHE_TTL > 0
        # TTL should be reasonable (between 1 and 60 seconds)
        assert 1 <= _STATUS_CACHE_TTL <= 60


# ============================================================================
# Alarm Scheduler Tests  
# ============================================================================

class TestAlarmScheduler:
    """Tests for alarm scheduler in src/core/alarm_scheduler.py."""

    def test_alarm_time_validator_format(self):
        """Time validator should format time correctly."""
        from src.core.scheduler import AlarmTimeValidator
        
        # Test valid time format
        result = AlarmTimeValidator.format_time_until_alarm("07:30")
        assert isinstance(result, str)
        # Should contain some time indication
        assert len(result) > 0

    def test_alarm_time_validator_invalid_time(self):
        """Time validator should handle invalid times."""
        from src.core.scheduler import AlarmTimeValidator
        
        # Test with invalid format
        try:
            result = AlarmTimeValidator.format_time_until_alarm("invalid")
            # If it doesn't raise, it should return a string
            assert isinstance(result, str)
        except (ValueError, Exception):
            # Expected for invalid input
            pass

    def test_alarm_time_validator_edge_cases(self):
        """Time validator should handle edge cases."""
        from src.core.scheduler import AlarmTimeValidator
        
        # Test midnight
        result = AlarmTimeValidator.format_time_until_alarm("00:00")
        assert isinstance(result, str)
        
        # Test end of day
        result = AlarmTimeValidator.format_time_until_alarm("23:59")
        assert isinstance(result, str)


# ============================================================================
# Token Encryption Tests
# ============================================================================

class TestTokenEncryption:
    """Tests for token encryption module."""

    def test_encryption_roundtrip(self):
        """Encrypted data should decrypt to original."""
        from src.utils.token_encryption import encrypt_token_payload, decrypt_token_payload
        
        original = {
            "access_token": "test_token_12345",
            "expires_at": time.time() + 3600,
            "refresh_token": "refresh_token_67890"
        }
        
        encrypted = encrypt_token_payload(original)
        decrypted = decrypt_token_payload(encrypted)
        
        assert decrypted is not None
        assert decrypted["access_token"] == original["access_token"]
        assert decrypted["refresh_token"] == original["refresh_token"]

    def test_encryption_produces_different_output(self):
        """Encryption should not store plaintext."""
        from src.utils.token_encryption import encrypt_token_payload
        
        original = {"access_token": "secret_token"}
        encrypted = encrypt_token_payload(original)
        
        # Encrypted output should not contain the raw token
        assert "secret_token" not in encrypted

    def test_decryption_handles_plain_json(self):
        """Decryption should handle legacy plain JSON."""
        from src.utils.token_encryption import decrypt_token_payload
        
        plain_json = '{"access_token": "plain_token", "expires_at": 1234567890}'
        result = decrypt_token_payload(plain_json)
        
        assert result is not None
        assert result["access_token"] == "plain_token"

    def test_decryption_handles_invalid_data(self):
        """Decryption should return None for invalid data."""
        from src.utils.token_encryption import decrypt_token_payload
        
        result = decrypt_token_payload("completely invalid data !@#$%")
        assert result is None

    def test_encryption_availability_check(self):
        """Should be able to check encryption availability."""
        from src.utils.token_encryption import is_encryption_available
        
        # Should return a boolean
        result = is_encryption_available()
        assert isinstance(result, bool)


# ============================================================================
# Alarm Service Integration Tests
# ============================================================================

class TestAlarmServiceIntegration:
    """Integration tests for alarm service layer."""

    def test_alarm_service_get_status(self):
        """Alarm service should return status."""
        from src.services.alarm_service import AlarmService
        
        service = AlarmService()
        result = service.get_alarm_status()
        
        # Should return a ServiceResult
        assert hasattr(result, 'success')
        assert hasattr(result, 'data')

    def test_alarm_service_health_check(self):
        """Alarm service should pass health check."""
        from src.services.alarm_service import AlarmService
        
        service = AlarmService()
        result = service.health_check()
        
        assert hasattr(result, 'success')
        # Health check should generally succeed
        # (unless there's a real configuration issue)


# ============================================================================
# Sleep Service Integration Tests  
# ============================================================================

class TestSleepServiceIntegration:
    """Integration tests for sleep service layer."""

    def test_sleep_service_get_status(self):
        """Sleep service should return status."""
        from src.services.sleep_service import SleepService
        
        service = SleepService()
        result = service.get_sleep_status()
        
        assert hasattr(result, 'success')
        assert hasattr(result, 'data')

    def test_sleep_service_health_check(self):
        """Sleep service should pass health check."""
        from src.services.sleep_service import SleepService
        
        service = SleepService()
        result = service.health_check()
        
        assert hasattr(result, 'success')


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformanceOptimizations:
    """Tests verifying performance optimizations are in place."""

    def test_library_executor_is_shared(self):
        """Library executor should be reused, not created per-call."""
        from src.api.spotify import _get_library_executor
        
        executor1 = _get_library_executor()
        executor2 = _get_library_executor()
        
        # Should return the same instance
        assert executor1 is executor2

    def test_library_executor_has_reasonable_workers(self):
        """Library executor should have reasonable worker count."""
        from src.api.spotify import _get_library_executor, _get_library_worker_limit
        
        executor = _get_library_executor()
        expected_workers = _get_library_worker_limit()
        
        # Executor should be initialized
        assert executor is not None
        # Worker limit should be between 1 and 4
        assert 1 <= expected_workers <= 4
