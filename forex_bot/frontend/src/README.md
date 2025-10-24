# React Source (`frontend/src`)

This directory contains the TypeScript source for the dashboard.  The following
map describes each file.

| File/Folder | Purpose |
| --- | --- |
| `App.tsx` | Core dashboard component orchestrating forms, charts, and API calls. |
| `main.tsx` | Vite entry point that renders `<App />` into the DOM. |
| `index.css` | Tailwind base styles and custom CSS variables. |
| `components/` | UI building blocks (buttons, cards, inputs, selects). |
| `hooks/` | Custom hooks for REST and event-stream interactions. |
| `lib/` | Low-level helpers for API requests, SSE wiring, and formatting. |

See the subdirectory READMEs for details about the components, hooks, and
library helpers.
