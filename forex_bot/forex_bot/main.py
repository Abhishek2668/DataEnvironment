"""FastAPI entrypoint for the trading backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forex_bot.api import events, session, status, trade
from forex_bot.utils.logging import configure_logging
from forex_bot.utils.settings import get_settings

configure_logging()
settings = get_settings()

app = FastAPI(title="Forex Trading API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(trade.router)
app.include_router(status.router)
app.include_router(events.router)


__all__ = ["app"]
