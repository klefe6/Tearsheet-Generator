# TCP Calculation Replay Report (Step 6)

Validated: 2026-07-02  
Branch: `feature/tcp-v2-migration`  
Module: `tcp_calculations.py`

## Workbook Formula Topology

Audited all 112 completed rows in `tcp_alex.xlsx` sheet `NAV` via openpyxl formula inspection. Formulas below are normalized to relative references (`r` = current row, `r-1` = prior row).

### Constants and anchors

| Cell | Value | Use |
|------|-------|-----|
| U6 | 50,000 | Base NAV per tranche (`nav-x1` seed) |
| U10 | 0.20 | Performance fee rate (20%) |
| I$1 | 0.20 | Row 3 fee-rate alias (equivalent to U10) |
| L$3 | 50,000 | `%Net` anchor for rows 3–6 |
| A2 | 25,000 | Inception transfer for row 3 `$PL` |
| F2 | 25,000 | Inception NLV for row 3 `NLV` |
| E2 | 0 | Inception cash balance for row 3 `$PL` |

`BASELINE_AMOUNT = 150000` is **not** referenced anywhere in workbook formulas.

### Formula families by field

#### $PL (column H)

| Family | First row | Pattern |
|--------|-----------|---------|
| H-seed | 3 | `(E[r]-E[r-1]-R[r])-A2` — uses inception transfer **A2**, not current-row transfer |
| H-standard | 4+ | `(E[r]-E[r-1]-R[r])-A[r]` — when R is empty, reduces to `E[r]-E[r-1]-A[r]` |

Transfer timing: **current-row** `Cash Transfers` (column A) for rows 4+.

#### Inc. Fee (column I)

| Family | First row | Pattern |
|--------|-----------|---------|
| I-seed | 3 | `IF(H[r]>N[r-1], (H[r]-N[r-1])*I$1, 0)` |
| I-standard | 4+ | `IF(H[r]>N[r-1], (H[r]-N[r-1])*U$10, 0)` |

Fee applies to `$PL` above **prior-row Loss Carry** (column N), not prior HWM.

#### cumm fee (column J)

| Family | First row | Pattern |
|--------|-----------|---------|
| J-seed | 3 | `I[r]` |
| J-standard | 4+ | `I[r]+J[r-1]` |

#### Day PnL (column K)

| Family | First row | Pattern |
|--------|-----------|---------|
| K-seed | 3 | literal `0` |
| K-standard | 4+ | `H[r]-I[r]` |

Seed row forces Day PnL to zero even when `$PL` is non-zero.

#### NLV (column F)

| Family | All rows from 3 | Pattern |
|--------|-----------------|---------|
| F-standard | 3+ | `F[r-1]+H[r]+A[r]` |

Uses `$PL` and current-row transfer, not Day PnL.

#### nav-x1 (column L)

| Family | First row | Pattern |
|--------|-----------|---------|
| L-seed | 3 | `U6` (50,000) |
| L-standard | 4+ | `L[r-1]+(H[r]-I[r])/G[r]` |

Uses **unrounded** `H-I` divided by **current-row** tranche count (column G). Output precision: 3 decimal places.

#### Loss Carry (column N)

| Family | All rows from 3 | Pattern |
|--------|-----------------|---------|
| N-standard | 3+ | `MAX(0, Q[r-1]-L[r])` |

Uses **prior-row HWM** minus current NAV.

#### %Net (column O)

| Family | First row | Pattern |
|--------|-----------|---------|
| O-anchor-L3 | 3–6 | `(H[r]-I[r])/L$3` |
| O-anchor-L3G | 7+ | `(H[r]-I[r])/(L$3*G[r])` |

When G=1, families are numerically equivalent. When G=2 (from row 16), denominator doubles.

#### S net cummulative % (column P)

| Family | First row | Pattern |
|--------|-----------|---------|
| P-seed | 3–4 | `O[r]` |
| P-standard | 5+ | `O[r]+P[r-1]` |

Calculator rule: if prior `Trading Days` ≤ 1, `P = O`; else `P = O + P_prev`.

#### HWM (column Q)

| Family | First row | Pattern |
|--------|-----------|---------|
| Q-seed | 3 | `MAX(L$3:L[r])` |
| Q-standard | 4+ | `IF(AND(G[r]=G[r-1], L[r]>Q[r-1]), MAX(L$3:L[r]), Q[r-1]+(MAX(L$3:L[r])-Q[r-1])*(G[r]-G[r-1])/G[r-1])` |

`MAX(L$3:L[r])` is the running maximum of column L from row 3 through the current row. On tranche increase (row 16: G 1→2), HWM blends toward the running NAV peak.

### Manual vs calculated fields

| Field | Entry mode |
|-------|------------|
| Date | Manual |
| Cash Balance | Manual |
| Cash Transfers | Manual (deposit at row 16) |
| # (tranche count) | Manual |
| Trading Days | Manual / sequenced |
| All other audited fields | Formula-driven |

### Rounding behavior

Excel retains full binary-float precision through `H-I` for NAV accumulation. The calculator mirrors this by avoiding mid-chain currency quantization. Output boundaries:

- Currency display fields (`$PL`, fees, NLV, Loss Carry): compared at ±0.011
- `nav-x1`, `HWM`: quantized to 0.001 at output; compared at ±0.0005
- Percentages: compared at ±1e-7

## Seed policy

**Seed row:** Excel row 3 (first completed trading day, 2026-01-20).

Row 3 cannot be derived from a prior *completed* row. `build_seed_row()` uses `TCPInceptionContext` (row 2: E=0, F=25,000, A=25,000):

- `$PL = E3 - E2 - A2`
- `Inc. Fee = 0`
- `Day PnL = 0` (forced)
- `nav-x1 = U6 = 50,000`
- `NLV = F2 + H3 + A3`
- `%Net = (H3-I3)/L$3` using gross day `(H-I)`, not forced-zero Day PnL
- `Loss Carry = MAX(0, Q2-L3) = 0` (empty Q2 treated as 0)
- `HWM = MAX(L$3:L3) = 50,000`

**Replay start:** seed row 3, then rows 4–114 computed from prior **calculated** output.

## Calculator inputs

`TCPEntry` fields (manual only):

- `Date`
- `Cash Balance`
- `Cash Transfers` (≥ 0; negative raises `UnsupportedWithdrawal`)
- `#` tranche count (explicit; no auto-inference from deposit size)
- `Trading Days` (optional; defaults to prior + 1)

`TCPRules` constants:

- `performance_fee_rate = 0.20`
- `base_nav_per_tranche = 50000`

Internal chain field `_running_max_nav` supports HWM; stripped by `public_row()` before state persistence.

## Calculation order (rows 4+)

1. `$PL` from cash balance movement and transfers
2. `Inc. Fee` from `$PL` above prior Loss Carry
3. `gross_day = $PL - Inc. Fee` (full precision)
4. `Day PnL = gross_day`
5. `nav-x1 = prior_nav + gross_day / tranche_count` (quantize 0.001)
6. `NLV = prior_nlv + $PL + transfer`
7. `Loss Carry = MAX(0, prior_HWM - nav-x1)`
8. `%Net = gross_day / (base_nav * tranche_count)`
9. `S net cummulative %` per Trading Days rule
10. `HWM` from running NAV peak and tranche blend
11. `cumm fee = prior + Inc. Fee`

## Golden-row results

| Excel row | Date | Scenario | Result | Max field diff |
|----------:|------|----------|--------|---------------:|
| 3 | 2026-01-20 | First trading day | PASS | 0 |
| 4 | 2026-01-21 | Profit and fee | PASS | ~0 |
| 6 | 2026-01-23 | Small P&L rounding | PASS | ~0 |
| 7 | 2026-01-26 | Loss-carry initiation | PASS | ~0 |
| 8 | 2026-01-27 | HWM recovery | PASS | ~0 |
| 10 | 2026-01-29 | Under HWM with loss carry | PASS | ~0 |
| 16 | 2026-02-06 | Deposit, tranche 1→2 | PASS | ~0 |
| 17 | 2026-02-09 | First post-deposit row | PASS | ~0 |
| 114 | 2026-06-24 | Latest completed row | PASS | ~0 |

All golden rows match within field-specific tolerances.

## Full-ledger replay summary

```
completed_rows:              112
seed_rows:                   1
rows_attempted:              112
rows_matched:                112
rows_mismatched:             0
first_mismatch:              none
max_currency_difference:     2.91e-11 (nav-x1)
max_percentage_difference:   6.98e-17 (%Net)
final_calculated_nav:        44871.384
workbook_final_nav:          44871.384
final_nav_difference:        1.46e-11
final_hwm_difference:        0.0
final_loss_carry_difference: 1.18e-11
final_cumm_fee_difference:   2.70e-12
```

Formula-transition boundaries crossed during replay: row 3 seed, row 5 cumulative-%, row 7 %Net denominator (equivalent at G=1), row 16 tranche 1→2.

## Unsupported behavior

- **Withdrawals:** negative `Cash Transfers` raise `UnsupportedWithdrawal`. No historical withdrawal exists in the workbook; production editing must not enable withdrawals until a confirmed business rule exists.
- **Tranche inference:** deposit size does not auto-adjust `#`; tranche count is an explicit input.
- **BASELINE_AMOUNT 150000:** not used; guarded against in invariants.

## Production-readiness verdict

**Calculator layer: ready for wiring** — full historical replay matches the workbook with no unexplained drift. Website editing, JSON persistence, and preview calculator UI remain disabled per Step 6 scope.

## Workbook integrity (read-only audit)

| Metric | Value |
|--------|-------|
| Size (bytes) | 482,279 |
| SHA-256 | `1164a8cc10735ab3559fb322d681a15de72ffd94554b9d73dc01a25f03bd409c` |
| Modified during Step 6 | No |

Configured TCP active/backup/lock state files: not present (untouched).
