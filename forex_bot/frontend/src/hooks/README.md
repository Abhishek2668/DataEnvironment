# Custom Hooks (`frontend/src/hooks`)

Hooks encapsulate reusable stateful logic for interacting with the backend.

| File | Purpose |
| --- | --- |
| `useApi.ts` | Fetch helper for GET endpoints.  Manages loading/error state and exposes a `refetch` callback. |
| `useEventStream.ts` | Wraps `EventSource` to subscribe to server-sent events with automatic cleanup and reconnection handling. |

Compose these hooks inside components to keep networking concerns isolated from
UI rendering.
