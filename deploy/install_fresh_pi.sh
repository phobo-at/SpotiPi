#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$PROJECT_ROOT"
ENV_FILE="$APP_DIR/.env"
VENV_DIR="$APP_DIR/venv"
VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

info() { printf "ℹ️  %s\n" "$*"; }
warn() { printf "⚠️  %s\n" "$*"; }
err() { printf "❌ %s\n" "$*"; }
success() { printf "✅ %s\n" "$*"; }

confirm() {
  local prompt="$1"
  local default="${2:-y}"
  local yn
  local suffix
  if [[ "$default" == "y" ]]; then
    suffix="[Y/n]"
  else
    suffix="[y/N]"
  fi
  while true; do
    read -r -p "$prompt $suffix " yn || true
    yn="${yn:-$default}"
    case "$yn" in
      [Yy]* ) return 0 ;;
      [Nn]* ) return 1 ;;
      * ) echo "Bitte y oder n eingeben." ;;
    esac
  done
}

get_env_value() {
  local key="$1"
  if [ -f "$ENV_FILE" ]; then
    local line
    line=$(grep -E "^${key}=" "$ENV_FILE" | tail -n1 || true)
    if [ -n "$line" ]; then
      echo "${line#*=}"
    fi
  fi
}

upsert_env() {
  local key="$1"
  local value="$2"
  [ -z "$value" ] && return 0
  if [ -f "$ENV_FILE" ]; then
    grep -v "^${key}=" "$ENV_FILE" > "${ENV_FILE}.tmp" || true
    mv "${ENV_FILE}.tmp" "$ENV_FILE"
  fi
  printf "%s=%s\n" "$key" "$value" >> "$ENV_FILE"
}

ensure_env_default() {
  local key="$1"
  local value="$2"
  if [ -z "$(get_env_value "$key")" ]; then
    upsert_env "$key" "$value"
  fi
}

prompt_value() {
  local key="$1"
  local label="$2"
  local secret="${3:-false}"
  local current
  current="$(get_env_value "$key")"
  local value=""
  if [ -n "$current" ]; then
    if [ "$secret" = "true" ]; then
      read -r -s -p "$label (bereits gesetzt, Enter = behalten): " value
      echo ""
      [ -n "$value" ] && upsert_env "$key" "$value"
    else
      read -r -p "$label [${current}]: " value
      value="${value:-$current}"
      upsert_env "$key" "$value"
    fi
  else
    if [ "$secret" = "true" ]; then
      read -r -s -p "$label: " value
      echo ""
    else
      read -r -p "$label: " value
    fi
    [ -n "$value" ] && upsert_env "$key" "$value"
  fi
}

install_systemd_overrides() {
  local app_dir="$1"
  local service_override_dir="/etc/systemd/system/spotipi.service.d"
  local alarm_override_dir="/etc/systemd/system/spotipi-alarm.service.d"

  sudo mkdir -p "$service_override_dir"
  cat <<EOF | sudo tee "$service_override_dir/override.conf" >/dev/null
[Service]
WorkingDirectory=$app_dir
EnvironmentFile=-$app_dir/.env
ExecStart=
ExecStart=$app_dir/venv/bin/python run.py
EOF

  sudo mkdir -p "$alarm_override_dir"
  cat <<EOF | sudo tee "$alarm_override_dir/override.conf" >/dev/null
[Service]
WorkingDirectory=$app_dir
EnvironmentFile=-$app_dir/.env
ExecStart=
ExecStart=/usr/bin/env bash -lc '$app_dir/scripts/run_alarm.sh'
EOF
}

echo "🍓 SpotiPi – Guided Installation (Fresh Raspberry Pi)"
echo "====================================================="

if [ ! -f "$PROJECT_ROOT/run.py" ] || [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
  err "Bitte im Repo-Root ausführen (run.py/requirements.txt nicht gefunden)."
  exit 1
fi

if [ -f /proc/device-tree/model ]; then
  MODEL="$(tr -d '\0' </proc/device-tree/model)"
  info "Device: $MODEL"
else
  warn "Raspberry Pi nicht eindeutig erkannt. Installation trotzdem fortsetzen."
fi

info "Installationspfad: $APP_DIR"

if confirm "Systempakete aktualisieren? (apt update/upgrade)" "y"; then
  sudo apt update
  sudo apt upgrade -y
fi

if confirm "Basis-Pakete installieren (git, python3, venv, pip)?" "y"; then
  sudo apt install -y git python3 python3-venv python3-pip
fi

if [ ! -d "$VENV_DIR" ]; then
  info "Virtuelle Umgebung wird erstellt..."
  python3 -m venv "$VENV_DIR"
fi

info "Python-Abhängigkeiten installieren..."
"$VENV_PIP" install --upgrade pip
"$VENV_PIP" install -r "$PROJECT_ROOT/requirements.txt"

if [ ! -f "$ENV_FILE" ]; then
  info "Erstelle $ENV_FILE"
  touch "$ENV_FILE"
fi

info "Spotify-Konfiguration (.env)"
prompt_value "SPOTIFY_CLIENT_ID" "Spotify Client ID"
prompt_value "SPOTIFY_CLIENT_SECRET" "Spotify Client Secret" true
prompt_value "SPOTIFY_USERNAME" "Spotify Username"

if confirm "Hast du bereits einen Spotify Refresh Token?" "n"; then
  prompt_value "SPOTIFY_REFRESH_TOKEN" "Spotify Refresh Token" true
fi

if [ -z "$(get_env_value "FLASK_SECRET_KEY")" ]; then
  info "Generiere FLASK_SECRET_KEY..."
  if command -v python3 >/dev/null 2>&1; then
    secret_key="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  else
    secret_key="$(openssl rand -hex 32)"
  fi
  upsert_env "FLASK_SECRET_KEY" "$secret_key"
fi

ensure_env_default "SPOTIPI_ENV" "production"

chmod 600 "$ENV_FILE"
success ".env vorbereitet ($ENV_FILE)"

if confirm "Spotify Token jetzt generieren? (Browser auf dem Pi erforderlich)" "n"; then
  if ! "$VENV_PY" - <<'PY' >/dev/null 2>&1
import spotipy  # noqa: F401
PY
  then
    info "spotipy wird installiert..."
    "$VENV_PIP" install spotipy
  fi
  (cd "$PROJECT_ROOT" && "$VENV_PY" generate_token.py)
fi

if command -v systemctl >/dev/null 2>&1; then
  if confirm "Systemd-Service installieren & starten?" "y"; then
    if confirm "Alarm-Readiness-Timer aktivieren (empfohlen)?" "y"; then
      (cd "$PROJECT_ROOT" && SPOTIPI_ENABLE_ALARM_TIMER=1 bash ./deploy/install.sh)
    else
      (cd "$PROJECT_ROOT" && SPOTIPI_ENABLE_ALARM_TIMER=0 bash ./deploy/install.sh)
    fi
    install_systemd_overrides "$APP_DIR"
    sudo systemctl daemon-reload
    sudo systemctl restart spotipi.service
    success "Systemd Override gesetzt für $APP_DIR"
  fi
else
  warn "systemctl nicht gefunden; Service-Installation übersprungen."
fi

echo ""
success "Installation abgeschlossen."
echo "🌐 UI: http://spotipi.local:5000"
echo "🧪 Status: sudo systemctl status spotipi.service"
