from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Callable

from forex.logging_config import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class SessionConfig:
    session_start: time
    session_end: time
    timezone: timezone
    daily_profit_target_pct: float = 1.0
    daily_loss_limit_pct: float = 1.0
    max_trades_per_day: int = 10
    cooldown_bars: int = 3
    flatten_on_limit: bool = False
    flatten_on_target: bool = False


@dataclass
class SessionStatus:
    start_equity: float = 0.0
    current_equity: float = 0.0
    trades_today: int = 0
    cooldown_remaining: int = 0
    halted: bool = False
    target_hit: bool = False
    loss_limit_hit: bool = False
    last_reset: datetime | None = None

    @property
    def daily_return_pct(self) -> float:
        if self.start_equity <= 0:
            return 0.0
        return (self.current_equity - self.start_equity) / self.start_equity * 100


class SessionController:
    def __init__(
        self,
        config: SessionConfig,
        event_publisher: Callable[[str, dict], None] | None = None,
    ) -> None:
        self.config = config
        self.event_publisher = event_publisher
        self.state = SessionStatus()

    def start_day(self, equity: float, now: datetime) -> None:
        self.state = SessionStatus(
            start_equity=equity,
            current_equity=equity,
            trades_today=0,
            cooldown_remaining=0,
            halted=False,
            target_hit=False,
            loss_limit_hit=False,
            last_reset=now,
        )
        logger.info("session_start", extra={"equity": equity, "time": now.isoformat()})

    def update_equity(self, equity: float, now: datetime) -> None:
        self.state.current_equity = equity
        if self.state.start_equity <= 0:
            self.state.start_equity = equity
        self._check_limits(now)

    def register_trade(self) -> None:
        self.state.trades_today += 1

    def on_bar_closed(self) -> None:
        if self.state.cooldown_remaining > 0:
            self.state.cooldown_remaining -= 1

    def activate_cooldown(self) -> None:
        self.state.cooldown_remaining = max(self.config.cooldown_bars, 0)

    def can_open_new_positions(self, now: datetime) -> bool:
        if self.state.halted:
            return False
        if self.state.trades_today >= self.config.max_trades_per_day:
            return False
        if self.state.cooldown_remaining > 0:
            return False
        if not self._is_within_session(now):
            return False
        return True

    def _is_within_session(self, now: datetime) -> bool:
        local_now = now.astimezone(self.config.timezone)
        start = datetime.combine(local_now.date(), self.config.session_start, tzinfo=self.config.timezone)
        end = datetime.combine(local_now.date(), self.config.session_end, tzinfo=self.config.timezone)
        if end <= start:
            end += timedelta(days=1)
        return start <= local_now <= end

    def _check_limits(self, now: datetime) -> None:
        daily_return = self.state.daily_return_pct
        if daily_return >= self.config.daily_profit_target_pct and not self.state.target_hit:
            self.state.halted = True
            self.state.target_hit = True
            self._publish("daily_target_hit", {"daily_return_pct": daily_return, "time": now.isoformat()})
        elif daily_return <= -self.config.daily_loss_limit_pct and not self.state.loss_limit_hit:
            self.state.halted = True
            self.state.loss_limit_hit = True
            self._publish("daily_loss_limit_hit", {"daily_return_pct": daily_return, "time": now.isoformat()})

    def _publish(self, topic: str, payload: dict) -> None:
        logger.info(topic, extra=payload)
        if self.event_publisher:
            try:
                self.event_publisher(topic, payload)
            except Exception:  # pragma: no cover - defensive
                logger.exception("event_publish_failed", extra={"topic": topic})

    def maybe_reset(self, now: datetime) -> None:
        if not self.state.last_reset:
            return
        local_now = now.astimezone(self.config.timezone)
        last_reset = self.state.last_reset.astimezone(self.config.timezone)
        if local_now.date() != last_reset.date():
            self.start_day(self.state.current_equity, now)

    def snapshot(self) -> dict[str, float | int | bool]:
        return {
            "start_equity": self.state.start_equity,
            "current_equity": self.state.current_equity,
            "daily_return_pct": self.state.daily_return_pct,
            "trades_today": self.state.trades_today,
            "cooldown_remaining": self.state.cooldown_remaining,
            "halted": self.state.halted,
            "target_hit": self.state.target_hit,
            "loss_limit_hit": self.state.loss_limit_hit,
        }


__all__ = ["SessionController", "SessionConfig", "SessionStatus"]

