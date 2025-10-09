# SpotiPi Benchmark Guide

This guide explains how to measure request latency for the Raspberry Pi Zero W deployment using the lightweight instrumentation that ships with SpotiPi.

## What gets measured
- `GET /api/spotify/devices`: Spotify Connect device discovery path.
- `GET /api/music-library?fields=basic`: first page of the music library UI.
- Global Flask request timings (P50/P95/latest) exposed via `/api/perf/metrics`.

Per-endpoint timings are captured with a high-resolution timer and persisted in-memory with an LRU-sized buffer. Logging is rate limited to avoid stressing the Pi Zero W storage subsystem.

## Prerequisites
- The Flask app is running locally or on the Pi (`run.py` or systemd service).
- Spotify credentials are configured so `get_access_token()` succeeds.
- `curl` is available; `python3` (optional) formats JSON output.

## Quick run
```bash
# From the repository root
scripts/bench.sh
```

The script performs the following steps for each hot path:
1. Invalidates the unified cache (`/api/cache/invalidate/...`).
2. Sleeps briefly to ensure the cold run is truly uncached.
3. Executes a cold request (cache miss).
4. Executes several warm requests (cache hits).
5. Prints the current `/api/perf/metrics` snapshot.

Environment variables:
- `SPOTIPI_BENCH_BASE_URL` (default `http://localhost:5001`)
- `SPOTIPI_BENCH_RUNS` (default `5` warm iterations)
- `SPOTIPI_BENCH_COLD_SLEEP` (seconds before cold run, default `2`)

Example output:
```
[bench] Base URL: http://localhost:5001
[bench] Runs per endpoint: 5
[bench] === Devices (/api/spotify/devices) ===
[bench] invalidate /api/cache/invalidate/devices
cold   /api/spotify/devices -> code=200 time=1.342s
warm1  /api/spotify/devices -> code=200 time=0.182s
...
[bench] Perf monitor snapshot
{
  "timestamp": "2024-05-06T19:12:45Z",
  "metrics": {
    "GET api_spotify_devices": {
      "count": 18,
      "avg_ms": 310.5,
      "p50_ms": 185.1,
      "p95_ms": 1290.2,
      "latest_ms": 176.4,
      "slowest_ms": 1428.7,
      "last_status": 200
    },
    "OVERALL": {
      "count": 86,
      "avg_ms": 212.3,
      "p50_ms": 94.7,
      "p95_ms": 678.5,
      "slowest_ms": 1526.4
    }
  }
}
```

Use the P50/P95 values to verify that the warm start device list and first playlist page remain under the 1.5 s target on the Pi Zero W. For cold starts, ensure P95 stays below 3 s.

## Exporting metrics
The `/api/perf/metrics` endpoint can be collected by external monitoring (Prometheus exporter, Telegraf, etc.) to build historical latency charts. The payload already includes millisecond values for P50, P95, latest, and slowest samples.

## Troubleshooting
- **401 responses**: ensure the Spotify token cache is primed and the `.env` in production includes valid credentials.
- **High cold-start latency**: check the Pi’s network conditions and confirm the unified cache directory (`./cache/`) is writable.
- **Instrumentation spam**: adjust `SPOTIPI_PERF_LOG_INTERVAL` (seconds) or `SPOTIPI_PERF_WARN_THRESHOLD` (seconds) to throttle log output on low-power hardware.
