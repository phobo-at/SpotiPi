import datetime
from zoneinfo import ZoneInfo

import pytest

from src.core import alarm
from src.core import scheduler


TZ = ZoneInfo("Europe/Vienna")


def test_next_alarm_datetime_t_plus_90_seconds():
    reference = datetime.datetime(2025, 1, 1, 6, 58, 30, tzinfo=TZ)
    target = scheduler.next_alarm_datetime("07:00", reference=reference)
    assert target is not None
    delta = (target - reference).total_seconds()
    assert delta == pytest.approx(90.0, abs=0.01)


def test_next_alarm_datetime_handles_dst_forward_gap():
    # Europe/Vienna skips from 02:00 to 03:00 on 2024-03-31
    reference = datetime.datetime(2024, 3, 31, 1, 30, tzinfo=TZ)
    target = scheduler.next_alarm_datetime("02:30", reference=reference)
    assert target is not None
    assert target.hour == 3
    assert target.minute == 30
    # Ensure the alarm still fires on the same calendar day
    assert target.date() == reference.date()


def test_next_alarm_datetime_handles_dst_backward_overlap():
    # Last Sunday in October repeats the 02:00 hour; we expect the earliest slot.
    reference = datetime.datetime(2024, 10, 27, 0, 45, tzinfo=TZ)
    target = scheduler.next_alarm_datetime("02:15", reference=reference)
    assert target is not None
    assert target.hour == 2
    assert target.minute == 15
    assert target.fold == 0  # earliest occurrence


def test_execute_alarm_catchup_within_grace(monkeypatch):
    fixed_now = datetime.datetime(2025, 1, 1, 7, 2, tzinfo=TZ)

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    config = {
        "enabled": True,
        "time": "07:00",
        "device_name": "Living Room",
        "playlist_uri": "spotify:playlist:test",
        "alarm_volume": 50,
        "fade_in": False,
        "shuffle": False,
        "last_known_devices": {},
    }

    class DummyTransaction:
        def __init__(self):
            self._config = config.copy()
            self.saved = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def load(self):
            return self._config.copy()

        def save(self, cfg):
            self.saved = cfg.copy()

    transaction = DummyTransaction()

    monkeypatch.setattr(alarm.datetime, "datetime", FixedDateTime)
    monkeypatch.setattr(alarm, "load_config", lambda: config.copy())
    monkeypatch.setattr(alarm, "get_access_token", lambda: "token")
    monkeypatch.setattr(alarm, "get_device_id", lambda token, name: "device-123")
    monkeypatch.setattr(alarm, "set_volume", lambda *args, **kwargs: True)
    monkeypatch.setattr(alarm, "start_playback", lambda *args, **kwargs: None)
    monkeypatch.setattr(alarm, "config_transaction", lambda: transaction)

    result = alarm.execute_alarm(
        catchup_grace_seconds=600,
    )
    assert result is True
    assert transaction.saved is not None
    assert transaction.saved["enabled"] is False


def test_pending_state_alarm_handles_recent_miss(monkeypatch):
    from src.core.alarm_scheduler import AlarmScheduler

    scheduler_instance = AlarmScheduler()
    scheduled_utc = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(seconds=120)
    scheduler_instance._state = {
        "scheduled_utc": scheduled_utc.isoformat(),
        "alarm_time": "07:00",
    }
    scheduler_instance._last_alarm_time = "07:00"

    pending = scheduler_instance._pending_state_alarm()
    assert pending is not None
    delta = (datetime.datetime.now(tz=datetime.timezone.utc) - pending.astimezone(datetime.timezone.utc)).total_seconds()
    assert delta == pytest.approx(120, abs=5)
