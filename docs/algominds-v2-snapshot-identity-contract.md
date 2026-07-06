# Algominds v2 Snapshot Identity Contract

Optional `account_slug` identity on `AlgomindsV2FeeSnapshot` for multi-account
preview and persistence lanes. Identity metadata only — fee math is unchanged.

Repository: `klefe6/Tearsheet-Generator`  
Modules: `algominds_v2_snapshots.py`, `algominds_v2_daily_source.py`  
Related: `algominds_v2_account_registry.py`, `algominds_v2_snapshot_state.py`

---

## Purpose

The account registry and daily-source lanes carry `account_slug` on profiles and
rows, but persisted fee snapshots could not distinguish which account they belong
to. This lane adds optional snapshot identity for future `/{account_slug}` routes
and per-account state paths.

---

## Field contract

| Field | Type | Required | Purpose |
| ----- | ---- | -------- | ------- |
| `account_slug` | `str \| None` | No | URL-safe account key when known |

When provided, `account_slug` is validated via `validate_account_slug()` from
`algominds_v2_accounts.py`. `None` remains valid for backward compatibility.

`account_slug` is **not** login/auth.

---

## Fee math isolation

`compute_fee_snapshot()` ignores `account_slug`. Numeric fee results depend only
on balance, market, and benchmark inputs. Identity is carried for routing,
persistence, and display — not for calculation.

---

## Serialization

`snapshot_to_dict()` includes `account_slug` only when non-`None`.

`snapshot_from_dict()` treats a missing `account_slug` key as `None`, preserving
compatibility with snapshots written before this lane.

JSON round-trip preserves `account_slug` when present.

---

## Builder wiring

`build_fee_snapshot()` and `build_fee_snapshot_for_account_slug()` populate
`account_slug` from the resolved `AccountProfile`.

Row/profile slug mismatch rules are unchanged.

---

## Relationship to other modules

| Module | Role |
| ------ | ---- |
| `algominds_v2_accounts` | Slug validation |
| `algominds_v2_account_registry` | Canonical profile lookup (unchanged) |
| `algominds_v2_snapshot_state` | Persists `latest_snapshot` dict via snapshot serializers |
| `algominds_v2/fee_engine` | Pure fee math (unchanged) |

---

## Side-effect prohibitions

- No workbook reads
- No UI, Dash, Flask, or server binding
- No port binding (preview port 8311 remains unused)
- No repo-root state or `.env` creation at import time

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Optional `account_slug` on fee snapshots |
