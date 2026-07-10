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
| Benchmarks | `backend/app/benchmark_store.py` | **Cached real closes** (yfinance + CSV) |

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
| Real market closes? | **Yes** when cache or live fetch succeeds |
| Source | `backend/app/benchmark_store.py` — CSV cache + optional yfinance |
| Tickers | SPX → `^GSPC`, NDX → `^NDX`, BTC → `BTC-USD` |
| Cache location | `data/benchmark_cache/` (`GSPC_daily.csv`, `NDX_daily.csv`, `BTC-USD_daily.csv`) |
| Stored in DB? | **No** — file cache only |
| Date alignment | Prior close within **5 calendar days** on weekends/holidays (`benchmark_align_policy`) |
| Program start rebase | Forward roll up to **14 calendar days** if first uploader date has no close |
| Missing data | `benchmark_data_source: "unavailable"` — no synthetic values in default path |

### `benchmark_data_source` values

| Value | Meaning |
| ----- | ------- |
| `market_cache_live_fetch` | yfinance refreshed cache this request |
| `market_cache_cached` | Served from existing CSV cache (no network or cache-only mode) |
| `unavailable` | Benchmarks requested but no real closes could be resolved |
| `deterministic_fixture` | **Tests only** (`BENCHMARK_ALLOW_FIXTURE=1`) — never production default |
| `null` | No benchmarks requested |

Frontend treats only `market_cache_live_fetch` and `market_cache_cached` as
real/live-eligible (plain SPX/NDX/BTC labels; SPX+NDX on by default).

Synthetic fixture or frontend mock benchmarks use **(sample)** / **Preview**
labels and stay hidden by default.

## Client-facing rules

1. Mock fallback → banner: **Preview chart — demo data only**
2. Backend strategy lines → banner: **From uploader entries**
3. Real/cached benchmarks → plain labels; SPX+NDX enabled by default
4. Synthetic benchmarks → legend suffix **(sample)**; hidden until user enables
5. Unavailable benchmarks → hide toggles; show unavailable notice
6. Never present fixture or generated benchmarks as live market performance

## Configuration

| Env var | Default | Purpose |
| ------- | ------- | ------- |
| `BENCHMARK_CACHE_DIR` | `data/benchmark_cache` | CSV cache directory |
| `BENCHMARK_CACHE_ONLY` | `0` | Skip yfinance; use cache files only |
| `BENCHMARK_ALLOW_FIXTURE` | `0` | Tests: allow deterministic fixture (not for prod) |
