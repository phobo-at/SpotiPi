"""Event-driven alarm scheduler to replace minute-based polling.

- Computes next alarm timestamp using `AlarmTimeValidator`
- Sleeps until just before the trigger window instead of waking every minute
- Reacts immediately to config changes via thread-safe config change listener
- Uses ALARM_TRIGGER_WINDOW_MINUTES for final execution window
"""
from __future__ import annotations

import copy
import datetime as _dt
import json
import logging
import os
import random
import socket
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..api.spotify import ensure_token_valid, get_access_token, get_device_id
from ..config import load_config
from ..constants import ALARM_TRIGGER_WINDOW_MINUTES
from ..utils.thread_safety import get_thread_safe_config_manager
from ..utils.timezone import get_local_timezone
from .alarm import execute_alarm
from .alarm_logging import (AlarmProbeContext, check_network_ready,
                            get_ntp_offset_ms, log_alarm_probe,
                            summarize_token_state)
from .scheduler import AlarmTimeValidator

_logger = logging.getLogger("alarm_scheduler")
LOCAL_TZ = get_local_timezone()
PREWARM_SECONDS = max(30, int(os.getenv("SPOTIPI_PREWARM_SECONDS", "120")))
CATCHUP_GRACE_SECONDS = max(
    int(ALARM_TRIGGER_WINDOW_MINUTES * 60),
    int(os.getenv("SPOTIPI_CATCHUP_GRACE_SECONDS", "600")),
)
DNS_PROBE_HOST = os.getenv("SPOTIPI_DNS_PROBE_HOST", "api.spotify.com")
STATE_PATH = Path(__file__).resolve().parents[2] / "cache" / "alarm_scheduler_state.json"
STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
_STATE_FILE_LOCK = threading.Lock()

class AlarmScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._running = False
        self._last_computed: Optional[_dt.datetime] = None
        self._last_config_snapshot: Optional[Dict[str, Any]] = None
        self._last_alarm_time: Optional[str] = None
        self._current_context: Optional[AlarmProbeContext] = None
        self._state: Dict[str, Any] = self._load_persisted_state()
        # Performance: Cache config in-memory to avoid repeated disk I/O + Pydantic validation
        self._cached_config: Optional[Dict[str, Any]] = None
        self._config_version: int = 0

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
                cfg_mgr.add_change_listener(self._on_config_changed)
            except Exception as e:
                _logger.debug(f"Config listener registration failed: {e}")
            _logger.info("⏰ AlarmScheduler started (event-driven mode)")

    def wake(self) -> None:
        self._wake_event.set()

    def stop(self) -> None:
        self._stop_event.set()
        self._wake_event.set()

    def _on_config_changed(self, new_config: Dict[str, Any]) -> None:
        """Handle config changes by updating cache and waking scheduler.
        
        Performance: Deep copy only once when config changes (not every loop iteration).
        """
        with self._lock:
            # Shallow copy is sufficient - config values are primitives or immutable
            # Exception: last_known_devices needs deep copy, but it's rarely used in alarm logic
            self._cached_config = {
                **new_config,
                "last_known_devices": copy.deepcopy(new_config.get("last_known_devices", {}))
            }
            self._config_version += 1
            _logger.debug(f"Config cache updated (version {self._config_version})")
        self.wake()

    def _compute_next_alarm(self) -> Optional[_dt.datetime]:
        # Performance: Use cached config to avoid repeated disk I/O + Pydantic validation
        with self._lock:
            if self._cached_config is None:
                # First load or cache invalidated - load from disk
                self._cached_config = load_config()
                _logger.debug("Config cache initialized (cold start)")
            cfg = self._cached_config
        
        # Extract only alarm-relevant fields (avoid unnecessary deep copy of entire config)
        self._last_config_snapshot = {
            "enabled": cfg.get("enabled"),
            "time": cfg.get("time"),
            "device_name": cfg.get("device_name"),
            "alarm_volume": cfg.get("alarm_volume"),
            "playlist_uri": cfg.get("playlist_uri"),
            "fade_in": cfg.get("fade_in"),
            "shuffle": cfg.get("shuffle"),
            "weekdays": cfg.get("weekdays"),
        }
        
        if not cfg.get("enabled"):
            return None
        alarm_time = cfg.get("time")
        self._last_alarm_time = alarm_time if isinstance(alarm_time, str) else None
        if not alarm_time or not AlarmTimeValidator.validate_time_format(alarm_time):
            return None
        try:
            pending = self._pending_state_alarm()
            if pending:
                return pending
            next_dt = AlarmTimeValidator.get_next_alarm_date(alarm_time)
            return next_dt
        except Exception as e:
            _logger.warning(f"Failed to compute next alarm: {e}")
            return None

    def _prewarm_device_cache(self, token: str, context: Optional[AlarmProbeContext]) -> str:
        config_snapshot = self._last_config_snapshot or {}
        device_name = config_snapshot.get("device_name")
        if not device_name:
            if context:
                context.set_device_result("prewarm", "skipped", reason="no_device")
            return "no-device"
        try:
            device_id = get_device_id(token, device_name)
            if device_id:
                _logger.debug("Device cache prewarm succeeded for %s", device_name)
                if context:
                    context.set_device_result("prewarm", "found", device_name=device_name)
                return "found"
            if context:
                context.set_device_result("prewarm", "missing", device_name=device_name)
            return "missing"
        except Exception as exc:  # pragma: no cover - best-effort
            _logger.debug("Device cache prewarm failed for %s: %s", device_name, exc)
            if context:
                context.set_device_result("prewarm", "error", device_name=device_name, error=str(exc))
            return "error"
        return "unknown"

    def _load_persisted_state(self) -> Dict[str, Any]:
        with _STATE_FILE_LOCK:
            try:
                with STATE_PATH.open("r", encoding="utf-8") as fh:
                    data = json.load(fh)
                    if isinstance(data, dict):
                        return data
            except FileNotFoundError:
                return {}
            except json.JSONDecodeError:
                _logger.warning("Ignoring corrupted scheduler state file at %s", STATE_PATH)
        return {}

    def _persist_state(self) -> None:
        with _STATE_FILE_LOCK:
            try:
                with STATE_PATH.open("w", encoding="utf-8") as fh:
                    json.dump(self._state, fh, indent=2)
            except OSError as exc:
                _logger.warning("Failed to persist scheduler state: %s", exc)

    def _record_schedule(self, scheduled: _dt.datetime) -> None:
        self._state["scheduled_utc"] = scheduled.astimezone(_dt.timezone.utc).isoformat()
        self._state["scheduled_local"] = scheduled.astimezone(LOCAL_TZ).isoformat()
        self._state["alarm_time"] = self._last_alarm_time
        self._state["persisted_at_utc"] = _dt.datetime.now(tz=_dt.timezone.utc).isoformat()
        self._state.pop("executed_utc", None)
        self._persist_state()

    def _record_execution(self, executed_at: _dt.datetime) -> None:
        self._state["executed_utc"] = executed_at.astimezone(_dt.timezone.utc).isoformat()
        self._persist_state()

    def _resolve_dns(self) -> Optional[bool]:
        try:
            socket.getaddrinfo(DNS_PROBE_HOST, 443, type=socket.SOCK_STREAM)
            return True
        except socket.gaierror:
            return False
        except Exception as exc:  # pragma: no cover - defensive
            _logger.debug("DNS probe error: %s", exc)
            return None

    def _perform_readiness_checks(self, context: Optional[AlarmProbeContext]) -> Dict[str, Any]:
        network_ready = check_network_ready()
        dns_ok = self._resolve_dns() if network_ready is not False else False
        token_value: Optional[str] = None
        try:
            token_value = get_access_token()
            token_available = bool(token_value)
        except Exception as exc:  # pragma: no cover - defensive
            _logger.debug("Token readiness probe failed: %s", exc)
            token_available = False

        device_ready: Optional[bool] = None
        device_id: Optional[str] = None
        device_name = context.device_name() if context else None
        if device_name and token_available:
            try:
                device_id = get_device_id(token_value or "", device_name)
                device_ready = bool(device_id)
            except Exception as exc:  # pragma: no cover - defensive
                _logger.debug("Device readiness probe failed: %s", exc)
                device_ready = False

        readiness = {
            "network_ready": network_ready,
            "dns_ok": dns_ok,
            "token_available": token_available,
            "device_ready": device_ready,
        }
        readiness["ready"] = (
            (network_ready is not False)
            and (dns_ok is not False)
            and token_available
            and (device_ready is not False)
        )
        if device_ready and context:
            context.set_device_result("readiness", "found", device_name=device_name, device_id=device_id)
        elif device_ready is False and context and device_name:
            context.set_device_result("readiness", "missing", device_name=device_name)

        if context:
            context.ntp_offset_ms = get_ntp_offset_ms()
            context.network_ready = network_ready
            context.spotify_auth_state = summarize_token_state()
            if not context.device_discovery_result:
                device_name = context.device_name()
                if device_name:
                    context.set_device_result("readiness", "pending", device_name=device_name)
            context.env_sampled = True
        return readiness

    def _compute_backoff(self, attempt: int) -> float:
        base = min(10.0, 2 ** min(attempt, 3))
        jitter = random.uniform(0.2, 0.7)
        return base + jitter

    def _pending_state_alarm(self) -> Optional[_dt.datetime]:
        scheduled_iso = self._state.get("scheduled_utc")
        if not scheduled_iso:
            return None
        state_alarm_time = self._state.get("alarm_time")
        if self._last_alarm_time and state_alarm_time and state_alarm_time != self._last_alarm_time:
            return None
        try:
            scheduled_dt = _dt.datetime.fromisoformat(scheduled_iso)
        except ValueError:
            return None
        if scheduled_dt.tzinfo is None:
            scheduled_dt = scheduled_dt.replace(tzinfo=_dt.timezone.utc)
        scheduled_utc = scheduled_dt.astimezone(_dt.timezone.utc)

        executed_iso = self._state.get("executed_utc")
        if executed_iso:
            try:
                executed_dt = _dt.datetime.fromisoformat(executed_iso)
                if executed_dt.tzinfo is None:
                    executed_dt = executed_dt.replace(tzinfo=_dt.timezone.utc)
                if executed_dt >= scheduled_utc:
                    return None
            except ValueError:
                pass

        now_utc = _dt.datetime.now(tz=_dt.timezone.utc)
        delta_seconds = (now_utc - scheduled_utc).total_seconds()
        if 0 <= delta_seconds <= CATCHUP_GRACE_SECONDS:
            return scheduled_utc.astimezone(LOCAL_TZ)
        return None

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            self._wake_event.clear()
            next_alarm = self._compute_next_alarm()
            self._last_computed = next_alarm
            context: Optional[AlarmProbeContext] = None
            if next_alarm:
                context = AlarmProbeContext(
                    scheduled_at=next_alarm,
                    timezone=LOCAL_TZ,
                    alarm_time=self._last_alarm_time or "",
                    config_snapshot=self._last_config_snapshot or {},
                )
                self._record_schedule(next_alarm)
            self._current_context = context
            if not next_alarm:
                # No alarm configured/enabled – wait a bit or until config changes
                _logger.debug("No active alarm (disabled or incomplete). Sleeping 60s or until change.")
                self._wake_event.wait(timeout=60)
                continue

            now = _dt.datetime.now(tz=LOCAL_TZ)
            seconds_until_raw = (next_alarm - now).total_seconds()
            catchup = False
            if seconds_until_raw <= 0:
                if seconds_until_raw >= -CATCHUP_GRACE_SECONDS:
                    catchup = True
                    _logger.info(
                        "Entering catch-up mode (missed by %.1fs <= %ss).",
                        abs(seconds_until_raw),
                        CATCHUP_GRACE_SECONDS,
                    )
                    log_alarm_probe(
                        context,
                        "catchup_activate",
                        extra={"seconds_late": abs(seconds_until_raw), "grace_seconds": CATCHUP_GRACE_SECONDS},
                        force=True,
                    )
                    seconds_until = 0.0
                else:
                    _logger.debug(
                        "Scheduled alarm %s missed by %.1fs (> grace %ss) – skipping to next cycle.",
                        next_alarm.isoformat(),
                        abs(seconds_until_raw),
                        CATCHUP_GRACE_SECONDS,
                    )
                    log_alarm_probe(
                        context,
                        "catchup_too_late",
                        extra={"seconds_late": abs(seconds_until_raw), "grace_seconds": CATCHUP_GRACE_SECONDS},
                        force=True,
                    )
                    self._wake_event.wait(timeout=2)
                    continue
            else:
                seconds_until = seconds_until_raw
            log_alarm_probe(context, "compute_next", extra={"seconds_until": seconds_until})
            trigger_window_seconds = ALARM_TRIGGER_WINDOW_MINUTES * 60
            if PREWARM_SECONDS > 0 and seconds_until > PREWARM_SECONDS:
                prewarm_wait = max(0.0, seconds_until - PREWARM_SECONDS)
                _logger.debug(
                    "Next alarm at %s (in %ss). Pre-warm in %ss.",
                    next_alarm.isoformat(),
                    int(seconds_until),
                    int(prewarm_wait),
                )
                log_alarm_probe(
                    context,
                    "prewarm_wait_start",
                    extra={
                        "seconds_until": seconds_until,
                        "prewarm_seconds": PREWARM_SECONDS,
                        "trigger_window_seconds": trigger_window_seconds,
                    },
                )
                woke_early = self._wake_event.wait(timeout=prewarm_wait)
                if woke_early:
                    _logger.debug("Woken before pre-warm due to config change – recompute.")
                    log_alarm_probe(
                        context,
                        "prewarm_wait_cancelled",
                        extra={"seconds_until": (next_alarm - _dt.datetime.now(tz=LOCAL_TZ)).total_seconds()},
                        force=True,
                    )
                    continue
                token_value: Optional[str] = None
                try:
                    log_alarm_probe(context, "prewarm_token_request", extra={"seconds_until": seconds_until})
                    token_value = ensure_token_valid()
                    _logger.info("Spotify token pre-warm executed (T-%ss).", PREWARM_SECONDS)
                except Exception as exc:
                    _logger.warning("Token pre-warm failed: %s", exc)
                    log_alarm_probe(context, "prewarm_token_error", extra={"error": str(exc)}, force=True)
                if not token_value:
                    token_value = get_access_token()
                    log_alarm_probe(
                        context,
                        "prewarm_token_fallback",
                        extra={"token_available": bool(token_value)},
                    )
                if token_value:
                    device_status = self._prewarm_device_cache(token_value, context)
                    log_alarm_probe(
                        context,
                        "prewarm_device_cache",
                        extra={"device_status": device_status, "device_name": context.device_name()},
                    )
                    
                    # HTTP Pool Pre-Warming: Establish HTTPS connection early to avoid cold-start penalty
                    # On Pi Zero W Wi-Fi, cold TCP+TLS handshake adds ~300-500ms to first API call
                    try:
                        log_alarm_probe(context, "prewarm_http_start")
                        from ..api.http import SESSION
                        # Cheap HEAD request to warm connection pool (triggers TLS handshake)
                        SESSION.head(
                            "https://api.spotify.com/v1/me",
                            headers={"Authorization": f"Bearer {token_value}"},
                            timeout=(2.0, 3.0)  # Short timeout for warm-up
                        )
                        log_alarm_probe(context, "prewarm_http_ok")
                    except Exception as exc:
                        # Non-fatal: Connection will establish on first real request if warm-up fails
                        error_type = exc.__class__.__name__
                        log_alarm_probe(
                            context, 
                            "prewarm_http_error", 
                            extra={"error_type": error_type, "error": str(exc)[:100]}
                        )

                now = _dt.datetime.now(tz=LOCAL_TZ)
                seconds_until = (next_alarm - now).total_seconds()
                if seconds_until <= 0:
                    log_alarm_probe(context, "prewarm_overdue", extra={"seconds_until": seconds_until}, force=True)
                    continue

            # Sleep until the execution window opens
            sleep_until_window = max(0, seconds_until - trigger_window_seconds)
            if sleep_until_window > 0:
                _logger.debug(
                    "Next alarm at %s (in %ss). Sleeping %ss until execution window.",
                    next_alarm.isoformat(),
                    int(seconds_until),
                    int(sleep_until_window),
                )
                log_alarm_probe(
                    context,
                    "window_sleep_start",
                    extra={
                        "seconds_until": seconds_until,
                        "sleep_seconds": sleep_until_window,
                        "trigger_window_seconds": trigger_window_seconds,
                    },
                )
                woke_early = self._wake_event.wait(timeout=sleep_until_window)
                if woke_early:
                    _logger.debug("Woken early due to config change – recompute.")
                    log_alarm_probe(
                        context,
                        "window_sleep_cancelled",
                        extra={"seconds_until": (next_alarm - _dt.datetime.now(tz=LOCAL_TZ)).total_seconds()},
                        force=True,
                    )
                    continue

            # Now inside execution window – attempt execution loop
            window_deadline = time.monotonic() + trigger_window_seconds
            log_alarm_probe(
                context,
                "window_enter",
                extra={
                    "seconds_until": (next_alarm - _dt.datetime.now(tz=LOCAL_TZ)).total_seconds(),
                    "window_deadline": window_deadline,
                },
            )
            executed = False
            attempt = 0
            while time.monotonic() <= window_deadline and not executed and not self._stop_event.is_set():
                readiness = self._perform_readiness_checks(context)
                if not readiness["ready"]:
                    delay = self._compute_backoff(attempt)
                    log_alarm_probe(
                        context,
                        "readiness_pending",
                        extra={
                            "window_deadline": window_deadline,
                            "seconds_remaining": max(0.0, window_deadline - time.monotonic()),
                            **readiness,
                            "backoff_sec": delay,
                        },
                        force=True,
                    )
                    if self._wake_event.wait(timeout=delay):
                        _logger.debug("Config change detected while waiting for readiness – aborting attempt.")
                        log_alarm_probe(context, "execute_aborted_config_change", force=True)
                        break
                    attempt += 1
                    continue

                log_alarm_probe(
                    context,
                    "execute_attempt",
                    extra={
                        "window_deadline": window_deadline,
                        "seconds_remaining": max(0.0, window_deadline - time.monotonic()),
                        "catchup": catchup,
                    },
                )
                executed = execute_alarm(probe=context, catchup_grace_seconds=CATCHUP_GRACE_SECONDS)
                if executed:
                    _logger.info("Alarm executed inside window.")
                    self._record_execution(_dt.datetime.now(tz=LOCAL_TZ))
                    log_alarm_probe(context, "execute_success", extra={"window_deadline": window_deadline}, force=True)
                    break

                delay = self._compute_backoff(attempt)
                log_alarm_probe(
                    context,
                    "execute_retry",
                    extra={
                        "window_deadline": window_deadline,
                        "seconds_remaining": max(0.0, window_deadline - time.monotonic()),
                        "backoff_sec": delay,
                    },
                )
                if self._wake_event.wait(timeout=delay):
                    _logger.debug("Config change detected while backing off – aborting attempt.")
                    log_alarm_probe(context, "execute_aborted_config_change", force=True)
                    break
                attempt += 1
            if not executed and not self._stop_event.is_set():
                log_alarm_probe(
                    context,
                    "window_complete",
                    extra={"executed": executed, "window_deadline": window_deadline},
                    force=True,
                )
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
