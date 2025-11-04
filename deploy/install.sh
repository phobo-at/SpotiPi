#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="/etc/systemd/system"

UNITS=(
  "deploy/systemd/spotipi.service"
  "deploy/systemd/spotipi-alarm.service"
  "deploy/systemd/spotipi-alarm.timer"
)

echo "📦 Installing SpotiPi systemd units..."
for unit in "${UNITS[@]}"; do
  SOURCE_PATH="$PROJECT_ROOT/$unit"
  if [ -f "$SOURCE_PATH" ]; then
    UNIT_NAME="$(basename "$unit")"
    echo "   ➕ $UNIT_NAME"
    sudo cp "$SOURCE_PATH" "$SYSTEMD_DIR/$UNIT_NAME"
  fi
done

sudo systemctl daemon-reload
sudo systemctl enable spotipi.service
sudo systemctl restart spotipi.service

# Enable alarm timer by default for robustness (catch-up after reboot)
if [ "${SPOTIPI_ENABLE_ALARM_TIMER:-1}" = "1" ]; then
  sudo systemctl enable --now spotipi-alarm.timer
  echo "✅ Alarm readiness timer enabled (spotipi-alarm.timer)"
  echo "   Timer runs daily at 05:30 with catch-up after reboot"
else
  echo "ℹ️  Alarm timer disabled (set SPOTIPI_ENABLE_ALARM_TIMER=1 to enable)"
fi

echo "✅ Installation complete."
