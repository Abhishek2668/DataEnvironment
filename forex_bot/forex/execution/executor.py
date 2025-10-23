from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable

from forex.broker.base import Broker
from forex.execution.risk import RiskParameters, position_size
from forex.logging_config import get_logger
from forex.strategy.base import Signal, Strategy
from forex.utils.types import OrderRequest, Price

logger = get_logger(__name__)


@dataclass
class ExecutionConfig:
    instrument: str
    risk_pct: float
    stop_distance_pips: float
    max_positions: int = 1


class Executor:
    def __init__(self, broker: Broker, strategy: Strategy, config: ExecutionConfig) -> None:
        self.broker = broker
        self.strategy = strategy
        self.config = config
        self.open_positions: list[dict] = []

    async def handle_signal(self, signal: Signal) -> None:
        if len(self.open_positions) >= self.config.max_positions:
            logger.info("max_positions_reached", extra={"instrument": self.config.instrument})
            return
        account = await self.broker.get_account()
        equity = float(account.get("balance", 0))
        units = position_size(
            RiskParameters(
                equity=equity,
                risk_pct=self.config.risk_pct,
                stop_distance_pips=self.config.stop_distance_pips,
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
        response = await self.broker.place_order(order)
        self.open_positions.append({"order": response, "signal": signal})
        logger.info(
            "order_submitted",
            extra={"instrument": order.instrument, "units": order.units, "side": order.side, "reason": signal.reason},
        )

    async def run_bar(self, price: Price) -> None:
        self.strategy.on_bar_close(price)
        signal = getattr(self.strategy, "get_signal", lambda: None)()
        if signal:
            await self.handle_signal(signal)


__all__ = ["Executor", "ExecutionConfig"]
