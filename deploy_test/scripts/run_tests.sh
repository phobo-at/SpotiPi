#!/usr/bin/env bash
# Simple test runner for SpotiPi
# Usage: ./scripts/run_tests.sh [extra pytest args]
set -euo pipefail

# Resolve project root (one level up from scripts/)
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Optional: create a .venv if none active (lightweight convenience)
if [ -z "${VIRTUAL_ENV:-}" ] && [ ! -d .venv ]; then
  echo "[info] Creating virtual environment (.venv)" >&2
  python3 -m venv .venv
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

if [ -z "${VIRTUAL_ENV:-}" ] && [ -d .venv ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Install dependencies if requirements.txt exists
if [ -f requirements.txt ]; then
  echo "[info] Installing dependencies (requirements.txt)" >&2
  pip install -q -r requirements.txt
fi

# Ensure src is on PYTHONPATH
export PYTHONPATH="$ROOT_DIR/src:${PYTHONPATH:-}"

# Default pytest options
PYTEST_OPTS="-ra"

# If coverage is available, enable it
if python -c 'import importlib,sys; sys.exit(0 if importlib.util.find_spec("coverage") else 1)' 2>/dev/null; then
  PYTEST_OPTS="--cov=src --cov-report=term-missing $PYTEST_OPTS"
fi

echo "[info] Running tests..."
pytest $PYTEST_OPTS "$@"

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
  echo "[info] ✅ Tests passed"
else
  echo "[error] ❌ Tests failed with exit code $EXIT_CODE" >&2
fi
exit $EXIT_CODE
