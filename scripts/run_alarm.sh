#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ -f "$ROOT_DIR/venv/bin/activate" ]; then
  # shellcheck source=/dev/null
  source "$ROOT_DIR/venv/bin/activate"
fi

python - <<'PY'
import datetime
from src.core.alarm_scheduler import AlarmScheduler
from src.core.alarm_logging import AlarmProbeContext, log_alarm_probe
from src.utils.timezone import get_local_timezone

tz = get_local_timezone()
scheduled = datetime.datetime.now(tz=tz)
context = AlarmProbeContext(
    scheduled_at=scheduled,
    timezone=tz,
    alarm_time="manual-health-probe",
)

scheduler = AlarmScheduler()
status = scheduler._perform_readiness_checks(context)
log_alarm_probe(
    context,
    "manual_health_probe",
    extra={"manual": True, **status},
    force=True,
)
PY
