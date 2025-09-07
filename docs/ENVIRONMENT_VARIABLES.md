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

---
*Documented on: September 5, 2025*  
*SpotiPi Auto-Detection System v1.0.0*

````
