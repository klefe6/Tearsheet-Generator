# data\agm — AGM Persistent Files

Expected files:

- `momentum_pacer_manual_daily_rows.json` — read/write, **backup required**
- `Momentum Fee Calculation.xlsx` — read-only, **backup required**
- `data\daily_balances\balances_*.csv` — pinned history, **backup required**
- `data\benchmarks\` — regenerable cache

Env keys: `HC_AGM_MANUAL_STATE_PATH`, `HC_AGM_FEE_WORKBOOK`, `HC_AGM_PINNED_CSV`
