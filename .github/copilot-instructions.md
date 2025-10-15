## SpotiPi • Copilot Guidance

### Architecture Cheatsheet
- Flask entrypoint: `run.py` imports `src/app.py`; templates/static at project root.
- Core domains live in `src/`: `core/` (alarm & scheduler), `services/` (business logic + `ServiceResult`), `api/spotify.py` (Spotify client), `utils/` (thread-safety, caching, logging, validation).
- Configuration is centralized via `src/config.py` + thread-safe wrapper in `src/utils/thread_safety.py`. Always read/write config with the provided helpers (`load_config()`, `save_config()`, `config_transaction()`).

### Coding Patterns to Follow
- **Concurrency**: Alarm scheduler and token cache are multi-threaded; never mutate config or caches without the thread-safe helpers.
- **Type hints**: Do not use PEP 604 unions (`A | B`); target 3.9-compatible syntax (`Optional[A]`, `Union[...]`).
- **API Responses**: Prefer `api_response(...)` and `ServiceResult.to_dict()` to keep the JSON envelope consistent (`success/timestamp/request_id`).
- **Logging**: Import `setup_logger` from `src/utils/logger.py`. Logs already use emoji prefixes—follow that convention sparingly, keep messages short.
- **Caching**: Use the unified cache layer via `get_cache_migration_layer()`. Avoid new ad‑hoc caches on disk; respect low-power TTL overrides (`SPOTIPI_*` env vars).
- **Spotify Client**: Re-use helpers in `src/api/spotify.py` (they already handle retries, token refresh, low-power worker limits). Do not instantiate raw `requests.Session`; use the shared proxy from `src/api/http.py`.
- **Validation**: All user input funnels through `src/utils/validation.py`. Raise/handle `ValidationError` rather than sprinkling manual checks.

### Pi Zero W Considerations
- Expect a single CPU core with limited RAM; minimize blocking calls on the request thread.
- Honour environment toggles like `SPOTIPI_LOW_POWER`, `SPOTIPI_LIBRARY_TTL_MINUTES`, `SPOTIPI_MAX_CONCURRENCY`.
- Writes to disk are expensive—only persist when TTLs justify it (see device-cache logic).

### Testing & Tooling
- Unit/integration tests live in `tests/`; they use Flask’s test client (no live server). Always update/add tests when touching routes, services, or Spotify interactions.
- Run `pytest` before deployment. Common targets: `tests/test_api_contract.py`, `tests/test_service_layer.py`, `tests/test_spotify_resilience.py`.
- Deployment uses `scripts/deploy_to_pi.sh`; it relies on rsync `--itemize-changes`. Do not alter the output format (`%i %f`) unless you update the parser too.

### When Adding New Code
- Stick to existing module boundaries (route → service manager → core utilities).
- Consider translation support: use `t_api("key", request, ...)` for messages surfaced to users.
- Rate-limit new endpoints with `@rate_limit("category")` and wrap handlers with `@api_error_handler`.
- Document new env vars or configuration flags in `config/default_config.json` and README if they impact users.

Keep suggestions focused on low-power, thread-safe patterns and respect the existing abstractions instead of reinventing them.***
