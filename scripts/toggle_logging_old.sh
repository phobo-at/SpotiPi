#!/bin/bash
#
# toggle_logging.sh – Enable or disable detailed SpotiPi logging on the Raspberry Pi
#
# Features:
#   * Creates / removes a systemd override for spotify-web.service
#   * Sets environment variables understood by our logger (see src/utils/logger.py)
#   * Ensures log directory exists when enabling
#   * Provides status output
#
# Usage:
#   ./scripts/toggle_logging.sh on                # Enable detailed logging (keeps production.json as-is)
#   ./scripts/toggle_logging.sh on --with-debug   # Enable logging AND set production.json "debug": true
#   ./scripts/toggle_logging.sh off               # Disable (revert override, leave production.json as-is)
#   ./scripts/toggle_logging.sh off --restore-debug  # Disable and set "debug": false IF we previously enabled it
#   ./scripts/toggle_logging.sh status            # Show current mode & effective env vars
#
# What "on" does:
#   - Creates /etc/systemd/system/spotify-web.service.d/override.conf with:
#       SPOTIPI_DEV=1
#       SPOTIPI_LOG_LEVEL=INFO  (could change to DEBUG if needed)
#       SPOTIPI_FORCE_FILE_LOG=1
#       SPOTIPI_LOG_DIR=/home/pi/spotipi_logs
#   - Restarts service
#   - If --with-debug übergeben: setzt config/production.json "debug": true (merkt sich Änderung)
#   - Wenn config/production.json bereits "debug": true war, wird kein Marker gesetzt
#
# What "off" does:
#   - systemctl revert spotify-web.service (removes override)
#   - Restarts service
#   - Mit --restore-debug: setzt "debug": false NUR wenn dieses Skript es vorher aktiviert hat
#
# NOTE: To get *even more* detail you could set SPOTIPI_LOG_LEVEL=DEBUG or also set
#       "debug": true in production.json for alarm evaluation traces.

set -euo pipefail

SERVICE="spotify-web.service"
OVERRIDE_DIR="/etc/systemd/system/${SERVICE}.d"
OVERRIDE_FILE="${OVERRIDE_DIR}/override.conf"
LOG_DIR="/home/pi/spotipi_logs"
CONFIG_FILE="/home/pi/spotify_wakeup/config/production.json"
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
  mkdir -p "${OVERRIDE_DIR}" 
  mkdir -p "${LOG_DIR}"
  chown pi:pi "${LOG_DIR}" || true

  cat > "${OVERRIDE_FILE}" <<EOF
[Service]
Environment=SPOTIPI_DEV=1
Environment=SPOTIPI_LOG_LEVEL=INFO
Environment=SPOTIPI_FORCE_FILE_LOG=1
Environment=SPOTIPI_LOG_DIR=${LOG_DIR}
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
