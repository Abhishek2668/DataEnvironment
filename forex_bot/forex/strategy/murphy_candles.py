from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from forex.fundamentals.filter import FundamentalFilter, FundamentalFilterConfig
from forex.strategy.base import Signal, Strategy, StrategyContext
from forex.ta.indicators import ATRState, MACDState, RSIState, EMAState
from forex.ta.patterns import PatternMatch, detect_patterns
from forex.utils.math import pip_size
from forex.utils.types import Price


DEFAULT_PATTERNS = [
    "engulfing",
    "hammer",
    "shooting_star",
    "harami",
    "morning_star",
    "evening_star",
    "pin_bar",
]


@dataclass
class MurphyCandlesConfig:
    timeframes: dict[str, str] = field(
        default_factory=lambda: {"signal": "M5", "trend": "M15", "confirm": "H1"}
    )
    risk_pct: float = 0.5
    max_positions: int = 1
    atr_period: int = 14
    atr_mult_sl: float = 1.5
    atr_mult_tp: float = 2.0
    spread_pips: float | None = None
    patterns_enabled: list[str] = field(default_factory=lambda: list(DEFAULT_PATTERNS))
    ta_params: dict[str, Any] = field(
        default_factory=lambda: {
            "fast_ma": 9,
            "slow_ma": 21,
            "rsi_period": 14,
            "rsi_ob": 70,
            "rsi_os": 30,
            "macd": [12, 26, 9],
        }
    )
    session: dict[str, Any] = field(
        default_factory=lambda: {"start": "00:00", "end": "23:59", "tz": "UTC"}
    )
    cooldown_bars: int = 3
    max_trades_per_day: int = 10
    daily_profit_target_pct: float = 1.0
    daily_loss_limit_pct: float = 1.0
    fundamental_filters: dict[str, Any] = field(
        default_factory=lambda: {"avoid_high_impact_minutes": 30, "enable_macro_bias": False}
    )
    trade_sides: str = "both"


def _extract_bar(price: Price) -> dict[str, float]:
    bar = (price.metadata or {}).get("bar") if price.metadata else None
    if not bar:
        mid = price.mid
        return {"open": mid, "high": mid, "low": mid, "close": mid, "volume": 0.0}
    return {
        "open": float(bar.get("open", price.mid)),
        "high": float(bar.get("high", price.mid)),
        "low": float(bar.get("low", price.mid)),
        "close": float(bar.get("close", price.mid)),
        "volume": float(bar.get("volume", 0.0)),
    }


class MurphyCandlesV1Strategy(Strategy):
    name = "murphy_candles_v1"

    def __init__(self, config: MurphyCandlesConfig | None = None) -> None:
        self.config = config or MurphyCandlesConfig()
        self.context: StrategyContext | None = None
        self.signal_bars: list[dict[str, float]] = []
        self.trend_fast = EMAState(self.config.ta_params["fast_ma"])
        self.trend_slow = EMAState(self.config.ta_params["slow_ma"])
        macd_params = self.config.ta_params.get("macd", [12, 26, 9])
        self.macd_state = MACDState(macd_params[0], macd_params[1], macd_params[2])
        self.rsi_state = RSIState(self.config.ta_params["rsi_period"])
        self.atr_state = ATRState(self.config.atr_period)
        self.pending_signal: Signal | None = None
        filter_config = FundamentalFilterConfig(
            avoid_high_impact_minutes=self.config.fundamental_filters.get("avoid_high_impact_minutes", 0),
            enable_macro_bias=self.config.fundamental_filters.get("enable_macro_bias", False),
        )
        self.fundamental_filter = FundamentalFilter(filter_config)
        self.last_trade_day: date | None = None
        self.trades_today = 0
        self.cooldown_remaining = 0

    def on_startup(self, context: StrategyContext) -> None:
        self.context = context
        self.signal_bars.clear()
        self.pending_signal = None
        self.trend_fast = EMAState(self.config.ta_params["fast_ma"])
        self.trend_slow = EMAState(self.config.ta_params["slow_ma"])
        macd_params = self.config.ta_params.get("macd", [12, 26, 9])
        self.macd_state = MACDState(macd_params[0], macd_params[1], macd_params[2])
        self.rsi_state = RSIState(self.config.ta_params["rsi_period"])
        self.atr_state = ATRState(self.config.atr_period)
        self.trades_today = 0
        self.last_trade_day = None
        self.cooldown_remaining = 0

    def on_price_tick(self, price: Price) -> None:
        pass

    def on_bar_close(self, price: Price) -> None:
        bar = _extract_bar(price)
        self.signal_bars.append(bar)
        if len(self.signal_bars) > 500:
            self.signal_bars.pop(0)
        self.cooldown_remaining = max(self.cooldown_remaining - 1, 0)
        self._reset_daily_counters(price.time.date())
        if not self.context:
            return
        if not self.fundamental_filter.should_trade_now(price.time, self.context.instrument):
            return
        atr = self.atr_state.update(bar["high"], bar["low"], bar["close"])
        close = bar["close"]
        fast = self.trend_fast.update(close)
        slow = self.trend_slow.update(close)
        rsi = self.rsi_state.update(close)
        macd_line, signal_line, histogram = self.macd_state.update(close)
        spread_limit = self._spread_limit()
        if spread_limit is not None and price.spread > spread_limit:
            return
        if atr is None or rsi is None:
            return
        if self.cooldown_remaining > 0:
            return
        if self.trades_today >= self.config.max_trades_per_day:
            return
        trend_direction = self._trend_direction(fast, slow, close)
        if trend_direction == "flat":
            return
        if not self._trade_side_allowed(trend_direction):
            return
        if not self._momentum_confirms(trend_direction, macd_line, signal_line, histogram, rsi):
            return
        pattern = self._pattern_confirmation(trend_direction)
        if not pattern:
            return
        pip = pip_size(self.context.instrument)
        stop_distance = atr * self.config.atr_mult_sl
        take_profit_distance = atr * self.config.atr_mult_tp
        stop_distance_pips = stop_distance / pip if pip else None
        take_profit_pips = take_profit_distance / pip if pip else None
        if stop_distance_pips is None:
            return
        if trend_direction == "buy":
            stop_price = price.bid - stop_distance
            take_profit_price = price.ask + take_profit_distance
        else:
            stop_price = price.ask + stop_distance
            take_profit_price = price.bid - take_profit_distance
        metadata = {
            "pattern": pattern.name,
            "trend_direction": trend_direction,
            "stop_price": stop_price,
            "take_profit_price": take_profit_price,
        }
        reason = f"{pattern.name}_{trend_direction}"
        self.pending_signal = Signal(
            trend_direction,
            strength=abs(macd_line - signal_line),
            reason=reason,
            stop_distance_pips=stop_distance_pips,
            take_profit_pips=take_profit_pips,
            metadata=metadata,
        )
        self.cooldown_remaining = self.config.cooldown_bars
        self.trades_today += 1

    def on_stop(self) -> None:
        self.pending_signal = None

    def get_signal(self) -> Signal | None:
        signal = self.pending_signal
        self.pending_signal = None
        return signal

    def _spread_limit(self) -> float | None:
        if self.config.spread_pips is None:
            return None
        if not self.context:
            return None
        pip = pip_size(self.context.instrument)
        return self.config.spread_pips * pip

    def _trend_direction(self, fast: float, slow: float, close: float) -> str:
        if fast > slow and close > slow:
            return "buy"
        if fast < slow and close < slow:
            return "sell"
        return "flat"

    def _momentum_confirms(
        self,
        direction: str,
        macd_line: float,
        signal_line: float,
        histogram: float,
        rsi: float,
    ) -> bool:
        rsi_ob = self.config.ta_params.get("rsi_ob", 70)
        rsi_os = self.config.ta_params.get("rsi_os", 30)
        if direction == "buy" and rsi >= rsi_ob:
            return False
        if direction == "sell" and rsi <= rsi_os:
            return False
        if direction == "buy" and (macd_line <= signal_line or histogram <= 0):
            return False
        if direction == "sell" and (macd_line >= signal_line or histogram >= 0):
            return False
        return True

    def _pattern_confirmation(self, direction: str) -> PatternMatch | None:
        if not self.signal_bars:
            return None
        matches = detect_patterns(self.signal_bars, self.config.patterns_enabled)
        for match in reversed(matches):
            if match.direction in {direction, "neutral"}:
                return match
        return None

    def _trade_side_allowed(self, direction: str) -> bool:
        trade_sides = self.config.trade_sides
        if trade_sides == "both":
            return True
        if trade_sides == "long" and direction == "buy":
            return True
        if trade_sides == "short" and direction == "sell":
            return True
        return False

    def _reset_daily_counters(self, today: date) -> None:
        if self.last_trade_day != today:
            self.last_trade_day = today
            self.trades_today = 0
            self.cooldown_remaining = 0


__all__ = ["MurphyCandlesConfig", "MurphyCandlesV1Strategy"]

