#!/usr/bin/env python3
"""
SpotiPi Background Server Manager

Features:
- Dedicated local profile (`--profile local`) for safe testing
- venv-first Python interpreter selection
- Health-check based startup validation (`/healthz`)
- Backward-compatible default profile paths/commands
"""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

import psutil


PROFILE_DEFAULTS = {
    "default": {
        "host": "127.0.0.1",
        "port": 5001,
        "spotipi_env": None,
        "debug": None,
        "force_waitress": None,
    },
    "local": {
        "host": "127.0.0.1",
        "port": 5001,
        "spotipi_env": "development",
        "debug": False,
        "force_waitress": True,
    },
}


def _resolve_python(project_root: Path, explicit: str | None = None) -> str:
    """Resolve Python executable, preferring the project venv."""
    if explicit:
        return explicit

    env_override = os.getenv("SPOTIPI_PYTHON")
    if env_override:
        return env_override

    venv_python = project_root / ".venv" / "bin" / "python"
    if venv_python.exists() and os.access(venv_python, os.X_OK):
        return str(venv_python)

    return sys.executable


class SpotiPiServerManager:
    """Manage SpotiPi as a background process."""

    def __init__(
        self,
        profile: str = "default",
        host: str | None = None,
        port: int | None = None,
        spotipi_env: str | None = None,
        debug: bool | None = None,
        force_waitress: bool | None = None,
        python_executable: str | None = None,
        start_timeout: int = 20,
    ):
        self.project_root = Path(__file__).parent.parent
        self.profile = profile
        self.start_timeout = max(5, int(start_timeout))

        suffix = "" if profile == "default" else f".{profile}"

        # Keep old filenames for default profile for backward compatibility.
        if profile == "default":
            self.pid_file = self.project_root / "scripts" / "server.pid"
            self.meta_file = self.project_root / "scripts" / "server.meta.json"
            self.log_file = self.project_root / "logs" / "server.log"
            self.error_log = self.project_root / "logs" / "server_error.log"
        else:
            self.pid_file = self.project_root / "scripts" / f"server{suffix}.pid"
            self.meta_file = self.project_root / "scripts" / f"server{suffix}.meta.json"
            self.log_file = self.project_root / "logs" / f"server{suffix}.log"
            self.error_log = self.project_root / "logs" / f"server{suffix}.error.log"

        self.log_file.parent.mkdir(exist_ok=True)

        defaults = PROFILE_DEFAULTS.get(profile, PROFILE_DEFAULTS["default"])
        meta = self._load_meta()

        self.host = host or meta.get("host") or defaults["host"]
        self.port = int(port or meta.get("port") or defaults["port"])
        self.spotipi_env = (
            spotipi_env
            if spotipi_env is not None
            else meta.get("spotipi_env", defaults["spotipi_env"])
        )
        self.debug = debug if debug is not None else meta.get("debug", defaults["debug"])
        self.force_waitress = (
            force_waitress
            if force_waitress is not None
            else meta.get("force_waitress", defaults["force_waitress"])
        )

        resolved_python = _resolve_python(
            self.project_root,
            python_executable or meta.get("python_executable"),
        )
        self.python_executable = resolved_python

    def _load_meta(self) -> dict[str, Any]:
        if not self.meta_file.exists():
            return {}
        try:
            return json.loads(self.meta_file.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_meta(self) -> None:
        payload = {
            "profile": self.profile,
            "host": self.host,
            "port": self.port,
            "spotipi_env": self.spotipi_env,
            "debug": self.debug,
            "force_waitress": self.force_waitress,
            "python_executable": self.python_executable,
            "updated_at": int(time.time()),
        }
        self.meta_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _cleanup_state_files(self) -> None:
        if self.pid_file.exists():
            self.pid_file.unlink()

    def _get_pid(self) -> int | None:
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text(encoding="utf-8").strip())
        except Exception:
            self._cleanup_state_files()
            return None

    def _matches_spotipi_process(self, pid: int) -> bool:
        if not psutil.pid_exists(pid):
            return False
        try:
            proc = psutil.Process(pid)
            cmdline = " ".join(proc.cmdline())
            return "run.py" in cmdline or "src.app" in cmdline
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def is_running(self) -> bool:
        pid = self._get_pid()
        if pid is None:
            return False

        if self._matches_spotipi_process(pid):
            return True

        self._cleanup_state_files()
        return False

    def _health_probe_host(self) -> str:
        host = (self.host or "").strip()
        if host in {"", "0.0.0.0", "::"}:
            return "127.0.0.1"
        return host

    def _health_url(self) -> str:
        return f"http://{self._health_probe_host()}:{self.port}/healthz"

    def _is_process_alive(self, pid: int) -> bool:
        if not psutil.pid_exists(pid):
            return False
        try:
            return psutil.Process(pid).is_running()
        except psutil.NoSuchProcess:
            return False

    def _wait_for_ready(self, pid: int) -> bool:
        deadline = time.time() + self.start_timeout
        health_url = self._health_url()
        request = Request(health_url, headers={"User-Agent": "SpotiPiServerManager/1.0"})

        while time.time() < deadline:
            if not self._is_process_alive(pid):
                return False

            try:
                with urlopen(request, timeout=1.0) as response:  # nosec B310
                    if 200 <= response.status < 300:
                        return True
            except URLError:
                pass
            except Exception:
                pass

            time.sleep(0.4)

        return False

    def _build_runtime_env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PORT"] = str(self.port)
        env["HOST"] = self.host

        if self.spotipi_env:
            env["SPOTIPI_ENV"] = self.spotipi_env

        if self.debug is not None:
            env["SPOTIPI_DEBUG"] = "1" if self.debug else "0"

        if self.force_waitress is not None:
            env["SPOTIPI_FORCE_WAITRESS"] = "1" if self.force_waitress else "0"

        if self.debug is False:
            env["SPOTIPI_DISABLE_RELOADER"] = "1"

        return env

    def get_status(self) -> dict[str, Any]:
        if not self.is_running():
            return {
                "status": "stopped",
                "profile": self.profile,
                "pid": None,
                "uptime": None,
                "memory_mb": None,
                "cpu_percent": None,
                "url": f"http://{self._health_probe_host()}:{self.port}",
                "log_file": str(self.log_file),
                "error_log": str(self.error_log),
            }

        pid = self._get_pid()
        if pid is None:
            return {"status": "stopped", "profile": self.profile}

        try:
            proc = psutil.Process(pid)
            uptime_s = max(0.0, time.time() - proc.create_time())
            return {
                "status": "running",
                "profile": self.profile,
                "pid": pid,
                "uptime": f"{int(uptime_s // 60)}m {int(uptime_s % 60)}s",
                "memory_mb": round(proc.memory_info().rss / 1024 / 1024, 1),
                "cpu_percent": round(proc.cpu_percent(interval=0.0), 1),
                "url": f"http://{self._health_probe_host()}:{self.port}",
                "log_file": str(self.log_file),
                "error_log": str(self.error_log),
            }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return {"status": "error", "profile": self.profile, "message": "Process not accessible"}

    def start(self) -> bool:
        if self.is_running():
            status = self.get_status()
            print("Server is already running")
            print(f"  Profile: {status.get('profile')}")
            print(f"  PID: {status.get('pid')}")
            print(f"  URL: {status.get('url')}")
            return True

        print("Starting SpotiPi server in background...")
        print(f"  Profile: {self.profile}")
        print(f"  Python: {self.python_executable}")
        print(f"  Host/Port: {self.host}:{self.port}")

        env = self._build_runtime_env()

        try:
            with open(self.log_file, "w", encoding="utf-8") as log_out, open(
                self.error_log, "w", encoding="utf-8"
            ) as log_err:
                process = subprocess.Popen(
                    [self.python_executable, "run.py"],
                    cwd=self.project_root,
                    stdout=log_out,
                    stderr=log_err,
                    env=env,
                    start_new_session=True,
                )

            self.pid_file.write_text(str(process.pid), encoding="utf-8")
            self._save_meta()

            if self._wait_for_ready(process.pid):
                print("Server started successfully")
                print(f"  PID: {process.pid}")
                print(f"  URL: http://{self._health_probe_host()}:{self.port}")
                print(f"  Logs: {self.log_file}")
                return True

            print("Server failed to start or did not become healthy in time")
            print(f"  Check logs: {self.error_log}")
            self.stop(force=True)
            return False

        except Exception as exc:
            print(f"Error starting server: {exc}")
            self._cleanup_state_files()
            return False

    def stop(self, force: bool = False) -> bool:
        pid = self._get_pid()
        if pid is None or not self._matches_spotipi_process(pid):
            print("Server is not running")
            self._cleanup_state_files()
            return True

        print(f"Stopping server (PID: {pid})...")
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            self._cleanup_state_files()
            print("Server was already stopped")
            return True

        deadline = time.time() + (2 if force else 10)
        while time.time() < deadline:
            if not psutil.pid_exists(pid):
                break
            time.sleep(0.3)

        if psutil.pid_exists(pid):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        self._cleanup_state_files()
        print("Server stopped")
        return True

    def restart(self) -> bool:
        print("Restarting server...")
        self.stop()
        time.sleep(0.5)
        return self.start()

    def _tail_file(self, file_path: Path, lines: int = 50, follow: bool = False) -> None:
        if not file_path.exists():
            print(f"No log file found: {file_path}")
            return

        if follow:
            print(f"Following {file_path} (Ctrl+C to stop)...")
            try:
                subprocess.run(["tail", "-f", str(file_path)], check=False)
            except KeyboardInterrupt:
                print("Stopped following logs")
            return

        print(f"Last {lines} lines from {file_path}:")
        result = subprocess.run(
            ["tail", f"-{max(1, lines)}", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout:
            print(result.stdout)

    def logs(self, lines: int = 50, follow: bool = False) -> None:
        self._tail_file(self.log_file, lines=lines, follow=follow)

    def error_logs(self, lines: int = 50, follow: bool = False) -> None:
        self._tail_file(self.error_log, lines=lines, follow=follow)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage SpotiPi background server")
    parser.add_argument(
        "command",
        choices=["start", "stop", "restart", "status", "logs", "errors"],
        help="Action to execute",
    )
    parser.add_argument(
        "--profile",
        default=os.getenv("SPOTIPI_MANAGER_PROFILE", "default"),
        help="Runtime profile (default, local, ...)",
    )
    parser.add_argument("--host", help="Bind host for server start")
    parser.add_argument("--port", type=int, help="Bind port for server start")
    parser.add_argument("--env", dest="spotipi_env", help="SPOTIPI_ENV override")
    parser.add_argument("--debug", choices=["true", "false"], help="Override debug mode")
    parser.add_argument(
        "--waitress",
        dest="force_waitress",
        action="store_true",
        help="Force waitress even when debug would be enabled",
    )
    parser.add_argument(
        "--no-waitress",
        dest="force_waitress",
        action="store_false",
        help="Disable waitress override",
    )
    parser.set_defaults(force_waitress=None)
    parser.add_argument("--python", dest="python_executable", help="Python executable to run run.py")
    parser.add_argument("--timeout", type=int, default=20, help="Startup health-check timeout in seconds")
    parser.add_argument("--lines", type=int, default=50, help="Lines for logs/errors command")
    parser.add_argument("-f", "--follow", action="store_true", help="Follow logs in real time")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    debug_override = None
    if args.debug is not None:
        debug_override = args.debug == "true"

    manager = SpotiPiServerManager(
        profile=args.profile,
        host=args.host,
        port=args.port,
        spotipi_env=args.spotipi_env,
        debug=debug_override,
        force_waitress=args.force_waitress,
        python_executable=args.python_executable,
        start_timeout=args.timeout,
    )

    if args.command == "start":
        return 0 if manager.start() else 1

    if args.command == "stop":
        return 0 if manager.stop() else 1

    if args.command == "restart":
        return 0 if manager.restart() else 1

    if args.command == "status":
        status = manager.get_status()
        print("SpotiPi Server Status")
        print("=" * 30)
        print(f"Profile: {status.get('profile', manager.profile)}")
        if status.get("status") == "running":
            print("Status: running")
            print(f"PID: {status.get('pid')}")
            print(f"Uptime: {status.get('uptime')}")
            print(f"Memory: {status.get('memory_mb')} MB")
            print(f"CPU: {status.get('cpu_percent')}%")
            print(f"URL: {status.get('url')}")
        else:
            print(f"Status: {status.get('status', 'unknown')}")
            print(f"URL: {status.get('url')}")
        print(f"Log: {status.get('log_file')}")
        print(f"Error log: {status.get('error_log')}")
        return 0

    if args.command == "logs":
        manager.logs(lines=args.lines, follow=args.follow)
        return 0

    if args.command == "errors":
        manager.error_logs(lines=args.lines, follow=args.follow)
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
