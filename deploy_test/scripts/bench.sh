#!/usr/bin/env bash
set -euo pipefail

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for benchmarking" >&2
  exit 1
fi

BASE_URL="${SPOTIPI_BENCH_BASE_URL:-http://localhost:5001}"
RUNS="${SPOTIPI_BENCH_RUNS:-5}"
COLD_WAIT="${SPOTIPI_BENCH_COLD_SLEEP:-2}"

log() {
  printf '[bench] %s\n' "$*"
}

call_endpoint() {
  local method="$1"
  local path="$2"
  shift 2
  local url="${BASE_URL}${path}"
  local response
  response=$(curl -sS -o /tmp/spotipi_bench_body.json "${url}" -w '%{http_code} %{time_total}' "$@" -X "$method") || {
    echo "curl failed for ${url}" >&2
    return 1
  }
  rm -f /tmp/spotipi_bench_body.json
  printf '%s\n' "${response}"
}

measure_request() {
  local label="$1"
  local path="$2"
  local method="${3:-GET}"
  local extra_flag="${4:-}"
  local result code duration
  if [[ -n "${extra_flag}" ]]; then
    result=$(curl -sS -o /tmp/spotipi_bench_body.json ${extra_flag} "${BASE_URL}${path}" -w '%{http_code} %{time_total}' -X "${method}")
  else
    result=$(curl -sS -o /tmp/spotipi_bench_body.json "${BASE_URL}${path}" -w '%{http_code} %{time_total}' -X "${method}")
  fi
  rm -f /tmp/spotipi_bench_body.json
  code="${result%% *}"
  duration="${result##* }"
  printf '%-6s %s -> code=%s time=%ss\n' "${label}" "${path}" "${code}" "${duration}"
}

invalidate_cache() {
  local path="$1"
  if [[ -z "${path}" ]]; then
    return
  fi
  log "invalidate ${path}"
  curl -sS -o /dev/null -X POST "${BASE_URL}${path}" || true
}

measure_route() {
  local name="$1"
  local path="$2"
  local invalidate="$3"
  log "=== ${name} (${path}) ==="
  invalidate_cache "${invalidate}"
  if [[ "${COLD_WAIT}" -gt 0 ]]; then
    sleep "${COLD_WAIT}"
  fi
  measure_request "cold" "${path}"
  for run in $(seq 1 "${RUNS}"); do
    measure_request "warm${run}" "${path}"
  done
}

main() {
  log "Base URL: ${BASE_URL}"
  log "Runs per endpoint: ${RUNS}"
  measure_route "Devices" "/api/spotify/devices" "/api/cache/invalidate/devices"
  measure_route "Library" "/api/music-library?fields=basic" "/api/cache/invalidate/music-library"

  log "Perf monitor snapshot"
  if command -v python3 >/dev/null 2>&1; then
    curl -sS "${BASE_URL}/api/perf/metrics" | python3 -m json.tool
  else
    curl -sS "${BASE_URL}/api/perf/metrics"
  fi
}

main "$@"
