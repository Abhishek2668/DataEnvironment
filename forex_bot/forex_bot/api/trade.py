"""Trade control routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from forex_bot.engine.core import TradingEngine
from forex_bot.utils.settings import get_settings

router = APIRouter(prefix="/api/trade", tags=["trade"])
settings = get_settings()
engine = TradingEngine.get_instance(settings)


class ForceSignalRequest(BaseModel):
    direction: str = Field(pattern="^(long|short)$")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


@router.post("/signal/force")
async def force_signal(payload: ForceSignalRequest) -> dict:
    if not engine.running or engine.current_run is None:
        raise HTTPException(status_code=409, detail="Trading engine is not running")
    engine.force_signal(payload.direction, payload.confidence)
    return {"status": "queued", "direction": payload.direction, "confidence": payload.confidence}


__all__ = ["router"]
