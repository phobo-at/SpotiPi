# Changelog

All notable changes to SpotiPi will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.1] - 2025-09-15

### 🐛 Critical Bugfix - Rate Limiting

This patch release fixes a critical production issue where alarm settings couldn't be saved due to overly restrictive rate limiting for single-user installations.

### 🔧 Fixed

**Rate Limiting Optimization for Single-User Installation:**
- Increased `config_changes` limit from 10/min to 100/min
- Increased `api_general` limit from 100/min to 300/min  
- Increased `spotify_api` limit from 50/min to 80/min (respects Spotify's 100/min limit)
- Increased `music_library` limit from 30/min to 100/min
- Increased `status_check` limit from 200/min to 500/min
- Increased `api_strict` limit from 20/min to 50/min

**Reduced Recovery Times:**
- Config changes block time: 10min → 30s
- API general block time: 1min → 30s
- Spotify API block time: 5min → 2min
- Music library block time: 2min → 1min

### 📋 Impact

- ✅ Alarm settings can now be saved without rate limiting errors
- ✅ Smooth UI interactions and responsive interface
- ✅ Better user experience for single-user Raspberry Pi installations
- ✅ Still respects Spotify API limits to prevent service blocking

### 🔍 Technical Details

The original rate limiting configuration was designed for multi-tenant systems but was too restrictive for single-user local installations. This update optimizes the limits while maintaining protection against API abuse and respecting external service constraints.

## [1.2.0] - 2025-09-14

### 🚀 Major Frontend Architecture Refactoring

This is a significant release that completely modernizes the frontend architecture with a 2200+ line JavaScript file refactored into a clean, modular ES6 system.

### ✨ New Features

**Modern JavaScript Architecture:**
- Complete modular ES6 refactoring of monolithic 2200+ line script.js
- 8 specialized modules with clear separation of concerns:
  - `main.js`: Application entry point and orchestration
  - `modules/state.js`: Centralized configuration and DOM caching
  - `modules/api.js`: Unified API layer with rate limiting and caching
  - `modules/ui.js`: Reactive UI management and DOM manipulation
  - `modules/settings.js`: Alarm and sleep timer configuration
  - `modules/eventListeners.js`: Event handler management
  - `modules/playlistSelector.js`: Music library modal functionality
  - `modules/weekdays.js`: Weekday selection logic
  - `modules/translation.js`: Internationalization support

**Performance Improvements:**
- Centralized DOM caching system for improved performance
- Smart API polling with configurable intervals
- ETag-based API response caching
- Rate limiting with intelligent backoff mechanisms

**Code Quality Enhancements:**
- Complete internationalization with English comments and backend translation integration
- Modern async/await patterns throughout codebase
- Comprehensive error handling with graceful degradation
- Clean import/export module organization

### 🔧 Technical Improvements

- Fixed Flask static file routing issues
- Resolved all circular dependency problems in ES6 modules
- Implemented direct event handlers for reliable sleep timer functionality
- Added comprehensive translation key support in translations.py
- Enhanced code maintainability and scalability

### 🐛 Bug Fixes

- Sleep timer activation/deactivation now works reliably with immediate UI feedback
- Eliminated JavaScript console errors from module loading
- Fixed missing imports and reference errors
- Resolved complex checkbox state management issues

### 📝 Code Quality

- Senior-level code review completed (Grade: B+ 85/100)
- Excellent maintainability and very good scalability
- All user-facing strings now properly translatable
- Consistent coding patterns and modern best practices

### 📋 Migration Notes

- Legacy script.js backed up as script.js.bak
- No breaking changes to API endpoints or configuration
- Automatic migration of existing functionality to new architecture
- All existing features maintained with improved reliability

## [1.1.1] - 2025-09-12

### 🛠 Patch Release

Small corrective release after reverting experimental modular frontend changes.

### Changed
- Reverted temporary modular JS refactor (app.js + feature modules) to restore stable legacy bundle while investigation continues.
- Maintained previous 1.1.0 feature set (no feature removals for end users).

### Fixed
- Eliminated potential inconsistent state caused by partially deployed modular scripts.
- Ensured version reporting (`get_app_info()`) reflects correct semantic patch bump.

### Notes
- Modular frontend work will return in a future minor release (>= 1.2.0) with full test coverage and incremental migration plan.
- No database or API contract changes in this patch.


### ✨ New Features

**Music Library Enhancements:**
- 🎤 **Artist Top Tracks** - Interactive artists tab now shows and plays top tracks for each artist
- ▶️ **Direct Track Playback** - Play individual tracks directly from the music library
- 🔀 **Enhanced Shuffle Support** - Shuffle mode now available for both alarm and sleep timer

**Alarm System Improvements:**
- 📅 **Daily Alarm Support** - Alarms with no weekdays selected now trigger daily at the next possible time
- 🔄 **Improved Scheduling Logic** - Better handling of alarm timing and weekday calculations

**API & Performance:**
- ⏱️ **Increased API Timeout** - Spotify API timeout extended from 10s to 30s for better reliability
- 🚀 **Enhanced Error Handling** - Improved connection stability and error recovery

### 🐛 Bug Fixes

- Fixed alarm not starting when no weekdays were selected
- Resolved Spotify API timeout issues with slow connections
- Fixed shuffle mode not activating properly for alarms
- Improved CSS alignment for toggle switches across different UI sections

### 🔧 Technical Improvements

- Added `/play` endpoint for direct track playback control
- Enhanced `start_playback()` function to support both playlist contexts and individual tracks
- Improved JavaScript playback functions with better error handling
- Optimized deployment scripts with detailed logging for file operations

### 🎨 UI/UX Improvements

- Better visual alignment of toggle switches throughout the interface
- Enhanced responsive design for artist top tracks display
- Improved loading states and user feedback during playback operations

## [1.0.0] - 2025-08-14

### 🎉 Initial Release

SpotiPi v1.0.0 is the first stable release of the Smart Alarm Clock & Sleep Timer with Spotify Integration.

#### ✨ Features

**Core Functionality:**
- 🔔 **Smart Alarm System** - Wake up to your favorite Spotify music with customizable schedules
- 😴 **Sleep Timer** - Fall asleep to music with automatic fade-out and stop functionality
- 🎵 **Music Library Browser** - Browse and play your Spotify playlists, albums, artists, and tracks
- 🔊 **Multi-Device Support** - Control playback on any connected Spotify device

**Alarm Features:**
- ⏰ Flexible time scheduling with weekday selection
- 🎶 Choose from playlists, albums, artists, or individual tracks
- 🔀 Shuffle and fade-in options
- 📱 Easy enable/disable toggle
- 🔊 Volume control with automatic device synchronization

**Sleep Timer Features:**
- ⏱️ Preset durations (15, 30, 45, 60 minutes) or custom time
- 🎵 Music selection from entire Spotify library
- 🌙 Gradual fade-out for peaceful sleep
- 🔄 Easy start/stop controls

**User Interface:**
- 📱 Responsive PWA design for mobile and desktop
- 🎨 Dark theme optimized for nighttime use
- 🚀 Fast and intuitive navigation
- ♿ Accessibility features with proper ARIA labels

**Technical Features:**
- 🔧 Automatic Raspberry Pi detection and optimization
- 💾 SD-card friendly logging system
- 🌐 RESTful API with comprehensive error handling
- 🔄 Real-time status updates and synchronization
- 🛡️ Robust error handling and recovery

#### 🏗️ System Requirements

- **Python 3.8+** with Flask framework
- **Active Spotify Premium Account** with API access
- **Spotify Application** registered in Spotify Developer Dashboard
- **Network Connection** for Spotify API communication

#### 🚀 Supported Platforms

- **Raspberry Pi** (optimized for headless operation)
- **Linux/macOS/Windows** (development and testing)
- **Mobile Browsers** (PWA functionality)

#### 📋 Installation

1. Clone the repository
2. Install Python dependencies: `pip install -r requirements.txt`
3. Configure Spotify API credentials
4. Run the application: `python run.py`

For detailed setup instructions, see [README.md](README.md).

---

## Release Philosophy

**v1.0.0** represents a stable, feature-complete release suitable for daily use. All core functionality has been thoroughly tested and optimized for both development and production environments.

Future releases will follow semantic versioning:
- **MAJOR** versions for breaking changes
- **MINOR** versions for new features (backward compatible)
- **PATCH** versions for bug fixes (backward compatible)# Test Hook Commit Fri Aug 15 00:59:29 CEST 2025