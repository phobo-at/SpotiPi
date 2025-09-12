# Changelog

All notable changes to SpotiPi will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2025-09-09
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
# Vollautomatisches Hook System Test Fri Aug 15 01:02:03 CEST 2025
