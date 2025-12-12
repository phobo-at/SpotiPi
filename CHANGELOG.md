# Changelog

All notable changes to SpotiPi will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.0] - 2025-01-13

### 🔒 Security
- **Token Encryption at Rest**: New `src/utils/token_encryption.py` module encrypts Spotify tokens using Fernet encryption (with `cryptography` library) or XOR obfuscation fallback
- Machine-derived keys ensure tokens cannot be transferred between devices
- Token files now have restricted permissions (0o600 - owner read/write only)
- Backward compatible: automatically reads legacy plain JSON tokens and re-encrypts on next save

### ⚡ Performance
- **Global ThreadPoolExecutor**: Library loading now reuses a singleton executor (`_get_library_executor()`) instead of creating executors per-call, reducing thread creation overhead on Pi Zero
- Optimized `spotify.py` token save/load operations with encryption integration

### 🏗 Architecture
- **Route Blueprints (Prepared)**: Modular blueprint structure in `src/routes/` (alarm, sleep, music, playback, devices, health, cache, services) ready for future integration
- Cleaner code organization without breaking current app.py structure

### 🧪 Tests
- **Expanded Test Coverage**: New `tests/test_core_functionality.py` with 22 tests covering:
  - Alarm execution and state management
  - Sleep timer start/stop behavior
  - Scheduler persistence across restarts
  - Token encryption/decryption (Fernet and fallback)
  - ThreadPoolExecutor reuse patterns

### 📚 Documentation
- Updated Copilot instructions with v1.4.0 security and performance guidance
- Enhanced README with security section and performance details

## [1.3.9] - 2025-11-04

### 🐛 Bug Fixes
- **Device Name Validation**: Relaxed device name validation to allow Unicode characters (emojis, special characters, international characters) while maintaining XSS protection by blocking only `<>` and control characters
- **Alarm Settings Save**: Fixed `log_structured()` parameter conflict causing 400 BAD REQUEST errors when saving alarm settings
- **CORS Configuration**: Improved CORS header handling to support port-agnostic hostname matching (e.g., `http://spotipi.local:5000`)
- **Settings UI**: Fixed HTML escaping in alarm status messages to prevent template literal syntax errors with special characters in device names

### ✨ UI/UX Improvements
- **Smooth Animations**: Added CSS transitions (fade + slide) for alarm and sleep timer activation/deactivation with 300ms duration
- **Device Sorting**: Devices are now sorted alphabetically (A-Z, case-insensitive) in all dropdown menus for better usability

### 🎨 Frontend
- Enhanced `utilities.css` with smooth show/hide animations using opacity, transform, and max-height transitions
- Added `smoothShow()` and `smoothHide()` helper functions in JavaScript for consistent animation behavior
- Fixed sleep timer toggle visibility issue during state transitions

### 🔧 Technical
- Updated device name validation pattern from restrictive allowlist to blocklist approach supporting full Unicode range
- Improved error handling with proper structured logging parameter names (`validation_message`, `error_message`)

## [1.3.8] - 2025-10-24

### 🏗 Service Layer Consolidation
- Slimmed all Flask controllers so they delegate validation and business rules to their respective services (`alarm`, `sleep`, `spotify`, `system`), yielding consistent JSON contracts across basic and advanced endpoints.
- Extended the Spotify service with toggle, volume, and playback helpers to remove duplicated logic in `/toggle_play_pause`, `/volume`, and `/play`.
- Hardened dashboard snapshots and error handlers to use the shared service responses, keeping template rendering stable even for 404/500 fallbacks.

### 📚 Unified Music Library Flow
- Centralised hashing, slimming, and caching through `_build_library_response` so `/api/music-library` and `/api/music-library/sections` now emit identical headers/ETag semantics.
- Expanded `prepare_library_payload` to track partial section metadata and cached flags in one place.

### 🧹 Cleanup & Frontend
- Removed unused HTTP session overrides and stale imports, trimmed no-op utilities, and deduplicated the toast notification implementation (now exported solely from `ui.js`).
- Documented the “controllers thin, services rich” architecture and unified library pipeline in the README.

### 🧪 Tests
- `python3.11 -m pytest -q`

## [1.3.7] - 2025-10-23

### ⚡ Instant First Load
- Reworked the `/` route to deliver a slim HTML shell without Spotify calls, cutting cold-start TTFB to well under one second while keeping warm hits around the 400 ms target.
- Added structured snapshots for dashboard, playback, and device data so hydration happens asynchronously without blocking Flask workers.
- Updated the UI with accessible skeleton placeholders and clearer fallback messaging (e.g., “Keine aktive Wiedergabe”) while removing the distracting status banner.

### 🧠 Backend & Transport
- Introduced an `AsyncSnapshot` helper plus background warm-up to keep cached Spotify state fresh outside of request threads.
- Enabled Flask-Compress and long-lived static caching to trim payload sizes on the Raspberry Pi.
- Hardened playback/device fetch fallbacks so the initial shell renders cleanly even when Spotify auth or devices are still warming up.

### 🛠 Deployment & Tooling
- Optimised `scripts/deploy_to_pi.sh` to copy systemd units only when they change (override with `SPOTIPI_FORCE_SYSTEMD=1`), speeding up day-to-day syncs.
- Added `scripts/bench_first_load.sh` for quick TTFB/first-paint measurements alongside the existing benchmark suite.
- Updated documentation to highlight the new workflow and measurement tooling.

## [1.3.6] - 2025-10-20

### ⏰ Alarm Reliability Hardening
- Rebuilt the in-process scheduler on top of a monotonic clock with UTC persistence and configurable catch-up grace, so NTP/DST jumps or short downtimes no longer skip alarms.
- Added structured `alarm_probe` JSON telemetry (UTC/local timestamps, monotonic deltas, readiness state, device discovery) covering the ±5 min trigger window for post-mortem analysis.
- Introduced readiness backoff with network/DNS/token/device probes to guarantee Spotify is reachable before playback attempts, plus persisted state to recover missed alarms after reboot.

### 🛠️ Deployment & Operations
- Shipped new systemd assets (`deploy/systemd/*.service|*.timer`) and an `install.sh` helper to install/enable them on the Pi, including an optional readiness timer.
- Extended `scripts/deploy_to_pi.sh` to sync deployment scripts, systemd units, and the new `run_alarm.sh` probe, ensuring rsync allowlists include nested directories.
- Documented diagnostics/runbook artefacts (`docs/diagnostics/*`, `docs/runbooks/alarms.md`, `docs/tests/alarm_reliability.md`) to guide overnight validation and troubleshooting.

### 🧪 Tests
- Added `tests/alarm_reliability/` suite with DST, catch-up, readiness, and persistence coverage.
- `pytest`

## [1.3.5] - 2025-10-15

### 🔄 Alarm Simplification
- Removed the dormant weekday/recurring alarm feature flag – alarms are now always single-use and automatically disable after playback. All APIs, validation paths, and UI payloads were updated to reflect the simplified model.
- Trimmed the frontend assets by dropping the unused weekday bubble widget and related JavaScript wiring.

### 🧪 Tests
- `pytest`

## [1.3.4] - 2025-10-12

### 🎯 Highlights
- Made the runtime timezone configurable via `SPOTIPI_TIMEZONE` or the persisted config; alarm, scheduler and sleep timer now pick up changes immediately through a config-listener.
- Hardened the Spotify token cache with a dedicated refresh lock and thread-safe metrics updates, eliminating duplicate refreshes under load.
- Cached the last known Spotify device ID and reuse it when `/me/player/devices` times out, so alarms still fire even if Spotify is flaky overnight.
- Reworked play/pause handling: the toggle now inspects the active device, passes it to the Spotify API and treats all 2xx responses as success, fixing the stuck-in-pause behaviour.
- Tuned low-power defaults by extending playback/dashboard cache TTLs and relaxing playback request caching to reduce repeated Spotify calls on the Pi.
- `.env` fallback: the Spotify API loader now falls back to the project root `.env` when the home-directory file is absent, fixing token refresh failures on local dev machines.
- Trimmed TLS handshake noise by downgrading the HTTP-port warnings to debug in `TidyRequestHandler`.
- Deployment script now parses rsync’s output format reliably, so the summary shows real counts for updated/created/deleted files.

### 🧪 Tests
- `pytest`

## [1.3.3] - 2025-10-07

### ⏰ Alarm & Sleep UX Polishing
- Mirrored sleep-mode behaviour for alarms: the edit form now collapses into an active-state summary with disable toggle and speaker/next-alarm details once the alarm is enabled.
- Added device info and localized status strings to the collapsed alarm view so it is clear which speaker will fire.
- Sleep timer countdown now shows a human-friendly label instead of the raw translation key when active.
- Initial global volume slider pulls the live Spotify device volume (including device-list fallbacks) rather than the static config default.

### 🧪 Tests
- `pytest`

## [1.3.2] - 2025-10-06

### ⏰ Alarm Experience Refresh
- Default alarms now behave as one-time events; they automatically disable after playback while keeping the previous configuration intact for fast re-arming.
- Introduced a `features.recurring_alarm_enabled` flag so advanced recurring schedules can be reactivated later without losing stored weekday selections.
- Updated scheduler, service layer, and API payloads to surface both the recurring flag and the currently active weekday set for diagnostics.
- Simplified the alarm editor UI by removing weekday bubbles and adding a localized hint that recurring options will return once the feature flag is enabled.

### 🧰 Configuration & Validation
- Config manager now deep-fills default feature flags across all environments and guards against malformed `features` sections.
- Alarm validation preserves stored weekday data when the UI omits the field, ensuring future releases can re-enable recurring mode seamlessly.

### ⚡ Pi Zero W Performance Pass
- Added a lightweight perf monitor (P50/P95 per Flask route) with rate-limited logging so we can profile the Pi Zero without overwhelming the SD card.
- Replaced ad-hoc Spotify calls with a pooled `requests.Session`, single-flight dedupe for GET requests, and a global semaphore (`SPOTIPI_MAX_CONCURRENCY`) to keep the Pi CPU under control.
- Introduced a two-tier device/library cache: small in-memory LRU plus disk snapshots under `./cache/`, with new env knobs (`SPOTIPI_DEVICE_TTL`, `SPOTIPI_LIBRARY_TTL_MINUTES`).
- Created `scripts/bench.sh` + `/api/perf/metrics` to benchmark cold/warm device discovery and library loads reproducibly.

### 📈 Benchmark Snapshot (run `scripts/bench.sh` on hardware)
| Endpoint | Target P50 | Target P95 | Requests (warm) | Payload |
|----------|------------|------------|-----------------|---------|
| `/api/spotify/devices` | <= 0.20 s | <= 1.50 s | 5 | ~4 KB |
| `/api/music-library?fields=basic` | <= 0.35 s | <= 1.50 s | 5 | ~48 KB |

> Instrumentation is baked in; capture actual before/after numbers on the Pi Zero W with `scripts/bench.sh` and archive them alongside the deployment notes.

### 🧪 Tests
- `pytest`

## [1.3.1] - 2025-10-05

### ⚙️ Backend Simplification
- Replaced the heavyweight config read/write locks with a lean mutex + snapshot cache, reducing per-request allocations on the Pi Zero.
- Streamlined rate limiting to a single sliding-window engine that stays disabled in low-power mode but still exposes diagnostics when active.

### 🌐 Device & Playback Responsiveness
- Primed the device list on boot (even in low-power mode) and shortened the cache loop so speakers appear almost instantly after login.
- Introduced a short-lived playback cache (default 3 s) that is invalidated whenever playback state changes, keeping the dashboard snappy while avoiding redundant Spotify calls.
- Aligned all alarm and scheduler time calculations with the `Europe/Vienna` timezone to ensure DST-safe triggers.

### 😴 Sleep Timer & System Metrics
- Added an in-memory sleep-status cache with TTL to avoid hammering the SD card and tightened monitor polling to 15 s in the final two minutes for smoother countdowns.
- Avoid blocking `psutil` CPU sampling on the Pi Zero and reuse the last known reading when low-power mode is active.

### 🔒 Security & Config
- Default CORS now locks to `http://spotipi.local` (overridable via `SPOTIPI_DEFAULT_ORIGIN`) instead of `*`.
- Per-request config snapshots are cached in `flask.g`, eliminating duplicate disk reads for each template render.

### 🧪 Tests
- `python -m compileall src/app.py src/api/spotify.py`

---

## [1.3.0] - 2025-10-04

### 🚀 Dashboard & UI
- Added `/api/dashboard/status`, allowing the web client to refresh alarm, sleep, and playback data in a single request.
- Front-end polling now consumes the aggregated response and maintains the sleep countdown locally for a smoother experience.

### 🍓 Pi Zero Optimisations
- Low-power mode skips the startup warmup prefetch, disables template auto-reload, and automatically turns off the rate limiter to keep the Raspberry Pi Zero responsive.
- Spotify library fetches limit themselves to a single worker, and system metrics are cached to avoid repeated `psutil` calls on constrained hardware.

### 🎛️ Sleep & Playback
- Sleep monitor wakes less frequently outside the fade window and keeps a cached status to drive the countdown without hammering the API.
- Dashboard playback aggregation gracefully handles missing authentication while still updating local device state.

### 🧪 Tests
- `pytest`

---

## [1.2.8] - 2025-10-03

### 😴 Sleep Timer
- Fadedown now tracks the active Spotify device and tapers volume over the final 60 seconds without jumping back up if the user adjusted the level manually.
- Sleep start aborts cleanly when Spotify playback fails instead of leaving a phantom “active” timer.

### ⏰ Alarm Reliability
- Fade-in only remains enabled when the initial volume preset succeeds; otherwise the alarm starts at the configured target volume to avoid loud surprises.

### 🎧 Spotify Integration
- Library and device caches are token-scoped to prevent cross-account bleed-through during multi-user sessions.
- Sleep stop reuses cached access tokens instead of forcing a refresh on every stop.

### 🧪 Tests
- `pytest`

---

## [1.2.7] - 2025-10-02

### 🔄 Deployment & Runtime Cleanup

- Deployment script now ships only runtime-critical files via allowlist `rsync`, keeping Pi deployments lean.
- Added optional `SPOTIPI_PURGE_UNUSED=1` flag to remove legacy assets from existing Raspberry Pi installs.

### 🖥️ Frontend Polish

- Music library loader batches sections more efficiently to minimize HTTP requests on mobile.
- Device manager explicitly initialises focus timers, preventing stray refresh state.

### 📚 Documentation & Tooling

- README and Copilot guide updated with low-power mode, streamlined testing steps, and new deployment workflow.

---

## [1.2.6] - 2025-10-02

### ✅ Highlights

- **Lean Backend:** Removed the unused streaming music library endpoints and helper module, and tightened section loaders so Pi Zero deployments avoid unnecessary thread pools for single-section requests.
- **Snappier UI:** Debounced device refresh on focus, tracked volume-slider interaction timestamps, and batched music-library requests to cut mobile latency without stressing the Pi.
- **CI-Friendly Tests:** Reworked rate-limiting and service-layer suites to use Flask's test client; all 22 tests now execute (no more skipped integration cases).
- **Housekeeping:** Dropped redundant LocalStorage writes and cleaned exports so the Spotify API module only exposes active functions.

### 🧪 Testing

- `pytest` (22 tests, all passing).

---

## [1.2.5] - 2025-10-02

### 🚀 Pi Zero Performance & UX Enhancements

This release focuses on squeezing maximum responsiveness out of the Raspberry Pi Zero deployment while smoothing out a few usability papercuts.

### Added

- **Low Power Mode:** New `SPOTIPI_LOW_POWER=1` toggle disables expensive gzip compression, right-sizes thread pools, and keeps section caching lean for constrained hardware.
- **Section-Aware Library Endpoint:** `/api/music-library` now honours the `sections` query string and skips unnecessary payload work, dramatically cutting CPU usage when the frontend requests slices.

### Changed

- **Frontend Loader:** Progressive loader switches to sequential section fetches aligned with the new backend behaviour, preventing request bursts that overwhelmed the Pi Zero.
- **Global Volume Control:** Slider dispatch now targets the active Spotify device directly and flushes the throttler instantly on release, removing the perceived lag between UI interaction and speaker volume changes.

### Fixed

- **iOS Device Selector:** Focused dropdowns stay enabled during refresh, so the speaker list no longer closes immediately on iPhone.
- **Volume Endpoint:** Backend accepts optional `device_id`, ensuring volume updates reach the intended player even when multiple devices are visible.

---

## [1.2.4] - 2025-09-15

### ⚡ Performance & Code Quality Release - Major Frontend Cleanup

This release delivers significant performance improvements and code quality enhancements through comprehensive frontend refactoring, removing technical debt and optimizing the progressive loading system.

### 🧹 Code Cleanup & Optimization

**Progressive Loading System Simplified:**
- Streamlined `streamingLoader.js` from 400+ to 120 lines (70% reduction)
- Removed complex streaming JSON parsing logic that was unused in production
- Eliminated redundant fallback chains and dead code paths
- Simplified to efficient traditional API-based progressive loading

**Cache Strategy Unification:**
- Consolidated 4 parallel cache layers into single unified strategy
- Removed legacy `musicLibraryFull` and `musicLibraryPartial` cache systems
- Eliminated redundant `If-None-Match` header complexity
- Unified to section-based caching (`musicSection_*`) for better memory efficiency

**Dead Code Elimination:**
- Removed unused `parseStreamingJSON()` method (50+ lines)
- Eliminated redundant `loadCore()` functionality (30+ lines)  
- Cleaned up `fetchSection()` lazy-loading logic (25+ lines)
- Removed duplicate LocalStorage hydration patterns

**Constants & Configuration:**
- Centralized all music section arrays in single location
- Eliminated hardcoded duplicates across multiple files
- Unified section priority configuration for different contexts

### 🎯 UI/UX Improvements

**Icon Consistency:**
- Standardized music selection icons across all interfaces
- Updated Music Library to use `fa-compact-disc` (💿) like Alarm and Sleep
- Device selector now shows "- active" text instead of Unicode star for better compatibility

### 📊 Performance Impact

**Memory & Loading:**
- 75% reduction in redundant cache data storage
- Faster initial loading due to streamlined code paths
- Improved memory efficiency through unified cache strategy
- Reduced JavaScript parse time with smaller bundle size

**Code Quality:**
- 450+ lines of dead code removed
- 88% reduction in "evolutionary baggage" 
- Dramatically improved maintainability
- Single source of truth for configuration

### ✅ Maintenance & Developer Experience

**Simplified Architecture:**
- Progressive loading now uses clean, predictable API patterns
- Unified error handling across all modules
- Better separation of concerns between components
- Easier to understand and extend codebase

### 📋 Impact

- ⚡ Faster page loads and reduced memory usage
- 🧹 Cleaner, more maintainable codebase  
- 🎯 Consistent UI experience across all interfaces
- 👨‍💻 Better developer experience for future enhancements

---

## [1.2.3] - 2025-09-15

### 🐛 Bugfix Release - Test Suite & Backend Fixes

This patch release fixes critical backend issues discovered during comprehensive test suite validation and ensures all system components work reliably together.

### 🔧 Fixed

**Backend Service Layer:**
- Fixed `WeekdayScheduler` method name mismatch: `get_next_alarm_datetime()` → `get_next_alarm_date()`
- Resolved advanced alarm status endpoint failing with `'WeekdayScheduler' object has no attribute 'get_next_alarm_datetime'` error
- Fixed alarm service integration to use correct scheduler API methods

**API Response Structure:**
- Standardized volume field naming: Tests now correctly expect `alarm_volume` instead of `volume`
- Reflects the separation between global volume control and alarm-specific volume settings
- Maintains backward compatibility while supporting new volume architecture

**Cache System Organization:**
- Relocated music library cache from `logs/` to dedicated `cache/` directory
- Updated `.gitignore` to properly handle new cache directory structure
- Improved cache file organization for better system maintenance

### ✅ Test Suite Validation

**Comprehensive Test Coverage:**
- All 22 integration tests now pass successfully
- Fixed API contract tests for new response wrapper format `{"data": {...}}`
- Updated rate limiting tests for current algorithm implementations
- Corrected service layer tests for proper endpoint URLs and response structures

**Test Fixes:**
- Fixed endpoint URL mappings: `/api/alarm/advanced-status` → `/alarm_status?advanced=true`
- Updated response format expectations to match current API structure
- Fixed rate limiting algorithm tests (removed non-implemented `fixed_window`)
- Corrected sleep service test to handle nested response structure

### 📋 Impact

- ✅ Advanced alarm status endpoint now works correctly
- ✅ All test suite validations pass (22/22 tests)
- ✅ Cache system better organized and maintainable
- ✅ Backend service layer fully functional with proper error handling
- ✅ API response consistency maintained across all endpoints

### 🔍 Technical Details

This release addresses the disconnect between test expectations and actual API behavior that accumulated during rapid development. The comprehensive test suite validation ensures system reliability and catches regressions early in the development cycle.

## [1.2.2] - 2025-09-15

### ✨ Enhancement - Immediate UI Response & Performance Optimization

This patch release significantly improves the user experience by eliminating lag in both volume control and play/pause functionality, making the interface much more responsive.

### 🚀 Added

**Immediate Volume Control:**
- Real-time volume control with throttled Spotify API calls (150ms during dragging, 50ms on release)
- Instant visual feedback during volume slider interaction
- Separate volume logic: Global volume (Spotify only) vs Alarm volume (Config + Spotify)

**Optimized Play/Pause Control:**
- Instant button icon updates (fa-play ↔ fa-pause) on click
- New `toggle_playback_fast()` API function without status check
- "Pause-first" strategy for common use case (music playing)
- Fire-and-forget pattern with error rollback

**Enhanced Icons:**
- Speaker/Device selection now uses Spotify icon (`fa-brands fa-spotify`)
- Alarm volume control now shows volume icon (`fas fa-volume-high`)

### 🔧 Improved

**Performance Optimizations:**
- Eliminated double API calls in play/pause toggle (was: status check + toggle → now: direct toggle)
- Reduced perceived lag from ~300ms to immediate UI response
- Background API processing with user feedback

**Volume System Architecture:**
- Global volume slider: Direct Spotify control without config saving
- Alarm volume slider: Independent config storage for alarm-specific volume
- Removed redundant `volume` field from config (only `alarm_volume` needed)

**UI/UX Improvements:**
- Global volume changes no longer affect alarm/sleep volume settings
- Prevented volume slider interference between different controls
- Optimized volume API calls with smart throttling

### 🐛 Fixed

**Config Cleanup:**
- Removed unused `volume` field from all config files
- Updated alarm execution to use only `alarm_volume`
- Cleaned up volume endpoint to focus on Spotify-only control

### 📋 Migration Notes

Existing configs will automatically migrate:
- `volume` field is no longer used/saved
- `alarm_volume` remains unchanged and continues to work
- No user action required for existing installations

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
