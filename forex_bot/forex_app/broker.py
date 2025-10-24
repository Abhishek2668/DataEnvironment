"""Broker interfaces and paper implementation."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from .models import Position, PositionStatus, SignalDirection


class BrokerError(RuntimeError):
    pass


@dataclass(slots=True)
class BrokerPosition:
    id: str
    instrument: str
    side: SignalDirection
    units: int
    entry_price: float
    stop_loss: float | None
    take_profit: float | None
    opened_at: datetime
    closed_at: datetime | None = None
    status: PositionStatus = PositionStatus.OPEN
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    risk_fraction: float = 0.0
    reason: str | None = None

    def to_model(self) -> Position:
        return Position(
            id=self.id,
            instrument=self.instrument,
            side=self.side,
            units=self.units,
            entry_price=self.entry_price,
            stop_loss=self.stop_loss,
            take_profit=self.take_profit,
            opened_at=self.opened_at,
            closed_at=self.closed_at,
            status=self.status,
            unrealized_pnl=self.unrealized_pnl,
            realized_pnl=self.realized_pnl,
            risk_fraction=self.risk_fraction,
        )


@dataclass
class AccountState:
    balance: float = 100_000.0
    equity: float = 100_000.0
    free_margin: float = 100_000.0
    margin_used: float = 0.0
    last_price: float = 0.0


class Broker:
    async def place_order(self, intent):
        raise NotImplementedError

    async def close_position(self, position_id: str, reason: str) -> Position:
        raise NotImplementedError

    async def list_open_positions(self) -> list[Position]:
        raise NotImplementedError

    async def account_summary(self) -> AccountState:
        raise NotImplementedError

    async def refresh_mark_to_market(self, instrument: str, price: float) -> None:
        raise NotImplementedError


class PaperBroker(Broker):
    """Minimalistic paper trading broker."""

    def __init__(self) -> None:
        self.account = AccountState()
        self.positions: dict[str, BrokerPosition] = {}
        self.pending_orders: list[dict] = []

    async def place_order(self, intent) -> Position:
        position_id = uuid.uuid4().hex
        opened_at = datetime.utcnow()
        position = BrokerPosition(
            id=position_id,
            instrument=intent.instrument,
            side=intent.side,
            units=int(intent.units),
            entry_price=intent.price,
            stop_loss=intent.stop_loss,
            take_profit=intent.take_profit,
            opened_at=opened_at,
            risk_fraction=getattr(intent, "risk_fraction", 0.0),
        )
        self.positions[position_id] = position
        self.account.margin_used += abs(intent.units) * intent.price * 0.02
        self.account.free_margin = max(0.0, self.account.equity - self.account.margin_used)
        return position.to_model()

    async def close_position(self, position_id: str, reason: str) -> Position:
        position = self.positions.get(position_id)
        if not position:
            raise BrokerError(f"Unknown position {position_id}")
        position.status = PositionStatus.CLOSED
        position.reason = reason
        position.realized_pnl += position.unrealized_pnl
        position.unrealized_pnl = 0.0
        position.closed_at = datetime.utcnow()
        self.account.balance += position.realized_pnl
        self.account.equity = self.account.balance
        self.account.margin_used = max(0.0, self.account.margin_used - abs(position.units) * position.entry_price * 0.02)
        self.account.free_margin = max(0.0, self.account.equity - self.account.margin_used)
        return position.to_model()

    async def list_open_positions(self) -> list[Position]:
        return [pos.to_model() for pos in self.positions.values() if pos.status == PositionStatus.OPEN]

    async def account_summary(self) -> AccountState:
        return self.account

    async def refresh_mark_to_market(self, instrument: str, price: float) -> None:
        for position in self.positions.values():
            if position.instrument != instrument or position.status != PositionStatus.OPEN:
                continue
            direction = 1 if position.side == SignalDirection.LONG else -1
            move = (price - position.entry_price) * direction
            position.unrealized_pnl = move * abs(position.units)
        self.account.equity = self.account.balance + sum(pos.unrealized_pnl for pos in self.positions.values())
        self.account.free_margin = max(0.0, self.account.equity - self.account.margin_used)


class OandaBroker(Broker):
    """Placeholder for OANDA integration."""

    async def place_order(self, intent):  # pragma: no cover - real integration
        raise BrokerError("OANDA broker not implemented in this environment")

    async def close_position(self, position_id: str, reason: str) -> Position:  # pragma: no cover - real integration
        raise BrokerError("OANDA broker not implemented in this environment")

    async def list_open_positions(self) -> list[Position]:  # pragma: no cover - real integration
        raise BrokerError("OANDA broker not implemented in this environment")

    async def account_summary(self) -> AccountState:  # pragma: no cover - real integration
        raise BrokerError("OANDA broker not implemented in this environment")

    async def refresh_mark_to_market(self, instrument: str, price: float) -> None:  # pragma: no cover - real integration
        raise BrokerError("OANDA broker not implemented in this environment")


__all__ = ["PaperBroker", "OandaBroker", "Broker", "BrokerError", "AccountState"]
