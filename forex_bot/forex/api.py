from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pendulum
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from forex.backtest.engine import BacktestConfig, Backtester, CandleBar
from forex.backtest.reports import write_reports
from forex.broker.oanda import OandaBroker, OandaError
from forex.broker.paper_sim import PaperSimBroker
from forex.config import Settings, get_settings
from forex.data.candles_store import CandleStore
from forex.data.run_store import RunStore
from forex.realtime.bus import EventBus
from forex.realtime.live import LiveRunConfig, LiveRunner, LiveRunnerError
from forex.strategy.registry import UnknownStrategyError, create_strategy, list_strategies
from forex.utils.time import utc_now
from forex.utils.types import OrderRequest

ORIGINS = ["http://localhost:5173", "http://localhost:3000"]


class LiveRunRequest(BaseModel):
    strategy: str
    instrument: str
    granularity: str
    risk: float = Field(gt=0)
    max_positions: int = Field(default=1, ge=1)
    stop_distance_pips: float = Field(default=20.0, gt=0)
    spread_pips: float | None = Field(default=None, ge=0)
    take_profit_pips: float | None = Field(default=None, ge=0)
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    def _aliases(cls, data: Any) -> Any:  # noqa: N805 - pydantic hook signature
        if isinstance(data, dict):
            if "sl" in data and "stop_distance_pips" not in data:
                data["stop_distance_pips"] = data.pop("sl")
            if "tp" in data and "take_profit_pips" not in data:
                data["take_profit_pips"] = data.pop("tp")
        return data


class BacktestRequest(BaseModel):
    strategy: str
    instrument: str
    granularity: str
    risk: float = Field(gt=0)
    max_positions: int = Field(default=1, ge=1)
    spread_pips: float = Field(default=0.8, ge=0)
    slippage: float = Field(default=0.00005, ge=0)
    start: datetime | None = Field(default=None, alias="from")
    end: datetime | None = Field(default=None, alias="to")
    params: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class OrderCreateRequest(BaseModel):
    instrument: str
    units: int
    side: str
    stop_loss: float | None = None
    take_profit: float | None = None

    model_config = ConfigDict(extra="ignore")


class CancelOrderRequest(BaseModel):
    order_id: str


def create_broker(settings: Settings):
    if settings.broker == "oanda":
        try:
            return OandaBroker()
        except OandaError:
            return PaperSimBroker(spread_pips=settings.spread_pips_default)
    return PaperSimBroker(spread_pips=settings.spread_pips_default)


def ensure_paper_only(settings: Settings) -> None:
    if getattr(settings, "oanda_env", "practice") != "practice":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail={"paper_only": True})


def get_settings_dependency(request: Request) -> Settings:
    return request.app.state.settings


def get_broker_dependency(request: Request):
    return request.app.state.broker


def get_event_bus(request: Request) -> EventBus:
    return request.app.state.event_bus


def get_candle_store(request: Request) -> CandleStore:
    return request.app.state.candle_store


def get_run_store(request: Request) -> RunStore:
    return request.app.state.run_store


def get_live_runner(request: Request) -> LiveRunner:
    return request.app.state.live_runner


def require_token(request: Request, settings: Settings = Depends(get_settings_dependency)) -> None:
    token = settings.dash_token
    provided = request.headers.get("authorization", "")
    if not provided.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    incoming = provided.split(" ", 1)[1]
    if incoming != token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")


def create_app(
    *,
    settings: Settings | None = None,
    broker=None,
    candle_store: CandleStore | None = None,
    event_bus: EventBus | None = None,
    run_store: RunStore | None = None,
    live_runner: LiveRunner | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Forex Paper Trading API")
    bus = event_bus or EventBus()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    store = candle_store or CandleStore()
    broker_instance = broker or create_broker(settings)
    run_store_instance = run_store or RunStore(engine=store.engine)
    live_runner_instance = live_runner or LiveRunner(
        broker=broker_instance,
        strategy_factory=create_strategy,
        event_bus=bus,
        run_store=run_store_instance,
    )

    app.state.settings = settings
    app.state.event_bus = bus
    app.state.candle_store = store
    app.state.broker = broker_instance
    app.state.run_store = run_store_instance
    app.state.live_runner = live_runner_instance

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config")
    async def config(settings: Settings = Depends(get_settings_dependency)) -> dict[str, Any]:
        return {
            "base_currency": settings.base_currency,
            "timezone": settings.timezone.name,
            "broker": settings.broker,
            "environment": getattr(settings, "oanda_env", "practice"),
        }

    @app.get("/api/instruments")
    async def instruments(broker=Depends(get_broker_dependency)) -> Any:
        return await broker.get_instruments()

    @app.get("/api/candles")
    async def candles(
        instrument: str = Query(...),
        granularity: str = Query(...),
        limit: int = Query(500, ge=1, le=2000),
        start: str | None = Query(None),
        end: str | None = Query(None),
        store: CandleStore = Depends(get_candle_store),
    ) -> list[dict[str, Any]]:
        start_dt = pendulum.parse(start) if start else None
        end_dt = pendulum.parse(end) if end else None
        records = store.load_candles(instrument=instrument, granularity=granularity, start=start_dt, end=end_dt)
        sliced = list(records)[-limit:]
        return [
            {
                "time": candle.time.isoformat(),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            }
            for candle in sliced
        ]

    @app.get("/api/strategies")
    async def strategies() -> list[dict[str, Any]]:
        return list_strategies()

    @app.get("/api/orders")
    async def orders(broker=Depends(get_broker_dependency)) -> Any:
        return await broker.get_orders()

    @app.get("/api/positions")
    async def positions(broker=Depends(get_broker_dependency)) -> Any:
        return await broker.get_open_positions()

    @app.get("/api/account")
    async def account(broker=Depends(get_broker_dependency)) -> Any:
        return await broker.get_account()

    @app.get("/api/runs")
    async def runs(store: RunStore = Depends(get_run_store)) -> list[dict[str, Any]]:
        payload = []
        for run in store.list_runs():
            payload.append(
                {
                    "id": run.id,
                    "type": run.type,
                    "status": run.status,
                    "strategy": run.strategy,
                    "instrument": run.instrument,
                    "granularity": run.granularity,
                    "started_at": run.started_at.isoformat(),
                    "ended_at": run.ended_at.isoformat() if run.ended_at else None,
                    "config": run.config,
                }
            )
        return payload

    @app.get("/api/runs/{run_id}/metrics")
    async def run_metrics(run_id: str, store: RunStore = Depends(get_run_store)) -> Any:
        metrics = store.get_metrics(run_id)
        if not metrics:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics not found")
        return metrics

    @app.post("/api/run-live")
    async def run_live(
        payload: LiveRunRequest,
        settings: Settings = Depends(get_settings_dependency),
        runner: LiveRunner = Depends(get_live_runner),
        _=Depends(require_token),
    ) -> dict[str, Any]:
        ensure_paper_only(settings)
        spread = payload.spread_pips if payload.spread_pips is not None else settings.spread_pips_default
        try:
            run_id = await runner.start(
                LiveRunConfig(
                    strategy=payload.strategy,
                    instrument=payload.instrument,
                    granularity=payload.granularity,
                    risk_pct=payload.risk,
                    stop_distance_pips=payload.stop_distance_pips,
                    max_positions=payload.max_positions,
                    spread_pips=spread,
                    params=payload.params,
                    take_profit_pips=payload.take_profit_pips,
                )
            )
        except UnknownStrategyError as exc:  # pragma: no cover - validated earlier
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except LiveRunnerError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        return {"run_id": run_id, "status": "started"}

    @app.post("/api/stop-live")
    async def stop_live(
        runner: LiveRunner = Depends(get_live_runner),
        settings: Settings = Depends(get_settings_dependency),
        _=Depends(require_token),
    ) -> dict[str, Any]:
        ensure_paper_only(settings)
        await runner.stop()
        return {"status": "stopped"}

    @app.post("/api/backtest")
    async def backtest(
        payload: BacktestRequest,
        settings: Settings = Depends(get_settings_dependency),
        store: CandleStore = Depends(get_candle_store),
        run_store: RunStore = Depends(get_run_store),
        _=Depends(require_token),
    ) -> dict[str, Any]:
        ensure_paper_only(settings)
        try:
            strategy = create_strategy(payload.strategy, payload.params)
        except UnknownStrategyError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        candles = store.load_candles(
            instrument=payload.instrument,
            granularity=payload.granularity,
            start=payload.start,
            end=payload.end,
        )
        if not candles:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No candles available")
        candle_bars = [
            CandleBar(
                time=candle.time,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
            )
            for candle in candles
        ]
        config = BacktestConfig(
            instrument=payload.instrument,
            granularity=payload.granularity,
            risk_pct=payload.risk,
            max_positions=payload.max_positions,
            spread=payload.spread_pips * 0.0001,
            slippage=payload.slippage,
        )
        backtester = Backtester(strategy, config)
        run_id = utc_now().format("YYYYMMDDHHmmss")
        run_store.start_run(
            run_id,
            run_type="backtest",
            strategy=payload.strategy,
            instrument=payload.instrument,
            granularity=payload.granularity,
            config={
                "risk": payload.risk,
                "max_positions": payload.max_positions,
                "spread_pips": payload.spread_pips,
                "slippage": payload.slippage,
                "params": payload.params,
                "start": payload.start.isoformat() if payload.start else None,
                "end": payload.end.isoformat() if payload.end else None,
            },
        )
        result = await asyncio.to_thread(backtester.run, candle_bars)
        output_dir = Path("backtest_output") / run_id
        await asyncio.to_thread(write_reports, result, output_dir)
        run_store.save_metrics(run_id, result.metrics, result.equity_curve)
        run_store.finish_run(run_id, status="completed")
        return {"run_id": run_id, "metrics": result.metrics, "equity_curve": result.equity_curve}

    @app.post("/api/orders")
    async def create_order(
        payload: OrderCreateRequest,
        broker=Depends(get_broker_dependency),
        settings: Settings = Depends(get_settings_dependency),
        _=Depends(require_token),
    ) -> Any:
        ensure_paper_only(settings)
        request = OrderRequest(
            instrument=payload.instrument,
            units=payload.units,
            side=payload.side,  # type: ignore[arg-type]
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
        )
        return await broker.place_order(request)

    @app.post("/api/cancel")
    async def cancel_order(
        payload: CancelOrderRequest,
        broker=Depends(get_broker_dependency),
        settings: Settings = Depends(get_settings_dependency),
        _=Depends(require_token),
    ) -> dict[str, Any]:
        ensure_paper_only(settings)
        await broker.cancel_order(payload.order_id)
        return {"status": "cancelled"}

    @app.get("/api/stream/logs")
    async def stream_logs(bus: EventBus = Depends(get_event_bus)) -> StreamingResponse:
        async def generator():
            queue = bus.subscribe("logs")
            try:
                while True:
                    item = await queue.get()
                    yield f"data: {json.dumps(item)}\n\n"
            finally:
                bus.unsubscribe("logs", queue)

        return StreamingResponse(generator(), media_type="text/event-stream")

    @app.get("/api/stream/prices")
    async def stream_prices(
        instrument: str = Query(...),
        bus: EventBus = Depends(get_event_bus),
    ) -> StreamingResponse:
        topic = f"prices:{instrument.upper()}"

        async def generator():
            queue = bus.subscribe(topic)
            try:
                while True:
                    item = await queue.get()
                    yield f"data: {json.dumps(item)}\n\n"
            finally:
                bus.unsubscribe(topic, queue)

        return StreamingResponse(generator(), media_type="text/event-stream")

    @app.get("/api/stream/events")
    async def stream_events(bus: EventBus = Depends(get_event_bus)) -> StreamingResponse:
        async def generator():
            queue = bus.subscribe("events")
            try:
                while True:
                    item = await queue.get()
                    yield f"data: {json.dumps(item)}\n\n"
            finally:
                bus.unsubscribe("events", queue)

        return StreamingResponse(generator(), media_type="text/event-stream")

    return app


app = create_app()

