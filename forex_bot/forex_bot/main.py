"""FastAPI entrypoint for the trading backend."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forex_bot.api import events, session, status, trade
from forex_bot.utils.logging import configure_logging
from forex_bot.utils.settings import get_settings
from forex_bot.utils import EventBus
from forex.data.candles_store import CandleStore
from forex_app.news import NewsService
from forex_bot.broker.oanda import OandaBroker
from forex_bot.broker.paper import PaperBroker
from forex_bot.engine.core import TradingEngine

configure_logging()
settings = get_settings()

# --- Initialize dependencies ---
event_bus = EventBus()
candle_store = CandleStore(settings.db_path)
news_service = NewsService(settings)

# --- Select broker based on .env ---
if settings.broker == "oanda":
    broker = OandaBroker(settings, candle_store, event_bus)
else:
    broker = PaperBroker(settings, candle_store, event_bus)

# --- Initialize trading engine ---
engine = TradingEngine(settings=settings)

# --- Create FastAPI app ---
app = FastAPI(title="Forex Trading API", version="1.0.0")

# Attach shared state for access inside routers
app.state.engine = engine
app.state.broker = broker
app.state.settings = settings

# --- CORS setup ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(session.router)
app.include_router(trade.router)
app.include_router(status.router)
app.include_router(events.router)

__all__ = ["app"]
