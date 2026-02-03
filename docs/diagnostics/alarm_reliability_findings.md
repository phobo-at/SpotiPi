# Alarm Reliability Audit Findings

## Status (Feb 2026)

The core reliability gaps called out in the original audit have been addressed:

- Execution window now uses `time.monotonic()` to avoid NTP/DST jumps shrinking the trigger window.
- Catch‑up grace and a persisted state file are in place (`cache/alarm_scheduler_state.json`).
- systemd units ship in `deploy/systemd/` with `spotipi-alarm.timer` set to `Persistent=true`.
- Structured alarm logs are emitted via the `alarm_probe` logger for easier correlation.

## Remaining Risks / Follow‑ups

- **DST ambiguity:** Next‑alarm computation still relies on wall‑clock calculations in `src/core/scheduler.py`. DST gaps/ambiguous times can still cause duplicate/skip behavior.
- **Test gaps:** There are no automated tests covering DST transitions or time‑shift scenarios.
- **Readiness edge cases:** Spotify/device readiness still depends on network timing; repeated failures can consume the execution window. Consider more aggressive backoff or a local fallback strategy.

## Code References

- `src/core/alarm_scheduler.py` — monotonic execution window + persisted state
- `src/core/scheduler.py` — next‑alarm time calculation
- `src/core/alarm.py` — trigger window checks
- `deploy/systemd/spotipi-alarm.timer` — persistent catch‑up timer
- `src/utils/logger.py` — structured logging helpers

