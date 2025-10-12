#!/usr/bin/env python3
"""
Custom Werkzeug request handler that sanitises noisy binary request lines.

On the Raspberry Pi we often see TLS handshake attempts (from phones probing
https://) hitting the plain HTTP port.  The default Werkzeug dev server logs
those raw bytes which renders unreadable escape sequences in the logs.

The TidyRequestHandler below detects non-printable request lines and replaces
them with a concise warning.
"""

from __future__ import annotations

import logging
import string
from typing import Any

from werkzeug.serving import WSGIRequestHandler

_LOGGER = logging.getLogger(__name__)
_PRINTABLE = set(string.printable)


class TidyRequestHandler(WSGIRequestHandler):
    """Werkzeug request handler with friendly logging for binary request lines."""

    _ALLOWED_CONTROL = {"\r", "\n", "\t"}

    def _looks_like_tls(self, line: str) -> bool:
        if not line:
            return False
        sample = line[:16]
        return any(
            ch not in _PRINTABLE and ch not in self._ALLOWED_CONTROL
            for ch in sample
        )

    def _sanitize(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if self._looks_like_tls(value):
            return "<binary request line>"
        cleaned = "".join(ch if ch in _PRINTABLE else "?" for ch in value)
        return cleaned

    def handle(self) -> None:
        try:
            super().handle()
        except ValueError:
            request_line = getattr(self, "requestline", "")
            if isinstance(request_line, bytes):
                try:
                    request_line = request_line.decode("latin1", "ignore")
                except Exception:  # pragma: no cover - defensive
                    request_line = ""
            if self._looks_like_tls(request_line):
                _LOGGER.debug(
                    "Suppressed TLS handshake on HTTP port from %s",
                    self.address_string(),
                )
                self.close_connection = True
            else:
                raise

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        if self._looks_like_tls(self.requestline):
            _LOGGER.debug(
                "%s - TLS handshake on HTTP port (%s)",
                self.address_string(),
                code,
            )
            return
        super().log_request(code, size)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003 (werkzeug API)
        sanitized = tuple(self._sanitize(arg) for arg in args)
        super().log_message(format, *sanitized)


__all__ = ["TidyRequestHandler"]
