from __future__ import annotations

from forex_app.risk import RiskManager, estimate_pip_value
from forex_app.settings import Settings
from forex_app.models import SignalDirection


def test_position_plan_respects_risk_budget() -> None:
    settings = Settings()
    manager = RiskManager(settings)
    equity = 100_000.0
    price = 1.2
    atr = 0.001

    plan = manager.position_plan(equity=equity, price=price, atr=atr, direction=SignalDirection.LONG)
    assert plan is not None

    allocation = equity * float(settings.TRADE_ALLOCATION_PCT)
    risk_budget = allocation * float(settings.RISK_PCT_PER_TRADE)
    pip_value = estimate_pip_value(price)
    risk_per_unit = 1.5 * atr * pip_value
    max_loss = abs(plan.units) * risk_per_unit
    assert max_loss <= risk_budget + 1e-6

    leverage = abs(plan.units) * price / equity
    assert leverage <= float(settings.MAX_LEVERAGE)
