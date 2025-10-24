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
    price = engine.last_price()
    if price is None and engine.context is not None:
        candles = await engine.store.get_latest(engine.context.instrument, engine.context.timeframe, 1)
        if candles:
            price = candles[-1].close
    if price is None:
        raise HTTPException(status_code=409, detail="No market data available")
    engine.force_signal(payload.direction, payload.confidence)
    order = await engine.broker.place_order(
        run_id=engine.current_run.id,
        instrument=engine.context.instrument if engine.context else "EUR_USD",
        direction=payload.direction,
        price=price,
        confidence=payload.confidence,
    )
    return {"status": "ok", "order": order}


__all__ = ["router"]
