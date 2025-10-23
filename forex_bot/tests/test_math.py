from forex.utils.math import pip_size, pip_value, units_for_risk


def test_pip_size():
    assert pip_size("EUR_USD") == 0.0001
    assert pip_size("USD_JPY") == 0.01


def test_pip_value():
    assert pip_value("EUR_USD", 10000) == 1.0


def test_units_for_risk():
    units = units_for_risk(equity=10000, risk_pct=1, stop_distance_pips=20, instrument="EUR_USD")
    assert units > 0
    assert isinstance(units, int)
