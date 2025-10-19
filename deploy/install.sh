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

if [ "${SPOTIPI_ENABLE_ALARM_TIMER:-0}" = "1" ]; then
  sudo systemctl enable --now spotipi-alarm.timer
else
  echo "ℹ️  Alarm readiness timer available (spotipi-alarm.timer). Enable with SPOTIPI_ENABLE_ALARM_TIMER=1 ./deploy/install.sh"
fi

echo "✅ Installation complete."
