# Glenn Daily Uploader — Frontend

Frontend-only scaffold for the **Glenn Daily Uploader**: a clean fintech dashboard
for entering daily NLVs, cash transfers, and fees for the four products
(**TKP**, **TCP**, **AGM**, **Y&Q**), with a normalized performance chart on top.

> **Scope of this package.** This is UI only. It does **not** import from, modify,
> or talk to the existing TKP/TCP/AGM/Y&Q tearsheet apps or any production data.
> All data here is mock. "Export All Changes" is a non-destructive mock action —
> no backend call is made yet.

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
| `npm run dev` | Dev server, sandbox env (hot reload) |
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
| `VITE_API_BASE_URL` | `http://localhost:8090/api` | *(placeholder — set the real URL later)* |

- `VITE_APP_ENV` drives only the on-screen environment badge for now.
- `VITE_API_BASE_URL` is reserved for the future export wiring; it is **not called** yet.

To override locally without editing the committed files, create `.env.local`
(git-ignored). See `.env.example` for the contract.

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

## Behavior (this PR)

- **Enter** — appends a row to that product's local state and clears the numeric inputs.
- **Delete Last Row** — removes the most recent local row for that product.
- **Export All Changes** — shows a mock toast; sends nothing.

State lives in `App.tsx` (`rowsByProduct`), keyed by product, so the export step
already has everything it needs when a real backend endpoint is wired in later.

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
