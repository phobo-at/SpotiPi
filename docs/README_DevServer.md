````markdown
# SpotiPi DevServer Setup

## Installation

1. **Clone repo & install dependencies:**
```bash
git clone <repo-url>
cd spotipi
pip install -r requirements.txt
```

2. **Set up Spotify credentials:**
```bash
# Create .env file in ~/.spotipi/.env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret  
SPOTIFY_REFRESH_TOKEN=your_refresh_token
SPOTIFY_USERNAME=your_username
```

3. **Load shell functions:**
```bash
# Optional: add the helper to your PATH (or call it directly via ./spoti)
chmod +x ./spoti
```

## Usage

```bash
# Start server (Port 5001, Auto-reload)
./spoti start

# Check status
./spoti status

# View logs
./spoti logs

# Stop server
./spoti stop

# Restart server
./spoti restart
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
- ✅ Parallel API loading (~2.5s for 374 items)
- ✅ All playlists (owned + subscribed)
- ✅ Comprehensive logging
- ✅ Simple PID-based management

## Troubleshooting

```bash
# In case of issues: kill processes
pkill -f "python.*run.py"
rm -f scripts/server.pid

# Check logs
tail -f logs/server.log
```

````
