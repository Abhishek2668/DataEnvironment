from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Iterable, Optional

from forex.broker.base import Broker
from forex.execution.risk import RiskParameters, position_size
from forex.logging_config import get_logger
from forex.strategy.base import Signal, Strategy
from forex.utils.types import OrderRequest, Price
from forex.utils.time import utc_now

if TYPE_CHECKING:
    from forex.realtime.bus import EventBus

logger = get_logger(__name__)


@dataclass
class ExecutionConfig:
    instrument: str
    risk_pct: float
    stop_distance_pips: float
    max_positions: int = 1


class Executor:
    def __init__(
        self,
        broker: Broker,
        strategy: Strategy,
        config: ExecutionConfig,
        event_bus: "EventBus" | None = None,
        on_trade: Callable[[dict[str, Any]], Awaitable[dict[str, Any] | None]] | None = None,
    ) -> None:
        self.broker = broker
        self.strategy = strategy
        self.config = config
        self.open_positions: list[dict] = []
        self.event_bus = event_bus
        self.on_trade = on_trade

    async def handle_signal(self, signal: Signal) -> None:
        if len(self.open_positions) >= self.config.max_positions:
            logger.info("max_positions_reached", extra={"instrument": self.config.instrument})
            return
        account = await self.broker.get_account()
        equity = float(account.get("balance", 0))
        stop_distance_pips = signal.stop_distance_pips or self.config.stop_distance_pips
        units = position_size(
            RiskParameters(
                equity=equity,
                risk_pct=self.config.risk_pct,
                stop_distance_pips=stop_distance_pips,
                instrument=self.config.instrument,
            )
        )
        if units <= 0:
            logger.warning("units_zero", extra={"equity": equity})
            return
        order = OrderRequest(
            instrument=self.config.instrument,
            units=units,
            side=signal.side,  # type: ignore[arg-type]
        )
        stop_price = signal.metadata.get("stop_price") if signal.metadata else None
        take_profit_price = signal.metadata.get("take_profit_price") if signal.metadata else None
        if stop_price is not None:
            order.stop_loss = float(stop_price)
        if take_profit_price is not None:
            order.take_profit = float(take_profit_price)
        response = await self.broker.place_order(order)
        self.open_positions.append({"order": response, "signal": signal})
        logger.info(
            "order_submitted",
            extra={"instrument": order.instrument, "units": order.units, "side": order.side, "reason": signal.reason},
        )
        trade_payload = {
            "instrument": order.instrument,
            "side": order.side,
            "units": order.units,
            "reason": signal.reason,
            "response": response,
            "timestamp": utc_now().isoformat(),
        }
        session_snapshot: Optional[dict[str, Any]] = None
        if self.on_trade:
            session_snapshot = await self.on_trade(trade_payload)
        event_payload: dict[str, Any] = {"type": "new_trade", "trade": trade_payload}
        if session_snapshot:
            for key, value in session_snapshot.items():
                event_payload.setdefault(key, value)
        if self.event_bus:
            await self.event_bus.publish("events", event_payload)

    async def run_bar(self, price: Price) -> None:
        self.strategy.on_bar_close(price)
        signal = getattr(self.strategy, "get_signal", lambda: None)()
        if signal:
            await self.handle_signal(signal)


__all__ = ["Executor", "ExecutionConfig"]
