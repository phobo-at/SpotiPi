# Alarm Reliability Test Suite

| Test | Scope | Assurance |
| --- | --- | --- |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_t_plus_90_seconds` | Unit | Verifies that `next_alarm_datetime()` schedules the next alarm exactly 90 s in the future, preventing premature trigger drift. |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_handles_dst_forward_gap` | Unit | Confirms DST forward gaps (Europe/Vienna) roll over to the first valid time (03:30 during the spring jump). |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_handles_dst_backward_overlap` | Unit | Checks that DST fallback keeps the earliest occurrence (fold 0) for duplicated hours. |
| `tests/alarm_reliability/test_scheduler.py::test_execute_alarm_catchup_within_grace` | Unit | Ensures alarms missed by ≤10 min still execute using catch-up grace and auto-disable afterwards. |
| `tests/alarm_reliability/test_scheduler.py::test_pending_state_alarm_handles_recent_miss` | Unit | Exercises persisted scheduler state so alarms missed during downtime (≤ grace) are retried on restart. |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_weekdays_skips_weekend` | Unit | Recurring alarm restricted to Mon–Fri skips the weekend to the next Monday. |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_single_weekday_crosses_week` | Unit | A single selected weekday advances across the week boundary to the next matching day. |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_weekday_matches_today_later` | Unit | When today matches a selected weekday and the time is still ahead, the alarm fires today. |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_none_weekdays_unchanged` | Unit | `weekdays=None` keeps the original single-use behaviour (regression guard). |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_empty_weekdays_unchanged` | Unit | An empty weekday list imposes no restriction (treated as one-time). |
| `tests/alarm_reliability/test_scheduler.py::test_execute_alarm_skips_wrong_weekday` | Unit | `execute_alarm()` does not fire on a non-selected weekday and does not auto-disable. |
| `tests/alarm_reliability/test_scheduler.py::test_execute_alarm_recurring_stays_enabled` | Unit | A recurring alarm fires on a selected weekday and stays enabled afterwards (no auto-disable). |
| `tests/alarm_reliability/test_readiness.py::test_readiness_fails_until_network_and_token` | Integration (mocked Spotify/network) | Simulates network+token outage followed by recovery to validate readiness gating and device discovery retries. |

Run the suite with:

```bash
pytest tests/alarm_reliability
```

Weekday **input** validation (parsing the `weekdays` form field) is covered separately in
`tests/test_alarm_input_validation.py`.
