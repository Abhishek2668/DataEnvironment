"""Broker implementation that proxies trades to OANDA's REST API."""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime
from typing import Iterable, List

import httpx
from sqlalchemy import select

from forex_bot.data.candles import CandleStore
from forex_bot.data.models import OrderORM, PositionORM
from forex_bot.utils.event_bus import EventBus

logger = logging.getLogger(__name__)


class OandaBroker:
    """Submit market orders to OANDA and persist fills locally."""

    def __init__(self, settings, store: CandleStore, bus: EventBus) -> None:
        self.settings = settings
        self.store = store
        self.bus = bus
        self._lock = asyncio.Lock()
        self._base_url = (
            "https://api-fxtrade.oanda.com"
            if settings.oanda_env.lower() == "live"
            else "https://api-fxpractice.oanda.com"
        )
        token = (
            settings.oanda_api_token.get_secret_value()
            if settings.oanda_api_token
            else None
        )
        if not token:
            raise RuntimeError("OANDA_API_TOKEN is required when using the OANDA broker")
        if not settings.oanda_account_id:
            raise RuntimeError("OANDA_ACCOUNT_ID is required when using the OANDA broker")
        self._token = token

    async def execute_trade(
        self,
        instrument: str,
        direction: str,
        *,
        run_id: str,
        price: float,
        confidence: float,
    ) -> dict:
        payload = await self.place_order(
            run_id=run_id,
            instrument=instrument,
            direction=direction,
            price=price,
            confidence=confidence,
        )
        logger.info("[BROKER] Trade executed: %s %s @ %.5f", instrument, direction, price)
        return payload

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
        body = {
            "order": {
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",
                "type": "MARKET",
                "positionFill": "DEFAULT",
            }
        }
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/v3/accounts/{self.settings.oanda_account_id}/orders"
        async with self._lock:
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, read=30.0)) as client:
                    response = await client.post(url, json=body, headers=headers)
                    response.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error("Failed to place OANDA order: %s", exc)
                raise

            data = response.json()
            order_fill = data.get("orderFillTransaction", {})
            order_id = order_fill.get("id", uuid.uuid4().hex)
            fill_price = float(order_fill.get("price", price))
            filled_units = int(float(order_fill.get("units", units)))
            now = datetime.utcnow()

            position_id = uuid.uuid4().hex
            session = self.store._session_factory()
            try:
                order = OrderORM(
                    id=order_id,
                    run_id=run_id,
                    instrument=instrument,
                    direction=direction,
                    units=filled_units,
                    price=fill_price,
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
                    entry_price=fill_price,
                    units=abs(filled_units),
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
                "price": fill_price,
                "units": filled_units,
                "confidence": confidence,
            }
            await self.bus.publish("order.filled", payload)
            return payload

    async def update_positions(self, run_id: str, *, instrument: str, price: float) -> List[dict]:
        # Mirror paper broker behaviour locally for consistent analytics.
        async with self._lock:
            closed = await asyncio.to_thread(
                self._update_positions_sync, run_id, instrument, price
            )
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
                pos.status = "closed"
                pos.exit_price = price
                pos.closed_at = datetime.utcnow()
                pos.pnl = pnl
                session.add(pos)
                session.commit()
                closed.append(
                    {
                        "run_id": run_id,
                        "position_id": pos.id,
                        "order_id": pos.order_id,
                        "reason": reason,
                        "pnl": pnl,
                        "instrument": instrument,
                        "exit_price": price,
                    }
                )
        finally:
            session.close()
        return closed

    async def list_open_positions(self, run_id: str) -> List[dict]:
        return [pos for pos in await self.store.list_positions(run_id) if pos["status"] == "open"]

    async def unrealized_pnl(self, run_id: str, *, instrument: str, price: float) -> float:
        positions = await self.list_open_positions(run_id)
        unrealized = 0.0
        for pos in positions:
            units = pos["units"]
            entry_price = pos["entry_price"]
            if pos["direction"] == "long":
                unrealized += (price - entry_price) * units
            else:
                unrealized += (entry_price - price) * units
        return unrealized


__all__ = ["OandaBroker"]
