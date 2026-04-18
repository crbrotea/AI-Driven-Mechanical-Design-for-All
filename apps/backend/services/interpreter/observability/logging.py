"""Structured logging with structlog, JSON output for Cloud Logging."""
from __future__ import annotations

import hashlib
import logging
import sys
from typing import Any, cast

import structlog


def configure_logging(
    *, level: str = "INFO", json_output: bool = True
) -> None:
    """Configure structlog and stdlib logging. Call once at startup."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Only add our StreamHandler when no handlers are present (e.g. in production).
    # In test environments pytest already installs its caplog handler on root —
    # clearing it would break log capture.
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        root_logger.addHandler(handler)

    final_renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer()
    )

    # Render the final string BEFORE passing to stdlib so that caplog
    # (and any other handler) sees the formatted JSON/text in record.getMessage().
    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        final_renderer,
    ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named bound logger."""
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def hash_prompt(prompt: str) -> str:
    """Return a stable sha256 hex hash of `prompt` for PII-safe logging."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
