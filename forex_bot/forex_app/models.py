"""Shared pydantic models used across the trading platform."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


StageName = Literal[
    "data",
    "features",
    "rl",
    "risk",
    "order",
    "broker",
    "position",
    "pnl",
    "news",
]


class Candle(BaseModel):
    instrument: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class FeatureSnapshot(BaseModel):
    ema_fast: float
    ema_slow: float
    rsi: float
    atr: float
    returns: float


class SignalDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class Signal(BaseModel):
    direction: SignalDirection
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    features: FeatureSnapshot | None = None
    meta: dict[str, float] = Field(default_factory=dict)


class OrderIntent(BaseModel):
    instrument: str
    side: SignalDirection
    units: int
    price: float
    stop_loss: float | None = None
    take_profit: float | None = None
    reason_codes: list[str] = Field(default_factory=list)
    risk_fraction: float = 0.0


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class Position(BaseModel):
    id: str
    instrument: str
    side: SignalDirection
    entry_price: float
    units: int
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: datetime
    closed_at: datetime | None = None
    status: PositionStatus = PositionStatus.OPEN
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    risk_fraction: float = 0.0


class PositionPL(BaseModel):
    position_id: str
    realized: float
    unrealized: float
    fees: float = 0.0


class NewsItem(BaseModel):
    ts: datetime
    title: str
    url: str
    source: str
    sentiment: float
    impact: Literal["low", "medium", "high"] = "low"
    symbols: list[str] = Field(default_factory=list)


class EngineStageStatus(BaseModel):
    stage: StageName
    status: Literal["idle", "ok", "blocked", "error"] = "idle"
    reason: str | None = None
    last_event_ts: datetime | None = None
    metrics: dict[str, float] = Field(default_factory=dict)


class EngineStatus(BaseModel):
    run_id: str | None
    mode: Literal["paper", "live"]
    broker: str
    instrument: str | None = None
    heartbeat_ts: datetime
    stages: list[EngineStageStatus]
    latest_event: dict[str, str | float | int] | None = None
    idle_reason: str | None = None


class EventEnvelope(BaseModel):
    trace_id: str
    stage: StageName
    ts: datetime
    decision: str
    reason_codes: list[str] = Field(default_factory=list)
    payload: dict[str, float | str | int] = Field(default_factory=dict)


class BacktestRequest(BaseModel):
    symbol: str
    tf: str
    start: datetime
    end: datetime


class BacktestResult(BaseModel):
    equity_curve: list[tuple[datetime, float]]
    stats: dict[str, float]
    trades: list[Position]


__all__ = [
    "BacktestRequest",
    "BacktestResult",
    "Candle",
    "EngineStageStatus",
    "EngineStatus",
    "EventEnvelope",
    "FeatureSnapshot",
    "NewsItem",
    "OrderIntent",
    "Position",
    "PositionPL",
    "PositionStatus",
    "Signal",
    "SignalDirection",
]
