"""In-memory paper broker that persists trades to SQLite."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Dict, Iterable, List

from sqlalchemy import select

from forex_bot.data.candles import CandleStore
from forex_bot.data.models import OrderORM, PositionORM
from forex_bot.utils.event_bus import EventBus

logger = logging.getLogger(__name__)


class PaperBroker:
    """Minimal paper broker that fills market orders immediately."""

    def __init__(self, settings, store: CandleStore, bus: EventBus) -> None:
        self.settings = settings
        self.store = store
        self.bus = bus
        self._balance = settings.paper_starting_balance
        self._lock = asyncio.Lock()

    async def place_order(
        self,
        *,
        run_id: str,
        instrument: str,
        direction: str,
        price: float,
        confidence: float,
    ) -> dict:
        units = self.settings.trade_units if direction == "long" else -self.settings.trade_units
        async with self._lock:
            return await self._place_and_fill(
                run_id=run_id,
                instrument=instrument,
                direction=direction,
                units=units,
                price=price,
                confidence=confidence,
            )

    async def _place_and_fill(
        self,
        *,
        run_id: str,
        instrument: str,
        direction: str,
        units: int,
        price: float,
        confidence: float,
    ) -> dict:
        order_id = uuid.uuid4().hex
        position_id = uuid.uuid4().hex
        now = datetime.utcnow()
        session = self.store._session_factory()
        try:
            order = OrderORM(
                id=order_id,
                run_id=run_id,
                instrument=instrument,
                direction=direction,
                units=units,
                price=price,
                status="filled",
                created_at=now,
                executed_at=now,
            )
            position = PositionORM(
                id=position_id,
                run_id=run_id,
                order_id=order_id,
                instrument=instrument,
                direction=direction,
                entry_price=price,
                units=abs(units),
                status="open",
                opened_at=now,
            )
            session.add(order)
            session.add(position)
            session.commit()
        finally:
            session.close()

        payload = {
            "order_id": order_id,
            "position_id": position_id,
            "instrument": instrument,
            "direction": direction,
            "price": price,
            "units": units,
            "confidence": confidence,
        }
        await self.bus.publish("order.filled", payload)
        logger.info("Filled paper order %s", payload)
        return payload

    async def update_positions(self, run_id: str, *, instrument: str, price: float) -> List[dict]:
        async with self._lock:
            closed = await asyncio.to_thread(self._update_positions_sync, run_id, instrument, price)
        for payload in closed:
            await self.bus.publish("position.closed", payload)
        return closed

    def _update_positions_sync(self, run_id: str, instrument: str, price: float) -> List[dict]:
        session = self.store._session_factory()
        closed: List[dict] = []
        try:
            stmt = (
                select(PositionORM)
                .where(
                    PositionORM.run_id == run_id,
                    PositionORM.instrument == instrument,
                    PositionORM.status == "open",
                )
                .order_by(PositionORM.opened_at.asc())
            )
            open_positions: Iterable[PositionORM] = session.execute(stmt).scalars().all()
            for pos in open_positions:
                target_take = pos.entry_price * (1 + self.settings.take_profit_pct)
                target_stop = pos.entry_price * (1 - self.settings.stop_loss_pct)
                should_close = False
                if pos.direction == "long":
                    if price >= target_take:
                        reason = "take_profit"
                        should_close = True
                    elif price <= target_stop:
                        reason = "stop_loss"
                        should_close = True
                    pnl = (price - pos.entry_price) * pos.units
                else:
                    target_take = pos.entry_price * (1 - self.settings.take_profit_pct)
                    target_stop = pos.entry_price * (1 + self.settings.stop_loss_pct)
                    if price <= target_take:
                        reason = "take_profit"
                        should_close = True
                    elif price >= target_stop:
                        reason = "stop_loss"
                        should_close = True
                    pnl = (pos.entry_price - price) * pos.units
                if not should_close:
                    continue
                self._balance += pnl
                pos.status = "closed"
                pos.exit_price = price
                pos.closed_at = datetime.utcnow()
                pos.pnl = pnl
                session.add(pos)
                session.commit()
                event_payload = {
                    "run_id": run_id,
                    "position_id": pos.id,
                    "order_id": pos.order_id,
                    "reason": reason,
                    "pnl": pnl,
                    "instrument": instrument,
                    "exit_price": price,
                }
                closed.append(event_payload)
        finally:
            session.close()
        return closed

    async def account_summary(self) -> Dict[str, float]:
        async with self._lock:
            return {"balance": self._balance}

    async def list_open_positions(self, run_id: str) -> List[dict]:
        return [pos for pos in await self.store.list_positions(run_id) if pos["status"] == "open"]


__all__ = ["PaperBroker"]
