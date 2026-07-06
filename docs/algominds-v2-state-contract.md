# Algominds v2 Preview State Contract

Pure JSON persistence helpers for Algominds v2 preview development. This module
stores raw preview inputs only — no fee calculations, no workbook access, no
UI, and no server binding.

Repository: `klefe6/Tearsheet-Generator`  
Module: `algominds_v2_state.py`  
Related: `algominds_v2_config.py`, `docs/algominds-v2-isolation-contract.md`

---

## Purpose

Preview-state scaffolding for future lanes:

1. Preview Dash app on port `8311` (not implemented here).
2. Daily balance ingestion (not implemented here).
3. Fee-engine integration using persisted raw inputs (not implemented here).

---

## State file format

| Item | Value |
| ---- | ----- |
| Format | JSON object |
| Schema version | `1` |
| Decimal fields | Stored as **strings** (`account_balance`, `fee_removal`) |
| Missing file | Treated as empty state |

### Fields

| Field | Type | Notes |
| ----- | ---- | ----- |
| `schema_version` | integer | Required; must be `1` |
| `last_updated_utc` | string or null | ISO-8601 UTC timestamp |
| `account_balance` | decimal string or omitted | Raw gross balance input |
| `fee_removal` | decimal string or omitted | Crystallized fee payable outstanding |
| `notes` | string or null | Operator notes |

---

## Path resolution

State path is resolved via `load_algominds_v2_config()`:

| Item | Default |
| ---- | ------- |
| Filename | `algominds_daily_returns_secret_state.json` |
| Location | Repository root |
| Override | `ALGOMINDS_V2_STATE_PATH` |

`resolve_preview_state_path()` never creates files. Tests must use temporary
directories via explicit `repo_root` / `env` injection.

---

## Write semantics

Writes occur only through `write_preview_state()`:

1. Parent directories are created on write only.
2. Payload is written to a sibling temp file.
3. `os.replace()` atomically promotes the temp file.
4. A short-lived `*.lock` file blocks concurrent writers in the same process.

Cross-process locking beyond atomic replace is **not** guaranteed in this lane.

---

## Read semantics

| Condition | Result |
| --------- | ------ |
| File missing | Empty `AlgomindsV2PreviewState` |
| Invalid JSON | `PreviewStateCorruptedError` |
| Schema mismatch | `PreviewStateSchemaError` |
| Float decimals | Rejected (must be strings) |

---

## Side-effect prohibitions

Importing `algominds_v2_state` must not:

- create repo-root state files;
- read workbooks;
- start or bind a server;
- import Dash, Flask, TKP, TCP, Momentum Pacer, pandas, or openpyxl.

---

## Relationship to config foundation

`algominds_v2_config.py` defines port and path constants. This module consumes
that config for path resolution only. Fee engine (`algominds_v2/fee_engine.py`)
and ledger (`algominds_v2/fee_ledger.py`) remain unchanged.

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Initial preview state foundation on `feature/algominds-v2-state` |
