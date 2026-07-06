# Algominds v2 Account Registry Contract

Read-only in-code registry of `AccountProfile` entries for Algominds v2. Resolves
which accounts exist for future `/{account_slug}` routes without UI, persistence,
or workbook access.

Repository: `klefe6/Tearsheet-Generator`  
Module: `algominds_v2_account_registry.py`  
Related: `algominds_v2_accounts.py`, `algominds_v2_daily_source.py`

---

## Purpose

The daily-source lane introduced `AccountProfile` and per-row `account_slug` values,
but profiles were defined ad hoc in tests. This registry centralizes the canonical
set of account profiles for:

- future account-specific preview URLs
- deterministic profile lookup by slug
- default-account resolution for an initial single-account UI

---

## Future URL contract

Account-specific views will use:

```text
/{account_slug}
```

Examples: `/prop`, `/acct-60k`, `/client-a`

`account_slug` is **not** login/auth. It identifies an account/profile view only.

This lane does **not** add URL routes.

---

## Registry behavior

| Function | Behavior |
| -------- | -------- |
| `get_account_profile(slug)` | Validate slug format; return matching `AccountProfile`; raise `AccountProfileNotFoundError` for unknown slug |
| `list_account_profiles()` | Return immutable deterministic tuple of all profiles |
| `get_default_account_profile()` | Return the single profile with `is_default=True` |

### Initial registry entries

| account_slug | display_name | benchmark_base | is_default |
| ------------ | ------------ | -------------- | ---------- |
| `prop` | Proprietary Aggregate | 30000 | yes |
| `acct-60k` | 60k Benchmark Account | 60000 | no |

Display names are non-sensitive labels only. Do not store investor names, account
numbers, private identifiers, or real client labels in the registry.

Exactly one profile must be marked `is_default=True` (currently `prop`).

---

## Account profile fields

Each registry entry is an `AccountProfile` with:

| Field | Purpose |
| ----- | ------- |
| `account_slug` | URL-safe path key |
| `display_name` | Non-sensitive human label |
| `inception_date` | Account inception |
| `benchmark_base` | Per-account benchmark nominal base |
| `starting_spx` | SPX at account inception |
| `starting_balance` | Starting balance reference |
| `fee_schedule_id` | Defaults to `algominds-tiered-spx-relative` |
| `commission_rate` | Metadata only unless fee engine extended later |
| `is_default` | Marks default account for future UI |

`commission_rate` is stored as metadata only. Custom fee schedules are not applied
in this lane.

---

## Optional daily-source helpers

`algominds_v2_daily_source.py` may expose convenience helpers that resolve a profile
from the registry before calling existing builders:

- `build_fee_snapshot_for_account_slug(...)`
- `compute_daily_fee_result_for_account_slug(...)`

These helpers:

- call `get_account_profile(account_slug)`
- delegate to `build_fee_snapshot` / `compute_daily_fee_result`
- reject profile/row slug mismatch
- do not read/write state or add persistence
- do not change fee math

---

## Read-only for now

The registry is in-code and read-only. A future lane may move profile definitions
to a secure persisted configuration with operator-controlled provisioning.

---

## Relationship to other modules

| Module | Role |
| ------ | ---- |
| `algominds_v2_accounts` | `AccountProfile` dataclass and slug validation |
| `algominds_v2_daily_source` | Daily rows and snapshot builders |
| `algominds_v2_snapshots` | Pure fee snapshot computation |

This lane does not modify fee engine, ledger, config, state, or snapshot-state modules.

---

## Side-effect prohibitions

- No workbook reads
- No UI, Dash, Flask, or server binding
- No port binding (preview port 8311 remains unused)
- No repo-root state or `.env` creation at import time
- No investor names, account numbers, or private identifiers in registry data

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Initial read-only account profile registry |
