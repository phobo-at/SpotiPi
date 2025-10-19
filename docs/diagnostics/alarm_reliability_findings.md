# Alarm Reliability Audit Findings

## Timebase & Scheduling
- `src/core/alarm_scheduler.py:90-161`  
  ```python
  now = _dt.datetime.now(tz=LOCAL_TZ)
  seconds_until = (next_alarm - now).total_seconds()
  ...
  window_deadline = time.time() + trigger_window_seconds
  while time.time() <= window_deadline:
      executed = execute_alarm()
  ```  
  *Findings:* The event-driven scheduler repeatedly recomputes `seconds_until` from wall-clock datetimes and relies on `time.time()` for the execution window deadline. Any NTP correction, DST jump, or manual clock adjustment can push `time.time()` forward and shrink the window, causing overnight misfires. There is no monotonic reference, misfire grace, or persistence across process restarts.

- `src/core/scheduler.py:23-46`  
  ```python
  now = datetime.datetime.now(tz=LOCAL_TZ)
  target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
  if target <= now:
      target += datetime.timedelta(days=1)
  ```  
  *Findings:* Next-alarm computations depend on the local timezone without handling ambiguous/non-existent times (DST gaps in `Europe/Vienna`). The `replace`/`+1 day` approach ignores `fold` flags, so DST transitions can yield duplicate or skipped alarms.

- `src/core/alarm.py:57-115`  
  ```python
  now = datetime.datetime.now(tz=LOCAL_TZ)
  target_today = now.replace(...)
  diff_minutes = (now - target_today).total_seconds() / 60
  if diff_minutes > ALARM_TRIGGER_WINDOW_MINUTES:
      return False
  ```  
  *Findings:* Alarm execution checks use wall-clock deltas with a fixed `ALARM_TRIGGER_WINDOW_MINUTES = 1.5` (see `src/constants.py:7`). If the scheduler thread lags >90 s (e.g., system wake-up, NTP step), the guard rejects the alarm instead of catching up.

- `src/utils/thread_safety.py:51-84`  
  ```python
  def _cache_stale(self) -> bool:
      return (time.monotonic() - self._cache_timestamp) > _CACHE_TTL
  ```  
  *Findings:* Config caching uses `time.monotonic()`, so the infrastructure is ready for monotonic scheduling—contrast with `AlarmScheduler`, which still uses wall clock.

- `tests/`: No scheduler or DST coverage exists; current test suite cannot regress or reproduce overnight failures.

## Spotify Startup Path
- `src/api/spotify.py:326-438` (`_refresh_access_token_impl`)  
  *Findings:* Token refresh uses retry/backoff with `time.sleep(delay)` (wall clock), but revalidation in the scheduler only happens during the pre-warm window (`ensure_token_valid()`); long idle periods rely on the scheduler thread waking on time.

- `src/api/spotify.py:890-1038` (`get_devices`, `_remember_device_mapping`)  
  *Findings:* Device discovery depends on cached responses. Failure to find the configured device falls back to stale cache entries but does not retry with jitter/backoff; repeated overnight attempts may exhaust the window.

- `src/services/spotify_service.py:15-120`  
  *Findings:* `get_authentication_status()` stores `self._last_token_check = datetime.now()`, but there is no watchdog ensuring the background scheduler refreshes tokens during extended idle periods.

## Startup & Deployment
- `run.py:15-60` and `src/app.py:1514-1538`  
  *Findings:* Scheduler thread starts inside the Flask process; there is no external supervisor (systemd timer) for persistence or catch-up after downtime.

- `scripts/deploy_to_pi.sh:24-196`  
  *Findings:* Deployment script restarts `spotipi.service`, yet no service/timer definitions exist in the repo. Lack of systemd units eliminates Persistent timers and makes overnight execution depend solely on the in-process scheduler thread.

## Observability & Logging
- Alarm logs (`src/core/alarm.py`) are human-readable strings; there is no structured JSON logging containing UTC/local timestamps, monotonic offsets, network readiness, or Spotify token/device state. Correlating overnight failures requires manual log scraping.

## Summary
The current alarm pipeline is dominated by wall-clock computations with a short 90 s execution window and no persistence. NTP adjustments or DST transitions can skip alarms, and there is no structured telemetry to diagnose misses. Spotify token/device readiness is best-effort without resilient retries around the trigger window. Systemd integration is absent despite deployment scripts referencing a service, so alarms cannot leverage `Persistent=true` timers today.
