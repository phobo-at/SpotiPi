## SpotiPi • Copilot Guidance (v1.3.8)

### Architecture Cheatsheet
- Flask entrypoint: `run.py` imports `src/app.py`; templates/static at project root.
- Core domains live in `src/`: `core/` (alarm & scheduler), `services/` (business logic + `ServiceResult`), `api/spotify.py` (Spotify client), `utils/` (thread-safety, caching, logging, validation).
- Configuration is centralized via `src/config.py` + thread-safe wrapper in `src/utils/thread_safety.py`. Always read/write config with the provided helpers (`load_config()`, `save_config()`, `config_transaction()`).
- **Config validation (v1.3.8)**: Use Pydantic schemas in `src/config_schema.py`. Config is automatically validated via `validate_config_dict()` with graceful fallback to legacy validation.

### Coding Patterns to Follow
- **Concurrency**: Alarm scheduler and token cache are multi-threaded; never mutate config or caches without the thread-safe helpers.
- **Type hints**: Do not use PEP 604 unions (`A | B`); target 3.9-compatible syntax (`Optional[A]`, `Union[...]`).
- **API Responses**: Prefer `api_response(...)` and `ServiceResult.to_dict()` to keep the JSON envelope consistent (`success/timestamp/request_id`).
- **Logging**: Import `setup_logger` from `src/utils/logger.py`. Logs already use emoji prefixes—follow that convention sparingly, keep messages short.
  - **Structured logging (v1.3.8)**: Use `log_structured(logger, level, msg, **context)` for production logs with structured fields. Auto-enabled on Pi via `SPOTIPI_JSON_LOGS=1`.
  - Example: `log_structured(logger, "error", "Alarm failed", alarm_id="abc", error_code="device_not_found")`
- **Caching**: Use the unified cache layer via `get_cache_migration_layer()`. Avoid new ad‑hoc caches on disk; respect low-power TTL overrides (`SPOTIPI_*` env vars).
- **Spotify Client**: Re-use helpers in `src/api/spotify.py` (they already handle retries, token refresh, low-power worker limits). Do not instantiate raw `requests.Session`; use the shared proxy from `src/api/http.py`.
  - **HTTP Retry (v1.3.8)**: All Spotify API calls automatically retry on transient errors (429, 500, 502, 503, 504) with exponential backoff. Configure via `SPOTIPI_HTTP_BACKOFF_FACTOR`, `SPOTIPI_HTTP_RETRY_TOTAL`.
- **Validation**: All user input funnels through `src/utils/validation.py`. Raise/handle `ValidationError` rather than sprinkling manual checks.
  - **Config validation (v1.3.8)**: Pydantic models in `src/config_schema.py` provide automatic type validation, field constraints, and clear error messages.

### Pi Zero W Considerations
- Expect a single CPU core with limited RAM; minimize blocking calls on the request thread.
- Honour environment toggles like `SPOTIPI_LOW_POWER`, `SPOTIPI_LIBRARY_TTL_MINUTES`, `SPOTIPI_MAX_CONCURRENCY`.
- Writes to disk are expensive—only persist when TTLs justify it (see device-cache logic).
- **Alarm persistence (v1.3.8)**: systemd timer (`spotipi-alarm.timer`) runs daily at 05:30 as backup to in-process scheduler. Enabled by default via `SPOTIPI_ENABLE_ALARM_TIMER=1`.

### Testing & Tooling
- Unit/integration tests live in `tests/`; they use Flask's test client (no live server). Always update/add tests when touching routes, services, or Spotify interactions.
- Run `pytest` before deployment. Common targets: `tests/test_api_contract.py`, `tests/test_service_layer.py`, `tests/test_spotify_resilience.py`.
  - **New test suites (v1.3.8)**: `tests/test_config_validation.py` (27 tests for Pydantic schemas), `tests/test_spotify_retry.py` (16 tests for HTTP retry logic).
- Deployment uses `scripts/deploy_to_pi.sh`; it relies on rsync `--itemize-changes`. Do not alter the output format (`%i %f`) unless you update the parser too.

### When Adding New Code
- Stick to existing module boundaries (route → service manager → core utilities).
- Consider translation support: use `t_api("key", request, ...)` for messages surfaced to users.
- Rate-limit new endpoints with `@rate_limit("category")` and wrap handlers with `@api_error_handler`.
- Document new env vars or configuration flags in `config/default_config.json` and README if they impact users.
- **Config changes (v1.3.8)**: Update Pydantic models in `src/config_schema.py` when adding new config fields. Add field validators for constraints (ranges, patterns, enums).
- **Logging best practices (v1.3.8)**: Use structured logging for error paths, especially in alarm/playback code. Include contextual fields (alarm_id, device_name, error_code) for correlation.

### v1.3.8 Critical Improvements
- **Alarm Persistence**: systemd timer provides backup scheduling layer (daily 05:30 check, persistent catch-up after downtime).
- **Structured Logging**: JSON logs with structured fields for production observability. Automatically enabled on Pi, queryable via `journalctl -o json`.
- **Config Validation**: Pydantic v2 schemas validate all config fields (time format, volume range, timezone, weekdays). Prevents runtime errors from malformed configs.
- **HTTP Retry**: Automatic retry with exponential backoff for transient Spotify API errors (429 rate limits, 503 service unavailable). Respects `Retry-After` headers.

### Documentation References
- **Config validation**: See `docs/CONFIG_SCHEMA_VALIDATION.md` for Pydantic schema details, validation rules, error handling.
- **Structured logging**: See `docs/JSON_LOGGING.md` for JSONFormatter usage, log querying patterns, monitoring examples.
- **HTTP retry**: See `docs/SPOTIFY_API_RETRY.md` for retry configuration, backoff calculation, troubleshooting.
- **Environment variables**: See `docs/ENVIRONMENT_VARIABLES.md` for all `SPOTIPI_*` flags, including new v1.3.8 additions.
- **Critical gaps fixed**: See `docs/CODE_REVIEW_GAPS.md` for complete overview of v1.3.8 improvements.

Keep suggestions focused on low-power, thread-safe patterns and respect the existing abstractions instead of reinventing them.
