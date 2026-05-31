#!/usr/bin/env python3
"""
Alarm time utilities for single-use and recurring (weekday) alarms.
"""

from __future__ import annotations

import datetime
from typing import Optional, Sequence, Tuple

from ..utils.timezone import get_local_timezone

LOCAL_TZ = get_local_timezone()


def _normalize_weekdays(weekdays: Optional[Sequence[int]]) -> Optional[set[int]]:
    """Return a set of valid 0-6 weekday ints, or ``None`` for daily/once.

    Empty or ``None`` means "no weekday restriction" (single-use semantics).
    Invalid entries are silently dropped; callers validate stricter upstream.
    """
    if not weekdays:
        return None
    valid = {day for day in weekdays if isinstance(day, int) and 0 <= day <= 6}
    return valid or None


def _coerce_time_components(alarm_time: str) -> Optional[Tuple[int, int]]:
    """Return (hour, minute) tuple if ``alarm_time`` is valid."""
    try:
        hour, minute = map(int, alarm_time.split(":"))
    except (ValueError, AttributeError):
        return None
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return hour, minute
    return None


def next_alarm_datetime(
    alarm_time: str,
    reference: Optional[datetime.datetime] = None,
    weekdays: Optional[Sequence[int]] = None,
) -> Optional[datetime.datetime]:
    """Return the next datetime that matches ``alarm_time`` in the local timezone.

    When ``weekdays`` is a non-empty list of ints (0=Monday … 6=Sunday), the
    result is advanced to the next day whose weekday is in the set. ``None`` or
    an empty list keeps the original single-use behaviour (today or tomorrow).
    """
    components = _coerce_time_components(alarm_time)
    if components is None:
        return None

    hour, minute = components
    allowed_days = _normalize_weekdays(weekdays)
    now = reference.astimezone(LOCAL_TZ) if reference is not None else datetime.datetime.now(tz=LOCAL_TZ)

    def _normalize(target: datetime.datetime) -> datetime.datetime:
        """Adjust for DST gaps/overlaps by round-tripping through UTC."""
        if target.tzinfo is None:
            target = target.replace(tzinfo=LOCAL_TZ)
        roundtrip = target.astimezone(datetime.timezone.utc).astimezone(LOCAL_TZ)
        if (
            roundtrip.hour != target.hour
            or roundtrip.minute != target.minute
            or roundtrip.second != target.second
            or roundtrip.fold != target.fold
        ):
            return roundtrip
        return target

    def _at(day: datetime.date) -> Optional[datetime.datetime]:
        try:
            return _normalize(
                datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL_TZ)
            )
        except ValueError:
            return None

    # Search forward day-by-day for the first matching, future occurrence.
    # 8-day cap guarantees a full week is covered (plus today) even with DST.
    base = now.date()
    for offset in range(0, 9):
        candidate = _at(base + datetime.timedelta(days=offset))
        if candidate is None:
            continue
        if candidate <= now:
            continue
        if allowed_days is not None and candidate.weekday() not in allowed_days:
            continue
        return candidate
    return None


class AlarmTimeValidator:
    """Validate and format alarm times."""

    @staticmethod
    def validate_time_format(time_str: str) -> bool:
        """Return True if ``time_str`` is in HH:MM format."""
        return _coerce_time_components(time_str) is not None

    @staticmethod
    def is_alarm_time_now(alarm_time: str, tolerance_minutes: float = 1.5) -> bool:
        """Check whether the current time is within tolerance of ``alarm_time``."""
        components = _coerce_time_components(alarm_time)
        if components is None:
            return False

        hour, minute = components
        now = datetime.datetime.now(tz=LOCAL_TZ)
        target_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        diff_minutes = abs((now - target_today).total_seconds() / 60)
        return diff_minutes <= tolerance_minutes

    @staticmethod
    def format_time_until_alarm(
        alarm_time: str, weekdays: Optional[Sequence[int]] = None
    ) -> str:
        """Return human-readable delta until the next alarm."""
        next_dt = next_alarm_datetime(alarm_time, weekdays=weekdays)
        if not next_dt:
            return "Invalid alarm time"

        now = datetime.datetime.now(tz=LOCAL_TZ)
        delta = next_dt - now
        if delta.total_seconds() < 0:
            return "Alarm time has passed"

        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes = remainder // 60

        if days > 0:
            return f"in {days} day{'s' if days != 1 else ''}, {hours}h {minutes}m"
        if hours > 0:
            return f"in {hours}h {minutes}m"
        return f"in {minutes}m"

    @staticmethod
    def parse_time_string(time_str: str) -> Optional[Tuple[int, int]]:
        """Parse HH:MM string into ``(hour, minute)`` if valid."""
        return _coerce_time_components(time_str)

    @staticmethod
    def get_next_alarm_date(
        alarm_time: str,
        reference: Optional[datetime.datetime] = None,
        weekdays: Optional[Sequence[int]] = None,
    ) -> Optional[datetime.datetime]:
        """Backwards-compatible wrapper for legacy imports."""
        return next_alarm_datetime(alarm_time, reference=reference, weekdays=weekdays)
