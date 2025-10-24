"""Structured logging configuration."""
from __future__ import annotations

import logging
import sys
from typing import Any

try:  # pragma: no cover - optional dependency
    import structlog
except Exception:  # pragma: no cover - fallback to stdlib
    structlog = None


def configure_logging() -> None:
    """Configure structlog for JSON-formatted logs."""

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    if structlog is not None:
        timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
        shared_processors: list[Any] = [
            structlog.stdlib.add_log_level,
            timestamper,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                *shared_processors,
                structlog.processors.JSONRenderer(),
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
            cache_logger_on_first_use=True,
        )
        handler.setFormatter(structlog.stdlib.ProcessorFormatter(structlog.processors.JSONRenderer()))
    else:
        formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)
    root_logger.handlers.clear()
    root_logger.addHandler(handler)


__all__ = ["configure_logging"]
