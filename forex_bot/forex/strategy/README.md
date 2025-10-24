# Strategy Engine (`forex/strategy`)

Strategies encapsulate trading logic and adhere to the protocol defined in
`base.py`.  They transform price observations into directional signals consumed
by the execution layer.

| File | Purpose |
| --- | --- |
| `__init__.py` | Re-exports key strategy types. |
| `base.py` | Declares `StrategyContext`, `Strategy` protocol, and `Signal` container. |
| `registry.py` | Maintains a registry of available strategies, exposes `list_strategies()` for the API, and `create_strategy()` for runtime instantiation. |
| `rsi_mean_revert.py` | Implements an RSI-based mean-reversion strategy with ATR-aware signalling. |
| `sma_crossover.py` | Implements a moving-average crossover strategy with spread filtering. |

## Strategy Lifecycle

1. `Strategy.on_startup(context)` receives metadata (instrument, granularity,
   risk, max positions).
2. `Strategy.on_price_tick(price)` updates state on every incoming tick.
3. `Strategy.on_bar_close(price)` is invoked per completed bar and may set the
   latest `Signal`.
4. `get_signal()` (optional) exposes the most recent actionable signal.  The
   executor clears or replaces signals as orders are filled.
5. `Strategy.on_stop()` is called when a run ends.

When authoring new strategies, add a config dataclass, register the factory in
`registry.py`, and ensure tests cover edge cases.
