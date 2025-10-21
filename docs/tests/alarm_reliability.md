# Alarm Reliability Test Suite

| Test | Scope | Assurance |
| --- | --- | --- |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_t_plus_90_seconds` | Unit | Verifies that `next_alarm_datetime()` schedules the next alarm exactly 90 s in the future, preventing premature trigger drift. |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_handles_dst_forward_gap` | Unit | Confirms DST forward gaps (Europe/Vienna) roll over to the first valid time (03:30 during the spring jump). |
| `tests/alarm_reliability/test_scheduler.py::test_next_alarm_datetime_handles_dst_backward_overlap` | Unit | Checks that DST fallback keeps the earliest occurrence (fold 0) for duplicated hours. |
| `tests/alarm_reliability/test_scheduler.py::test_execute_alarm_catchup_within_grace` | Unit | Ensures alarms missed by ≤10 min still execute using catch-up grace and auto-disable afterwards. |
| `tests/alarm_reliability/test_scheduler.py::test_pending_state_alarm_handles_recent_miss` | Unit | Exercises persisted scheduler state so alarms missed during downtime (≤ grace) are retried on restart. |
| `tests/alarm_reliability/test_readiness.py::test_readiness_fails_until_network_and_token` | Integration (mocked Spotify/network) | Simulates network+token outage followed by recovery to validate readiness gating and device discovery retries. |

Run the suite with:

```bash
pytest tests/alarm_reliability
```
