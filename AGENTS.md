# SpotiPi Agent Guidelines (v1.6.0)

This file is the canonical source of AI coding instructions for this repository.

## Scope and Precedence

- Use this file as the single instruction source for automated coding assistants.
- If another instruction file conflicts with this document, `AGENTS.md` wins.
- Keep guidance focused on Pi-safe runtime behavior, thread safety, and maintainable frontend UX.

## Architecture Snapshot

- Flask entrypoint is `run.py`, loading the app from `src/app.py`.
- Route blueprints live in `src/routes/`.
- Business logic belongs in `src/services/` and returns `ServiceResult`.
- Alarm/scheduler flows are in `src/core/`.
- Spotify integration lives in `src/api/spotify.py` and shared HTTP helpers in `src/api/http.py`.
- Config is centralized via `src/config.py` plus thread-safe helpers in `src/utils/thread_safety.py`.

## Core Engineering Rules

- Keep Python compatible with 3.9 syntax. Avoid `A | B` union syntax.
- Never mutate config or shared cache directly. Use:
  - `load_config()`
  - `save_config()`
  - `config_transaction()`
- Prefer consistent API envelopes with `api_response(...)` and `ServiceResult.to_dict()`.
- Use centralized validation in `src/utils/validation.py` and handle `ValidationError`.
- Reuse existing Spotify API helpers; do not create ad-hoc `requests.Session` instances.
- Use shared caching via `get_cache_migration_layer()` and honor configured TTLs.

## Logging and Observability

- Use `setup_logger(__name__)` from `src/utils/logger.py`.
- Prefer structured logging on error/critical paths:
  - `log_structured(logger, level, msg, **context)`
- Include useful context keys (for example `alarm_id`, `device_name`, `error_code`) where available.

## Raspberry Pi Guardrails

- Assume low CPU and memory on Pi Zero W; avoid expensive work on request threads.
- Respect low-power env toggles such as:
  - `SPOTIPI_LOW_POWER`
  - `SPOTIPI_MAX_CONCURRENCY`
  - `SPOTIPI_LIBRARY_TTL_MINUTES`
- Minimize disk writes and only persist when TTL/robustness justify it.
- Do not break production systemd behavior under `deploy/systemd/`.

## Security and Data Safety

- Keep Spotify token handling within `src/utils/token_encryption.py` patterns.
- Maintain restricted token file permissions (`0o600`).
- Escape user-controlled strings in JS template literals.
- Preserve input sanitization rules, including device-name validation constraints.

## Frontend and UX Baseline

- Keep UI responsive and reliable across mobile and desktop breakpoints.
- Respect `prefers-reduced-motion`.
- Preserve accessibility primitives (`aria-*`, roles, labels) for interactive and dynamic UI.
- Reuse established UI patterns before adding new variants (loading skeletons, empty states, transitions).

## Testing and Quality Gates

- Add or update tests for any behavioral change in routes, services, or Spotify integration.
- Use deterministic tests with Flask test client (no live Spotify calls).
- Run `pytest` before finishing changes.
- If deployment behavior is touched, verify `scripts/deploy_to_pi.sh` output format assumptions remain valid.

## Change Checklist

- Keep route handlers thin and move logic to service/core layers.
- Add new config fields to schema/defaults/documentation together.
- Document new environment variables in `config/default_config.json` and `Readme.MD`.
- Prefer extending existing modules over creating parallel abstractions.
