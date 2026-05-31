# Alarm Reliability Runbook

## Quick Checklist
- Confirm the alarm scheduler thread is running (`journalctl -u spotipi.service | grep "AlarmScheduler started"`).
- Inspect structured probe logs (`alarm_probe`) around the incident window.
- Verify system clock discipline (`timedatectl timesync-status`).
- **Recurring alarms:** if `weekdays` is set, the alarm only fires on selected days (0=Mon … 6=Sun). A non-matching day is an *intentional* skip and logs the `execute_wrong_weekday` probe event — not a miss. Recurring alarms stay enabled after firing; only one-time alarms (`weekdays` empty/None) auto-disable.

## Core Diagnostics
- `timedatectl` – validate timezone, NTP sync, RTC offsets.
- `journalctl -u spotipi.service -u spotipi.timer --since "yesterday"` – collect application + timer logs (look for `alarm_probe` JSON lines).
- `nmcli device status` / `nmcli general status` – confirm Wi-Fi link state.
- `iw dev wlan0 get power_save` – ensure power save remains disabled.
- `systemctl list-timers --all | grep spotipi` – check optional readiness timer status.

### Focused Log Queries
- `journalctl -u spotipi.service --since "today 05:00" | rg alarm_probe` – extract JSON probe records around a trigger.
- `jq` snippet (local): `journalctl -u spotipi.service -o cat | rg alarm_probe | jq '.delta_sec, .scheduler_state, .device_discovery_result'`.

## Readiness & Health Checks
- `curl -s http://spotipi.local:5000/api/dashboard/status | jq '.alarm'` – verify alarm configuration surfaced via API (there is no dedicated `/api/alarm/status`; the dashboard aggregate carries it, and may return `202` while the snapshot is still pending).
- `sudo systemctl status spotipi.service` – ensure the service is active; restart if unhealthy.
- Optional manual probe: `sudo systemctl start spotipi-alarm.service` (records readiness without playing audio).

## Measurement Plan (Overnight Stability)
1. **Baseline** – capture three consecutive mornings with `alarm_probe` entries showing `execute_success` and `delta_sec` within ±5 s of zero.
2. **Track metrics** – export probe logs to CSV (timestamp, delta_sec, network_ready, token_available, device_ready).
3. **Alert threshold** – raise incident if ≥1 miss per week OR `delta_sec` leaves ±90 s window.
4. **Regression guard** – keep `pytest tests/alarm_reliability` in CI; rerun before each deployment.

## Recovery Steps
1. Restart scheduler: `sudo systemctl restart spotipi.service`.
2. If timers are enabled: `sudo systemctl restart spotipi-alarm.timer`.
3. Force config reload by toggling the alarm via UI or re-saving it: `curl -X POST http://spotipi.local:5000/save_alarm -d 'enabled=on&time=07:00&device_name=...&alarm_volume=20'` (there is no `/api/alarm/enable`).
4. Re-run manual readiness: `sudo systemctl start spotipi-alarm.service`.
