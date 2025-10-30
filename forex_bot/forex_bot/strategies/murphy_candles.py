"""Adaptive multi-regime trading strategy with confidence scoring."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

from forex_bot.data.models import Candle

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Signal:
    """Structured strategy output consumed by the trading engine."""

    direction: str
    confidence: float
    reason: str
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    regime: str | None = None
    indicators: Dict[str, float] | None = None
    confidence_breakdown: Dict[str, float] | None = None
    rr_ratio: float | None = None
    timestamp: datetime | None = None
    position_size: int | None = None
    metadata: Dict[str, Any] | None = None


class MurphyStrategy:
    """Multi-strategy adaptive logic that toggles between regimes."""

    def __init__(self) -> None:
        self._time_filter_zone = "America/New_York"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(
        self,
        candles: List[Candle],
        threshold: float | None = None,
        *,
        context: Dict[str, Any] | None = None,
    ) -> Optional[Signal]:
        if not candles:
            return None
        context = context or {}
        latest = candles[-1]

        if not self._within_trading_window(latest.timestamp):
            logger.debug("[STRATEGY] Time filter blocked trade at %s", latest.timestamp)
            return None

        if context.get("news_blocked"):
            logger.info("[STRATEGY] High impact news window active; skipping trade")
            return None

        regime = self.evaluate_market_regime(candles)
        indicators = self._compute_indicator_snapshot(candles)
        if indicators is None:
            return None

        higher_tf = context.get("higher_timeframes", {})
        signal_payload = self.generate_signals(
            candles,
            regime,
            indicators,
            higher_tf=higher_tf,
        )
        if signal_payload is None:
            return None

        confidence, breakdown = self.compute_confidence(
            regime,
            signal_payload["direction"],
            indicators,
            higher_tf,
            signal_payload,
        )
        if threshold is None:
            threshold = 0.6
        if confidence < threshold:
            logger.info(
                "[STRATEGY] Confidence %.2f below threshold %.2f; signal ignored",
                confidence,
                threshold,
            )
            return None

        entry_price = signal_payload["entry_price"]
        stop_loss = signal_payload["stop_loss"]
        take_profit = signal_payload["take_profit"]
        rr_ratio = self._compute_rr_ratio(entry_price, stop_loss, take_profit, signal_payload["direction"])

        signal = Signal(
            direction=signal_payload["direction"],
            confidence=confidence,
            reason=signal_payload["reason"],
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            regime=regime,
            indicators=indicators,
            confidence_breakdown=breakdown,
            rr_ratio=rr_ratio,
            timestamp=latest.timestamp,
            metadata={
                "signal_context": signal_payload,
            },
        )
        logger.info(
            "[STRATEGY] %s regime signal=%s confidence=%.2f rr=%.2f",
            regime,
            signal.direction,
            signal.confidence,
            rr_ratio if rr_ratio is not None else float("nan"),
        )
        return signal

    # ------------------------------------------------------------------
    # Regime & signal helpers
    # ------------------------------------------------------------------
    def evaluate_market_regime(self, candles: List[Candle]) -> str:
        adx = self._adx(candles, period=14)
        regime = "trend" if adx is not None and adx > 25 else "range"
        logger.debug("[STRATEGY] ADX=%.2f regime=%s", adx if adx is not None else float("nan"), regime)
        return regime

    def generate_signals(
        self,
        candles: List[Candle],
        regime: str,
        indicators: Dict[str, float],
        *,
        higher_tf: Dict[str, List[Candle]] | None = None,
    ) -> Optional[Dict[str, Any]]:
        higher_tf = higher_tf or {}
        if regime == "trend":
            return self._trend_signal(candles, indicators, higher_tf)
        return self._range_signal(candles, indicators, higher_tf)

    def compute_confidence(
        self,
        regime: str,
        direction: str,
        indicators: Dict[str, float],
        higher_tf: Dict[str, List[Candle]],
        signal_payload: Dict[str, Any],
    ) -> tuple[float, Dict[str, float]]:
        breakdown: Dict[str, float] = {}

        adx = indicators.get("adx", 0.0)
        adx_conf = 0.3 if ((regime == "trend" and adx > 25) or (regime == "range" and adx <= 25)) else 0.0
        breakdown["regime"] = adx_conf

        alignment = self._higher_timeframe_alignment(direction, higher_tf)
        breakdown["higher_tf"] = 0.2 if alignment else 0.0

        rsi = indicators.get("rsi", 50.0)
        macd = indicators.get("macd", 0.0)
        rsi_macd = (rsi > 50 and macd > 0 and direction == "long") or (
            rsi < 50 and macd < 0 and direction == "short"
        )
        breakdown["momentum"] = 0.2 if rsi_macd else 0.0

        vol_support = self._volatility_support(indicators)
        breakdown["volatility"] = 0.2 if vol_support else 0.0

        price_action_confirm = self._price_action_confirmation(direction, signal_payload)
        breakdown["price_action"] = 0.1 if price_action_confirm else 0.0

        confidence = sum(breakdown.values())
        return confidence, breakdown

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _within_trading_window(self, timestamp: datetime) -> bool:
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        try:
            from zoneinfo import ZoneInfo  # Local import keeps dependency optional

            localized = timestamp.astimezone(ZoneInfo(self._time_filter_zone))
        except Exception:  # pragma: no cover - fallback for systems without tzdata
            localized = timestamp
        return 8 <= localized.hour < 12

    def _compute_indicator_snapshot(self, candles: List[Candle]) -> Optional[Dict[str, float]]:
        if len(candles) < 200:
            return None
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        volumes = [c.volume for c in candles]

        indicators = {
            "close": closes[-1],
            "ema20": self._ema(closes, 20),
            "sma50": self._sma(closes, 50),
            "sma200": self._sma(closes, 200),
            "rsi": self._rsi(closes, period=14),
            "macd": self._macd(closes),
            "atr": self._atr(highs, lows, closes, period=14),
            "bollinger_mid": self._sma(closes, 20),
            "bollinger_std": self._stddev(closes, 20),
            "volume": volumes[-1],
            "volume_avg": mean(volumes[-20:]) if len(volumes) >= 20 else volumes[-1],
            "adx": self._adx(candles, period=14),
        }
        return indicators

    def _trend_signal(
        self,
        candles: List[Candle],
        indicators: Dict[str, float],
        higher_tf: Dict[str, List[Candle]],
    ) -> Optional[Dict[str, Any]]:
        sma50 = indicators.get("sma50")
        sma200 = indicators.get("sma200")
        ema20 = indicators.get("ema20")
        rsi = indicators.get("rsi")
        macd = indicators.get("macd")
        atr = indicators.get("atr")
        close_price = indicators.get("close")
        if None in {sma50, sma200, ema20, rsi, macd, atr, close_price}:
            return None

        direction: Optional[str] = None
        reason: str = ""
        if sma50 > sma200 and close_price > ema20 and rsi > 50 and macd > 0:
            direction = "long"
            reason = "trend_follow_long"
        elif sma50 < sma200 and close_price < ema20 and rsi < 50 and macd < 0:
            direction = "short"
            reason = "trend_follow_short"
        if direction is None:
            return None

        swing_low = self._last_swing_low(candles)
        swing_high = self._last_swing_high(candles)
        atr_stop = 1.5 * atr
        if direction == "long":
            stop_loss = min(swing_low, close_price - atr_stop) if swing_low is not None else close_price - atr_stop
            take_profit = close_price + (close_price - stop_loss) * 3
        else:
            stop_loss = max(swing_high, close_price + atr_stop) if swing_high is not None else close_price + atr_stop
            take_profit = close_price - (stop_loss - close_price) * 3

        payload = {
            "direction": direction,
            "entry_price": close_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": reason,
            "regime": "trend",
            "swing_reference": swing_low if direction == "long" else swing_high,
        }
        payload["higher_tf_alignment"] = self._higher_timeframe_alignment(direction, higher_tf)
        return payload

    def _range_signal(
        self,
        candles: List[Candle],
        indicators: Dict[str, float],
        higher_tf: Dict[str, List[Candle]],
    ) -> Optional[Dict[str, Any]]:
        mid = indicators.get("bollinger_mid")
        std = indicators.get("bollinger_std")
        rsi = indicators.get("rsi")
        close_price = indicators.get("close")
        atr = indicators.get("atr")
        if None in {mid, std, rsi, close_price, atr}:
            return None

        upper_band = mid + 2 * std
        lower_band = mid - 2 * std
        direction: Optional[str] = None
        reason: str = ""

        if close_price <= lower_band * 1.01 and rsi < 30:
            direction = "long"
            reason = "range_reversal_long"
        elif close_price >= upper_band * 0.99 and rsi > 70:
            direction = "short"
            reason = "range_reversal_short"

        if direction is None:
            return None

        if direction == "long":
            stop_loss = lower_band - atr * 0.5
            take_profit = mid
        else:
            stop_loss = upper_band + atr * 0.5
            take_profit = mid

        payload = {
            "direction": direction,
            "entry_price": close_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "reason": reason,
            "regime": "range",
            "bollinger_upper": upper_band,
            "bollinger_lower": lower_band,
        }
        payload["higher_tf_alignment"] = self._higher_timeframe_alignment(direction, higher_tf)
        return payload

    def _higher_timeframe_alignment(
        self,
        direction: str,
        higher_tf: Dict[str, List[Candle]],
    ) -> bool:
        if not higher_tf:
            return False
        alignment_checks: List[bool] = []
        for timeframe, candles in higher_tf.items():
            if not candles:
                continue
            closes = [c.close for c in candles]
            sma50 = self._sma(closes, 50)
            sma200 = self._sma(closes, 200)
            if sma50 is None or sma200 is None:
                continue
            if direction == "long":
                alignment_checks.append(sma50 >= sma200)
            else:
                alignment_checks.append(sma50 <= sma200)
        return all(alignment_checks) and bool(alignment_checks)

    def _volatility_support(self, indicators: Dict[str, float]) -> bool:
        atr = indicators.get("atr", 0.0)
        volume = indicators.get("volume", 0.0)
        volume_avg = indicators.get("volume_avg", volume)
        return atr > 0 and volume >= volume_avg * 0.9

    def _price_action_confirmation(self, direction: str, payload: Dict[str, Any]) -> bool:
        if direction == "long":
            swing = payload.get("swing_reference")
            entry = payload.get("entry_price")
            return swing is not None and entry is not None and entry > swing
        else:
            swing = payload.get("swing_reference")
            entry = payload.get("entry_price")
            if swing is None or entry is None:
                return False
            return entry < swing

    def _compute_rr_ratio(
        self,
        entry: Optional[float],
        stop_loss: Optional[float],
        take_profit: Optional[float],
        direction: str,
    ) -> Optional[float]:
        if None in {entry, stop_loss, take_profit}:
            return None
        if direction == "long":
            risk = entry - stop_loss
            reward = take_profit - entry
        else:
            risk = stop_loss - entry
            reward = entry - take_profit
        if risk <= 0:
            return None
        return reward / risk

    # ------------------------------------------------------------------
    # Indicator calculations
    # ------------------------------------------------------------------
    def _sma(self, values: List[float], period: int) -> Optional[float]:
        if len(values) < period or period <= 0:
            return None
        return sum(values[-period:]) / period

    def _ema(self, values: List[float], period: int) -> Optional[float]:
        if len(values) < period or period <= 0:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        for price in values[period:]:
            ema = (price - ema) * multiplier + ema
        return ema

    def _macd(self, values: List[float]) -> Optional[float]:
        fast = self._ema(values, 12)
        slow = self._ema(values, 26)
        if fast is None or slow is None:
            return None
        return fast - slow

    def _rsi(self, values: List[float], period: int = 14) -> Optional[float]:
        if len(values) <= period:
            return None
        gains: List[float] = []
        losses: List[float] = []
        for i in range(1, len(values)):
            diff = values[i] - values[i - 1]
            gains.append(max(diff, 0.0))
            losses.append(abs(min(diff, 0.0)))
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _atr(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> Optional[float]:
        if len(highs) <= period:
            return None
        trs: List[float] = []
        for i in range(1, len(highs)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i - 1]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        if len(trs) < period:
            return None
        return sum(trs[-period:]) / period

    def _adx(self, candles: List[Candle], period: int = 14) -> Optional[float]:
        if len(candles) <= period:
            return None
        plus_dm: List[float] = []
        minus_dm: List[float] = []
        trs: List[float] = []
        for i in range(1, len(candles)):
            current = candles[i]
            prev = candles[i - 1]
            up_move = current.high - prev.high
            down_move = prev.low - current.low
            plus_dm.append(max(up_move, 0.0) if up_move > down_move and up_move > 0 else 0.0)
            minus_dm.append(max(down_move, 0.0) if down_move > up_move and down_move > 0 else 0.0)
            tr = max(
                current.high - current.low,
                abs(current.high - prev.close),
                abs(current.low - prev.close),
            )
            trs.append(tr)
        if len(trs) < period:
            return None

        def smoothed(series: List[float]) -> List[float]:
            smooth: List[float] = []
            accumulator = sum(series[:period])
            smooth.append(accumulator)
            for value in series[period:]:
                accumulator = accumulator - (accumulator / period) + value
                smooth.append(accumulator)
            return smooth

        tr_smooth = smoothed(trs)
        plus_smooth = smoothed(plus_dm)
        minus_smooth = smoothed(minus_dm)
        if not tr_smooth or not plus_smooth or not minus_smooth:
            return None

        di_plus = [100 * ps / ts if ts else 0.0 for ps, ts in zip(plus_smooth, tr_smooth)]
        di_minus = [100 * ms / ts if ts else 0.0 for ms, ts in zip(minus_smooth, tr_smooth)]
        dx = [
            100 * abs(p - m) / (p + m)
            if (p + m) != 0
            else 0.0
            for p, m in zip(di_plus, di_minus)
        ]
        if len(dx) < period:
            return None
        return sum(dx[-period:]) / period

    def _stddev(self, values: List[float], period: int) -> Optional[float]:
        if len(values) < period:
            return None
        window = values[-period:]
        if all(v == window[0] for v in window):
            return 0.0
        return pstdev(window)

    def _last_swing_low(self, candles: List[Candle], lookback: int = 10) -> Optional[float]:
        if len(candles) < lookback:
            return None
        recent = candles[-lookback:]
        return min(c.low for c in recent)

    def _last_swing_high(self, candles: List[Candle], lookback: int = 10) -> Optional[float]:
        if len(candles) < lookback:
            return None
        recent = candles[-lookback:]
        return max(c.high for c in recent)


__all__ = ["MurphyStrategy", "Signal"]
