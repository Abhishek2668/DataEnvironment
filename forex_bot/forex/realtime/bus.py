from __future__ import annotations

import asyncio
import collections
import contextlib
from typing import Any, Dict, List


class EventBus:
    """A lightweight asyncio-based pub/sub event bus."""

    def __init__(self) -> None:
        self._topics: Dict[str, List[asyncio.Queue[Any]]] = collections.defaultdict(list)

    def subscribe(self, topic: str) -> asyncio.Queue[Any]:
        queue: asyncio.Queue[Any] = asyncio.Queue()
        self._topics[topic].append(queue)
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue[Any]) -> None:
        with contextlib.suppress(ValueError):
            self._topics[topic].remove(queue)
        if not self._topics.get(topic):
            self._topics.pop(topic, None)

    async def publish(self, topic: str, data: Any) -> None:
        subscribers = list(self._topics.get(topic, []))
        for queue in subscribers:
            await queue.put(data)


__all__ = ["EventBus"]

