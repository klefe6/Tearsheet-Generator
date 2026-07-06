# Algominds v2 Fee Snapshot Contract

Pure helpers that bridge daily balance inputs into the Algominds v2 fee engine and
liability display semantics. No ingestion, workbook access, UI, or server binding.

Repository: `klefe6/Tearsheet-Generator`  
Module: `algominds_v2_snapshots.py`  
Related: `algominds_v2/fee_engine.py`, `algominds_v2/fee_ledger.py`, `algominds_v2_state.py`

---

## Purpose

Answer, for a point-in-time balance snapshot:

> Given today's account balance, fee removal/outstanding, HWM, SPX start/end, and
> benchmark base, what is the current estimated fee, after-fee NLV, HWM result, and
> displayed fee owed?

Future lanes will connect daily data sources and the preview app. This lane does
not implement ingestion or persistence beyond optional JSON helpers.

---

## Required raw inputs

| Field | Meaning |
| ----- | ------- |
| `as_of_date` | Snapshot date (ISO calendar date) |
| `account_balance` | Raw gross account balance |
| `fee_removal` | Crystallized fee payable / outstanding |
| `prior_high_water_mark` | Prior HWM for the period |
| `spx_start` | S&P price index at period start |
| `spx_end` | S&P price index at period end |
| `benchmark_base` | Per-account benchmark nominal base |
| `notes` | Optional operator notes |

---

## Fee basis

```text
fee_basis = account_balance - fee_removal
```

`fee_removal` represents crystallized-but-unpaid fees that remain inside broker-
reported gross balance and must be excluded before computing a new fee.

---

## Computation flow

1. Validate snapshot inputs (Decimal-only, non-negative balances, positive SPX/base).
2. Call `algominds_v2.fee_engine.crystallize_month()`.
3. Call `algominds_v2.fee_ledger.calculate_liability()` for display fields.

---

## Output fields

| Field | Source |
| ----- | ------ |
| `current_estimated_fee` | Fee engine `current_period_fee` |
| `after_fee_nlv` | Fee engine `after_fee_nlv` |
| `next_high_water_mark` | Fee engine HWM ratchet |
| `benchmark_dollar_return` | Fee engine BDR |
| `eligible_profit` | Fee engine eligible profit |
| `fee_basis` | Fee engine fee basis |
| `displayed_fee_owed` | Ledger total owed (positive) |
| `signed_fee_liability` | Ledger signed liability (non-positive) |
| `nlv` | Ledger NLV (must match `after_fee_nlv`) |

---

## JSON helpers

`snapshot_to_dict()` / `snapshot_from_dict()` / `snapshot_to_json()` serialize
Decimal values as strings. These helpers perform no file I/O.

---

## Side-effect prohibitions

This module must not:

- create state or `.env` files at import time;
- read workbooks;
- start or bind a server;
- import Dash, Flask, TKP, TCP, Momentum Pacer, pandas, or openpyxl.

---

## Relationship to other modules

| Module | Role |
| ------ | ---- |
| `algominds_v2_config.py` | Port/path constants (unchanged here) |
| `algominds_v2_state.py` | JSON preview-state persistence (unchanged here) |
| `algominds_v2/fee_engine.py` | Pure fee math oracle |
| `algominds_v2/fee_ledger.py` | Liability display semantics |

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Initial fee snapshot foundation on `feature/algominds-v2-snapshots` |
