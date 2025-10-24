from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import json


@dataclass(slots=True)
class FundamentalFilterConfig:
    avoid_high_impact_minutes: int = 0
    enable_macro_bias: bool = False
    calendar_path: Path | None = None


class FundamentalFilter:
    def __init__(self, config: FundamentalFilterConfig | None = None) -> None:
        self.config = config or FundamentalFilterConfig()
        self._events: list[dict[str, Any]] | None = None

    def load_events(self) -> list[dict[str, Any]]:
        if self._events is not None:
            return self._events
        path = self.config.calendar_path
        if not path or not Path(path).exists():
            self._events = []
            return self._events
        with Path(path).open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        events: list[dict[str, Any]] = []
        for entry in payload:
            when = datetime.fromisoformat(entry["time"])
            events.append({"time": when, "impact": entry.get("impact", "medium"), "instruments": entry.get("instruments", [])})
        self._events = events
        return self._events

    def should_trade_now(self, now: datetime, instrument: str) -> bool:
        minutes = self.config.avoid_high_impact_minutes
        if minutes <= 0:
            return True
        events = self.load_events()
        window = timedelta(minutes=minutes)
        for event in events:
            event_time: datetime = event["time"]
            if event["instruments"] and instrument not in event["instruments"]:
                continue
            if abs((event_time - now).total_seconds()) <= window.total_seconds():
                return False
        return True


def should_trade_now(now: datetime, instrument: str, filters: Iterable[FundamentalFilter] | None = None) -> bool:
    if not filters:
        return True
    for filter_ in filters:
        if not filter_.should_trade_now(now, instrument):
            return False
    return True


__all__ = ["FundamentalFilter", "FundamentalFilterConfig", "should_trade_now"]

