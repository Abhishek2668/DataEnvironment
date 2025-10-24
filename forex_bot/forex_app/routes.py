"""FastAPI routes for the trading platform."""
from __future__ import annotations

import json
import uuid
from collections import deque
from datetime import datetime, timedelta

from fastapi import Depends, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from .metrics import CONTENT_TYPE_LATEST, generate_latest

from .broker import OandaBroker, PaperBroker
from .data import CandleStore, FeatureCalculator, FeatureWindow, generate_synthetic_candles
from .engine import TradingEngine
from .event_bus import EventBus
from .logging import configure_logging
from .models import (
    BacktestResult,
    EngineStatus,
    NewsItem,
    Position,
    PositionStatus,
    Signal,
    SignalDirection,
)
from .news import NewsService
from .risk import RiskManager
from .rl_agent import RLSignalService
from .settings import Settings, SettingsUpdate, get_settings, update_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()
    app = FastAPI(title="Forex RL Trading API")
    event_bus = EventBus()
    candle_store = CandleStore(settings.DB_PATH)
    news_service = NewsService(settings)
    broker = PaperBroker() if settings.BROKER == "paper" else OandaBroker()
    engine = TradingEngine(
        settings=settings,
        broker=broker,
        candle_store=candle_store,
        event_bus=event_bus,
        news_service=news_service,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.settings = settings
    app.state.event_bus = event_bus
    app.state.candle_store = candle_store
    app.state.engine = engine
    app.state.news_service = news_service

    async def trace_dependency(response: Response) -> str:
        trace_id = uuid.uuid4().hex
        response.headers["X-Trace-Id"] = trace_id
        return trace_id

    def get_news(request: Request) -> NewsService:
        return request.app.state.news_service

    @app.get("/api/health")
    async def health(trace_id: str = Depends(trace_dependency)) -> dict[str, str | None]:
        status_payload: EngineStatus = await engine.status()
        instrument = status_payload.instrument or "EUR_USD"
        latest_candle = candle_store.latest(instrument)
        return {
            "status": "ok",
            "trace_id": trace_id,
            "mode": status_payload.mode,
            "broker": settings.BROKER,
            "heartbeat_ts": status_payload.heartbeat_ts.isoformat(),
            "latest_data_ts": latest_candle.timestamp.isoformat() if latest_candle else None,
        }

    @app.get("/api/status", response_model=EngineStatus)
    async def status_endpoint(trace_id: str = Depends(trace_dependency)) -> EngineStatus:
        payload = await engine.status()
        if payload.latest_event is None:
            payload.latest_event = {"trace_id": trace_id}
        else:
            payload.latest_event["trace_id"] = trace_id
        return payload

    @app.post("/api/session/start")
    async def session_start(payload: dict, trace_id: str = Depends(trace_dependency)) -> dict[str, str | bool]:
        instrument = payload.get("instrument", "EUR_USD")
        timeframe = payload.get("tf", "M5")
        mode = payload.get("mode", "paper")
        run_id = await engine.start(instrument=instrument, timeframe=timeframe, mode=mode)
        return {"trace_id": trace_id, "run_id": run_id, "mode": mode}

    @app.post("/api/session/stop")
    async def session_stop(trace_id: str = Depends(trace_dependency)) -> dict[str, str | bool]:
        await engine.stop()
        return {"trace_id": trace_id, "stopped": True}

    @app.get("/api/positions/open")
    async def open_positions(trace_id: str = Depends(trace_dependency)) -> dict[str, list[dict]]:
        positions = await engine.broker.list_open_positions()
        return {"trace_id": trace_id, "positions": [p.model_dump() for p in positions]}

    @app.get("/api/orders/pending")
    async def pending_orders(trace_id: str = Depends(trace_dependency)) -> dict[str, list[dict]]:
        return {"trace_id": trace_id, "orders": []}

    class ForceSignalPayload(Signal):
        pass

    @app.post("/api/trade/signal/force")
    async def force_signal(payload: ForceSignalPayload, trace_id: str = Depends(trace_dependency)) -> dict[str, str | bool]:
        await engine.force_signal(payload)
        return {"trace_id": trace_id, "forced": True}

    @app.get("/api/events/stream")
    async def events_stream(trace_id: str = Depends(trace_dependency)) -> StreamingResponse:
        async def generator():
            queue = await event_bus.subscribe("events")
            try:
                while True:
                    item = await queue.get()
                    payload = {"trace_id": trace_id, **item}
                    yield f"data: {json.dumps(payload)}\n\n"
            finally:
                await event_bus.unsubscribe("events", queue)

        return StreamingResponse(generator(), media_type="text/event-stream")

    @app.get("/api/news", response_model=list[NewsItem])
    async def news_endpoint(trace_id: str = Depends(trace_dependency), service: NewsService = Depends(get_news)) -> list[NewsItem]:
        return await service.fetch_news()

    @app.post("/api/settings")
    async def update_settings_endpoint(payload: SettingsUpdate, trace_id: str = Depends(trace_dependency)) -> dict[str, str | dict]:
        nonlocal settings
        new_settings = update_settings(settings, payload)
        app.state.settings = new_settings
        engine.settings = new_settings
        engine.risk.settings = new_settings
        engine.rl_service.settings = new_settings
        settings = new_settings
        return {"trace_id": trace_id, "updated": payload.model_dump(exclude_none=True)}

    @app.post("/api/backtest/run", response_model=BacktestResult)
    async def backtest_run(payload: dict, trace_id: str = Depends(trace_dependency)) -> BacktestResult:
        symbol = payload.get("symbol", "EUR_USD")
        start = datetime.fromisoformat(payload["start"]) if "start" in payload else datetime.utcnow() - timedelta(days=7)
        candles = list(
            generate_synthetic_candles(
                instrument=symbol,
                start=start,
                steps=500,
                base_price=1.1,
                interval=timedelta(minutes=5),
            )
        )
        window = FeatureWindow(deque(maxlen=500))
        calc = FeatureCalculator(window)
        risk = RiskManager(settings)
        rl = RLSignalService(settings)
        equity = 100_000.0
        equity_curve: list[tuple[datetime, float]] = []
        trades: list[Position] = []
        for candle in candles:
            window.append(candle)
            features = calc.compute()
            if not features:
                continue
            signal = rl.predict(features)
            if signal.direction == SignalDirection.FLAT or signal.confidence < float(settings.MIN_SIGNAL_CONF):
                continue
            plan = risk.position_plan(
                equity=equity,
                price=candle.close,
                atr=features.atr,
                direction=signal.direction,
            )
            if not plan:
                continue
            intent = risk.build_order_intent(
                plan=plan,
                instrument=candle.instrument,
                price=candle.close,
                direction=signal.direction,
                reason_codes=["backtest"],
            )
            position = Position(
                id=uuid.uuid4().hex,
                instrument=intent.instrument,
                side=intent.side,
                entry_price=intent.price,
                units=intent.units,
                stop_loss=intent.stop_loss,
                take_profit=intent.take_profit,
                opened_at=candle.timestamp,
                status=PositionStatus.CLOSED,
                unrealized_pnl=0.0,
                realized_pnl=intent.risk_fraction * equity * 2,
                risk_fraction=intent.risk_fraction,
            )
            equity += position.realized_pnl
            trades.append(position)
            equity_curve.append((candle.timestamp, equity))
        stats = {
            "CAGR": 0.0,
            "Sharpe": 0.0,
            "MaxDD": 0.0,
            "Win%": 100.0 if trades else 0.0,
        }
        return BacktestResult(equity_curve=equity_curve, stats=stats, trades=trades)

    @app.get("/api/metrics")
    async def metrics_endpoint() -> PlainTextResponse:
        data = generate_latest()
        return PlainTextResponse(data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()


__all__ = ["create_app", "app"]
