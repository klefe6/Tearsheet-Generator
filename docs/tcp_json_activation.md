# TCP v2 JSON Activation (Step 9)

Validated: 2026-07-02  
Branch: `feature/tcp-v2-migration`

## State modes

| Mode | Env value | Authoritative source | Writes |
|------|-----------|---------------------|--------|
| Workbook fallback | `workbook` (default) | Excel ledger | Disabled |
| JSON active | `json_active` | Valid active TCP JSON | Enabled when authenticated |

```text
TCP_V2_STATE_MODE=workbook
TCP_V2_STATE_MODE=json_active
```

Optional path overrides:

```text
TCP_V2_STATE_PATH
TCP_V2_STATE_BACKUP_PATH
TCP_V2_STATE_LOCK_PATH
TCP_V2_ALLOW_WORKBOOK_FALLBACK=true|false
```

Importing configuration creates no files.

## Seed command

Dry run:

```text
.\.venv310\Scripts\python.exe scripts\seed_tcp_state.py --dry-run --expected-row-count 112 --expected-latest-date 2026-06-24 --expected-latest-nav 44871.384
```

Real seed (preview default path):

```text
.\.venv310\Scripts\python.exe scripts\seed_tcp_state.py --seed --expected-row-count 112 --expected-latest-date 2026-06-24 --expected-latest-nav 44871.384
```

Replace existing preview state:

```text
.\.venv310\Scripts\python.exe scripts\seed_tcp_state.py --seed --replace-existing ...
```

Expected seed values (current workbook contract):

- Rows: 112
- Latest date: 2026-06-24
- Latest NAV: 44871.384
- Revision: 1
- Source: `excel_bootstrap`

Absolute workbook paths are excluded from persisted JSON.

## JSON source precedence (`json_active`)

1. Valid active JSON → `data_source=json`, writes enabled
2. Corrupt active + valid backup → `data_source=json_backup`, read-only recovery
3. Missing/invalid JSON with fallback enabled → `data_source=workbook_fallback`, read-only
4. Missing/invalid JSON with fallback disabled → load error

Reads never auto-seed, repair, or overwrite active state.

## Write-enable conditions

Authenticated Add/Delete persistence requires:

```text
TCP_V2_STATE_MODE=json_active
AND valid active JSON loaded (data_source=json)
AND TCP_V2_ADMIN_TOKEN configured
AND TCP_V2_SESSION_SECRET configured
AND authenticated Flask session
```

## Add mutation sequence

1. Preview calculation (`simulate_add_row` / `compute_tcp_row`)
2. Authenticated **Save Row**
3. Server re-parses original inputs and recomputes row
4. Lock → load active state → verify `expected_revision`
5. Append row → `save_state` with revision + 1
6. Refresh canonical NAV store, dashboard, admin ledger

Stale revision or double-submit: one succeeds, the other receives a controlled stale-revision error.

## Delete mutation sequence

1. Deletion preview of final row
2. Authenticated **Delete Last Row**
3. Verify final-row date still matches preview
4. Remove only the final completed row (minimum-row guard)
5. Atomic save with revision + 1

## Backup semantics

Before each successful mutation, the prior valid active revision is copied to backup.

```text
Seed: active r1
Add:  active r2, backup r1
Delete: active r3, backup r2
```

## Browser refresh / restart

Active JSON is reloaded on refresh and server restart. Excel is not re-imported on startup in `json_active` mode.

## Operational rollback

Set:

```text
TCP_V2_STATE_MODE=workbook
```

This makes the workbook authoritative, disables writes, and leaves JSON files untouched.

Manual recovery from backup is operational: copy backup over active only through controlled procedures outside ordinary app startup.

## Runtime files (never commit)

- `tcp_daily_returns_secret_state.json`
- `tcp_daily_returns_secret_state.backup.json`
- `tcp_daily_returns_secret_state.lock`
- `tests/_tmp_state/`, `tests/_canary_state/`, `_runtime/`

## Remaining limitations

- Negative cash transfers blocked
- Tranche count remains explicit admin input
- Export disabled (`Export will be enabled after persistence parity validation`)
- Single prior-state backup slot
- No production deployment in Step 9

## Next phase

Perform full three-way parity and resilience acceptance across the Excel ledger, current TCP v1, and JSON-backed TCP v2 before preparing production cutover.
