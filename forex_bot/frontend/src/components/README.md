# UI Components (`frontend/src/components`)

The components directory houses reusable building blocks used throughout the
dashboard.  Components are intentionally small so they can be composed inside
`App.tsx` or future feature modules.

| Path | Purpose |
| --- | --- |
| `ui/button.tsx` | Tailwind-styled `<button>` wrapper supporting variants and disabled states. |
| `ui/card.tsx` | Layout primitives for card containers (`Card`, `CardHeader`, `CardContent`, etc.). |
| `ui/input.tsx` | Standardised text/number input with consistent styling. |
| `ui/select.tsx` | Native `<select>` wrapper with label + helper styling. |

Add new UI primitives under `ui/` and export them through an index module if you
need to share them broadly.
