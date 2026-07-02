# TCP Resilience Acceptance (Step 10)

Validated: 2026-07-02  
Branch: `feature/tcp-v2-migration`

## State modes exercised

- `json_active` with disposable state directories
- `workbook` rollback mode
- `json_active` with fallback enabled/disabled

## Acceptance matrix

| Scenario | Expected | Result | Pass |
| -------- | -------- | ------ | ---- |
| G1 Normal startup | Valid JSON loads, revision correct | revision 1, 112 rows | Yes |
| G2 Missing active | Workbook fallback, writes disabled | `workbook_fallback` | Yes |
| G3 Corrupt active + valid backup | Backup served read-only | `json_backup` / `recovered_backup` | Yes |
| G4 Invalid active + backup | Workbook fallback when allowed | `workbook_fallback` | Yes |
| G5 Fallback disabled | Controlled error, no writes | Exception on load | Yes |
| G6 Interrupted write | Prior active preserved | Active bytes unchanged on failure | Yes |
| G7 Concurrent writers | One success, one stale conflict | Exactly one success | Yes |
| G8 Duplicate submit | Second rejected | Stale revision on second add | Yes |
| G9 Stale delete preview | Rejected after state change | Delete with stale revision fails | Yes |
| G10 Lock timeout | Controlled failure, state unchanged | Save fails under held lock | Yes |
| G11 Server restart | Persisted mutations survive reload | revision 2 after add reload | Yes |
| G12 Missing secrets | Mutations unavailable | AdminAuth not configured | Yes |
| G13 Workbook rollback | Workbook authoritative, JSON untouched | JSON bytes unchanged | Yes |
| G14 TKP isolation | TKP state untouched | TKP file size unchanged | Yes |

## Orphan backup disposition

| Item | Value |
| ---- | ----- |
| Filename | `tcp_daily_returns_secret_state.backup.json` (orphan duplicate) |
| Configured recovery path? | Yes (same name), but content was stale duplicate rev 1 |
| Schema validity | Valid TCP schema revision 1 |
| Relationship to active | Different checksum from current clean active seed |
| Action | Moved to gitignored `_runtime/quarantine/` with orphan suffix |
| Final active backup status | **Absent** after quarantine (clean revision-1 baseline) |

## Final clean preview baseline

| Field | Value |
| ----- | ----- |
| Revision | 1 |
| Rows | 112 |
| Latest date | 2026-06-24 |
| Latest NAV | 44871.384 |
| Data source (`json_active`) | `json` |
| Lock | Absent |
| Git tracked | No |

## Remaining resilience risks

- Single backup slot (prior revision only)
- No production deployment validation yet
- Deployed TCP v1 parity not confirmed against live port 8302

## Production-readiness verdict

```text
PASS — preview resilience acceptance complete for cutover planning (deployment still out of scope)
```

Harness: `scripts/audit_tcp_acceptance.py resilience`

Tests: `tests/test_tcp_resilience_acceptance.py`
