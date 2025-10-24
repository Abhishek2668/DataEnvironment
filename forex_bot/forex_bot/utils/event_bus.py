"""Asynchronous publish/subscribe event bus."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Set


@dataclass(slots=True)
class Event:
    """Runtime event published by the trading engine."""

    type: str
    payload: Dict[str, Any]
    timestamp: datetime

    def encode(self) -> Dict[str, Any]:
        payload = dict(self.payload)
        payload.update({"type": self.type, "ts": self.timestamp.isoformat(timespec="seconds")})
        return payload


class EventBus:
    """Simple asyncio-based broadcast bus."""

    def __init__(self) -> None:
        self._topics: Dict[str, Set[asyncio.Queue[Event]]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, topic: str) -> asyncio.Queue[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue()
        async with self._lock:
            self._topics[topic].add(queue)
        return queue

    async def unsubscribe(self, topic: str, queue: asyncio.Queue[Event]) -> None:
        async with self._lock:
            queues = self._topics.get(topic)
            if not queues:
                return
            queues.discard(queue)
            if not queues:
                self._topics.pop(topic, None)

    async def publish(self, topic: str, payload: Dict[str, Any]) -> None:
        event = Event(type=topic, payload=payload, timestamp=datetime.utcnow())
        async with self._lock:
            targets = list(self._topics.get(topic, set())) + list(self._topics.get("*", set()))
        for queue in targets:
            await queue.put(event)


__all__ = ["Event", "EventBus"]
