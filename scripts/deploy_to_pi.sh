#!/bin/bash
#
# 🚀 Deploy SpotiPi to Raspberry Pi - Minimal Runtime Sync
# Synchronizes only runtime-required files from the development machine to the Pi.
#
# Features:
# - Auto-detects local and remote paths
# - Configurable via environment variables
# - Transfers only the files the Pi needs to run SpotiPi

# 🔧 Configuration with smart defaults
PI_HOST="${SPOTIPI_PI_HOST:-pi@spotipi.local}"
APP_NAME="${SPOTIPI_APP_NAME:-spotipi}"

# Auto-detect local path (where this script is located)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_LOCAL_PATH="$(dirname "$SCRIPT_DIR")"

# Allow override via environment
LOCAL_PATH="${SPOTIPI_LOCAL_PATH:-$DEFAULT_LOCAL_PATH}"

# Auto-detect remote path
PI_PATH="${SPOTIPI_PI_PATH:-/home/pi/$APP_NAME}"

# Service name (systemd)
SERVICE_NAME="${SPOTIPI_SERVICE_NAME:-spotipi.service}"

REQUIRED_PATHS=(
  "run.py"
  "requirements.txt"
  "src"
  "static"
  "templates"
  "config"
  "deploy/systemd"
  "deploy/install.sh"
)

OPTIONAL_PATHS=(
  "pyproject.toml"
  "scripts/run_alarm.sh"
)

# Track which parent directories have been added to avoid duplicates
declare -a SEEN_PARENTS=()

add_include_parents() {
  local path="$1"
  local stack=()
  local current="$path"
  while [[ "$current" == */* ]]; do
    current="${current%/*}"
    stack+=("$current")
  done
  for (( idx=${#stack[@]}-1; idx>=0; idx-- )); do
    local parent="${stack[$idx]}"
    if [ -n "$parent" ] && [[ " ${SEEN_PARENTS[*]} " != *" $parent "* ]]; then
      RSYNC_ARGS+=("--include=$parent/")
      SEEN_PARENTS+=("$parent")
    fi
  done
}

cat <<INFO
🚀 Deploying SpotiPi to Raspberry Pi
📁 Local path: $LOCAL_PATH
🌐 Remote: $PI_HOST:$PI_PATH
INFO

# Verify local path exists
if [ ! -d "$LOCAL_PATH" ]; then
  echo "❌ Local path does not exist: $LOCAL_PATH"
  echo "💡 Set SPOTIPI_LOCAL_PATH environment variable or run from the project root"
  exit 1
fi

# Check that required files exist
MISSING=()
for item in "${REQUIRED_PATHS[@]}"; do
  if [ ! -e "$LOCAL_PATH/$item" ]; then
    MISSING+=("$item")
  fi
done

if [ ${#MISSING[@]} -ne 0 ]; then
  echo "❌ Missing required files/directories:"
  for item in "${MISSING[@]}"; do
    echo "   - $item"
  done
  exit 1
fi

# Build rsync include/exclude rules (allowlist)
RSYNC_ARGS=(
  -av
  --delete
  --prune-empty-dirs
  --itemize-changes
  '--out-format=%i %f'
  --checksum
  --stats
  --exclude='*.pyc'
  --exclude='__pycache__/'
  --exclude='.DS_Store'
  --exclude='logs/'
  --exclude='*.log'
)

# Include rules for required paths
ALL_PATHS=("${REQUIRED_PATHS[@]}" "${OPTIONAL_PATHS[@]}")

for path in "${ALL_PATHS[@]}"; do
  if [ -e "$LOCAL_PATH/$path" ]; then
    if [ -d "$LOCAL_PATH/$path" ]; then
      add_include_parents "$path"
      RSYNC_ARGS+=("--include=$path/")
      RSYNC_ARGS+=("--include=$path/***")
    else
      add_include_parents "$path"
      RSYNC_ARGS+=("--include=$path")
    fi
  fi
done

# Exclude everything else
RSYNC_ARGS+=("--exclude=*")

SYNC_CMD=(rsync "${RSYNC_ARGS[@]}" "$LOCAL_PATH/" "$PI_HOST:$PI_PATH/")

echo "📋 Synchronizing runtime files to Pi..."

# Run rsync and capture output
TMP_OUTPUT="$(mktemp)"
TMP_DELETIONS="$(mktemp)"

# Dry-run to capture deletions
RSYNC_DRY_RUN=("${SYNC_CMD[@]}")
RSYNC_DRY_RUN+=(--dry-run)
"${RSYNC_DRY_RUN[@]}" > "$TMP_OUTPUT"
grep "deleting " "$TMP_OUTPUT" > "$TMP_DELETIONS" || true

# Actual sync
"${SYNC_CMD[@]}" > "$TMP_OUTPUT"
RSYNC_STATUS=$?

if [ $RSYNC_STATUS -ne 0 ]; then
  echo "❌ Failed to sync code"
  cat "$TMP_OUTPUT"
  rm -f "$TMP_OUTPUT" "$TMP_DELETIONS"
  exit 1
fi

# Prepare summary data from itemized output
UPDATED=0
NEW_FILES=0
SYSTEMD_CHANGED=0
declare -a UPDATED_PATHS=()

while IFS= read -r line; do
  # rsync itemized lines look like ">f.st...... path/to/file"
  if [[ "$line" == ">f"* ]]; then
      UPDATED=$((UPDATED + 1))
      path="${line#* }"
      if [ "$path" != "$line" ]; then
        UPDATED_PATHS+=("$path")
        if [[ "$path" == deploy/systemd/* ]]; then
          SYSTEMD_CHANGED=1
        fi
      fi
      if [[ "${line:0:3}" == ">f+" ]]; then
        NEW_FILES=$((NEW_FILES + 1))
      fi
  fi
done < "$TMP_OUTPUT"

if grep -q "deploy/systemd" "$TMP_DELETIONS" 2>/dev/null; then
  SYSTEMD_CHANGED=1
fi

EXISTING_UPDATED=$((UPDATED - NEW_FILES))
if [ $EXISTING_UPDATED -lt 0 ]; then EXISTING_UPDATED=0; fi

DELETED=$(wc -l < "$TMP_DELETIONS" | tr -d ' ')
BYTES_TRANSFERRED=$(grep -E "Total transferred file size" "$TMP_OUTPUT" | cut -d':' -f2 | xargs)
[ -z "$BYTES_TRANSFERRED" ] && BYTES_TRANSFERRED="0 bytes"


cat <<SUMMARY

📊 Deployment Summary
=====================
📁 Files updated: $EXISTING_UPDATED
📁 Files created: $NEW_FILES
🗑️  Files deleted: $DELETED
📦 Data transferred: $BYTES_TRANSFERRED
SUMMARY

if [ "$DELETED" -gt 0 ]; then
  echo "🗑️  Deleted from Pi:"
  sed 's/.*deleting /   ❌ /' "$TMP_DELETIONS"
fi

echo ""
if [ "$UPDATED" -gt 0 ]; then
  echo "📁 Updated files:"
  for idx in "${!UPDATED_PATHS[@]}"; do
    if [ "$idx" -lt 10 ]; then
      echo "   ✅ ${UPDATED_PATHS[$idx]}"
    else
      break
    fi
  done
  REMAINING=$((UPDATED - 10))
  if [ "$REMAINING" -gt 0 ]; then
    echo "   ... and $REMAINING more files"
  fi
  if [ "$NEW_FILES" -gt 0 ]; then
    echo "📁 New files created: $NEW_FILES"
  fi
else
  echo "📁 No file content changes detected"
fi

rm -f "$TMP_OUTPUT" "$TMP_DELETIONS"

echo "✅ Code synchronized successfully"

# Update systemd units (optional)
if [ "${SPOTIPI_DEPLOY_SYSTEMD:-1}" = "1" ]; then
  if [ "$SYSTEMD_CHANGED" -eq 1 ] || [ "${SPOTIPI_FORCE_SYSTEMD:-0}" = "1" ]; then
    echo "⚙️ Updating systemd units on Pi..."
    for unit in spotipi.service spotipi-alarm.service spotipi-alarm.timer; do
      if ssh "$PI_HOST" "[ -f \"$PI_PATH/deploy/systemd/$unit\" ]"; then
        ssh "$PI_HOST" "sudo cp $PI_PATH/deploy/systemd/$unit /etc/systemd/system/$unit"
        echo "   📄 Installed $unit"
      fi
    done
    ssh "$PI_HOST" "sudo systemctl daemon-reload"
    if [ -n "$SERVICE_NAME" ]; then
      ssh "$PI_HOST" "sudo systemctl enable $SERVICE_NAME" || true
    fi
    if [ "${SPOTIPI_ENABLE_ALARM_TIMER:-0}" = "1" ]; then
      ssh "$PI_HOST" "sudo systemctl enable --now spotipi-alarm.timer" || true
    fi
  else
    echo "⚙️ Systemd units unchanged; skipping remote update (set SPOTIPI_FORCE_SYSTEMD=1 to force sync)"
  fi
fi

# Optional cleanup of unused files on the Pi (one-time purge)
if [ "${SPOTIPI_PURGE_UNUSED:-}" = "1" ]; then
  echo "🧹 Removing unused files from Pi..."
  UNUSED_PATHS=(
    "$PI_PATH/.git"
    "$PI_PATH/.github"
    "$PI_PATH/tests"
    "$PI_PATH/docs"
    "$PI_PATH/prototyping"
    "$PI_PATH/logs"
    "$PI_PATH/.pytest_cache"
    "$PI_PATH/node_modules"
    "$PI_PATH/.pre-commit-config.yaml"
    "$PI_PATH/.editorconfig"
    "$PI_PATH/.pylintrc"
    "$PI_PATH/CHANGELOG.md"
    "$PI_PATH/Readme.MD"
  )

  ssh "$PI_HOST" "for path in ${UNUSED_PATHS[*]}; do if [ -e \"\$path\" ]; then sudo rm -rf \"\$path\"; fi; done" && echo "✅ Unused files removed" || echo "⚠️  Cleanup step failed"
fi

# Restart service on Pi
if [ -n "$SERVICE_NAME" ]; then
  echo "🔄 Restarting service: $SERVICE_NAME"
  if ssh "$PI_HOST" "sudo systemctl restart $SERVICE_NAME"; then
    echo "✅ Service restarted successfully"
  else
    echo "❌ Failed to restart service"
    echo "💡 Check status: ssh $PI_HOST 'sudo systemctl status $SERVICE_NAME'"
    exit 1
  fi
fi

echo "🎵 SpotiPi deployment complete!"
echo "🌐 Access: http://spotipi.local:5000"

if [ "${SPOTIPI_SHOW_STATUS:-}" = "1" ]; then
  echo "\n📊 Service Status"
  ssh "$PI_HOST" "sudo systemctl status $SERVICE_NAME --no-pager -l"
fi
