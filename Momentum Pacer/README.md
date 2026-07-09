# Momentum Pacer (AGM) — Tearsheet

**CTA:** Algominds Financial LLC
**Program:** Momentum Pacer
**App file:** `mp_ts.py`
**Port:** 8304 (host `127.0.0.1`; override with `AGM_BIND_PORT`)

> This README was rewritten 2026-07-09 to match the actual app. The previous version
> described an older `calc_engine.py`/CSV template design (port 8079) that is no
> longer how this app works. `calc_engine.py` is currently **unused** by the app.
> See `../docs/REPO_MAP.md` for the repo-wide map.

---

## How to run

Production launch (from the repo root):

```bat
reboot_mp_ts.bat
```

That launcher `cd`s into `Momentum Pacer/`, sets `MP_TS_PRODUCTION=1` (disables Dash
debug/reloader — required behind the reverse proxy), and runs `python mp_ts.py` with
the `python` on PATH (no venv activation). Then open:

```
http://127.0.0.1:8304
```

For local development, run `python mp_ts.py` from inside `Momentum Pacer/` (debug
mode on by default when `MP_TS_PRODUCTION` is unset).

Note: the production process has historically run **elevated**; restarting it
requires an elevated session.

## Data sources (what the app actually reads)

| Source | Location | Notes |
|---|---|---|
| Daily balances (source of truth) | `data/daily_balances/balances_*.csv` | TradeStation export; the active filename is pinned by `DAILY_BALANCES_FILENAME` in `../algominds_daily_balances.py` and must be bumped when a new export is dropped. Force-tracked in git |
| Benchmark cache (^GSPC / ^NDX) | `data/benchmarks/*.csv` | Cache-first via `../algominds_benchmark_daily.py` (yfinance refresh; `AGM_BENCHMARK_CACHE_ONLY=1` forces offline). Force-tracked |
| Fee workbook | `Momentum Fee Calculation.xlsx` (this folder) | **Gitignored, machine-local.** Fee engine's payment-reconciliation reference. If missing, the app runs but crystallized-fee figures are silently wrong — copy it into any fresh worktree before running AGM fee tests |
| Admin manual rows | `momentum_pacer_manual_daily_rows.json` (this folder) | Gitignored runtime state written by the admin Add Row controls. No file locking — single writer only |

## Architecture notes

- `mp_ts.py` bootstraps imports of repo-root modules (`tearsheet_*`, `tcp_admin`,
  `algominds_*`) by inserting the repo root onto `sys.path` at startup — do not move
  this folder or the root modules without reading `../docs/REPO_MAP.md` §7 first.
- The app passes an explicit `assets_folder` pointing at the repo root's `assets/`
  directory (this folder has no assets dir of its own); without it the gate CSS 404s.
- Fee logic lives in `../algominds_daily_fees.py` (daily slab/HWM accrual) with
  hand-confirmed payment evidence in `../algominds_fee_payment_evidence.py`. Derived
  monthly display comes from `../algominds_monthly_summary.py` and
  `../algominds_monthly_stats.py`. `/monthly` deliberately returns 404.
- Tests: `../tests/test_agm_*.py`, run from the repo root, e.g.
  `..\.venv310\Scripts\python.exe -m pytest tests/test_agm_password_gate.py -q`.
