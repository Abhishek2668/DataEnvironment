"""Session management routes."""
from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from forex_bot.engine.core import TradingEngine
from forex_bot.engine.live_runner import LiveRunner
from forex_bot.utils.settings import get_settings

router = APIRouter(prefix="/api/session", tags=["session"])
settings = get_settings()
engine = TradingEngine.get_instance(settings)
runner = LiveRunner(engine)


class SessionStartRequest(BaseModel):
    instrument: Optional[str] = Field(default=None)
    timeframe: Optional[str] = Field(default=None)
    mode: Optional[str] = Field(default=None)


@router.post("/start")
async def start_trading(payload: SessionStartRequest) -> dict:
    if engine.running:
        return {"status": "already_running", "run_id": engine.current_run.id if engine.current_run else None}

    await runner.start(instrument=payload.instrument, timeframe=payload.timeframe, mode=payload.mode)

    run_id: str | None = None
    for _ in range(50):
        if engine.current_run:
            run_id = engine.current_run.id
            break
        await asyncio.sleep(0.1)
    if run_id is None:
        raise HTTPException(status_code=503, detail="Engine failed to start")
    return {"status": "running", "run_id": run_id}


@router.post("/stop")
async def stop_trading() -> dict:
    if not engine.running:
        return {"status": "idle"}
    await runner.stop()
    return {"status": "stopped"}


@router.get("/state")
async def session_state() -> dict:
    status_payload = await engine.status()
    return status_payload


__all__ = ["router"]
