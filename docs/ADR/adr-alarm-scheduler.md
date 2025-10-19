# ADR: Alarm Scheduler Reliability (Monotonic Loop)

## Status
Accepted – 2025-10-19

## Context
- Overnight alarms drift or miss because the existing event-driven scheduler relied on wall-clock sleeps (`datetime.now`, `time.time`), so NTP adjustments and DST transitions shrank the 90 s execution window.
- The Flask process owned the scheduler thread; no external service/timer ensured catch-up after reboot or long sleeps.
- We need a fix that runs on Pi Zero W without adding heavyweight dependencies, keeps the UI-driven “next alarm” workflow, and supports future structured logging/tests.

## Options
1. **Internal monotonic scheduler**  
   - Replace wall-clock waits with `time.monotonic()` deadlines, persist the next scheduled UTC timestamp, add catch-up grace, and harden DST math.  
   - Pros: Minimal deployment changes, keeps dynamic config editing via web UI, integrates with existing thread-safe config system.  
   - Cons: Still in-process; must build persistence, tests, and logging ourselves.

2. **systemd timer + lightweight playback service**  
   - Use `OnCalendar=*/...` with `Persistent=true`, trigger a small script that performs readiness checks/playback.  
   - Pros: systemd handles catch-up/retry, journal integration “for free”.  
   - Cons: Dynamic alarm time updates require regenerating timer units (`systemctl daemon-reload`), which is slow on Pi Zero W; complicates UX (needs sudo); reintroduces deployment state drift.

## Decision
Adopt **Option 1 (internal monotonic scheduler)**.

Rationale:
- Keeps the interactive config editing pipeline intact (no systemd reloads on each change).
- Allows granular telemetry (JSON probe logs) and fine-grained retries inside the trigger window.
- Less operational friction for existing `run.py` / `gunicorn` deployments where we cannot assume root/systemd access.
- The added persistence (`cache/alarm_scheduler_state.json`) and catch-up logic close the key reliability gaps without new external dependencies.

## Implementation Highlights
- Scheduler now tracks deadlines with `time.monotonic()` and derives UTC/local timestamps from a DST-aware helper (`src/core/scheduler.py`).
- Catch-up grace (`SPOTIPI_CATCHUP_GRACE_SECONDS`, default 600 s) lets alarms fire after short outages; persistence records scheduled/executed UTC times.
- Structured probe logs (`alarm_probe`) capture UTC/local/monotonic context plus network/token/Spotify device state for ±5 min around the trigger.
- Execution path (`src/core/alarm.py`) understands catch-up grace and emits JSON instrumentation.

## Consequences / Follow-ups
- New state file lives at `cache/alarm_scheduler_state.json`; include it in backups or deployments.
- Deployment scripts must ensure the `cache/` directory is writable on Pi (already true).
- Tests must cover catch-up, DST forward/back transitions, and monotonic scheduling (see `tests/alarm_reliability/*`).
- If a future release switches to systemd timers, this ADR should be revisited or superseded with detailed migration steps.
