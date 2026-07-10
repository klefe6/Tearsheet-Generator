# Glenn Daily Uploader — Frontend

Frontend-only scaffold for the **Glenn Daily Uploader**: a clean fintech dashboard
for entering daily NLVs, cash transfers, and fees for the four products
(**TKP**, **TCP**, **AGM**, **Y&Q**), with a normalized performance chart on top.

> **Scope of this package.** UI for the Glenn Daily Uploader. When
> `VITE_API_BASE_URL` points at a running backend, Enter / Delete / Export and
> the performance chart use real API endpoints. If the backend is unreachable,
> the UI falls back to local mock data so preview still works.

## Stack

- [Vite](https://vitejs.dev/) + [React](https://react.dev/) + TypeScript
- [Recharts](https://recharts.org/) for the performance chart
- Plain CSS + CSS Modules (no UI framework)

Dependencies are intentionally minimal.

## Run it locally

From this directory (`uploader/frontend`):

```bash
npm install
npm run dev
```

Vite prints a local URL (default <http://localhost:5173>). Open it in a browser.
`npm run dev` uses the **sandbox** environment.

Other scripts:

| Command | What it does |
|---|---|
| `npm run dev` | Dev server on **5173** (sandbox env, strict port) |
| `npm run dev:local` | Same as `dev` — use with `.env.local` for local API |
| `npm run smoke:check` | Verify backend :8091 (and frontend if running) |
| `npm run dev:prod` | Dev server, production env |
| `npm run build` | Type-check + production build to `dist/` |
| `npm run build:sandbox` | Type-check + sandbox build |
| `npm run preview` | Serve the last production build |
| `npm run typecheck` | `tsc --noEmit` only |

> Vite's dev server runs on **5173**, well clear of the protected tearsheet ports
> (8301/8302/8303/8304 and the 83xx preview block). Nothing here starts, stops, or
> touches those services.

## Environment config

Vite loads `.env.<mode>` automatically. Two committed templates ship with the repo
(no secrets — just wiring):

| Var | Sandbox | Production |
|---|---|---|
| `VITE_APP_ENV` | `sandbox` | `production` |
| `VITE_API_BASE_URL` | `https://uploader-sandbox.hcresearch.ltd/api` | `https://uploader.hcresearch.ltd/api` |

> This is a **Vite** app — use `VITE_*` variables only. There is no
> `INTERNAL_API_ORIGIN` or `NEXT_PUBLIC_*` wiring in this codebase.

**Future public URLs**

| Environment | Frontend | Backend API |
|---|---|---|
| Sandbox | `https://uploader-sandbox.hcresearch.ltd` | `https://uploader-sandbox.hcresearch.ltd/api` |
| Production | `https://uploader.hcresearch.ltd` | `https://uploader.hcresearch.ltd/api` |

**Local dev** (override via `.env.local`, git-ignored):

| Service | URL |
|---|---|
| Frontend (Vite) | `http://127.0.0.1:5173` |
| Backend API | `http://127.0.0.1:8091/api` |

Copy `.env.local.example` → `.env.local`:

```
VITE_API_BASE_URL=http://127.0.0.1:8091/api
```

- `VITE_APP_ENV` drives the on-screen environment badge.
- `VITE_API_BASE_URL` is the **only** backend URL the frontend calls (via `src/api/client.ts`).

See `.env.example` for the full contract.

## What's on the page

1. **Page header** — title *Glenn Daily Uploader* + subtitle. No sidebar, no
   top-right profile/admin area.
2. **Performance chart card** (full width) — *Performance of $100,000 Investment*,
   seven series (TKP, TCP, AGM, Y&Q, SPX, NDX, BTC), a date-range pill (1M / 3M /
   6M / 1Y), a clickable legend, and a hover tooltip. Every series is re-normalized
   to $100,000 at the start of the selected range.
3. **Four product cards** in one row — each with a colored header + icon, a compact
   entry form (fields per the rules below), **Enter** / **Delete Last Row** buttons,
   and a *last 7 rows* table.
4. **Export All Changes** — a full-width button that raises a mock confirmation toast.

### Field rules (per product)

| Product | Form fields | Table columns |
|---|---|---|
| **TKP** | Date · StoneX NLV · Plus500 NLV · Cash Transfer | Date · StoneX NLV · Plus500 NLV · Cash |
| **TCP** | Date · StoneX NLV · Cash Transfer | Date · StoneX NLV · Cash |
| **AGM** | Date · TradeStation NLV · Cash Transfer · Fee | Date · TradeStation NLV · Cash · Fee |
| **Y&Q** | Date · StoneX NLV · Cash Transfer | Date · StoneX NLV · Cash |

TKP is the only card with **both** StoneX NLV and Plus500 NLV; AGM is the only card
with a **Fee**.

## Behavior

- **Enter** — `POST /api/rows/{program}`; falls back to local append if backend unreachable.
- **Delete Last Row** — `DELETE /api/rows/{program}/last`; falls back to local trim on network failure.
- **Export All Changes** — `POST /api/export/all` (dry-run preview by default; does **not** push to live TKP/TCP/AGM/Y&Q sites).
- **Undo Last Merge** — mock only (no backend endpoint).

See `backend/docs/LOCAL_DEV.md` for ports, DB reset, and export details.

## Structure

```
src/
  App.tsx                 page shell + shared row state + export/toast
  types.ts                shared types
  config/products.ts      the four product definitions (fields, columns, colors)
  data/performance.ts     deterministic mock chart series + range normalization
  data/rows.ts            mock seed rows per product
  lib/format.ts           currency / date formatters
  components/
    PageHeader.tsx
    PerformanceChart.tsx  Recharts multi-line chart, range pill, legend, tooltip
    ProductCard.tsx       one config-driven card (form + buttons + table)
    Toast.tsx
  styles/global.css       CSS variables + base styles
```

## Color system

| Product | Color |
|---|---|
| TKP | Blue `#2a78d6` |
| TCP | Green `#12a150` |
| AGM | Purple `#7c3aed` |
| Y&Q | Orange / gold `#e0a000` |

Chart benchmarks: SPX / NDX are muted **dashed** reference lines; BTC is the
prominent, most-volatile line (`#e8543a`). The product + BTC hues were validated
colorblind-safe against a white surface.
