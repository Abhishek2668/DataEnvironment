"""Market data ingestion and feature engineering utilities."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Deque, Iterable

import numpy as np
import pandas as pd
from sqlalchemy import Column, DateTime, Float, Integer, MetaData, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .models import Candle, FeatureSnapshot

WINDOW_LIMIT = 500

metadata = MetaData()
Base = declarative_base(metadata=metadata)


class CandleORM(Base):
    __tablename__ = "candles"

    id = Column(Integer, primary_key=True)
    instrument = Column(String, index=True, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Float, nullable=False)


@dataclass(slots=True)
class FeatureWindow:
    """In-memory window of candle closes for technical analysis."""

    candles: Deque[Candle]

    def append(self, candle: Candle) -> None:
        self.candles.append(candle)
        if len(self.candles) > WINDOW_LIMIT:
            self.candles.popleft()

    def to_dataframe(self) -> pd.DataFrame:
        data = {
            "timestamp": [c.timestamp for c in self.candles],
            "open": [c.open for c in self.candles],
            "high": [c.high for c in self.candles],
            "low": [c.low for c in self.candles],
            "close": [c.close for c in self.candles],
            "volume": [c.volume for c in self.candles],
        }
        return pd.DataFrame(data).set_index("timestamp")


class CandleStore:
    """Persist candles to SQLite and maintain an in-memory feature window."""

    def __init__(self, path: Path) -> None:
        self.engine = create_engine(f"sqlite:///{path}", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.window = FeatureWindow(deque(maxlen=WINDOW_LIMIT))

    def add(self, candle: Candle) -> None:
        with self.Session() as session:
            session.merge(
                CandleORM(
                    instrument=candle.instrument,
                    timestamp=candle.timestamp,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
            )
            session.commit()
        self.window.append(candle)

    def list(self, instrument: str, limit: int = 200) -> list[Candle]:
        with self.Session() as session:
            rows: list[CandleORM] = (
                session.query(CandleORM)
                .filter(CandleORM.instrument == instrument)
                .order_by(CandleORM.timestamp.desc())
                .limit(limit)
                .all()
            )
        candles = [
            Candle(
                instrument=row.instrument,
                timestamp=row.timestamp,
                open=row.open,
                high=row.high,
                low=row.low,
                close=row.close,
                volume=row.volume,
            )
            for row in reversed(rows)
        ]
        return candles

    def latest(self, instrument: str) -> Candle | None:
        data = self.list(instrument=instrument, limit=1)
        return data[-1] if data else None


class FeatureCalculator:
    """Compute technical indicators required by the RL policy."""

    def __init__(self, window: FeatureWindow) -> None:
        self.window = window

    def compute(self) -> FeatureSnapshot | None:
        if len(self.window.candles) < 20:
            return None
        df = self.window.to_dataframe()
        closes = df["close"]
        ema_fast = closes.ewm(span=8, adjust=False).mean().iloc[-1]
        ema_slow = closes.ewm(span=21, adjust=False).mean().iloc[-1]
        delta = closes.diff().dropna()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14).mean().iloc[-1]
        avg_loss = loss.rolling(window=14).mean().iloc[-1]
        rs = np.inf if avg_loss == 0 else avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        atr = self._atr(df)
        if np.isnan(atr):
            return None
        returns = closes.pct_change().iloc[-1]
        return FeatureSnapshot(
            ema_fast=float(ema_fast),
            ema_slow=float(ema_slow),
            rsi=float(rsi),
            atr=float(atr),
            returns=float(returns),
        )

    @staticmethod
    def _atr(df: pd.DataFrame, period: int = 14) -> float:
        high = df["high"]
        low = df["low"]
        close = df["close"]
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                (high - low),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(window=period).mean().iloc[-1]
        return float(atr)


def generate_synthetic_candles(
    *,
    instrument: str,
    start: datetime,
    steps: int,
    base_price: float,
    interval: timedelta,
) -> Iterable[Candle]:
    price = base_price
    rng = np.random.default_rng(seed=42)
    for index in range(steps):
        timestamp = start + index * interval
        change = rng.normal(0, 0.0005)
        open_price = price
        close = max(0.0001, price * (1 + change))
        high = max(open_price, close) * (1 + abs(change) * 0.5)
        low = min(open_price, close) * (1 - abs(change) * 0.5)
        volume = float(rng.integers(1000, 5000))
        price = close
        yield Candle(
            instrument=instrument,
            timestamp=timestamp,
            open=open_price,
            high=high,
            low=low,
            close=close,
            volume=volume,
        )


__all__ = ["CandleStore", "FeatureCalculator", "generate_synthetic_candles", "FeatureWindow"]
