# Utility Helpers (`forex/utils`)

Utility modules provide shared primitives leveraged across strategies, brokers,
execution, and tests.

| File | Purpose |
| --- | --- |
| `__init__.py` | Convenience exports. |
| `math.py` | Numerical helpers: pip sizing, position sizing, ATR, and equity metrics. |
| `time.py` | Timezone helpers built on `pendulum`, including `utc_now()` and conversions. |
| `types.py` | Dataclasses and typing primitives for prices, orders, trades, and streams. |

These helpers centralise domain-specific calculations so strategies and services
remain focused on orchestration logic.
