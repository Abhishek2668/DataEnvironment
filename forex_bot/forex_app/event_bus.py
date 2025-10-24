"""Simple in-process pub/sub event bus."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import AsyncIterator, DefaultDict


class EventBus:
    """Asynchronous fan-out for engine events and logs."""

    def __init__(self) -> None:
        self._topics: DefaultDict[str, set[asyncio.Queue]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def publish(self, topic: str, message: dict) -> None:
        """Publish a message to a topic."""

        async with self._lock:
            queues = list(self._topics.get(topic, set()))
        for queue in queues:
            await queue.put(message)

    async def subscribe(self, topic: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._topics[topic].add(queue)
        return queue

    async def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            queues = self._topics.get(topic)
            if not queues:
                return
            queues.discard(queue)
            if not queues:
                self._topics.pop(topic, None)

    @asynccontextmanager
    async def listener(self, topic: str) -> AsyncIterator[asyncio.Queue]:
        queue = await self.subscribe(topic)
        try:
            yield queue
        finally:
            await self.unsubscribe(topic, queue)


__all__ = ["EventBus"]
