"""Centralised logging configuration for the trading backend."""
from __future__ import annotations

import logging
import sys

_LOGGER_INITIALISED = False


def configure_logging(level: int = logging.INFO) -> None:
    """Configure a consistent logging format for the entire application."""

    global _LOGGER_INITIALISED
    if _LOGGER_INITIALISED:
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    _LOGGER_INITIALISED = True


__all__ = ["configure_logging"]
