"""Persistent storage for candles and run metadata."""
from __future__ import annotations

import asyncio
import statistics
import uuid
from datetime import datetime
from typing import Iterable, List

from sqlalchemy import select

from forex_bot.data.models import (
    Candle,
    CandleORM,
    OrderORM,
    PositionORM,
    Run,
    RunORM,
    create_session_factory,
)


class CandleStore:
    """Manage candle ingestion and run bookkeeping."""

    def __init__(self, settings) -> None:
        self.settings = settings
        self._session_factory = create_session_factory(str(settings.db_path))

    async def create_run(self, instrument: str, timeframe: str, mode: str) -> Run:
        return await asyncio.to_thread(self._create_run_sync, instrument, timeframe, mode)

    def _create_run_sync(self, instrument: str, timeframe: str, mode: str) -> Run:
        run = RunORM(
            id=uuid.uuid4().hex,
            instrument=instrument,
            timeframe=timeframe,
            mode=mode,
            status="running",
        )
        session = self._session_factory()
        try:
            session.add(run)
            session.commit()
            session.refresh(run)
            return Run.model_validate(
                {
                    "id": run.id,
                    "instrument": run.instrument,
                    "timeframe": run.timeframe,
                    "mode": run.mode,
                    "status": run.status,
                    "started_at": run.started_at,
                    "stopped_at": run.stopped_at,
                }
            )
        finally:
            session.close()

    async def complete_run(self, run_id: str) -> None:
        await asyncio.to_thread(self._complete_run_sync, run_id)

    def _complete_run_sync(self, run_id: str) -> None:
        session = self._session_factory()
        try:
            run: RunORM | None = session.get(RunORM, run_id)
            if not run:
                return
            run.status = "stopped"
            run.stopped_at = datetime.utcnow()
            session.add(run)
            session.commit()
        finally:
            session.close()

    async def record_candle(self, candle: Candle) -> None:
        await asyncio.to_thread(self._record_candle_sync, candle)

    def _record_candle_sync(self, candle: Candle) -> None:
        session = self._session_factory()
        try:
            session.merge(
                CandleORM(
                    instrument=candle.instrument,
                    timeframe=candle.timeframe,
                    timestamp=candle.timestamp,
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=candle.volume,
                )
            )
            session.commit()
        finally:
            session.close()

    async def get_latest(self, instrument: str, timeframe: str, limit: int = 200) -> List[Candle]:
        return await asyncio.to_thread(self._get_latest_sync, instrument, timeframe, limit)

    def _get_latest_sync(self, instrument: str, timeframe: str, limit: int) -> List[Candle]:
        session = self._session_factory()
        try:
            stmt = (
                select(CandleORM)
                .where(CandleORM.instrument == instrument, CandleORM.timeframe == timeframe)
                .order_by(CandleORM.timestamp.desc())
                .limit(limit)
            )
            rows: Iterable[CandleORM] = session.execute(stmt).scalars().all()
            candles = [
                Candle(
                    instrument=row.instrument,
                    timeframe=row.timeframe,
                    timestamp=row.timestamp,
                    open=row.open,
                    high=row.high,
                    low=row.low,
                    close=row.close,
                    volume=row.volume,
                )
                for row in reversed(list(rows))
            ]
            return candles
        finally:
            session.close()

    async def list_positions(self, run_id: str) -> list[dict]:
        return await asyncio.to_thread(self._list_positions_sync, run_id)

    def _list_positions_sync(self, run_id: str) -> list[dict]:
        session = self._session_factory()
        try:
            stmt = select(PositionORM).where(PositionORM.run_id == run_id).order_by(PositionORM.opened_at.desc())
            rows = session.execute(stmt).scalars().all()
            payload: list[dict] = []
            for row in rows:
                payload.append(
                    {
                        "id": row.id,
                        "instrument": row.instrument,
                        "direction": row.direction,
                        "entry_price": row.entry_price,
                        "exit_price": row.exit_price,
                        "status": row.status,
                        "units": row.units,
                        "opened_at": row.opened_at.isoformat(),
                        "closed_at": row.closed_at.isoformat() if row.closed_at else None,
                        "pnl": row.pnl,
                    }
                )
            return payload
        finally:
            session.close()

    async def list_orders(self, run_id: str) -> list[dict]:
        return await asyncio.to_thread(self._list_orders_sync, run_id)

    def _list_orders_sync(self, run_id: str) -> list[dict]:
        session = self._session_factory()
        try:
            stmt = select(OrderORM).where(OrderORM.run_id == run_id).order_by(OrderORM.created_at.desc())
            rows = session.execute(stmt).scalars().all()
            payload: list[dict] = []
            for row in rows:
                payload.append(
                    {
                        "id": row.id,
                        "direction": row.direction,
                        "price": row.price,
                        "status": row.status,
                        "instrument": row.instrument,
                        "units": row.units,
                        "created_at": row.created_at.isoformat(),
                        "executed_at": row.executed_at.isoformat() if row.executed_at else None,
                    }
                )
            return payload
        finally:
            session.close()

    async def average_price(self, instrument: str, timeframe: str, window: int = 20) -> float | None:
        candles = await self.get_latest(instrument, timeframe, window)
        if len(candles) < window:
            return None
        closes = [c.close for c in candles[-window:]]
        return statistics.fmean(closes)


__all__ = ["CandleStore"]
