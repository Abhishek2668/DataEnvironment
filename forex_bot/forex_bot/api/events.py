"""Server-sent events endpoint."""
from __future__ import annotations

import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from forex_bot.engine.core import TradingEngine
from forex_bot.utils.settings import get_settings

router = APIRouter(prefix="/api/stream", tags=["events"])
settings = get_settings()
engine = TradingEngine.get_instance(settings)


async def event_stream():
    queue = await engine.bus.subscribe("*")
    try:
        initial = json.dumps({"type": "engine.status", "running": engine.running})
        yield f"data: {initial}\n\n"
        while True:
            event = await queue.get()
            payload = json.dumps(event.encode())
            yield f"data: {payload}\n\n"
    finally:
        await engine.bus.unsubscribe("*", queue)


@router.get("/events")
async def stream_events() -> StreamingResponse:
    return StreamingResponse(event_stream(), media_type="text/event-stream")


__all__ = ["router"]
