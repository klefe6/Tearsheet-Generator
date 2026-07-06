# Algominds v2 Snapshot / State Integration Contract

Persists the latest Algominds v2 fee snapshot inside preview-state JSON. Bridges
`algominds_v2_state` persistence with `algominds_v2_snapshots` computation.

Repository: `klefe6/Tearsheet-Generator`  
Module: `algominds_v2_snapshot_state.py`  
Related: `algominds_v2_state.py`, `algominds_v2_snapshots.py`

---

## Storage model

Preview state JSON (`schema_version: 1`) may include an optional object:

```json
{
  "schema_version": 1,
  "last_updated_utc": "...",
  "account_balance": "...",
  "fee_removal": "...",
  "notes": "...",
  "latest_snapshot": {
    "as_of_date": "2026-05-31",
    "account_balance": "50125.21",
    "fee_removal": "0",
    "prior_high_water_mark": "44483.423270",
    "spx_start": "7209.01",
    "spx_end": "7580.06",
    "benchmark_base": "30000",
    "notes": "optional"
  }
}
```

Decimal values in `latest_snapshot` are stored as **strings**.

---

## Backward compatibility

| Condition | Behavior |
| --------- | -------- |
| Missing state file | Empty preview state; no latest snapshot |
| State without `latest_snapshot` | Reads normally; `load_latest_snapshot` returns `None` |
| Existing preview fields | Preserved when saving latest snapshot |

---

## API

| Function | Purpose |
| -------- | ------- |
| `load_latest_snapshot(path)` | Deserialize latest snapshot or `None` |
| `save_latest_snapshot(path, snapshot)` | Merge snapshot into preview state and write |
| `compute_latest_snapshot_result(path)` | Load + `compute_fee_snapshot()` |

Writes occur only through `save_latest_snapshot` → `write_preview_state`.

---

## Side-effect prohibitions

- No import-time file creation
- No workbook reads
- No server binding
- No UI / Dash / Flask
- Snapshot computation remains pure in `algominds_v2_snapshots`

---

## Future lanes

A later lane will connect real daily balance ingestion and the preview app on
port `8311`. This integration does not implement ingestion or UI.

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Initial snapshot/state integration on `feature/algominds-v2-snapshot-state` |
