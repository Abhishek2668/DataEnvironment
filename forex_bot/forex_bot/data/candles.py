"""Persistent storage for candles and run metadata."""
from __future__ import annotations

import asyncio
import logging
import statistics
import uuid
from datetime import datetime, timezone
from typing import Iterable, List, Sequence

import httpx
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


logger = logging.getLogger(__name__)


OANDA_PRACTICE_BASE = "https://api-fxpractice.oanda.com"
OANDA_TRADE_BASE = "https://api-fxtrade.oanda.com"


_TIMEFRAME_SECONDS = {
    "M1": 60,
    "M5": 5 * 60,
    "M15": 15 * 60,
    "M30": 30 * 60,
    "H1": 60 * 60,
    "H4": 4 * 60 * 60,
    "D": 24 * 60 * 60,
}


class CandleStore:
    """Manage candle ingestion and run bookkeeping."""

    def __init__(self, settings) -> None:
        self.settings = settings
        self._session_factory = create_session_factory(str(settings.db_path))
        self._oanda_base_url = (
            OANDA_PRACTICE_BASE if settings.oanda_env.lower() != "live" else OANDA_TRADE_BASE
        )

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
        self._record_candles_sync([candle])

    def _record_candles_sync(self, candles: Sequence[Candle]) -> None:
        if not candles:
            return
        session = self._session_factory()
        try:
            instrument = candles[0].instrument
            timeframe = candles[0].timeframe
            timestamps = [c.timestamp for c in candles]
            stmt = (
                select(CandleORM.timestamp)
                .where(
                    CandleORM.instrument == instrument,
                    CandleORM.timeframe == timeframe,
                    CandleORM.timestamp.in_(timestamps),
                )
            )
            existing = {row for (row,) in session.execute(stmt)}
            created = 0
            for candle in candles:
                if candle.timestamp in existing:
                    continue
                session.add(
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
                created += 1
            if created:
                session.commit()
        finally:
            session.close()

    async def get_latest(self, instrument: str, timeframe: str, limit: int = 200) -> List[Candle]:
        candles = await asyncio.to_thread(self._get_latest_sync, instrument, timeframe, limit)
        if not candles or self._should_refresh(candles[-1], timeframe):
            remote_candles = await self._fetch_remote_candles(instrument, timeframe, limit)
            if remote_candles:
                await asyncio.to_thread(self._record_candles_sync, remote_candles)
                logger.info(
                    "[CANDLESTORE] Pulled %s candles for %s (%s)",
                    len(remote_candles),
                    instrument,
                    timeframe,
                )
                candles = await asyncio.to_thread(self._get_latest_sync, instrument, timeframe, limit)
        return candles

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

    def _should_refresh(self, last_candle: Candle, timeframe: str) -> bool:
        seconds = _TIMEFRAME_SECONDS.get(timeframe.upper())
        if not seconds:
            return False
        now = datetime.utcnow()
        return (now - last_candle.timestamp).total_seconds() >= seconds

    async def _fetch_remote_candles(
        self, instrument: str, timeframe: str, limit: int
    ) -> Sequence[Candle]:
        token = (
            self.settings.oanda_api_token.get_secret_value()
            if getattr(self.settings, "oanda_api_token", None)
            else None
        )
        if not token:
            logger.warning("OANDA_API_TOKEN not configured; skipping remote candle fetch")
            return []
        params = {"granularity": timeframe, "count": limit, "price": "M"}
        url = f"{self._oanda_base_url}/v3/instruments/{instrument}/candles"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0)) as client:
                response = await client.get(url, params=params, headers={"Authorization": f"Bearer {token}"})
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("Failed to fetch candles from OANDA: %s", exc)
            return []

        payload = response.json()
        raw_candles = payload.get("candles", [])
        candles: list[Candle] = []
        for entry in raw_candles:
            if not entry.get("complete", True):
                continue
            mid = entry.get("mid") or {}
            try:
                timestamp = self._parse_timestamp(entry["time"])
                candles.append(
                    Candle(
                        instrument=instrument,
                        timeframe=timeframe,
                        timestamp=timestamp,
                        open=float(mid.get("o", 0.0)),
                        high=float(mid.get("h", 0.0)),
                        low=float(mid.get("l", 0.0)),
                        close=float(mid.get("c", 0.0)),
                        volume=float(entry.get("volume", 0.0)),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.debug("Skipping malformed candle payload: %s", exc)
                continue
        return candles

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

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
