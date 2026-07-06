# Algominds v2 Fee Engine Contract

Pure accounting domain for Algominds v2 tearsheet development. This document
describes authoritative inputs, golden-test scope, and workbook hazards. It does
not define runtime configuration.

Repository: `klefe6/Tearsheet-Generator`  
Branch: `feature/algominds-v2-fee-engine`  
Package: `algominds_v2/`

---

## Source hierarchy

When reconciling aggregate fund-level inputs, prefer sources in this order:

```text
Sri All Accts
> Summary Proprietary (for June proprietary and later consolidated rows)
> monthly working sheets
> Sri Fees - Prop Acct (legacy)
> mp_ts.py display layer
```

The `mp_ts.py` display layer is Algominds v1 and must not be treated as the
accounting oracle for v2 fee-engine parity.

---

## Golden parity scope

| Period | Status |
| ------ | ------ |
| Nov 2025 – Apr 2026 | Crystallized proprietary goldens (original set) |
| May 2026 | Finalized; included in golden parity |
| June 2026 | Finalized proprietary (Summary Proprietary); included |
| July 2026 | **Excluded** — placeholder with carried SPX and carried balance |

Golden tests hard-code aggregate inputs only. Tests never read the workbook at
runtime.

---

## Core formulas

### Fee basis

```text
fee_basis = Account Balance - Fee Removal
          = raw_gross_account_balance - crystallized_fee_payable_outstanding
```

Crystallized-but-unpaid fees may remain in broker-reported gross balance and
must be excluded before computing a new fee.

### Benchmark base

```text
benchmark_dollar_return = benchmark_base * (spx_end - spx_start) / spx_start
```

`benchmark_base` is **per account** (e.g. 30000 or 60000). It must not be
globally hard-coded in application configuration. The engine accepts
`benchmark_base` as a parameter; tests cover variable-base cases.

### Manual fee waivers

Manual fee waivers are **operator overrides** layered on top of engine output.
They are not fee-engine behavior.

Example hazard: a workbook row where the formula produces ~43.379 but an
operator hard-types zero. The pure engine must return the formulaic fee; a
downstream waiver layer may zero it for display or ledger policy.

---

## Workbook hazards (documented, not encoded in engine)

1. **Wrong base reference** — Some non-proprietary placeholder rows reference
   `$D$3` instead of their own account `benchmark_base`.

2. **Stale SPX inputs** — At least one June working sheet carries stale SPX
   start/end values. Prefer Summary Proprietary / Sri All Accts for June
   proprietary goldens.

3. **Manual waiver vs formula** — Some account sections show identical balance
   inputs but different fee treatment because an operator waived the fee. The
   engine does not reproduce waived zero-fee rows automatically.

4. **July placeholder** — July 2026 rows reuse prior-month SPX and balance
   carry-forwards; not suitable as a crystallized golden oracle.

---

## SPX continuity chain (proprietary)

For proprietary goldens Nov 2025 through Jun 2026, each month's `spx_start`
equals the prior month's `spx_end`:

```text
2025-11: 6737.49 → 6849.09
2025-12: 6849.09 → 6845.5
2026-01: 6845.5  → 6939.03
2026-02: 6939.03 → 6878.88
2026-03: 6878.88 → 6528.52
2026-04: 6528.52 → 7209.01
2026-05: 7209.01 → 7580.06
2026-06: 7580.06 → 7499.36
```

---

## Privacy

This document and golden fixtures contain **no investor names, account numbers,
or private identifiers**. Redacted case labels (e.g. `acct-60k-2026-05`) are
used in tests for variable-base and inception scenarios.

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Golden set refreshed: May/Jun added, Jul excluded, variable-base and inception cases, manual-waiver documentation |
