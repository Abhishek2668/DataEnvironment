# Execution Layer (`forex/execution`)

Execution bridges strategy output and broker order placement while enforcing
risk management rules.

| File | Purpose |
| --- | --- |
| `__init__.py` | Re-exports execution helpers. |
| `executor.py` | Coordinates strategy signals, applies risk sizing, dispatches orders, and publishes events. |
| `risk.py` | Calculates position sizes from risk parameters using utility math helpers. |

## How It Works

1. The realtime runner feeds price ticks into `Executor.run_bar()`.
2. Strategies update internal state via `Strategy.on_bar_close()` and may expose
   a `get_signal()` method returning a `Signal`.
3. `Executor.handle_signal()` requests account equity from the broker,
   calculates position size with `RiskParameters` + `position_size()`, and submits
   an `OrderRequest`.
4. Optional event bus integration emits telemetry for the UI/logging.

This separation keeps risk logic testable and brokers swappable.
