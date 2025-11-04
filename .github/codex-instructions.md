## SpotiPi • Codex Guidance (v1.3.9)

### Quick Context
- Platform: Flask app (`run.py` → `src/app.py`) serving as Spotify alarm clock for Raspberry Pi Zero W.
- Core modules live in `src/`: `core/` (alarms, scheduler, sleep), `services/` (business logic + `ServiceResult`), `api/spotify.py` (Spotify client, cached token handling), `utils/` (thread safety, caching, validation, logging).
- Config/state flows through `src/config.py` and the thread-safe wrapper in `src/utils/thread_safety.py`. Use `load_config()` / `save_config()` / `config_transaction()` only.
- **Config validation (v1.3.8)**: Pydantic schemas in `src/config_schema.py` validate all config fields with graceful fallback to legacy validation.

### Coding Rules
- Target Python 3.9 syntax (no `A | B` unions). Prefer `Optional`, `Union`, `Dict`, etc.
- Reuse existing helpers: `api_response()`, `ServiceResult`, `t_api()`, unified cache layer (`get_cache_migration_layer()`), shared HTTP session (`src/api/http.py`).
- Guard concurrent mutations with the provided thread-safe abstractions. Never touch global caches/configs directly.
- **Logging**: Use `setup_logger(__name__)` from `src/utils/logger.py`; keep messages concise.
  - **Structured logging (v1.3.8+)**: Use `log_structured(logger, level, msg, **context)` for production logs with structured fields. Auto-enabled on Pi via `SPOTIPI_JSON_LOGS=1`.
- Respect low-power environment toggles (`SPOTIPI_LOW_POWER`, `SPOTIPI_MAX_CONCURRENCY`, etc.) when adding work that may stress the Pi Zero.
- **Alarm persistence (v1.3.8+)**: systemd timer runs daily at 05:30 as backup to in-process scheduler.

### Spotify Client Constraints
- Use functions in `src/api/spotify.py` (they already handle retries, rate limits, token refresh, caching). Avoid raw `requests` usage.
- **HTTP Retry (v1.3.8+)**: All Spotify API calls automatically retry on transient errors (429, 500, 502, 503, 504) with exponential backoff. Configure via `SPOTIPI_HTTP_BACKOFF_FACTOR`, `SPOTIPI_HTTP_RETRY_TOTAL`.
- Device handling prefers name + cached ID fallback; ensure new code doesn't bypass those helpers.
- **Device sorting (v1.3.9)**: Devices are sorted alphabetically (A-Z, case-insensitive) in all API responses.

### API / Route Patterns
- Decorate routes with `@api_error_handler` and the appropriate `@rate_limit("category")`.
- For user-visible strings, call `t_api("key", request, ...)` so translations stay consistent.
- When returning JSON, use `api_response(success=..., data=..., message=..., error_code=...)`.
- **CORS (v1.3.9)**: Port-agnostic hostname matching supports development environments (e.g., `http://spotipi.local:5000`).

### Validation & Security
- All user input funnels through `src/utils/validation.py`. Raise/handle `ValidationError` rather than sprinkling manual checks.
- **Device names (v1.3.9)**: Relaxed validation allows Unicode/emoji while blocking only `<>` and control characters for XSS protection.
- **HTML escaping (v1.3.9)**: Always escape user-controlled strings in JavaScript template literals to prevent injection attacks.

### Testing Expectations
- Update or add tests under `tests/` whenever behaviour changes. Pytest already uses the Flask test client; keep new tests deterministic (no real Spotify calls).
- Run `pytest` before suggesting deployment. Key suites: `test_api_contract.py`, `test_service_layer.py`, `test_spotify_resilience.py`.
- **New test suites (v1.3.8+)**: `test_config_validation.py` (27 tests), `test_spotify_retry.py` (16 tests).

### Deployment Notes
- Deployment script `scripts/deploy_to_pi.sh` parses rsync `--itemize-changes` output `%i %f`. If you touch deployment logic, keep that format intact.
- Minimise disk writes on the Pi; persistent caches/logs should only be written when TTL/config justify it.

### UI/UX Patterns (v1.3.9)
- **Smooth animations**: Use CSS transitions (300ms) with `smoothShow()` and `smoothHide()` helpers for consistent fade+slide effects.
- **Accessibility**: Always include ARIA attributes (`role`, `aria-label`, `aria-live`) for dynamic content changes.

### When Unsure
- Prefer extending existing modules over creating new, parallel code paths.
- Ask for clarifications if a requirement clashes with thread safety, Pi constraints, or test coverage.
