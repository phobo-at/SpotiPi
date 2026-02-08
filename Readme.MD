# SpotiPi (v1.5.1)

Smart Spotify alarm clock and sleep timer for Raspberry Pi.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Raspberry Pi](https://img.shields.io/badge/platform-Raspberry%20Pi-red.svg)](https://www.raspberrypi.org/)

## Features

- Spotify playback for alarms and sleep timer
- Mobile-friendly web UI with playback controls
- Local server profile for safe development testing
- Raspberry Pi optimized defaults and low-power toggles
- Resilient alarm scheduler with catch-up behavior
- Encrypted token storage and restricted token file permissions

## Quick Start (Local)

```bash
git clone https://github.com/phobo-at/SpotiPi.git
cd SpotiPi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Fill in SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_USERNAME

python generate_token.py
./scripts/local_server.sh start
```

Open: [http://127.0.0.1:5001](http://127.0.0.1:5001)

## Local Server Commands

```bash
./scripts/local_server.sh start
./scripts/local_server.sh stop
./scripts/local_server.sh status
./scripts/local_server.sh logs -f
```

Advanced manager (custom profile/flags):

```bash
./.venv/bin/python scripts/server_manager.py start --profile local
./.venv/bin/python scripts/server_manager.py status --profile local
./.venv/bin/python scripts/server_manager.py logs --profile local -f
```

Local profile log files:

- `logs/server.local.log`
- `logs/server.local.error.log`

## Raspberry Pi Setup

On the Pi:

```bash
git clone https://github.com/phobo-at/SpotiPi.git /home/pi/spotipi
cd /home/pi/spotipi
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python generate_token.py
./deploy/install.sh
```

From your dev machine (sync + restart service):

```bash
./scripts/deploy_to_pi.sh
```

Useful deploy flags:

- `SPOTIPI_FORCE_SYSTEMD=1` forces systemd unit refresh
- `SPOTIPI_PURGE_UNUSED=1` removes old/unneeded files on the Pi once

## Configuration

Minimum `.env` values:

```env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_USERNAME=your_username
```

Common optional overrides:

```env
SPOTIPI_LOW_POWER=1
SPOTIPI_TIMEZONE=Europe/Vienna
SPOTIPI_MAX_CONCURRENCY=2
SPOTIPI_DEVICE_TTL=10
SPOTIPI_LIBRARY_TTL_MINUTES=60
```

Full environment variable reference: [`docs/ENVIRONMENT_VARIABLES.md`](docs/ENVIRONMENT_VARIABLES.md)

## Architecture

- Flask app entrypoint: `run.py` -> `src/app.py`
- Routes via blueprints in `src/routes/`
- Business logic in `src/services/`, alarm/scheduler in `src/core/`
- Shared config/thread safety helpers in `src/config.py` and `src/utils/thread_safety.py`

## Testing

```bash
pytest
```

Optional local quality checks:

```bash
pre-commit run --all-files
```

## Documentation

- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- [`docs/ENVIRONMENT_VARIABLES.md`](docs/ENVIRONMENT_VARIABLES.md)
- [`docs/SPOTIFY_API_RETRY.md`](docs/SPOTIFY_API_RETRY.md)
- [`docs/CONFIG_SCHEMA_VALIDATION.md`](docs/CONFIG_SCHEMA_VALIDATION.md)
- [`docs/JSON_LOGGING.md`](docs/JSON_LOGGING.md)

## Screenshot

<img src="docs/images/spotipi.png" alt="SpotiPi Interface" width="100%">

## Contributing

- Follow [`CONTRIBUTING.md`](CONTRIBUTING.md)
- Follow AI assistant rules in [`AGENTS.md`](AGENTS.md)

## License

MIT
