## SpotiPi • Codex Guidance (v1.3.5)

### Quick Context
- Platform: Flask app (`run.py` → `src/app.py`) serving as Spotify alarm clock for Raspberry Pi Zero W.
- Core modules live in `src/`: `core/` (alarms, scheduler, sleep), `services/` (business logic + `ServiceResult`), `api/spotify.py` (Spotify client, cached token handling), `utils/` (thread safety, caching, validation, logging).
- Config/state flows through `src/config.py` and the thread-safe wrapper in `src/utils/thread_safety.py`. Use `load_config()` / `save_config()` / `config_transaction()` only.

### Coding Rules
- Target Python 3.9 syntax (no `A | B` unions). Prefer `Optional`, `Union`, `Dict`, etc.
- Reuse existing helpers: `api_response()`, `ServiceResult`, `t_api()`, unified cache layer (`get_cache_migration_layer()`), shared HTTP session (`src/api/http.py`).
- Guard concurrent mutations with the provided thread-safe abstractions. Never touch global caches/configs directly.
- Logging goes through `setup_logger(__name__)` from `src/utils/logger.py`; keep messages concise.
- Respect low-power environment toggles (`SPOTIPI_LOW_POWER`, `SPOTIPI_MAX_CONCURRENCY`, etc.) when adding work that may stress the Pi Zero.

### Spotify Client Constraints
- Use functions in `src/api/spotify.py` (they already handle retries, rate limits, token refresh, caching). Avoid raw `requests` usage.
- Device handling prefers name + cached ID fallback; ensure new code doesn’t bypass those helpers.

### API / Route Patterns
- Decorate routes with `@api_error_handler` and the appropriate `@rate_limit("...")`.
- For user-visible strings, call `t_api("key", request, ...)` so translations stay consistent.
- When returning JSON, use `api_response(success=..., data=..., message=..., error_code=...)`.

### Testing Expectations
- Update or add tests under `tests/` whenever behaviour changes. Pytest already uses the Flask test client; keep new tests deterministic (no real Spotify calls).
- Run `pytest` before suggesting deployment. Key suites: `test_api_contract.py`, `test_service_layer.py`, `test_spotify_resilience.py`.

### Deployment Notes
- Deployment script `scripts/deploy_to_pi.sh` parses rsync `--itemize-changes` output `%i %f`. If you touch deployment logic, keep that format intact.
- Minimise disk writes on the Pi; persistent caches/logs should only be written when TTL/config justify it.

### When Unsure
- Prefer extending existing modules over creating new, parallel code paths.
- Ask for clarifications if a requirement clashes with thread safety, Pi constraints, or test coverage.***
