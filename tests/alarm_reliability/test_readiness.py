import datetime
from zoneinfo import ZoneInfo

from src.core.alarm_logging import AlarmProbeContext
from src.core.alarm_scheduler import AlarmScheduler


TZ = ZoneInfo("Europe/Vienna")


def make_context():
    scheduled = datetime.datetime(2025, 1, 1, 7, 0, tzinfo=TZ)
    return AlarmProbeContext(
        scheduled_at=scheduled,
        timezone=TZ,
        alarm_time="07:00",
        config_snapshot={"device_name": "Living Room"},
    )


def test_readiness_fails_until_network_and_token(monkeypatch):
    scheduler = AlarmScheduler()
    context = make_context()

    # First probe: everything offline
    monkeypatch.setattr("src.core.alarm_scheduler.check_network_ready", lambda: False)
    monkeypatch.setattr(AlarmScheduler, "_resolve_dns", lambda self: False)
    monkeypatch.setattr("src.core.alarm_scheduler.get_access_token", lambda: None)
    readiness = scheduler._perform_readiness_checks(context)
    assert readiness["ready"] is False
    assert readiness["network_ready"] is False
    assert readiness["dns_ok"] is False
    assert readiness["token_available"] is False

    # Second probe: full recovery
    monkeypatch.setattr("src.core.alarm_scheduler.check_network_ready", lambda: True)
    monkeypatch.setattr(AlarmScheduler, "_resolve_dns", lambda self: True)
    monkeypatch.setattr("src.core.alarm_scheduler.get_access_token", lambda: "token")
    monkeypatch.setattr("src.core.alarm_scheduler.get_device_id", lambda token, name: "device-123")
    readiness = scheduler._perform_readiness_checks(context)
    assert readiness["ready"] is True
    assert readiness["network_ready"] is True
    assert readiness["dns_ok"] is True
    assert readiness["token_available"] is True
    assert readiness["device_ready"] is True
