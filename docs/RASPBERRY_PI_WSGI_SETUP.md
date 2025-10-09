# Raspberry Pi Waitress Deployment Guide

This guide explains how to keep SpotiPi running smoothly on a Raspberry
Pi (Zero W or similar) after the switch to the Waitress WSGI server.

## 1. Update the application

1. SSH into the Pi user that owns the SpotiPi checkout.
2. Pull the latest sources:
   ```bash
   cd /opt/spotipi  # adjust if you use a different path
   git pull
   ```
3. Update the Python environment:
   ```bash
   source venv/bin/activate  # or your preferred virtualenv
   pip install --upgrade -r requirements.txt
   ```
   The new Waitress dependency is installed in this step.

## 2. Verify environment secrets

Ensure the runtime secrets live in `~/.spotipi/.env` (not in the repo):

```
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REFRESH_TOKEN=...
FLASK_SECRET_KEY=...
```

Set permissions to `chmod 600 ~/.spotipi/.env`.

## 3. Review configuration

SpotiPi still reads `config/production.json` by default. Optional new
tuning knobs for Waitress:

- `SPOTIPI_WAITRESS_THREADS` (default `4`) — lower to `2` on a Pi Zero if
  you want to reduce CPU usage.
- `SPOTIPI_WAITRESS_BACKLOG` (default `128`) — only change if you expect
  many concurrent connections.

Add them to `~/.spotipi/.env` if you need to override the defaults.

## 4. Test run manually

Before touching systemd, run the app once to ensure everything works:

```bash
source venv/bin/activate
python run.py
```

You should see the startup message followed by
`🍽️ Using Waitress WSGI server ...`. Open the UI from a browser in the
LAN to confirm normal behaviour.

Stop the process with `Ctrl+C` when you're done testing.

## 5. Update systemd service (if used)

No command line changes are required, but it is a good moment to check
that your unit file resembles the following minimal example:

```
[Unit]
Description=SpotiPi WSGI service
After=network-online.target

[Service]
Type=simple
User=spotipi
WorkingDirectory=/opt/spotipi
Environment="PYTHONPATH=/opt/spotipi"
EnvironmentFile=/home/spotipi/.spotipi/.env
ExecStart=/opt/spotipi/venv/bin/python /opt/spotipi/run.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Reload systemd and restart the service:

```bash
sudo systemctl daemon-reload
sudo systemctl restart spotipi.service
sudo systemctl status spotipi.service
```

## 6. Monitor logs

Waitress integrates with the existing logging setup. Check Application
logs and journal entries if you want to confirm everything ran smoothly:

```bash
journalctl -u spotipi.service -f
```

The UI and API continue to operate on the same port as before (default
5000/5001 based on configuration).

## 7. Optional tuning

- Set `SPOTIPI_WAITRESS_THREADS=2` for Pi Zero W to reduce context
  switches.
- Combine with a reverse proxy (nginx/Caddy) if you plan to expose the
  app beyond the home network.

