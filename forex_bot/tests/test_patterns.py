from forex.ta.patterns import detect_patterns


def test_detect_bullish_engulfing() -> None:
    bars = [
        {"open": 1.1000, "high": 1.1050, "low": 1.0950, "close": 1.0970},
        {"open": 1.0960, "high": 1.1100, "low": 1.0940, "close": 1.1080},
    ]
    matches = detect_patterns(bars, ["engulfing"])
    assert matches
    assert matches[-1].direction == "bull"


def test_detect_bearish_shooting_star() -> None:
    bars = [
        {"open": 1.1000, "high": 1.1400, "low": 1.0950, "close": 1.1010},
    ]
    matches = detect_patterns(bars, ["shooting_star"])
    assert matches
    assert matches[-1].direction == "bear"

