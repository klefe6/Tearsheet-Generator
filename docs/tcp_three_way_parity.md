# TCP Three-Way Parity Acceptance (Step 10)

Validated: 2026-07-02  
Branch: `feature/tcp-v2-migration`

## Baselines compared

| Source | Identity | Checksum (SHA-256 prefix) |
| ------ | -------- | ------------------------- |
| Excel workbook | `tcp_alex.xlsx` / `NAV` | `1164a8cc…` |
| TCP v1 | `git HEAD:tcp_ts.py` (`6b0e6d06…` working tree differs) | Committed HEAD used for acceptance |
| TCP v2 JSON | Preview active state revision 1 | `489841bb…` |

Deployed production TCP v1 was **not** positively identified. Acceptance compares committed **HEAD** `tcp_ts.py` via isolated subprocess (no server start, benchmarks mocked).

## Row-level parity

| Metric | Result |
| ------ | ------ |
| Rows compared | 112 |
| Rows matched | 112 |
| Mismatches | 0 |
| First mismatch | none |
| Latest date | `2026-06-24` (all sources) |
| Latest NAV | `44871.384` |

All required ledger fields match between Excel adapter output and JSON state records within tolerance (`1e-3` currency, `1e-6` percent).

## Dashboard parity summary

| Output | Excel/accepted | TCP v1 (HEAD) | TCP v2 | Classification | User-visible impact |
| ------ | -------------: | ------------: | -----: | -------------- | ------------------- |
| Latest date | 2026-06-24 | 2026-06-24 | 2026-06-24 | MATCH | Labels agree |
| Latest NAV | 44871.384 | 44871.384 | 44871.384 | MATCH | Chart endpoint agrees |
| Monthly table | Workbook-derived sparse | 2025 overrides present | No overrides | INTENTIONAL_V2_CORRECTION | v2 matches workbook; v1 had inert 2025-04/2025-10 overrides |
| NAV chart points | 112 sparse | 109 (asfreq/ffill) | 112 sparse | INTENTIONAL_V2_CORRECTION | v1 forward-fills business days |
| Daily metrics | Sparse workbook method | asfreq/ffill series | Sparse ledger method | INTENTIONAL_V2_CORRECTION | Trading-day counts differ |
| BASELINE_AMOUNT 150000 | n/a (inert) | constant defined | first NAV baseline | V1_LEGACY_INERT | No v2 dependency |
| Public Daily Returns table | absent | absent | absent | MATCH | Preserved |
| Percentage NAV axis | absent | absent | absent | MATCH | Preserved |

## UI parity

Preserved: TCP product name, BTC/ETH copy, account-stat presentation, no public Daily Returns table, no percentage NAV axis, mobile/desktop label structure.

Intentionally changed: dynamic v2 propagation vs v1 startup-static dashboard; sparse ledger-backed chart vs v1 business-day fill.

## Kevin decision table

| Decision | Recommendation | Blocks cutover? | Explicit approval needed? |
| -------- | -------------- | --------------- | ------------------------- |
| Sparse dates vs v1 asfreq/ffill | Recommended acceptance | No | No |
| v2 daily-metric methodology | Recommended acceptance | No | No |
| Public Daily Returns absent | Recommended acceptance | No | No |
| Percent NAV axis absent | Recommended acceptance | No | No |
| Drawdown/benchmark static/deferred | Recommended acceptance | No | No |
| Withdrawal blocked | Recommended acceptance | No | No |
| Tranche explicit input | Recommended acceptance | No | No |
| Export disabled initial cutover | Recommended acceptance | No | No |
| Remove v1 2025 monthly overrides | Recommended acceptance | No | **Requires explicit approval** |

## Cutover blockers

None from parity acceptance.

## Final parity verdict

```text
PASS — Excel↔JSON row parity complete; v1↔v2 differences classified with no unresolved blockers
```

Harness: `scripts/audit_tcp_acceptance.py parity`
