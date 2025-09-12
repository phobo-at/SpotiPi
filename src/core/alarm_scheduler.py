"""Event-driven alarm scheduler to replace minute-based polling.

- Computes next alarm timestamp using existing WeekdayScheduler
- Sleeps until just before trigger window instead of waking every minute
- Reacts immediately to config changes via thread-safe config change listener
- Uses ALARM_TRIGGER_WINDOW_MINUTES for final execution window
"""
from __future__ import annotations
import threading
import time
import datetime as _dt
from typing import Optional
import logging

from .alarm import execute_alarm
from .scheduler import WeekdayScheduler, AlarmTimeValidator
from ..config import load_config
from ..constants import ALARM_TRIGGER_WINDOW_MINUTES
from ..utils.thread_safety import get_thread_safe_config_manager

_logger = logging.getLogger("alarm_scheduler")

class AlarmScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._running = False
        self._last_computed: Optional[_dt.datetime] = None

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._thread = threading.Thread(target=self._run_loop, name="AlarmScheduler", daemon=True)
            self._running = True
            self._thread.start()
            try:
                # Register change listener to wake the scheduler when config updates
                cfg_mgr = get_thread_safe_config_manager()
                cfg_mgr.add_change_listener(lambda _cfg: self.wake())
            except Exception as e:
                _logger.debug(f"Config listener registration failed: {e}")
            _logger.info("⏰ AlarmScheduler started (event-driven mode)")

    def wake(self) -> None:
        self._wake_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    def _compute_next_alarm(self) -> Optional[_dt.datetime]:
        cfg = load_config()
        if not cfg.get("enabled"):
            return None
        alarm_time = cfg.get("time")
        if not alarm_time or not AlarmTimeValidator.validate_time_format(alarm_time):
            return None
        weekdays = cfg.get("weekdays", [])
        try:
            next_dt = WeekdayScheduler.get_next_alarm_date(alarm_time, weekdays)
            return next_dt
        except Exception as e:
            _logger.warning(f"Failed to compute next alarm: {e}")
            return None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self._wake_event.clear()
            next_alarm = self._compute_next_alarm()
            self._last_computed = next_alarm
            if not next_alarm:
                # No alarm configured/enabled – wait a bit or until config changes
                _logger.debug("No active alarm (disabled or incomplete). Sleeping 60s or until change.")
                self._wake_event.wait(timeout=60)
                continue

            now = _dt.datetime.now()
            seconds_until = (next_alarm - now).total_seconds()
            if seconds_until <= 0:
                # Already passed; recompute next cycle
                _logger.debug("Computed alarm time already passed – recomputing soon.")
                time.sleep(2)
                continue

            # We sleep until we enter the execution window
            trigger_window_seconds = ALARM_TRIGGER_WINDOW_MINUTES * 60
            sleep_until_window = max(0, seconds_until - trigger_window_seconds)
            if sleep_until_window > 0:
                _logger.debug(f"Next alarm at {next_alarm.isoformat()} (in {int(seconds_until)}s). Sleeping {int(sleep_until_window)}s.")
                woke_early = self._wake_event.wait(timeout=sleep_until_window)
                if woke_early:
                    _logger.debug("Woken early due to config change – recompute.")
                    continue

            # Now inside execution window – attempt execution loop
            window_deadline = time.time() + trigger_window_seconds
            executed = False
            while time.time() <= window_deadline and not executed and not self._stop_event.is_set():
                executed = execute_alarm()
                if executed:
                    _logger.info("Alarm executed inside window.")
                    break
                # If not executed (maybe conditions not yet ready), retry in short interval
                if self._wake_event.wait(timeout=5):  # config changed mid-window
                    _logger.debug("Config changed during window – abort current attempt and recompute.")
                    break
            # After attempt, loop to recompute next alarm

# Singleton pattern
_scheduler_instance: Optional[AlarmScheduler] = None

def get_alarm_scheduler() -> AlarmScheduler:
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = AlarmScheduler()
    return _scheduler_instance

def start_alarm_scheduler() -> None:
    get_alarm_scheduler().start()
