# TCP Dynamic Dashboard Scope (Step 7)

Validated: 2026-07-02  
Branch: `feature/tcp-v2-migration`  
Module: `tcp_dashboard.py` + `tcp_ts_v2.py`

## Dynamic versus static classification

| Output | Initial v2 classification | Reason | Source |
| ------ | ------------------------- | ------ | ------ |
| Monthly performance | **Dynamic** | Rebuilt from canonical NAV each propagation | `recompute_tcp_monthly_performance()` |
| Daily metrics | **Dynamic** | Rebuilt from canonical NAV daily returns | `recompute_tcp_daily_metrics()` |
| NAV chart | **Dynamic** | Plotly figure from canonical NAV series | `build_tcp_nav_figure()` |
| Current-data labels | **Dynamic** | Latest completed ledger date | `build_tcp_current_data_labels()` |
| Drawdown table | Static / future | Not in Step 7 scope; v1 startup-only | `tcp_ts.py` `drawdown_profile()` |
| Drawdown chart | Static / future | Not in Step 7 scope | `tcp_ts.py` `build_drawdown_figure()` |
| Benchmark comparison | Static / external | External yfinance downloads in v1 | `tcp_ts.py` benchmark section |
| Account statistics | Static copy | Product configuration cards | `tcp_ts.py` layout |
| Disclosures | Static copy | Shared disclosure module / static text | `tcp_ts.py` footer |

Step 7 live scope matches the proven TKP propagation subset (monthly, daily metrics, NAV chart, date labels) — not every tearsheet statistic.

## Dynamic output contract

### Canonical record shape

```json
{"Date": "2026-06-24", "NAV": 44871.384}
```

- Derived from completed ledger rows (`nav-x1` required).
- Chronological, unique dates, finite NAV.
- Date-only candidate rows excluded.

### Percentage representation

| Layer | Representation |
| ----- | -------------- |
| Internal daily returns | **Decimal** (`0.01` = 1%) |
| Monthly table cells | **Percentage points** (`4.5800%`) |
| Display strings | Formatted at presentation boundary (`×100` for daily metrics) |

### Monthly-return formula

```text
baseline = first completed NAV
month_last = last NAV in calendar month
month_first = last NAV before month start (or baseline for first month)
monthly_return_pct_points = (month_last - month_first) / baseline * 100
year_total = sum of monthly percentage points in year
```

No `override_months` (2025-04 / 2025-10). No `BASELINE_AMOUNT = 150000`.

### Daily-return formula

```text
baseline = first completed NAV
daily_return_decimal = (NAV_t - NAV_{t-1}) / baseline
```

First completed row is seed only — excluded via `diff().dropna()`.

### Seed-row treatment

- First ledger row establishes baseline NAV.
- No return computed for seed day.
- Day PnL / fee ledger fields are **not** used in dashboard math.

### Sharpe / annualization / win rate

| Item | Policy |
| ---- | ------ |
| Sharpe ratio | **Not computed** (matches TCP v1 public metrics) |
| Risk-free rate | None |
| Annualization | `cumulative_decimal * 365 / calendar_span_days` |
| Win rate | `returns > 0` |
| Loss rate | `returns < 0` |
| Zero-return days | Neither win nor loss |

### Chart point policy

- One point per completed ledger row (112 points).
- No `asfreq` business-day forward fill.
- No benchmark trace.
- No percentage NAV axis (deferred product decision).
- Latest point: **2026-06-24**, NAV **44871.384**.

### Current-label wording

- Header: `Data current to`
- Date line: `{Month Day, Year} close` (e.g. `June 24, 2026 close`)
- Desktop and mobile share the same source date.

## Parity: TCP v1 vs TCP v2 dynamic

| Output | TCP v1 (production) | TCP v2 dynamic | Difference | Classification |
| ------ | ------------------: | -------------: | ---------- | -------------- |
| Monthly performance | First-NAV baseline, with 2025 overrides | First-NAV baseline, no overrides | Overrides inert for Jan 2026 inception data | **Legacy override removal** (no effect on current ledger) |
| Daily metrics trading days | Business-day `asfreq` + `ffill` index | Actual completed trading rows only | Fewer zero-return filler days in v2 | **Seed-row / index treatment correction** |
| Daily metrics formulas | Same `diff/baseline`, 365-day annualization | Identical formulas on sparse series | Counts/percentages may differ slightly from filler days | **Documented methodology difference** |
| Latest NAV | 44871.384 | 44871.384 | None | Match |
| Latest date | 2026-06-24 | 2026-06-24 | None | Match |
| Chart point count | ~business-day filled | 112 completed rows | v2 uses sparse ledger dates | **Documented methodology difference** |
| Baseline | First NAV (50000) | First NAV (50000) | None | Match |
| $150,000 baseline | Defined but unused in TCP v1 | Not referenced | None | Match |

No unexplained financial differences on latest NAV/date. Remaining v1 differences are documented index-methodology choices, not calculation bugs.

## Full replay / parity validation

```
Completed rows:     112
Latest date:        2026-06-24
Latest NAV:         44871.384
Canonical points:   112
Monthly table:      renders 2026 months
Daily metrics:      inception + TTM columns populated
```

## Unsupported / deferred

- Website editing (Add/Delete row)
- Active JSON state
- Percentage NAV axis
- Drawdown dynamic rebuild
- Benchmark dynamic rebuild
- Negative transfer editing

## Production-readiness verdict

**Dashboard propagation layer: ready for read-only preview.** Editing, JSON persistence, and admin shell remain disabled per master plan.
