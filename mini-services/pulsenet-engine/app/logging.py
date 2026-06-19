"""Structured JSON logging with per-run correlation IDs.

Every ingest/ripple run gets a correlation id so you can grep one run end-to-end:
    grep '"correlation_id": "abc123"' engine.log
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import uuid
from datetime import datetime, timezone

# Holds the correlation id for the current async task / request.
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default="-"
)


def new_correlation_id() -> str:
    """Generate + bind a fresh correlation id to the current context."""
    cid = uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


def set_correlation_id(cid: str) -> None:
    _correlation_id.set(cid)


def get_correlation_id() -> str:
    return _correlation_id.get()


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line, tagged with the correlation id."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "correlation_id": get_correlation_id(),
            "msg": record.getMessage(),
        }
        # Attach any structured extras passed via logger.info(..., extra={"extra": {...}})
        extra = getattr(record, "extra", None)
        if isinstance(extra, dict):
            payload.update(extra)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_configured = False


def configure_logging(level: str = "INFO") -> None:
    """Idempotent root-logger setup. Safe to call from main or tests."""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Module-scoped logger. Use `logger.info("msg", extra={"extra": {...}})`."""
    return logging.getLogger(name)
