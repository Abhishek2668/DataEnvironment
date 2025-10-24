# Frontend Library Helpers (`frontend/src/lib`)

Small utilities that support the React application.

| File | Purpose |
| --- | --- |
| `api.ts` | Wrapper around `fetch` that injects the dashboard auth token and parses JSON responses. |
| `sse.ts` | Helper for creating `EventSource` instances with automatic token headers. |
| `utils.ts` | Convenience helpers (e.g. formatting timestamps) consumed by components. |

These helpers are deliberately framework-agnostic so they can be reused by tests
or future feature modules.
