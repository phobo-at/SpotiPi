````markdown
# 🌍 ENVIRONMENT VARIABLES DOCUMENTATION

## 📋 **SpotiPi Environment Configuration**

### 🎯 **Auto-Detection System**

SpotiPi features an **intelligent Auto-Detection System** for Raspberry Pi:

```python
# Automatic Raspberry Pi Detection:
✅ ARM architecture + Linux
✅ Hostname contains "raspberrypi"  
✅ Pi-specific file: /sys/firmware/devicetree/base/model
✅ Manual override: SPOTIPI_RASPBERRY_PI=1
```

**Automatic Behavior:**
- **Raspberry Pi detected** → `production` environment, minimal logging (SD card protection)
- **Other systems** → `development` environment, full logging

### 🔧 **Environment Variables Override**

#### **SPOTIPI_ENV** - Environment Override
```bash
SPOTIPI_ENV=development  # or 'production'
```
- **Function:** Overrides automatic environment detection
- **Use Cases:**
  - Test Raspberry Pi in development mode
  - Set non-Pi system to production
  - Explicit control over config loading

#### **SPOTIPI_DEV** - Development Logging
```bash
SPOTIPI_DEV=1  # Enables development logging
```
- **Function:** Forces full logging (even on Raspberry Pi)
- **Use Cases:**
  - **CRITICAL for Pi debugging:** Without this flag minimal logging
  - Full logs for troubleshooting on Pi
  - Development features on production environment

#### **SPOTIPI_JSON_LOGS** - Structured JSON Logging
```bash
SPOTIPI_JSON_LOGS=1  # Enables JSON-formatted logs
```
- **Function:** Outputs logs in structured JSON format for better parsing and correlation
- **Defaults:** Automatically enabled on Raspberry Pi in production mode (since v1.3.8)
- **Use Cases:**
  - Log aggregation systems (journalctl, Loki, ELK stack)
  - Automated log analysis and alerting
  - Correlation of alarm failures across multiple fields
  - Machine-readable logs for monitoring dashboards
- **Output Example:**
  ```json
  {"timestamp": "2025-11-04T06:30:00.123Z", "level": "ERROR",
   "logger": "alarm_scheduler", "message": "Alarm execution failed",
   "alarm_id": "20251104T063000Z", "error_code": "device_not_found",
   "source": "alarm.py:184"}
  ```

#### **SPOTIPI_RASPBERRY_PI** - Pi Simulation
```bash
SPOTIPI_RASPBERRY_PI=1  # Forces Pi behavior
```
- **Function:** Simulates Raspberry Pi behavior on any system
- **Use Cases:**
- Test Pi-optimized logging settings
- Simulate production behavior on development machine
- CI/CD pipeline testing

#### **SPOTIPI_TIMEZONE** - Runtime Timezone Override
```bash
SPOTIPI_TIMEZONE="Europe/Berlin"
```
- **Function:** Overrides the configured timezone used for alarms, scheduler and sleep timer calculations
- **Defaults:** Falls back to the `timezone` field in the SpotiPi config (`Europe/Vienna` if unset)
- **Use Cases:**
  - Deployments outside Central Europe requiring accurate local time handling
  - Runtime overrides in containerised environments without writing config files
  - Testing alarm behaviour for different locales without editing JSON configs

#### **PORT** - Port Override
```bash
PORT=5001  # Custom port
```
- **Function:** Overrides default port logic
- **Default Behavior:**
  - Production: Port 5000
  - Development: Port 5001

#### **SPOTIPI_APP_NAME** - App Namespace
```bash
SPOTIPI_APP_NAME=spotipi  # Changes ~/.spotipi and log names
```
- **Function:** Names the per-user config directory (e.g., `~/.spotipi`) and log prefixes.
- **Use Cases:**
  - Run multiple instances side-by-side
  - Isolate config/credentials per deployment

#### **SPOTIPI_CORS_ORIGINS** - CORS Allowlist
```bash
SPOTIPI_CORS_ORIGINS=http://spotipi.local,http://localhost:5001
```
- **Function:** Comma-separated list of allowed origins for CORS.
- **Defaults:** If unset, requests from the default host are allowed.

#### **SPOTIPI_DEFAULT_HOST** - CORS Fallback Host
```bash
SPOTIPI_DEFAULT_HOST=spotipi.local
```
- **Function:** Fallback host used to allow same-LAN UI access when no explicit CORS allowlist is set.

#### **SPOTIPI_WARMUP** - Background Snapshot Warmup
```bash
SPOTIPI_WARMUP=0  # Disable background warmup (useful for tests)
```
- **Function:** Enables/disables background cache warmup at startup.

### 📊 **Logging Behavior Matrix**

| System | SPOTIPI_DEV | SPOTIPI_JSON_LOGS | Environment | Logging Level | File Logging | Format |
|--------|-------------|-------------------|-------------|---------------|--------------|--------|
| **Raspberry Pi** | `not set` | `auto (1)` | production | WARNING | ❌ Disabled | JSON (systemd) |
| **Raspberry Pi** | `=1` | `auto (1)` | development | INFO | ✅ Enabled | JSON |
| **Raspberry Pi** | `=1` | `=0` | development | INFO | ✅ Enabled | Traditional |
| **Other Systems** | `not set` | `=0` | development | INFO | ✅ Enabled | Colored |
| **Other Systems** | `not set` | `=1` | development | INFO | ✅ Enabled | JSON |

**Notes:**
- JSON logging is **automatically enabled** on Raspberry Pi in production mode (since v1.3.8)
- Set `SPOTIPI_JSON_LOGS=0` to force traditional logging even on Pi
- JSON logs include structured fields: `timestamp`, `level`, `logger`, `message`, plus any custom context
- Traditional colored logs are best for local development; JSON logs for production monitoring

### 🎯 **Practical Application**

#### **Development on Raspberry Pi:**
```bash
# Enable full debugging on Pi
SPOTIPI_DEV=1
```

#### **Production Monitoring with JSON Logs:**
```bash
# Query alarm failures from journalctl
ssh pi@spotipi.local 'journalctl -u spotipi.service --since "2025-11-04 06:00" | grep "alarm_probe"'

# Extract specific alarm execution
ssh pi@spotipi.local 'journalctl -u spotipi.service -o json | jq "select(.MESSAGE | contains(\"alarm_id\"))"'

# Count errors by error_code
ssh pi@spotipi.local 'journalctl -u spotipi.service --since today -o json | jq -r "select(.LEVEL == \"ERROR\") | .MESSAGE" | jq -r ".error_code" | sort | uniq -c'
```

#### **Production Testing on Dev Machine:**
```bash
# Simulate Pi behavior
SPOTIPI_RASPBERRY_PI=1
SPOTIPI_ENV=production
```

#### **Custom Environment:**
```bash
# Explicit control
SPOTIPI_ENV=production
SPOTIPI_DEV=1          # Production config, but development logging
PORT=8080              # Custom port
```

### ⚠️ **Important Notes**

#### **SD Card Protection:**
- **Raspberry Pi without SPOTIPI_DEV=1:** Minimal logging to RAM (/tmp)
- **Prevents:** Excessive SD card writes that lead to degradation

#### **Override Hierarchy:**
1. **Environment Variables** (highest priority)
2. **Auto-Detection** (medium priority) 
3. **Default Values** (lowest priority)

#### **Debugging Recommendations:**
- **Pi Issues:** Always set `SPOTIPI_DEV=1` for full logs
- **Environment Issues:** Set `SPOTIPI_ENV` explicitly
- **Port Conflicts:** Use `PORT` variable

### 🚀 **Performance Flags (Pi Zero W)**

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPOTIPI_MAX_CONCURRENCY` | `2` | Limits concurrent Spotify API requests; keep low on the Pi Zero W. |
| `SPOTIPI_LIBRARY_WORKERS` | `2` (Pi) / `3` (Dev) | Max parallel workers for library loading. Automatically respects MAX_CONCURRENCY. |
| `SPOTIPI_DEVICE_TTL` | `10` | Device discovery cache in seconds (clamped 5-15). |
| `SPOTIPI_LIBRARY_TTL_MINUTES` | `60` | Full library cache TTL in minutes (clamped 30-120). |
| `SPOTIPI_SECTION_TTL_MINUTES` | `60` | Section (playlists/albums/etc.) cache TTL in minutes. |
| `SPOTIPI_HTTP_TIMEOUT` | `3.0` | Default Spotify HTTP timeout in seconds. |
| `SPOTIPI_HTTP_LONG_TIMEOUT` | `6.0` | Extended timeout for long-running Spotify calls. |
| `SPOTIPI_CACHE_MAX_ENTRIES` | `64` | In-memory cache size before LRU eviction. |
| `SPOTIPI_LIBRARY_LOAD_TIMEOUT` | `20.0` | Timeout in seconds for parallel library loading (prevents blocking on poor network). |
| `SPOTIPI_LIBRARY_SECTION_TIMEOUT` | `15.0` | Timeout in seconds for individual section loading (playlists/albums/tracks/artists). |
| `SPOTIPI_CONFIG_CACHE_TTL` | `30.0` (Pi) / `5.0` (Dev) | Config cache TTL in seconds. Higher on Pi to reduce SD-Card reads. |
| `SPOTIPI_DEVICE_DISK_PERSIST_SECONDS` | `600` (Pi) / `180` (Dev) | Interval in seconds before device cache is written to disk. Higher on Pi to reduce SD-Card writes. |
| `SPOTIPI_DEVICE_DISK_CACHE` | `1` | Enable/disable device cache persistence to disk. Set to `0` to disable disk writes entirely. |
| `SPOTIPI_DEVICE_DISK_MIN_TTL` | `60` | Minimum TTL required for device cache to be written to disk (prevents hot-loop writes). |
| `SPOTIPI_PLAYBACK_CACHE_TTL` | `5.0` (Pi) / `1.5` (Dev) | Playback state cache TTL in seconds. Higher on Pi to reduce Spotify API calls. |
| `SPOTIPI_STATUS_CACHE_SECONDS` | `5.0` (Pi) / `1.5` (Dev) | Dashboard status cache TTL in seconds. Higher on Pi to reduce API polling. |
| `SPOTIPI_PLAYBACK_STATUS_CACHE_SECONDS` | `5.0` (Pi) / `1.5` (Dev) | Playback status cache TTL in seconds. Higher on Pi to reduce API polling. |

### 🔄 **HTTP Retry Flags (Spotify API Resilience)**

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPOTIPI_HTTP_BACKOFF_FACTOR` | `0.6` | Exponential backoff multiplier for retries. Higher = longer waits between retries. |
| `SPOTIPI_HTTP_RETRY_TOTAL` | `5` | Maximum total retries across all error types (connect, read, status). |
| `SPOTIPI_HTTP_RETRY_CONNECT` | `3` | Maximum retries for connection errors (network unreachable, timeout). |
| `SPOTIPI_HTTP_RETRY_READ` | `4` | Maximum retries for read timeouts (server slow to respond). |
| `SPOTIPI_HTTP_POOL_CONNECTIONS` | `5` (Pi) / `10` (Dev) | Max simultaneous connections in HTTP pool. Lower on Pi to reduce memory. |
| `SPOTIPI_HTTP_POOL_MAXSIZE` | `10` (Pi) / `20` (Dev) | Max total connections in pool (active + idle). Lower on Pi to reduce memory. |
| `SPOTIPI_HTTP_TIMEOUTS` | `4.0,15.0` | Connect and read timeouts as CSV (e.g., "4.0,15.0"). |
| `SPOTIPI_HTTP_CONNECT_TIMEOUT` | `4.0` | Connect timeout in seconds (alternative to TIMEOUTS). |
| `SPOTIPI_HTTP_READ_TIMEOUT` | `15.0` | Read timeout in seconds (alternative to TIMEOUTS). |

**Retry Behavior (since v1.0, documented v1.3.8):**
- **Auto-retries:** 429 (rate limit), 500, 502, 503, 504 (server errors)
- **Respects `Retry-After` header** for 429 responses
- **No retry on:** 400, 401, 403, 404 (client errors)
- **Backoff calculation:** `backoff_factor * (2 ** (attempt - 1))`
  - Attempt 1: 0.6s, Attempt 2: 1.2s, Attempt 3: 2.4s, Attempt 4: 4.8s, Attempt 5: 9.6s
- **Total retry time:** ~18.6s with default settings (5 retries, backoff=0.6)

**Use Cases:**
- **Flaky network:** Increase `SPOTIPI_HTTP_RETRY_TOTAL=8` and `BACKOFF_FACTOR=0.8`
- **Fast network:** Reduce `RETRY_TOTAL=3` and `BACKOFF_FACTOR=0.3` for quicker failures
- **Frequent rate limits:** Increase `BACKOFF_FACTOR=1.5` to respect Spotify's limits

### ⏰ **Deployment & Alarm Flags**

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPOTIPI_ENABLE_ALARM_TIMER` | `1` | Controls systemd timer activation for alarm robustness. Set to `0` to disable timer and rely solely on in-process scheduler. |
| `SPOTIPI_DEPLOY_SYSTEMD` | `1` | Whether `deploy_to_pi.sh` updates systemd units. Set to `0` to skip systemd sync. |
| `SPOTIPI_FORCE_SYSTEMD` | `0` | Forces systemd unit re-installation even if unchanged. Set to `1` for manual override. |
| `SPOTIPI_PURGE_UNUSED` | `0` | Removes test/doc files from Pi during deployment. Set to `1` for cleanup. |

**Alarm Timer Details:**
- **Timer runs daily at 05:30** via `spotipi-alarm.timer`
- **Persistent catch-up** after reboot/downtime (`Persistent=true`)
- **Backup layer** in addition to in-process alarm scheduler thread
- **Since v1.3.8:** Enabled by default for production robustness

---
*Documented on: September 5, 2025*  
*Updated on: November 4, 2025 (v1.3.8 - Alarm Timer)*  
*SpotiPi Auto-Detection System v1.0.0*

````
