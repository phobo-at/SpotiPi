#!/usr/bin/env bash

set -euo pipefail

BASE_URL=${1:-http://localhost:5001}

echo "📏 Measuring cold TTFB for ${BASE_URL}/"
curl -s -o /dev/null -w 'cold_ttfb=%{time_starttransfer}s\n' "${BASE_URL}/"

sleep 1

echo "📏 Measuring warm TTFB"
curl -s -o /dev/null -w 'warm_ttfb=%{time_starttransfer}s\n' "${BASE_URL}/"

echo "📡 Endpoint hydration times"
for endpoint in /api/dashboard/status /playback_status /api/devices; do
  curl -s -o /dev/null -w "${endpoint}=%{time_starttransfer}s\\n" "${BASE_URL}${endpoint}"
done
