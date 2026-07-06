# Algominds v2 Per-Account State Contract

Per-account preview state path resolution for Algominds v2 multi-account routes.
Pure path helpers only — no UI, server, fee math, or workbook access.

Repository: `klefe6/Tearsheet-Generator`  
Module: `algominds_v2_account_state_paths.py`  
Related: `algominds_v2_snapshot_state.py`, `algominds_v2_state.py`

---

## Purpose

The global preview state file is unsafe once multiple account routes exist. This lane
resolves one preview JSON file per `account_slug` so `/prop` and `/acct-60k` can
persist independently.

Future target:

```text
/prop      → <state_root>/prop.json
/acct-60k  → <state_root>/acct-60k.json
```

When present, `snapshot.account_slug` must match the route/state path slug.

---

## Path resolution

| Function | Behavior |
| -------- | -------- |
| `resolve_preview_state_path(account_slug, ...)` | Validate slug; return `<state_root>/{account_slug}.json` |
| `resolve_account_state_root(...)` | Resolve configurable directory root |

Rules:

- `account_slug` is validated with `validate_account_slug()` before path construction.
- Resolver does **not** create, read, or write files/directories.
- Filename pattern: `{account_slug}.json`
- Resolved paths must remain under `state_root` (no traversal escape).

### State root

Default directory (under repo root): `algominds_v2_account_state`

Override environment variable:

```text
ALGOMINDS_V2_ACCOUNT_STATE_ROOT
```

Tests must use temporary `state_root` paths — never repo-root state files.

---

## Snapshot account validation

`validate_snapshot_account_slug(snapshot, expected_account_slug)`:

| snapshot.account_slug | Result |
| --------------------- | ------ |
| `None` | Pass (legacy/backward compatible) |
| matches expected | Pass |
| differs from expected | `ValueError` (cross-account mismatch) |

Future account-specific snapshots **should** include `account_slug`. Legacy snapshots
without it are tolerated but not rewritten in this lane.

---

## Account convenience wrappers

| Function | Behavior |
| -------- | -------- |
| `load_latest_snapshot_for_account(account_slug, ...)` | Resolve path; load; validate slug when present |
| `save_latest_snapshot_for_account(account_slug, snapshot, ...)` | Validate slug; resolve path; delegate to `save_latest_snapshot` |

Existing explicit-path APIs remain unchanged:

- `load_latest_snapshot(path)`
- `save_latest_snapshot(path, snapshot)`

---

## Out of scope

- No UI, Dash, Flask, or server binding
- No fee engine or ledger changes
- No workbook reads
- No deposits/withdrawals
- No exchange-fee cost math
- No migration of legacy global state file (document only)

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Per-account preview state path resolver |
