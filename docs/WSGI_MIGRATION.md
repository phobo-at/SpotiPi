# SpotiPi WSGI Migration Notes

SpotiPi now uses a production-ready WSGI server (Waitress) when the app
runs in non-debug mode. Development workflows remain unchanged: if the
configuration sets `debug=true` (or you override it via `FLASK_DEBUG=1`)
we still fall back to `app.run()` with the built-in Flask server.

## Runtime behaviour

- In `production` (default on Raspberry Pi) the launcher `run.py`
  automatically starts Waitress instead of the Flask dev server.
- Configuration values `host` and `port` come from the JSON config as
  before. New optional environment variables allow fine tuning:
  `SPOTIPI_WAITRESS_THREADS` (default `4`) and
  `SPOTIPI_WAITRESS_BACKLOG` (default `128`).
- If Waitress is missing from the environment the launcher prints a
  notice and continutes with the Flask dev server. This keeps quick
  prototyping working even before dependencies are updated.

## Why Waitress?

Waitress provides a hardened WSGI stack that restarts worker threads,
handles socket load gracefully and avoids the security issues that come
with running the debug server in production. It is lightweight, pure
Python and well-suited for Raspberry Pi hardware.

## Deployment checklist impact

- `requirements.txt` now includes `waitress>=2.1.2`; ensure it is
  installed on the target system (`pip install -r requirements.txt`).
- systemd units or helper scripts do not need changes—the entrypoint is
  still `python run.py`. No additional CLI arguments are required.
- Logging and the alarm scheduler run exactly as before because the
  application still calls `start_alarm_scheduler()` prior to starting the
  WSGI server.

