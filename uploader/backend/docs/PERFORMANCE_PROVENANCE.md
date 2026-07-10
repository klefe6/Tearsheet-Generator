# Performance chart — data provenance

This document answers where the top **Performance of $100,000 Investment**
chart gets its data. It is the contract for `/api/performance` and the
frontend `PerformanceChart` component.

## Data flow

```
PerformanceChart.tsx
  └─ fetchPerformance()  →  GET /api/performance
       ├─ success  → transformCombinedResponse / transformProgramResponse
       └─ failure  → buildCombinedTradingDaySeries / buildProgramBenchmarkSeries
                     (frontend/src/data/performance.ts — deterministic mock)
```

| Layer | File | Role |
| ----- | ---- | ---- |
| UI | `frontend/src/components/PerformanceChart.tsx` | Renders chart; prefers backend, falls back to mock |
| API client | `frontend/src/api/client.ts` | `fetchPerformance()` |
| Mock | `frontend/src/data/performance.ts` | Seeded random-walk demo series |
| API route | `backend/app/main.py` | `GET /api/performance` |
| Builder | `backend/app/performance.py` | Computes series from SQLite `daily_rows` |
| Benchmarks | `backend/app/benchmarks.py` | **Deterministic fixture** — not real market data |

## TKP / TCP / AGM / Y&Q (strategy lines)

When the backend is reachable (`program_data_source: "uploader_daily_rows"`):

| Question | Answer |
| -------- | ------ |
| Derived from uploader `daily_rows`? | **Yes** — `db.get_all_rows(program)` |
| Normalized from entered NLV? | **Yes** — `program_nlv()` per program, compounded to $100k base |
| Only uploader-entered rows? | **Yes** — no historical backfill |
| Reads live tearsheet apps? | **No** — never imports tkp_ts / tcp_ts_v2 / mp_ts |
| History before first uploader row? | **No** — series starts at first stored row |
| Missing dates | Only dates Glenn entered; no gap-filling |
| AGM `fee` | **Excluded** from performance (documented placeholder) |
| Cash transfers | Neutralized in return calculation |

When the backend is unreachable, strategy lines are **deterministic mock**
random walks from `performance.ts` — labeled **Preview** in the UI.

## SPX / NDX / BTC (benchmark lines)

Only shown in **individual program** mode (not combined).

| Question | Answer |
| -------- | ------ |
| Real market closes? | **No** |
| Source | `backend/app/benchmarks.py` — formula `drift * days + sin(...)` keyed by date |
| Stored in DB? | **No** |
| External API? | **No** |
| Date range | Any weekday; weekends return `None` (roll-forward up to 14 days) |
| Missing data | Warning in response; point omitted or series skipped |

API field: `benchmark_data_source: "deterministic_fixture"` when benchmarks
are included. Frontend labels these **(sample)** and hides them by default.

Frontend mock benchmarks use the same seeded random-walk as mock products.

## Client-facing rules

1. Mock fallback → banner: **Preview chart — demo data only**
2. Backend strategy lines → banner: **From uploader entries**
3. Synthetic benchmarks → legend suffix **(sample)**; hidden until user enables
4. Never present fixture benchmarks as live market performance

## Replacing benchmarks with real data (future)

Swap `_raw_value` in `benchmarks.py` for a cached ingestion lookup (e.g.
yfinance behind a file cache, as other tearsheet apps do). Bump
`benchmark_data_source` to `"market_cache"` and update frontend to treat that
as live-eligible.
