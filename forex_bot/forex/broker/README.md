# Broker Interfaces (`forex/broker`)

Broker modules translate strategy intentions into exchange-specific API calls or
simulate fills locally.  The API layer depends on these adapters via the
`Broker` abstract base class defined in `base.py`.

| File | Purpose |
| --- | --- |
| `__init__.py` | Re-exports broker implementations for convenience. |
| `base.py` | Declares the asynchronous `Broker` ABC and `BrokerFactory` protocol used throughout the backend. |
| `oanda.py` | Implements the OANDA v20 practice API (REST + streaming) with retry logic and request validation. |
| `paper_sim.py` | Provides a deterministic in-memory simulator for tests and offline development. |

## Usage Notes

- `api.create_broker()` instantiates either `OandaBroker` or `PaperSimBroker`
  depending on configuration and authentication success.
- `OandaBroker` enforces that practice credentials are configured via
  environment variables; missing values raise `OandaError`.
- The simulator mirrors the interface but generates synthetic prices and trade
  fills without any external dependencies.

When adding a new broker, subclass `Broker`, implement all abstract methods, and
update the selection logic in `api.create_broker()`.
