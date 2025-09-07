````markdown
# SpotiPi DevServer Setup

## Installation

1. **Clone repo & install dependencies:**
```bash
git clone <repo-url>
cd spotify_wakeup
pip install -r requirements.txt
```

2. **Set up Spotify credentials:**
```bash
# Create .env file in ~/.spotify_wakeup/.env
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret  
SPOTIFY_REFRESH_TOKEN=your_refresh_token
SPOTIFY_USERNAME=your_username
```

3. **Load shell functions:**
```bash
source spotipi.zsh
```

## Usage

```bash
# Start server (Port 5001, Auto-reload)
spotipi start

# Check status
spotipi status

# View logs
spotipi logs

# Stop server
spotipi stop

# Restart server
spotipi restart
```

## Direct execution

```bash
# With default settings
python app.py --dev --port 5001

# All options
python app.py --dev --debug --port 5001 --host 0.0.0.0
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
pkill -f "python.*app.py"
rm ~/.spotify_wakeup/dev_server.pid

# Check logs
tail -f ~/.spotify_wakeup/logs/spotipi_$(date +%Y-%m-%d).log
```

````
