# React Dashboard (`frontend/`)

The frontend directory contains a Vite + React + TypeScript dashboard that
interfaces with the FastAPI backend.  It handles authentication, surfaces
account state, launches backtests/live runs, and renders telemetry.

## Project Structure

| Path | Purpose |
| --- | --- |
| `index.html` | Vite entry template. |
| `src/main.tsx` | Bootstraps the React application and mounts `<App />`. |
| `src/App.tsx` | Top-level dashboard component containing forms, charts, and data fetching logic. |
| `src/components/` | Reusable UI primitives (see sub-README). |
| `src/hooks/` | Custom hooks for REST requests and server-sent events. |
| `src/lib/` | Low-level API helpers, SSE utilities, and formatting helpers. |
| `index.css`, `tailwind.config.ts`, `postcss.config.js` | Styling pipeline and theme customisation. |
| `vite.config.ts`, `tsconfig*.json` | Tooling configuration for Vite/TypeScript. |

## Data Fetching Flow

1. `src/lib/api.ts` creates a thin wrapper around `fetch`, injecting the dashboard
   token as a Bearer header.
2. `useApi` hook performs GET requests, manages loading/error state, and exposes
   a `refetch` callback.
3. `useEventStream` opens EventSource connections to `/api/stream/*` endpoints,
   allowing components to react to log, price, and metrics events.
4. `App.tsx` composes these hooks to populate dashboard panels (account summary,
   open positions, orders, price charts, run history, and metrics).

## Styling & Components

- Tailwind CSS powers utility classes.  `index.css` initialises base styles and
  imports Tailwind layers.
- `src/components/ui` contains minimal wrappers over standard HTML inputs and
  buttons that enforce consistent theming.
- Recharts renders line charts for equity curves inside `App.tsx`.

## Development Tips

- Run `npm install` then `npm run dev` to start the Vite server at
  `http://localhost:5173`.
- Use `.env` or `.env.local` to override `VITE_API_BASE` and `VITE_DASH_TOKEN`.
- The backend must be reachable and present the matching token for authenticated
  requests.

Additional READMEs exist inside `src/`, `src/components/`, `src/hooks/`, and
`src/lib/` to document individual files.
