"""Risk management and position sizing utilities."""
from __future__ import annotations

from dataclasses import dataclass

from .models import OrderIntent, SignalDirection
from .settings import Settings


def estimate_pip_value(price: float) -> float:
    """Approximate pip value for a standard lot sized by price."""

    price = max(price, 1e-6)
    return max(1e-6, 10.0 / price)


def leverage_for(units: int, price: float, equity: float) -> float:
    notional = abs(units) * price
    return notional / equity if equity else float("inf")


@dataclass(slots=True)
class PositionPlan:
    units: int
    stop_loss: float
    take_profit: float
    risk_fraction: float


class RiskManager:
    """ATR-based position sizing and gating rules."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.peak_equity = 0.0
        self.last_equity = 0.0

    def update_equity(self, equity: float) -> None:
        self.last_equity = equity
        self.peak_equity = max(self.peak_equity, equity)

    def max_drawdown_breached(self, equity: float) -> bool:
        if self.peak_equity == 0:
            return False
        drawdown = 1 - equity / self.peak_equity
        return drawdown >= float(self.settings.MAX_DRAWDOWN_STOP)

    def position_plan(self, *, equity: float, price: float, atr: float, direction: SignalDirection) -> PositionPlan | None:
        allocation = equity * float(self.settings.TRADE_ALLOCATION_PCT)
        if allocation <= 0:
            return None
        sl_distance = 1.5 * atr
        tp_distance = 3.0 * atr
        risk_budget = allocation * float(self.settings.RISK_PCT_PER_TRADE)
        pip_value = estimate_pip_value(price)
        risk_per_unit = max(1e-9, sl_distance * pip_value)
        units = int(risk_budget / risk_per_unit)
        if units <= 0:
            return None
        lev = leverage_for(units, price, equity)
        if lev > float(self.settings.MAX_LEVERAGE):
            return None
        stop_loss = price - sl_distance if direction == SignalDirection.LONG else price + sl_distance
        take_profit = price + tp_distance if direction == SignalDirection.LONG else price - tp_distance
        risk_fraction = risk_budget / equity if equity else 1.0
        return PositionPlan(
            units=units if direction != SignalDirection.SHORT else -units,
            stop_loss=stop_loss,
            take_profit=take_profit,
            risk_fraction=risk_fraction,
        )

    def build_order_intent(
        self,
        *,
        plan: PositionPlan,
        instrument: str,
        price: float,
        direction: SignalDirection,
        reason_codes: list[str],
    ) -> OrderIntent:
        return OrderIntent(
            instrument=instrument,
            side=direction,
            units=plan.units,
            price=price,
            stop_loss=plan.stop_loss,
            take_profit=plan.take_profit,
            reason_codes=reason_codes,
            risk_fraction=plan.risk_fraction,
        )


__all__ = ["RiskManager", "PositionPlan", "estimate_pip_value", "leverage_for"]
