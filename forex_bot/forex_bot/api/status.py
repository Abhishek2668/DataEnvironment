"""Health and status routes."""
from __future__ import annotations

from fastapi import APIRouter

from forex_bot.engine.core import TradingEngine
from forex_bot.utils.settings import get_settings

router = APIRouter(prefix="/api", tags=["status"])
settings = get_settings()
engine = TradingEngine.get_instance(settings)


@router.get("/health")
async def health() -> dict:
    status_payload = await engine.status()
    return {"status": "ok", "engine": status_payload}


@router.get("/status")
async def status() -> dict:
    status_payload = await engine.status()
    status_payload["broker"] = settings.broker
    status_payload["db_path"] = str(settings.db_path)
    return status_payload


__all__ = ["router"]
