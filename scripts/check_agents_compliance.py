#!/usr/bin/env python3
"""
Lightweight AGENTS.md compliance checks for local/CI quality gates.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
ROUTES_DIR = SRC_DIR / "routes"
LEGACY_DIR = ROOT / "static" / "js" / "modules"
README_PATH = ROOT / "Readme.MD"
DEFAULT_CONFIG_PATH = ROOT / "config" / "default_config.json"
ENV_DOC_PATH = ROOT / "docs" / "ENVIRONMENT_VARIABLES.md"

ALLOWED_REQUEST_FILES = {
    SRC_DIR / "api" / "spotify.py",
    SRC_DIR / "api" / "http.py",
}

ENV_PREFIX_REQUIREMENTS = (
    "SPOTIPI_WAITRESS_",
    "SPOTIPI_TOKEN_REFRESH_",
    "SPOTIPI_PLAYER_",
    "SPOTIPI_BREAKER_",
    "SPOTIPI_PLAYBACK_VERIFY_",
    "SPOTIPI_SHUFFLE_RETRY_",
    "SPOTIPI_ENABLE_DEBUG_ROUTES",
)


def iter_python_files(path: Path):
    for file_path in path.rglob("*.py"):
        if "__pycache__" in file_path.parts:
            continue
        yield file_path


def check_no_ad_hoc_requests(errors: list[str]) -> None:
    for file_path in iter_python_files(SRC_DIR):
        if file_path in ALLOWED_REQUEST_FILES:
            continue
        content = file_path.read_text(encoding="utf-8")
        if re.search(r"^\s*import\s+requests\b", content, flags=re.MULTILINE):
            errors.append(f"[requests] Forbidden `import requests` in {file_path.relative_to(ROOT)}")
        if re.search(r"\brequests\.(get|post|put|delete|patch|request)\(", content):
            errors.append(f"[requests] Forbidden direct `requests.*` call in {file_path.relative_to(ROOT)}")


def check_routes_envelope(errors: list[str]) -> None:
    for route_file in ROUTES_DIR.glob("*.py"):
        if route_file.name == "helpers.py":
            continue
        content = route_file.read_text(encoding="utf-8")
        if "jsonify(" in content:
            errors.append(f"[routes] Use `api_response(...)` instead of `jsonify(...)` in {route_file.relative_to(ROOT)}")


def check_legacy_not_reintroduced(errors: list[str]) -> None:
    index_html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    if "static/js/main.js" in index_html or "static/js/modules" in index_html:
        errors.append("[legacy] templates/index.html must not load legacy static/js modules directly")

    for file_path in (ROOT / "frontend" / "src").rglob("*"):
        if file_path.is_file():
            content = file_path.read_text(encoding="utf-8")
            if "static/js/modules" in content or "static/js/main.js" in content:
                errors.append(f"[legacy] Forbidden legacy import/reference in {file_path.relative_to(ROOT)}")

    # Ensure legacy directory still exists, but remains decoupled from shell entrypoint.
    if not LEGACY_DIR.exists():
        errors.append("[legacy] Expected static/js/modules directory is missing")


def check_config_write_patterns(errors: list[str]) -> None:
    for area in ("routes", "services", "core"):
        for file_path in (SRC_DIR / area).rglob("*.py"):
            content = file_path.read_text(encoding="utf-8")
            if "load_config(" in content and "save_config(" in content:
                errors.append(
                    f"[config] Found load+save pattern in {file_path.relative_to(ROOT)}; "
                    "use update_config_atomic()/config_transaction()"
                )


def check_env_docs(errors: list[str]) -> None:
    env_sources = []
    for file_path in list(iter_python_files(SRC_DIR)) + [ROOT / "run.py"]:
        if file_path.exists():
            env_sources.append(file_path.read_text(encoding="utf-8"))
    source_text = "\n".join(env_sources)
    env_vars = sorted(set(re.findall(r"SPOTIPI_[A-Z0-9_]+", source_text)))

    readme = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else ""
    default_cfg = DEFAULT_CONFIG_PATH.read_text(encoding="utf-8") if DEFAULT_CONFIG_PATH.exists() else ""
    env_doc = ENV_DOC_PATH.read_text(encoding="utf-8") if ENV_DOC_PATH.exists() else ""

    for variable in env_vars:
        if not any(
            variable.startswith(prefix) if prefix.endswith("_") else variable == prefix
            for prefix in ENV_PREFIX_REQUIREMENTS
        ):
            continue
        if variable not in readme:
            errors.append(f"[env-doc] {variable} missing in Readme.MD")
        if variable not in default_cfg:
            errors.append(f"[env-doc] {variable} missing in config/default_config.json")
        if variable not in env_doc:
            errors.append(f"[env-doc] {variable} missing in docs/ENVIRONMENT_VARIABLES.md")


def main() -> int:
    errors: list[str] = []
    check_no_ad_hoc_requests(errors)
    check_routes_envelope(errors)
    check_legacy_not_reintroduced(errors)
    check_config_write_patterns(errors)
    check_env_docs(errors)

    if errors:
        print("AGENTS.md compliance checks failed:")
        for issue in sorted(set(errors)):
            print(f"- {issue}")
        return 1

    print("AGENTS.md compliance checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
