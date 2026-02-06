#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANAGER="$PROJECT_DIR/scripts/server_manager.py"

if [[ -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_DIR/.venv/bin/python"
else
  PYTHON_BIN="python3"
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <start|stop|restart|status|logs|errors> [manager args]"
  exit 1
fi

exec "$PYTHON_BIN" "$MANAGER" \
  --profile local \
  --env development \
  --host 127.0.0.1 \
  --port 5001 \
  --debug false \
  --waitress \
  "$@"
