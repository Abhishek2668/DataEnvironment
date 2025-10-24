from forex.ta.indicators import ATRState, MACDState, RSIState


def test_rsi_state_progression() -> None:
    rsi = RSIState(period=3)
    values = [1.0, 1.2, 1.1, 1.3, 1.4]
    output = [rsi.update(v) for v in values]
    assert output[-1] is not None
    assert 0 <= output[-1] <= 100


def test_macd_crossing() -> None:
    macd = MACDState(3, 6, 4)
    values = [1.0, 1.1, 1.3, 1.4, 1.6]
    line, signal, hist = 0.0, 0.0, 0.0
    for value in values:
        line, signal, hist = macd.update(value)
    assert line > signal
    assert hist > 0


def test_atr_state_updates() -> None:
    atr = ATRState(period=3)
    inputs = [
        (1.2, 1.0, 1.1),
        (1.25, 1.05, 1.2),
        (1.3, 1.1, 1.25),
    ]
    value = None
    for high, low, close in inputs:
        value = atr.update(high, low, close)
    assert value is not None
    assert value > 0

