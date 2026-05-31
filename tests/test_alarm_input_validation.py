"""Tests for weekday handling in alarm form input validation.

Covers the form-data path (`validate_alarm_config` / `InputValidator.validate_weekdays`),
which parses JSON-array strings as sent by the frontend. The Pydantic schema
validation (config_schema.py) is covered separately in test_config_validation.py.
"""

import pytest

from src.utils.validation import (
    InputValidator,
    ValidationError,
    validate_alarm_config,
)


def _base_form(**overrides):
    form = {
        "time": "07:00",
        "volume": "50",
        "alarm_volume": "50",
        "playlist_uri": "",
        "device_name": "Living Room",
        "enabled": "on",
    }
    form.update(overrides)
    return form


class TestValidateWeekdays:
    def test_none_returns_none(self):
        result = InputValidator.validate_weekdays(None)
        assert result.is_valid
        assert result.value is None

    def test_empty_string_returns_none(self):
        result = InputValidator.validate_weekdays("")
        assert result.is_valid
        assert result.value is None

    def test_empty_array_returns_none(self):
        result = InputValidator.validate_weekdays("[]")
        assert result.is_valid
        assert result.value is None

    def test_json_string_parsed_sorted_deduped(self):
        result = InputValidator.validate_weekdays("[4, 1, 1, 0]")
        assert result.is_valid
        assert result.value == [0, 1, 4]

    def test_list_input(self):
        result = InputValidator.validate_weekdays([2, 3])
        assert result.is_valid
        assert result.value == [2, 3]

    def test_out_of_range_invalid(self):
        result = InputValidator.validate_weekdays("[0, 7]")
        assert not result.is_valid
        assert result.field_name == "weekdays"

    def test_negative_invalid(self):
        result = InputValidator.validate_weekdays("[-1]")
        assert not result.is_valid

    def test_malformed_json_invalid(self):
        result = InputValidator.validate_weekdays("not-json")
        assert not result.is_valid

    def test_non_integer_invalid(self):
        result = InputValidator.validate_weekdays("[1, \"x\"]")
        assert not result.is_valid

    def test_bool_rejected(self):
        # bool is a subclass of int and must not be accepted as a weekday.
        result = InputValidator.validate_weekdays([True])
        assert not result.is_valid


class TestValidateAlarmConfigWeekdays:
    def test_workdays_preset(self):
        validated = validate_alarm_config(_base_form(weekdays="[0,1,2,3,4]"))
        assert validated["weekdays"] == [0, 1, 2, 3, 4]

    def test_missing_weekdays_defaults_none(self):
        validated = validate_alarm_config(_base_form())
        assert validated["weekdays"] is None

    def test_invalid_weekdays_raises(self):
        with pytest.raises(ValidationError) as exc:
            validate_alarm_config(_base_form(weekdays="[9]"))
        assert exc.value.field_name == "weekdays"
