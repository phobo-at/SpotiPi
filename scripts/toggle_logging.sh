#!/bin/bash
#
# toggle_logging.sh – Enable or disable detailed SpotiPi logging on the Raspberry Pi - Path-Agnostic Version
#
# Features:
#   * Creates / removes a systemd override for spotipi.service
#   * Sets environment variables understood by our logger (see src/utils/logger.py)
#   * Ensures log directory exists when enabling
#   * Provides status output
#   * Path-agnostic: Auto-detects app name and paths
#
# Usage:
#   ./scripts/toggle_logging.sh on                # Enable detailed logging (keeps production.json as-is)
#   ./scripts/toggle_logging.sh on --with-debug   # Enable logging AND set production.json "debug": true
#   ./scripts/toggle_logging.sh off               # Disable (revert override, leave production.json as-is)
#   ./scripts/toggle_logging.sh off --restore-debug  # Disable and set "debug": false IF we previously enabled it
#   ./scripts/toggle_logging.sh status            # Show current mode & effective env vars

set -euo pipefail

# 🔧 Path-agnostic configuration
APP_NAME="${SPOTIPI_APP_NAME:-spotipi}"
SERVICE_NAME="${SPOTIPI_SERVICE_NAME:-spotipi.service}"
APP_PATH="${SPOTIPI_APP_PATH:-/home/pi/$APP_NAME}"
CONFIG_FILE="$APP_PATH/config/production.json"
LOG_DIR="${SPOTIPI_LOG_DIR:-/home/pi/${APP_NAME}_logs}"

SERVICE="$SERVICE_NAME"
OVERRIDE_DIR="/etc/systemd/system/${SERVICE}.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"
DEBUG_MARKER="${LOG_DIR}/.debug_enabled_by_toggle"

have_jq() { command -v jq >/dev/null 2>&1; }

modify_debug_flag() {
  local value="$1" # true / false
  if [ ! -f "$CONFIG_FILE" ]; then
    echo "⚠️  Config file not found: $CONFIG_FILE" >&2
    return 1
  fi
  if have_jq; then
    tmp=$(mktemp)
    jq ".debug=$value" "$CONFIG_FILE" > "$tmp" && mv "$tmp" "$CONFIG_FILE" || { echo "❌ jq modification failed" >&2; rm -f "$tmp"; return 1; }
  else
    # Fallback Python one-liner (preserves minimal formatting)
    python3 - "$CONFIG_FILE" "$value" <<'PY'
import json,sys,os
path=sys.argv[1]; val=sys.argv[2].lower()=="true"
data=json.load(open(path))
data['debug']=val
tmp=path+".tmp"
json.dump(data,open(tmp,'w'),indent=2)
open(tmp,'a').write('\n')
os.replace(tmp,path)
PY
  fi
  echo "🔧 Set production.json debug=$value"
}

current_debug_value() {
  if [ -f "$CONFIG_FILE" ]; then
    if have_jq; then
      jq -r '.debug // false' "$CONFIG_FILE"
    else
      python3 - "$CONFIG_FILE" <<'PY'
import json,sys
try:
  data=json.load(open(sys.argv[1]))
  print(str(data.get('debug', False)).lower())
except Exception:
  print('false')
PY
    fi
  else
    echo false
  fi
}

need_root() {
  if [ "${EUID}" -ne 0 ]; then
    echo "🔐 Re-running with sudo..." >&2
    sudo -- "$0" "$@"
    exit $?
  fi
}

cmd_status() {
  echo "📌 Service: ${SERVICE}" 
  echo "📁 App Path: ${APP_PATH}"
  echo "📋 Config: ${CONFIG_FILE}"
  echo "📂 Log Dir: ${LOG_DIR}"
  
  if systemctl is-active --quiet "${SERVICE}"; then
    echo "   Status: active"
  else
    echo "   Status: INACTIVE"
  fi

  if [ -f "${OVERRIDE_FILE}" ]; then
    echo "📝 Override present: ${OVERRIDE_FILE}"
    echo "----- override.conf -----"
    sed 's/^/   | /' "${OVERRIDE_FILE}" || true
    echo "-------------------------"
    echo "🔎 Effective Environment (filtered SPOTIPI_*):"
    systemctl show "${SERVICE}" -p Environment | tr ' ' '\n' | grep '^Environment=SPOTIPI_' | sed 's/^/   /' || true
    [ -d "${LOG_DIR}" ] && echo "📂 Log dir exists: ${LOG_DIR}" || echo "📂 Log dir missing: ${LOG_DIR}"
  else
    echo "ℹ️  No override active (minimal Pi logging mode)."
  fi
}

enable_logging() {
  local with_debug="$1" # yes / no
  need_root enable "$@"
  echo "🚀 Enabling detailed logging..."
  echo "📁 Using app path: $APP_PATH"
  echo "📂 Using log dir: $LOG_DIR"
  
  mkdir -p "${OVERRIDE_DIR}" 
  mkdir -p "${LOG_DIR}"
  chown pi:pi "${LOG_DIR}" || true

  cat > "${OVERRIDE_FILE}" <<EOF
[Service]
Environment=SPOTIPI_DEV=1
Environment=SPOTIPI_LOG_LEVEL=INFO
Environment=SPOTIPI_FORCE_FILE_LOG=1
Environment=SPOTIPI_LOG_DIR=${LOG_DIR}
Environment=SPOTIPI_APP_NAME=${APP_NAME}
# Uncomment for ultra verbose:
# Environment=SPOTIPI_LOG_LEVEL=DEBUG
EOF

  systemctl daemon-reload
  systemctl restart "${SERVICE}"
  echo "✅ Detailed logging enabled. View with: journalctl -u ${SERVICE} -f"
  echo "   File logs (if any) in: ${LOG_DIR}"

  if [ "$with_debug" = "yes" ]; then
    current=$(current_debug_value || echo false)
    if [ "$current" != "true" ]; then
      modify_debug_flag true && touch "$DEBUG_MARKER"
    else
      echo "ℹ️  debug already true in production.json (no marker set)"
    fi
  fi
}

disable_logging() {
  local restore_debug="$1" # yes / no
  need_root disable "$@"
  echo "🧹 Disabling detailed logging (reverting override)..."
  if [ -f "${OVERRIDE_FILE}" ]; then
    systemctl revert "${SERVICE}" || true
  fi
  systemctl daemon-reload
  systemctl restart "${SERVICE}"
  echo "✅ Reverted to minimal logging."

  if [ "$restore_debug" = "yes" ] && [ -f "$DEBUG_MARKER" ]; then
    modify_debug_flag false && rm -f "$DEBUG_MARKER" && echo "🔄 Restored debug=false (was enabled by script)" || true
  elif [ "$restore_debug" = "yes" ]; then
    echo "ℹ️  No marker found; leaving debug state unchanged"
  fi
}

usage() {
  grep '^# ' "$0" | sed 's/^# //'
  exit 1
}

# Validate paths before proceeding
if [ ! -d "$APP_PATH" ]; then
  echo "❌ App directory not found: $APP_PATH" >&2
  echo "💡 Set SPOTIPI_APP_PATH environment variable or check app name" >&2
  exit 1
fi

ACTION="${1:-}"
shift || true

WITH_DEBUG="no"
RESTORE_DEBUG="no"

while [ $# -gt 0 ]; do
  case "$1" in
    --with-debug|--debug)
      WITH_DEBUG="yes" ;;
    --restore-debug)
      RESTORE_DEBUG="yes" ;;
    -h|--help)
      usage ;;
    *) echo "❌ Unknown option: $1" >&2; usage ;;
  esac
  shift
done

case "$ACTION" in
  on|enable)
    enable_logging "$WITH_DEBUG" ;;
  off|disable)
    disable_logging "$RESTORE_DEBUG" ;;
  status)
    cmd_status ;;
  *)
    usage ;;
esac
