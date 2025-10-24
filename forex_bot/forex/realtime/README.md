# Realtime Orchestration (`forex/realtime`)

Realtime modules wire together streaming prices, strategy execution, and event
broadcasting so the UI can observe live runs.

| File | Purpose |
| --- | --- |
| `__init__.py` | Convenience exports. |
| `bus.py` | Asyncio-based publish/subscribe message bus for logs, prices, and events. |
| `live.py` | `LiveRunner` manages lifecycle of live paper-trading sessions, wiring broker streams into strategies and executors. |

## Lifecycle Overview

1. `LiveRunner.start()` validates no session is active, builds a strategy via the
   registry, initialises an `Executor`, and records metadata in `RunStore`.
2. An asyncio task streams broker prices, publishes them on the event bus, and
   feeds both `strategy.on_price_tick()` and `Executor.run_bar()`.
3. On cancellation or error, the runner records completion status, emits log
   events, and tears down resources.
4. Clients subscribe to `EventBus` topics via FastAPI endpoints to receive
   server-sent events.

This design keeps realtime coordination isolated so additional transports (e.g.
WebSockets) can reuse the event bus abstraction.
