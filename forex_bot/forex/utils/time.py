from __future__ import annotations

from datetime import datetime, timezone

import pendulum

from forex.config import get_settings


def utc_now() -> datetime:
    """Return aware UTC now."""

    return datetime.now(tz=timezone.utc)


def to_timezone(dt: datetime, tz: str | None = None) -> datetime:
    """Convert a datetime to configured timezone."""

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    settings = get_settings()
    target_tz = pendulum.timezone(tz or settings.default_timezone)
    pendulum_dt = pendulum.instance(dt)
    return pendulum_dt.in_timezone(target_tz.name)


__all__ = ["utc_now", "to_timezone"]
