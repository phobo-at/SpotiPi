# Flask Blueprint Modularization Plan

## Current State Analysis
- **Single File**: `src/app.py` (1166 lines)
- **35 Routes**: Organized by functional sections with emoji headers
- **Well Structured**: Clear separation with section comments
- **Service Integration**: Already uses service manager pattern
- **Challenge**: Growing complexity in single file

## Current Route Organization

### Existing Sections (from app.py)
```python
# 🏠 Main Routes                    # 1 route  - Home page
# 🔧 API Routes - Alarm Management  # 3 routes - Alarm config/status
# 🎵 API Routes - Music & Playback  # 11 routes - Spotify integration
# ⚖️ Health & Monitoring           # 5 routes - System health/metrics
# 😴 API Routes - Sleep Timer       # 3 routes - Sleep functionality  
# 🎵 Music Library & Standalone     # 3 routes - Library management
# 🧪 Debug Routes                   # 1 route  - Development tools
# 📊 Cache Management              # 6 routes - Cache operations
# ⚡ Services & Diagnostics        # 4 routes - Service layer APIs
```

## Proposed Blueprint Structure

### 1. Core Blueprints
```
src/blueprints/
├── __init__.py
├── main.py          # 🏠 Main pages (index, music_library)
├── alarm.py         # 🔧 Alarm management API endpoints
├── music.py         # 🎵 Music & Spotify integration
├── sleep.py         # 😴 Sleep timer functionality
└── system.py        # ⚖️ Health, metrics, debug, cache
```

### 2. Blueprint Configuration
```python
# src/blueprints/__init__.py
from flask import Blueprint

def register_blueprints(app):
    """Register all blueprints with the Flask app."""
    from .main import main_bp
    from .alarm import alarm_bp
    from .music import music_bp
    from .sleep import sleep_bp
    from .system import system_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(alarm_bp, url_prefix='/api')
    app.register_blueprint(music_bp, url_prefix='/api')
    app.register_blueprint(sleep_bp, url_prefix='/api')
    app.register_blueprint(system_bp, url_prefix='/api')
```

## Detailed Blueprint Breakdown

### Main Blueprint (`main.py`)
```python
from flask import Blueprint, render_template, request
from ..services.service_manager import get_service_manager

main_bp = Blueprint('main', __name__)

@main_bp.route("/")
def index():
    """Main page with alarm and sleep interface"""
    # Current index() logic
    
@main_bp.route("/music_library")
def music_library():
    """Music library browser page"""
    # Current music_library() logic
```

### Alarm Blueprint (`alarm.py`)
```python
from flask import Blueprint, request, jsonify
from ..utils.rate_limiting import rate_limit
from ..utils.validation import validate_alarm_config

alarm_bp = Blueprint('alarm', __name__)

@alarm_bp.route("/save_alarm", methods=["POST"])
@rate_limit("config_changes")
def save_alarm():
    """Save alarm configuration"""
    # Current save_alarm() logic

@alarm_bp.route("/alarm_status")
@rate_limit("status_check")
def alarm_status():
    """Get current alarm status"""
    # Current alarm_status() logic

@alarm_bp.route("/alarm/execute", methods=["POST"])
def execute_alarm():
    """Manual alarm execution endpoint"""
    # Current api_alarm_execute() logic
```

### Music Blueprint (`music.py`)
```python
from flask import Blueprint, request, jsonify
from ..api.spotify import get_access_token, get_devices
from ..utils.rate_limiting import rate_limit

music_bp = Blueprint('music', __name__)

@music_bp.route("/music-library")
@rate_limit("spotify_api")
def music_library():
    """Get music library data"""
    # Current api_music_library() logic

@music_bp.route("/music-library/sections")
@rate_limit("spotify_api")
def music_library_sections():
    """Get music library sections"""
    # Current api_music_library_sections() logic

@music_bp.route("/spotify/devices")
@rate_limit("spotify_api")  
def spotify_devices():
    """Get available Spotify devices"""
    # Current api_spotify_devices() logic

# Additional music/playback routes...
```

### Sleep Blueprint (`sleep.py`)
```python
from flask import Blueprint, request, jsonify
from ..core.sleep import start_sleep_timer, stop_sleep_timer
from ..utils.rate_limiting import rate_limit

sleep_bp = Blueprint('sleep', __name__)

@sleep_bp.route("/sleep_status")
@rate_limit("status_check")
def sleep_status():
    """Get current sleep timer status"""
    # Current sleep_status() logic

@sleep_bp.route("/sleep", methods=["POST"])
@rate_limit("config_changes")
def start_sleep():
    """Start sleep timer"""
    # Current sleep() logic

@sleep_bp.route("/stop_sleep", methods=["POST"])
@rate_limit("config_changes")
def stop_sleep():
    """Stop sleep timer"""
    # Current stop_sleep() logic
```

### System Blueprint (`system.py`)
```python
from flask import Blueprint, jsonify, request
from ..utils.rate_limiting import rate_limit, get_rate_limiter
from ..services.service_manager import get_service_manager

system_bp = Blueprint('system', __name__)

# Health & Monitoring
@system_bp.route("/spotify/health")
def spotify_health():
    """Spotify API health check"""
    # Current api_spotify_health() logic

@system_bp.route("/healthz")
def health_check():
    """Kubernetes-style health check"""
    # Current healthz() logic

@system_bp.route("/metrics")
def metrics():
    """Application metrics endpoint"""
    # Current metrics() logic

# Cache Management
@system_bp.route("/cache/status")
def cache_status():
    """Get cache system status"""
    # Current api_cache_status() logic

@system_bp.route("/cache/invalidate", methods=["POST"])
def invalidate_cache():
    """Invalidate all caches"""
    # Current api_cache_invalidate() logic

# Services & Diagnostics
@system_bp.route("/services/health")
def services_health():
    """Service layer health check"""
    # Current api_services_health() logic
```

## Refactored app.py Structure

### Slim Main Application
```python
# src/app.py (reduced from 1166 to ~200 lines)
"""
SpotiPi Main Application - Modular Blueprint Architecture
"""

import os
from pathlib import Path
from flask import Flask, Response, request
from functools import wraps

# Core imports
from .config import load_config
from .utils.logger import setup_logger, setup_logging
from .utils.rate_limiting import get_rate_limiter, add_rate_limit_headers
from .services.service_manager import get_service_manager
from .core.alarm_scheduler import start_alarm_scheduler
from .blueprints import register_blueprints

# Initialize Flask app
project_root = Path(__file__).parent.parent
app = Flask(__name__, 
           template_folder=str(project_root / "templates"), 
           static_folder=str(project_root / "static"),
           static_url_path='/static')

# Configuration
setup_logging()
logger = setup_logger("spotipi")
service_manager = get_service_manager()
rate_limiter = get_rate_limiter()

# Middleware and error handlers
@app.after_request
def after_request(response: Response):
    """CORS, compression, and security headers"""
    # Current after_request logic

def api_error_handler(f):
    """Global error handler decorator"""
    # Current api_error_handler logic

def api_response(success, data=None, message=None, status=200, error_code=None):
    """Standardized API response format"""
    # Current api_response logic

# Register all blueprints
register_blueprints(app)

def run_app(host="0.0.0.0", port=5001, debug=False):
    """Run the Flask app with alarm scheduler"""
    start_alarm_scheduler()
    app.run(host=host, port=port, debug=debug, threaded=True)

if __name__ == "__main__":
    # Current startup logic
```

## Migration Strategy

### Phase 1: Blueprint Infrastructure
1. **Create Blueprint Structure**
   ```bash
   mkdir src/blueprints
   touch src/blueprints/__init__.py
   touch src/blueprints/{main,alarm,music,sleep,system}.py
   ```

2. **Create Blueprint Registration System**
   - Implement `register_blueprints()` function
   - Update `app.py` to use blueprint registration

### Phase 2: Route Migration
1. **Main Blueprint** (2 routes)
   - Move `index()` and `music_library()` routes
   - Test template rendering

2. **Alarm Blueprint** (3 routes)
   - Move alarm management endpoints
   - Verify service layer integration

3. **Music Blueprint** (11 routes)
   - Move Spotify integration endpoints
   - Test API functionality

4. **Sleep Blueprint** (3 routes)
   - Move sleep timer endpoints
   - Verify background task integration

5. **System Blueprint** (16 routes)
   - Move health, metrics, cache, debug routes
   - Verify monitoring functionality

### Phase 3: Shared Components
1. **Extract Common Decorators**
   ```python
   # src/blueprints/decorators.py
   from functools import wraps
   from ..utils.rate_limiting import rate_limit as base_rate_limit
   
   def api_endpoint(rate_limit_category=None):
       """Combined decorator for API endpoints"""
       def decorator(f):
           if rate_limit_category:
               f = base_rate_limit(rate_limit_category)(f)
           f = api_error_handler(f)
           return f
       return decorator
   ```

2. **Blueprint Base Classes**
   ```python
   # src/blueprints/base.py
   class ServiceBlueprint:
       """Base class for service-integrated blueprints"""
       def __init__(self, service_manager):
           self.service_manager = service_manager
       
       def get_service(self, service_name):
           return getattr(self.service_manager, service_name)
   ```

## Benefits of Blueprint Architecture

### Development Benefits
- **Separation of Concerns**: Each blueprint handles one domain
- **Team Collaboration**: Reduced merge conflicts
- **Code Navigation**: Easier to find specific functionality
- **Testing**: Isolated blueprint testing possible

### Maintenance Benefits
- **Modular Updates**: Change one area without affecting others  
- **Code Reuse**: Shared components across blueprints
- **Scaling**: Easy to add new feature areas
- **Documentation**: Self-documenting structure

### Performance Benefits
- **Lazy Loading**: Blueprints loaded on demand
- **Route Organization**: More efficient route matching
- **Memory Usage**: Better memory allocation per feature

## Backward Compatibility

### URL Structure
- **No Changes**: All existing URLs remain identical
- **API Prefixes**: Consistent `/api` prefixing maintained
- **Route Names**: All route names preserved

### Template Integration
- **No Template Changes**: Templates continue to work unchanged
- **URL Generation**: `url_for()` calls remain compatible
- **Static Resources**: No changes to CSS/JS references

### Service Integration
- **Same Service Layer**: Service manager integration unchanged
- **Rate Limiting**: Existing rate limiting rules preserved
- **Authentication**: Token handling remains identical

## Implementation Checklist

### Pre-Migration
- [ ] Backup current `app.py`
- [ ] Create blueprint directory structure
- [ ] Set up blueprint registration system
- [ ] Create shared decorators and utilities

### Migration Steps
- [ ] **Main Blueprint**: Move home and music library pages
- [ ] **Alarm Blueprint**: Move alarm configuration endpoints
- [ ] **Music Blueprint**: Move Spotify integration endpoints  
- [ ] **Sleep Blueprint**: Move sleep timer functionality
- [ ] **System Blueprint**: Move health, cache, debug endpoints

### Post-Migration
- [ ] **Integration Testing**: Verify all endpoints work
- [ ] **Performance Testing**: Ensure no performance regression
- [ ] **Documentation**: Update API documentation
- [ ] **Deployment**: Test on Pi Zero environment

### Validation
- [ ] All 35 routes accessible and functional
- [ ] Service layer integration working
- [ ] Rate limiting and error handling preserved
- [ ] Template rendering unchanged
- [ ] JavaScript API calls working

## File Size Reduction

### Before Modularization
- `src/app.py`: 1166 lines (single file)

### After Modularization  
- `src/app.py`: ~200 lines (core setup)
- `src/blueprints/main.py`: ~100 lines
- `src/blueprints/alarm.py`: ~150 lines  
- `src/blueprints/music.py`: ~400 lines
- `src/blueprints/sleep.py`: ~120 lines
- `src/blueprints/system.py`: ~300 lines
- **Total**: ~1270 lines (better organized)

## Advanced Features (Future)

### Blueprint-Specific Features
```python
# Blueprint-specific middleware
@music_bp.before_request
def verify_spotify_token():
    """Ensure Spotify token is valid for music endpoints"""

# Blueprint-specific error handlers  
@music_bp.errorhandler(SpotifyAPIError)
def handle_spotify_error(error):
    """Handle Spotify-specific errors"""
```

### Dynamic Blueprint Loading
```python
# Load blueprints based on configuration
if config.get('features', {}).get('experimental_enabled'):
    from .experimental import experimental_bp
    app.register_blueprint(experimental_bp, url_prefix='/api/experimental')
```

### Blueprint Testing
```python
# Individual blueprint testing
class TestMusicBlueprint:
    def test_music_library_endpoint(self):
        # Test music blueprint in isolation
```

This blueprint architecture maintains SpotiPi's professional quality while significantly improving maintainability and development experience.