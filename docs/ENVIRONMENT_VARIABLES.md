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

### 📊 **Logging Behavior Matrix**

| System | SPOTIPI_DEV | Environment | Logging Level | File Logging | Log Directory |
|--------|-------------|-------------|---------------|--------------|---------------|
| **Raspberry Pi** | `not set` | production | WARNING | ❌ Disabled | /tmp/spotipi_logs |
| **Raspberry Pi** | `=1` | development | INFO | ✅ Enabled | ~/.spotify_wakeup/logs |
| **Other Systems** | `not set` | development | INFO | ✅ Enabled | ~/.spotify_wakeup/logs |
| **Other Systems** | `=1` | development | INFO | ✅ Enabled | ~/.spotify_wakeup/logs |

### 🎯 **Practical Application**

#### **Development on Raspberry Pi:**
```bash
# Enable full debugging on Pi
SPOTIPI_DEV=1
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
| `SPOTIPI_DEVICE_TTL` | `10` | Device discovery cache in seconds (clamped 5-15). |
| `SPOTIPI_LIBRARY_TTL_MINUTES` | `60` | Full library cache TTL in minutes (clamped 30-120). |
| `SPOTIPI_SECTION_TTL_MINUTES` | `60` | Section (playlists/albums/etc.) cache TTL in minutes. |
| `SPOTIPI_HTTP_TIMEOUT` | `3.0` | Default Spotify HTTP timeout in seconds. |
| `SPOTIPI_HTTP_LONG_TIMEOUT` | `6.0` | Extended timeout for long-running Spotify calls. |
| `SPOTIPI_CACHE_MAX_ENTRIES` | `64` | In-memory cache size before LRU eviction. |

---
*Documented on: September 5, 2025*  
*SpotiPi Auto-Detection System v1.0.0*

````
