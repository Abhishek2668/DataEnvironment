"""Helpers for running the trading engine in the background."""
from __future__ import annotations

import asyncio
from typing import Any

from forex_bot.engine.core import TradingEngine


class LiveRunner:
    """Wraps the engine with lifecycle friendly helpers."""

    def __init__(self, engine: TradingEngine) -> None:
        self.engine = engine
        self._task: asyncio.Task | None = None

    async def start(self, **kwargs: Any) -> None:
        if self._task and not self._task.done():
            return
        loop = asyncio.get_running_loop()
        self._task = loop.create_task(self.engine.start(**kwargs))

    async def stop(self) -> None:
        await self.engine.stop()
        if self._task:
            await self._task
            self._task = None


__all__ = ["LiveRunner"]
