# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is SpotiPi

Spotify alarm clock and sleep timer for Raspberry Pi. Flask backend + Preact/TypeScript frontend, dashboard-first SPA. Targets Pi Zero W (low CPU/memory) but runs on any platform.

## Commands

```bash
# Backend
source .venv/bin/activate
pip install -r requirements.txt
pytest                                # run all tests
pytest tests/test_api_contract.py     # single file
pytest -k "alarm"                     # pattern match

# Frontend
npm install
npm run build                         # production build (esbuild)
npm run build:dev                     # dev build (source maps)
npm run watch                         # watch mode
npm run typecheck                     # TypeScript check
npm run budget:check                  # performance budget
npm run test:e2e                      # Playwright E2E tests

# Local dev server
./scripts/local_server.sh start       # port 5001
./scripts/local_server.sh stop
./scripts/local_server.sh logs -f

# Deploy to Pi
cp scripts/deploy_to_pi.sh.example scripts/deploy_to_pi.sh  # first time only
./scripts/deploy_to_pi.sh
```

## Quality gates before finishing

- `pytest` for any backend change
- `npm run typecheck && npm run build && npm run budget:check` for frontend changes
- `npm run test:e2e` if UI behavior changed
- Commit rebuilt `static/dist/` together with frontend source changes (Pi can't rebuild)

## Architecture

**Backend layers** (keep route handlers thin, logic goes deeper):
- `run.py` -> `src/app.py` (Flask factory)
- `src/routes/` - Flask blueprints (thin HTTP layer)
- `src/services/` - business logic, returns `ServiceResult`
- `src/core/` - alarm scheduler, sleep timer entities
- `src/api/spotify.py` + `src/api/http.py` - Spotify Web API client with retry/backoff

**Frontend** (`frontend/src/` -> built to `static/dist/`):
- Preact SPA, esbuild bundler, TypeScript
- `app.tsx` - main app component
- `hooks/` - state management (polling, playback, settings, etc.)
- `lib/api.ts` - fetch wrappers; `lib/types.ts` - interfaces; `lib/view_models.ts` - form state
- New frontend logic goes in `frontend/src/`, NOT in legacy `static/js/modules/`

**Config & thread safety:**
- Never mutate config directly; use `load_config()`, `save_config()`, `config_transaction()`
- Thread-safe helpers in `src/utils/thread_safety.py`
- Secrets live at `~/.spotipi/.env` (canonical), repo `.env` is dev-only override

**Key contract:** `GET /api/dashboard/status` and `GET /playback_status` return `202` while snapshot data is `pending` or `auth_required`. Don't break this.

## Canonical rules

`AGENTS.md` is the authoritative AI instruction file for this repo. It covers Pi guardrails, security, logging, testing, and change checklists. If anything here conflicts with `AGENTS.md`, AGENTS.md wins.
