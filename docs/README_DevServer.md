# SpotiPi DevServer Setup

## Installation

1. **Clone repo & install dependencies:**
```bash
git clone <repo-url>
cd spotipi
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. **Set up Spotify credentials:**
```bash
mkdir -p ~/.spotipi
cp .env.example ~/.spotipi/.env
# Fill in SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET and SPOTIFY_USERNAME
python generate_token.py
```

`~/.spotipi/.env` is the canonical runtime secret file. A repo-root `.env` is only a local override for development.

3. **Load shell functions:**
```bash
# Optional: add the helper to your PATH (or call it directly via ./spoti)
chmod +x ./spoti
```

## Usage

```bash
# Start server (Port 5001, local profile)
./spoti start

# Check status
./spoti status

# View logs
./spoti logs

# Stop server
./spoti stop

# Restart server
./spoti restart

# Or use the local server wrapper directly
./scripts/local_server.sh start
```

## Direct execution

```bash
# With default settings
python run.py

# Flask CLI alternative (debug + reload)
FLASK_APP=src.app:get_app FLASK_DEBUG=1 flask run --port 5001 --host 0.0.0.0
```

## URLs

- **Main App**: http://localhost:5001
- **API**: http://localhost:5001/api/music-library

## Features

- ✅ Auto-reload on code changes
- ✅ Local profile with Pi-safe defaults and log separation
- ✅ All playlists (owned + subscribed)
- ✅ Comprehensive logging
- ✅ PID-based management via `./spoti` and `scripts/server_manager.py`
- ✅ Same `202 pending/auth_required` snapshot contract as production

## Troubleshooting

```bash
# In case of issues: kill processes
pkill -f "python.*run.py"
rm -f scripts/server.pid

# Check logs
tail -f logs/server.log
```
