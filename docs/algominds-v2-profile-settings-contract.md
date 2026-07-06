# Algominds v2 Profile Settings Contract

Account profile settings extensions for Algominds v2 admin and multi-account
preview lanes. Adds `number_of_units` and `exchange_fee_tier` to `AccountProfile`
and the read-only registry.

Repository: `klefe6/Tearsheet-Generator`  
Modules: `algominds_v2_accounts.py`, `algominds_v2_account_registry.py`

---

## Purpose

Before per-account state paths and the admin overview table, account profiles need
explicit settings that describe trading size and exchange fee tier. These are
profile metadata — not fee-engine inputs in this lane.

---

## benchmark_base vs number_of_units

| Field | Meaning |
| ----- | ------- |
| `benchmark_base` | Nominal benchmark base (e.g. 30000 or 60000). **Not** units. |
| `number_of_units` | Account/trading size setting. Typically **1** or **2** for now. |

These fields are independent. A 60k benchmark account may use 1 or 2 units.

---

## exchange_fee_tier

| Value | Meaning |
| ----- | ------- |
| `member` | Member exchange fee tier |
| `non-member` | Non-member exchange fee tier |

Allowed values are exactly `"member"` and `"non-member"` (lowercase, hyphenated).

`exchange_fee_tier` is **metadata only** in this lane. A future fee-cost lane may
wire tier into contract buy/sell fee math. No fee math changes here.

---

## Registry defaults

| account_slug | benchmark_base | number_of_units | exchange_fee_tier |
| ------------ | -------------- | --------------- | ----------------- |
| `prop` | 30000 | 1 | non-member |
| `acct-60k` | 60000 | 2 | member |

Display names remain non-sensitive. No investor names, account numbers, or
private identifiers.

---

## Future admin behavior (not implemented here)

- **Admin return percentages** will use **after-fee NLV** (current owed fees
  removed before return calculation).
- **Future input form** will support buy/sell, current NLV, and `number_of_units`.
- **Deposits and withdrawals** are explicitly out of scope for now.

---

## Out of scope

- No UI, Dash, Flask, or server binding
- No per-account state paths
- No fee engine or ledger changes
- No workbook reads
- No port binding

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Added number_of_units and exchange_fee_tier to AccountProfile |
