# 🎵 SpotiPi

**Smart Spotify alarm clock and sleep timer for Raspberry Pi**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)

Wake up to your favorite Spotify music with this elegant web-based alarm system. Features automatic environment detection, mobile-optimized interface, and seamless Raspberry Pi integration.

## ✨ Features

- 🎵 **Spotify Integration** - Wake up to any playlist, album, or track
- ⏰ **Smart Alarms** - One-shot alarms by default with optional recurring scheduling (feature flag)
- 😴 **Sleep Timer** - Peaceful fade-out for better sleep
- 📱 **Mobile First** - Responsive web interface, PWA support
- 🍓 **Pi Optimized** - Auto-detection and SD-card protection
- ⚡ **Fast Dashboard** - Aggregated status updates over a single request
- 🛡️ **Secure** - Environment variables for all credentials

## 🚀 Quick Start

```bash
# Clone and setup
git clone https://github.com/phobo-at/SpotiPi.git
cd SpotiPi
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure Spotify (get credentials from developer.spotify.com)
cp .env.example .env
# Edit .env with your Spotify Client ID and Secret

# Generate token and run
python generate_token.py
python run.py
```

Access at `http://localhost:5001` (development) or `http://spotipi.local:5000` (Pi)

## 🔧 Configuration

Create `.env` file:
```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret  
SPOTIFY_USERNAME=your_username

# Optional: Pi Zero / low-power mode optimizations
SPOTIPI_LOW_POWER=1
SPOTIPI_TIMEZONE=Europe/Vienna                 # Override detected timezone for alarms & scheduler
SPOTIPI_DEFAULT_ORIGIN=http://spotipi.local   # CORS allowlist fallback for LAN UI
SPOTIPI_PLAYBACK_CACHE_TTL=3.0                # Seconds to cache /me/player snapshot
SPOTIPI_DEVICE_TTL=10                         # Device cache TTL in seconds (5-15 on Pi Zero)
SPOTIPI_LIBRARY_TTL_MINUTES=60                # Library cache TTL in minutes (30-120)
SPOTIPI_MAX_CONCURRENCY=2                     # Global HTTP concurrency limit on low-power devices
```

Everything else is auto-configured with smart defaults.

### Pi Zero W Tuning

For stable playback on the Pi Zero W, these environment variables work well:

```env
SPOTIPI_HTTP_TIMEOUTS=5,18                 # Generous network/connect + read timeouts
SPOTIPI_STATUS_CACHE_SECONDS=0.8           # Server-side dashboard cache to lighten load
SPOTIPI_PLAYBACK_STATUS_CACHE_SECONDS=0.6  # Server-side playback cache (< 1 second)
SPOTIPI_PREWARM_SECONDS=150                # Token prewarm window ahead of alarm trigger
SPOTIPI_PLAYER_RETRIES=3                   # Playback attempts including exponential backoff
SPOTIPI_PLAYER_BACKOFF=1.0                 # Initial backoff delay in seconds
SPOTIPI_PLAYER_JITTER=0.4                  # Random jitter factor for backoff
SPOTIPI_DEVICE_TTL=10                      # Spotify device cache TTL in seconds
```

Adjust them freely without touching the code—set the values in `.env`, restart the service, and you’re done.

### Alarm Behaviour Flags

Recurring alarms are currently hidden behind a feature flag so they stay ready for a future configuration screen:

```json
"features": {
  "recurring_alarm_enabled": false
}
```

Leave the flag at `false` for the single-use experience. When you flip it to `true`, the stored weekday list becomes active again and the scheduler resumes recurring operation.

## 🍓 Raspberry Pi Setup

```bash
# On your Pi
git clone https://github.com/phobo-at/SpotiPi.git /home/pi/spotipi
cd /home/pi/spotipi && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt && python generate_token.py

# Install as service
sudo cp scripts/spotipi.service /etc/systemd/system/
sudo systemctl enable spotipi && sudo systemctl start spotipi
```

## 🧠 Performance Setup (Pi Zero W)

- **HTTP pooling & limits:** a shared `requests.Session` keeps TLS warm and caps concurrent Spotify API calls (`SPOTIPI_MAX_CONCURRENCY`, default `2`).
- **Two-tier caching:** devices persist to `./cache/spotify_devices_<hash>.json` (default TTL `SPOTIPI_DEVICE_TTL=10s`), the music library uses an in-memory LRU backed by disk (`SPOTIPI_LIBRARY_TTL_MINUTES=60`).
- **Instrumentation:** high-resolution timings for every Flask route plus per-endpoint P50/P95 logs; inspect via `/api/perf/metrics`.
- **Benchmark helper:** run `scripts/bench.sh` after deployment to measure cold/warm latencies and validate cache hit rates (details in `docs/benchmark.md`).

## 🚀 Deployment Workflow

```bash
# Sync runtime files to the Pi and restart the systemd service
./scripts/deploy_to_pi.sh

# Optional one-time cleanup of previously deployed unused files
SPOTIPI_PURGE_UNUSED=1 ./scripts/deploy_to_pi.sh
```
The deploy script uses an allowlist `rsync` (run.py, requirements, `src/`, `static/`, `templates/`, `config/`), keeping the Raspberry Pi installation minimal.

## 📸 Screenshots
<img src="docs/images/spotipi.png" alt="SpotiPi Interface" width="50%">

## 🏗️ Architecture

- **Backend**: Flask with modular service architecture
- **Frontend**: Responsive vanilla JS with PWA support
- **Integration**: Spotify Web API with token caching
- **Deployment**: Auto-detection (development vs. Raspberry Pi)

## 📝 Environment Detection

SpotiPi automatically configures itself:
- **macOS/Windows**: Development mode (port 5001, verbose logging)
- **Raspberry Pi**: Production mode (port 5000, minimal logging)
- **Override**: Use environment variables to force specific behavior

## 🤝 Contributing

1. Fork the repository
2. Create feature branch: `git checkout -b feature/name`
3. Install tooling (`pip install pre-commit`) and run `pre-commit install`
4. Run the formatter/linter locally: `pre-commit run --all-files`
5. Execute the test suite: `pytest`
6. Follow the [Contributing Guide](CONTRIBUTING.md)
7. Submit pull request

## 🧪 Development Workflow

- **Tooling**: Formatting and linting are managed via `pre-commit` (Black, Ruff, Prettier). Install once with `pre-commit install`.
- **Tests**: Run `pytest` to execute the in-process API/service suites—no external server required.
- **CI**: GitHub Actions runs the same checks (pre-commit + pytest) on every push/PR.

## 📄 License

MIT License - feel free to use and modify!

## 🤖 Development Story

This app was 100% vibe-coded with GitHub Copilot and an unhealthy amount of ☕ coffee. 
If you find any bugs, blame the caffeine dependency, not the AI! 😄

## 🙏 Credits

Built with Flask, Spotify Web API, and lots of ❤️ for better mornings.

---

**🌅 Made for music lovers who want to wake up right!**
