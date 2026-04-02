#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_FILE="$PROJECT_DIR/docs/images/spotipi.png"
BASE_URL="${PLAYWRIGHT_BASE_URL:-http://127.0.0.1:5001}"
WAIT_TIMEOUT_MS="${PLAYWRIGHT_SCREENSHOT_WAIT_MS:-2500}"

if [[ -f "$PROJECT_DIR/README.md" ]]; then
  README_FILE="$PROJECT_DIR/README.md"
elif [[ -f "$PROJECT_DIR/Readme.MD" ]]; then
  README_FILE="$PROJECT_DIR/Readme.MD"
else
  echo "Could not find README.md or Readme.MD in $PROJECT_DIR"
  exit 1
fi

started_local_server=0

cleanup() {
  if [[ "$started_local_server" -eq 1 ]]; then
    "$PROJECT_DIR/scripts/local_server.sh" stop >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if [[ -z "${PLAYWRIGHT_BASE_URL:-}" ]]; then
  if "$PROJECT_DIR/scripts/local_server.sh" status | rg -q "Status: running"; then
    echo "Using existing local server at $BASE_URL"
  else
    echo "Starting local server at $BASE_URL"
    "$PROJECT_DIR/scripts/local_server.sh" start
    started_local_server=1
  fi
else
  echo "Using PLAYWRIGHT_BASE_URL=$BASE_URL"
fi

echo "Capturing dashboard screenshot to docs/images/spotipi.png"
npx playwright screenshot \
  --device="Desktop Chrome" \
  --full-page \
  --wait-for-timeout="$WAIT_TIMEOUT_MS" \
  "$BASE_URL/" \
  "$IMAGE_FILE"

if rg -q '<img src="docs/images/spotipi.png"' "$README_FILE"; then
  echo "README reference already points to docs/images/spotipi.png"
else
  cat >>"$README_FILE" <<'EOF'

## Screenshot

<img src="docs/images/spotipi.png" alt="SpotiPi Interface" width="100%">
EOF
  echo "Added screenshot section to Readme.MD"
fi

echo "README screenshot updated."
