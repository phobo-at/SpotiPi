# SpotiPi Development Guide

## Project Overview
SpotiPi is a Raspberry Pi-optimized Spotify alarm clock with Flask web interface. The architecture is modular with service-oriented design and robust thread safety for concurrent alarm scheduling and web requests.

## Core Architecture

### Modular Structure (src/ based)
- **Entry Point**: `run.py` → `src/app.py` (Flask main app)
- **Service Layer**: `src/services/` - Business logic with standardized `ServiceResult` pattern
- **Core Logic**: `src/core/` - Alarm execution, scheduling, sleep timer
- **API Layer**: `src/api/spotify.py` - Spotify Web API integration with token caching
- **Utilities**: `src/utils/` - Thread safety, validation, caching, logging, library utilities

### Service Manager Pattern
All business logic flows through `ServiceManager` (`src/services/service_manager.py`):
```python
# Always use service layer for business operations
service_manager = get_service_manager()
result = service_manager.alarm.set_alarm_config(config_data)
if result.success:
    # Handle success
```

### Thread Safety (Critical)
- **Config Access**: Always use `config_transaction()` context manager for writes
- **Background Scheduler**: Alarm scheduler runs in background thread - avoid race conditions
- **Token Cache**: Thread-safe token management in `src/utils/token_cache.py`

## Development Workflows

### Local Development
```bash
python run.py  # Development server on :5001
```

### Testing
```bash
pytest
```
- The suite runs against the Flask test client—no external server needed.
- Update tests alongside any changes to business logic or API contracts.

### Deployment to Pi
```bash
./scripts/deploy_to_pi.sh
SPOTIPI_PURGE_UNUSED=1 ./scripts/deploy_to_pi.sh  # optional cleanup of legacy files
```

## Project-Specific Conventions

### Configuration Management
- **Environment Detection**: Auto-detects Pi vs development (`src/config.py`)
- **Low-Power Mode**: `SPOTIPI_LOW_POWER=1` toggles gzip off and limits worker pools (Pi Zero)
- **Thread-Safe Config**: Use `load_config()`/`save_config()` with transaction support
- **Environment Files**: `.env` for Spotify credentials (not synced to Pi)

### Validation Pattern
All user inputs validated through `src/utils/validation.py`:
```python
from src.utils.validation import validate_alarm_config, ValidationError
try:
    valid_config = validate_alarm_config(user_input)
except ValidationError as e:
    return {"error": e.message}
```

### API Response Pattern
Standardized responses using `ServiceResult`:
```python
return ServiceResult(
    success=True,
    data=response_data,
    message="Operation completed"
).to_dict()
```

### Logging Convention
- Use centralized logger: `from src.utils.logger import setup_logger`
- Module-specific loggers: `logger = setup_logger(__name__)`
- Emoji prefixes for log categories: 🚨 (alarm), 🎵 (spotify), 🔧 (system)

## Critical Integration Points

### Spotify API (`src/api/spotify.py`)
- **Token Management**: Auto-refresh with caching in `src/utils/token_cache.py`
- **Rate Limiting**: Built-in retry logic with exponential backoff
- **Parallel Loading**: Worker limits via `_get_library_worker_limit()` (respects low-power mode)
- **Network Health**: `spotify_network_health()` for diagnostics
- **Performance Optimization**: `toggle_playback_fast()` for immediate UI response
- **Targeted Volume Control**: Volume endpoint accepts `device_id` to hit the active player

### Alarm Scheduling (`src/core/alarm_scheduler.py`)
- **Weekday Logic**: Monday=0, Sunday=6 (Python datetime standard)
- **Trigger Window**: ±1.5 minutes tolerance (`ALARM_TRIGGER_WINDOW_MINUTES`)
- **Automatic Disable**: Alarms auto-disable after successful execution

### Pi-Specific Optimizations
- **SD Card Protection**: Minimal logging in production mode
- **Auto-Detection**: Hardware detection in `src/config.py`
- **Service Mode**: Systemd integration via deployment scripts

## Testing Strategy
- **API Contract Tests**: Unified response format validation in `tests/test_api_contract.py`
- **Service Layer Tests**: Mock external dependencies, test business logic
- **Thread Safety Tests**: Concurrent access validation in `tests/`
- **Rate Limiting Tests**: Decorator and throttling validation

## Flask Route Patterns

### Standard Route Structure
Routes follow a consistent pattern with decorators:
```python
@app.route("/api/endpoint")
@api_error_handler          # Structured error responses
@rate_limit("category")     # Rate limiting by operation type
def endpoint_handler():
    return api_response(success=True, data=result)
```

### Rate Limiting Categories
- `"config_changes"` - Settings modifications (save_alarm, device selection)
- `"spotify_api"` - External Spotify API calls (music library, playback)
- `"status_check"` - Status endpoints (alarm_status, cache stats)

### API Response Format
Always use `api_response()` helper for consistent JSON structure:
```python
return api_response(
    success=True/False,
    data=response_data,
    message=t_api("translation_key", request),  # Internationalized messages
    status=200,                                 # HTTP status code
    error_code="validation_error"              # Machine-readable error
)
```

## Cache Migration System

### Unified Cache Architecture
The project uses a sophisticated cache migration layer (`src/utils/cache_migration.py`) to gradually transition from multiple cache implementations to a unified system:

```python
# Access migration layer
cache_layer = get_cache_migration_layer()

# Legacy compatibility wrappers
cached_data = cache_layer.get_legacy_app_cache(force_refresh=False)
cache_layer.set_legacy_app_cache(data, expiry_hours=2)
```

### Cache Types & Storage
- **Music Library**: Persistent file-based cache in `cache/music_library_cache.json`
- **Token Cache**: Thread-safe token storage with auto-refresh
- **Config Cache**: Thread-local caching for performance
- **Migration Stats**: Tracks legacy vs unified cache usage

### Cache Invalidation Patterns
```python
# Thread-safe cache invalidation
invalidate_config_cache()

# Force refresh with backup fallback
cache_layer.get_legacy_app_cache(force_refresh=True)
```

## PWA/Mobile-First Frontend

### Progressive Web App Setup
Complete PWA implementation with `static/manifest.json`:
- **Standalone Display**: Runs as native-like app
- **Touch Optimized**: iOS safe areas, touch targets
- **Dark Theme**: Spotify-inspired design with `#1db954` primary color
- **No Offline Mode**: Requires active internet for Spotify API functionality

### Mobile-First CSS Architecture
Modular CSS architecture with main orchestrator (`static/css/main.css`):
```css
/* Modular structure with @import */
@import url('foundation/variables.css');    /* CSS Custom Properties */
@import url('foundation/base.css');         /* Base styles & PWA */
@import url('components/forms.css');        /* UI Components */
@import url('layout/main-layout.css');      /* Layout & responsive */

/* CSS Custom Properties in foundation/variables.css */
:root {
  --color-primary: #1db954;
  --color-bg: #1e1e1e;
  --spacing-md: 1rem;
}
```

### JavaScript Patterns
Client-side code (`static/js/main.js`) follows specific patterns:
- **Modular Architecture**: ES6 modules with clear separation (`modules/api.js`, `modules/ui.js`, etc.)
- **DOM Caching**: Central `DOM.getElement()` system for performance
- **API Polling**: Smart backoff with configurable intervals
- **Cache-First**: Uses `If-None-Match` headers for 304 responses
- **Error Boundaries**: Structured error handling matching backend

## Deployment & Service Setup

### Production Deployment Pipeline
```bash
./scripts/deploy_to_pi.sh                    # Allowlist rsync + systemd restart
SPOTIPI_PURGE_UNUSED=1 ./scripts/deploy_to_pi.sh  # Optional one-time purge of legacy assets
```

### Systemd Integration
Production runs via systemd service (`spotify-web.service`):
- **Auto-restart**: On failure or system reboot
- **Environment**: Production mode with minimal logging
- **User Context**: Runs as `pi` user with proper permissions
- **Port**: Production uses `:5000`, development `:5001`

### Background Process Management
```python
# Server management (scripts/server_manager.py)
manager = SpotiPiServerManager()
manager.start()    # Daemon with PID file
manager.stop()     # Graceful shutdown
manager.restart()  # Zero-downtime restart
```

### Pi-Specific Optimizations
- **Low Power Mode**: `SPOTIPI_LOW_POWER=1` disables gzip and caps worker pools for Pi Zero
- **SD Card Protection**: Minimal logging in production to prevent wear
- **Hardware Detection**: Auto-detects Pi vs development environment
- **Service Health**: Built-in health checks and automatic recovery

## Common Patterns
- **Tooling**: Run `pre-commit install`, `pre-commit run --all-files`, and `pytest` before submitting PRs
- **Error Handling**: Always return structured responses, never bare exceptions
- **Config Updates**: Use `config_transaction()` for atomic config changes  
- **Service Access**: Get services via `get_service_manager().service_name`
- **Background Tasks**: Use Flask's thread-safe patterns for alarm scheduling
- **Language**: Project language is English. Make sure that all comments, logs and .md files are created in English.
- **Translations**: Make sure that user-facing strings are translatable using the `t_api` function.
