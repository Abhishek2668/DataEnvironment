"""Explicit re-export of router modules."""
from __future__ import annotations

from forex_bot.api.events import router as events_router
from forex_bot.api.session import router as session_router
from forex_bot.api.status import router as status_router
from forex_bot.api.trade import router as trade_router

__all__ = ["events_router", "session_router", "status_router", "trade_router"]
