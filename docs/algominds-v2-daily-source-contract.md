# Algominds v2 Daily Source Contract

Multi-account daily balance foundations for Algominds v2. Defines account profiles,
daily balance rows, and pure builders into fee snapshots.

Repository: `klefe6/Tearsheet-Generator`  
Modules: `algominds_v2_accounts.py`, `algominds_v2_daily_source.py`

---

## Future URL contract

Account-specific views will use:

```text
/{account_slug}
```

Examples: `/prop`, `/acct-60k`, `/client-a`

`account_slug` is **not** login/auth. It identifies an account/profile view only.

The initial UI may default to one account, but the data model is multi-account capable now.

---

## Account profile

| Field | Purpose |
| ----- | ------- |
| `account_slug` | URL-safe key (lowercase, letters, numbers, hyphen) |
| `display_name` | Human label |
| `inception_date` | Account inception |
| `benchmark_base` | Per-account benchmark nominal base |
| `starting_spx` | SPX at account inception (may differ by account) |
| `starting_balance` | Starting balance reference |
| `fee_schedule_id` | Defaults to `algominds-tiered-spx-relative` |
| `commission_rate` | Metadata only unless fee engine extended later |
| `is_default` | Marks default account for future UI |

Custom fee schedules are **not** applied in this lane. `commission_rate` is stored as
metadata only.

---

## Daily balance row

| Field | Meaning |
| ----- | ------- |
| `account_slug` | Links row to account profile |
| `as_of_date` | Balance date |
| `account_balance` | Raw gross account balance |
| `fee_removal` | Crystallized fee payable / outstanding |
| `source_label` | Provenance label (e.g. manual-entry, broker-feed) |
| `notes` | Optional operator notes |

Validation:

- `account_balance >= 0`
- `fee_removal >= 0`
- `account_balance >= fee_removal`
- Decimal-only (no floats)

---

## Snapshot builder

`build_fee_snapshot(profile, row, spx_start, spx_end, prior_high_water_mark)` produces
an `AlgomindsV2FeeSnapshot` using:

- balances from the daily row
- `benchmark_base` from the account profile
- market inputs passed explicitly

`account_slug` is carried on profile/row models only. The pure fee snapshot schema is
unchanged.

`compute_daily_fee_result(...)` chains builder + `compute_fee_snapshot()`.

---

## Relationship to other modules

| Module | Role |
| ------ | ---- |
| `algominds_v2_snapshots` | Pure fee snapshot computation |
| `algominds_v2_snapshot_state` | Persist latest snapshot in preview JSON |
| `algominds_v2_state` | Preview state file format |

This lane does not wire persistence or ingestion.

---

## Side-effect prohibitions

- No workbook reads
- No UI, Dash, Flask, or server binding
- No repo-root state or `.env` creation at import time

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Initial multi-account daily source foundation |
