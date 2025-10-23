from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path
from typing import Any, Dict

from pythonjsonlogger import jsonlogger

DEFAULT_LOG_LEVEL = "INFO"
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


class JsonFormatter(jsonlogger.JsonFormatter):
    """Default JSON formatter used for all log records."""

    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:  # noqa: D401
        super().add_fields(log_record, record, message_dict)
        if not log_record.get("timestamp"):
            log_record["timestamp"] = self.formatTime(record, self.datefmt)
        log_record.setdefault("level", record.levelname)
        log_record.setdefault("logger", record.name)
        if isinstance(record.args, dict):
            log_record.setdefault("args", record.args)


def configure_logging(debug: bool = False) -> None:
    """Configure application logging."""

    level = "DEBUG" if debug else DEFAULT_LOG_LEVEL
    formatter = JsonFormatter("%(timestamp)s %(level)s %(name)s %(message)s")

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {"json": {"()": JsonFormatter}},
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": "json",
                "level": level,
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "level": level,
                "filename": str(LOG_DIR / "forex.log"),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 5,
            },
        },
        "root": {"handlers": ["stdout", "file"], "level": level},
    }

    logging.config.dictConfig(logging_config)


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger instance."""

    return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger"]
