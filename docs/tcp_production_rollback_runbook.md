# TCP v2 Production Rollback Runbook

Rollback restores **TCP v1 on port 8302** without Excel writeback and without deleting v2 incident state.

---

## General principles

1. **No automatic Excel writeback** — v2-only rows are reconciled manually.
2. **Preserve incident state** — copy active/backup JSON to archive before destructive steps.
3. **Port 8302** — only one TCP process at a time.
4. **Infrastructure unchanged** — Cloudflare still routes to 8302.

---

## Scenario 1 — v2 fails before any production mutation

### Steps

1. Stop v2 process on port 8302 (`taskkill` / Manager / debug.py).
2. Confirm port 8302 is free.
3. Restore `reboot_tcp_ts.bat` to launch `python tcp_ts.py` (committed rollback version).
4. Start v1:
   ```bat
   cd /d "C:\Coding Projects\Tearsheet Generator"
   call reboot_tcp_ts.bat
   ```
5. Verify:
   - `http://127.0.0.1:8302/` → 200
   - https://tcp-ts.hcresearch.ltd → 200
6. **Preserve** production v2 JSON directory for investigation (do not delete).

### Success criteria

- v1 serves public dashboard from workbook (static startup layout).
- No v2 process on 8302.
- v2 state files archived but not required for v1 operation.

---

## Scenario 2 — v2 fails after production mutations

### Steps

1. **Stop mutations** — unset admin secrets or stop process.
2. Record active revision and row count from `/healthz` or state file.
3. Archive state:
   ```powershell
   $archive = "$env:LOCALAPPDATA\HughesCompany\TCP\incident\$(Get-Date -Format yyyyMMdd_HHmmss)"
   New-Item -ItemType Directory -Force -Path $archive
   Copy-Item "$env:LOCALAPPDATA\HughesCompany\TCP\state\*" $archive
   ```
4. Identify rows added/deleted since seed (compare to cutover log baseline).
5. **Do not** push v2 rows into Excel automatically.
6. Restore v1 service (Scenario 1 steps 1–5).
7. Assign **data reconciliation owner** (Kevin/operations) before resuming daily v2 work.

### Success criteria

- v1 live on 8302.
- Incident archive complete.
- Reconciliation ticket opened for v2-only rows.

---

## Scenario 3 — active JSON corrupt, backup valid

### Steps

1. Stop admin mutations (disable secrets or stop app).
2. Preserve both active and backup files (copy to incident archive).
3. Options:
   - **A.** Manually promote backup → active after validation (operator procedure, not automatic).
   - **B.** Roll back to v1 (Scenario 1) while investigating.
4. Restart with `TCP_V2_ALLOW_WORKBOOK_FALLBACK=true` only if read-only workbook mode is acceptable temporarily.

### Success criteria

- No writes until validated JSON is active.
- Users see consistent data (backup or workbook read-only).

---

## Scenario 4 — both JSON files invalid

### Steps

1. Set `TCP_V2_STATE_MODE=workbook` and `TCP_V2_ALLOW_WORKBOOK_FALLBACK=true` for **read-only** dashboard if v2 must stay up briefly.
2. Disable admin writes (remove secrets).
3. Prefer full rollback to v1 (Scenario 1) for public stability.
4. Preserve corrupt files for forensics.

### Success criteria

- No fabricated/synthetic JSON created.
- Public page available (v1 or v2 workbook mode).

---

## Scenario 5 — admin authentication failure

### Steps

1. Public dashboard may remain up (read-only if secrets removed).
2. Disable mutations by unsetting `TCP_V2_ADMIN_TOKEN` / `TCP_V2_SESSION_SECRET` and restart.
3. Fix secret configuration; verify `/healthz` reports auth status safely (no secret leakage).
4. Roll back to v1 only if public site is affected or extended outage.

### Success criteria

- Mutations impossible while auth broken.
- Secrets rotated if compromise suspected.

---

## Scenario 6 — infrastructure / port failure

### Steps

1. Identify port owner: `netstat -ano | findstr :8302`
2. Restore original launcher (`reboot_tcp_ts.bat` → `tcp_ts.py`).
3. Confirm Cloudflare tunnel config still maps `tcp-ts.hcresearch.ltd` → `localhost:8302`.
4. Confirm Manager `service_config.py` still references `reboot_tcp_ts.bat` port 8302.

### Success criteria

- Single listener on 8302.
- Public route restored.

---

## v1 restart command (canonical)

```bat
cd /d "C:\Coding Projects\Tearsheet Generator"
set PYTHONIOENCODING=utf-8
call .venv310\Scripts\activate.bat
python tcp_ts.py
```

Or: `call reboot_tcp_ts.bat` after bat restored to v1 target.

### v1 health checks

| Check | Expected |
| ----- | -------- |
| `http://127.0.0.1:8302/` | 200 |
| https://tcp-ts.hcresearch.ltd | 200 |
| Process | Single Dash/Flask on 8302 |
| Data | Workbook-driven (note: v1 uses startup-static dashboard until restart) |

---

## Rollback manifest (capture at cutover)

| Artifact | SHA-256 / note |
| -------- | -------------- |
| Committed `tcp_ts.py` (HEAD at cutover) | Record at cutover |
| `reboot_tcp_ts.bat` (pre-cutover) | Record at cutover |
| Submodule SHA deployed | Record at cutover |
| Workbook at cutover | Record at cutover |

---

## Data reconciliation owner

| Role | Responsibility |
| ---- | -------------- |
| Kevin / data owner | Approve manual Excel updates for v2-only rows |
| Engineering | Preserve JSON archives, execute technical rollback |
| Operations | Process/port management, Manager restarts |

---

## Rollback success criteria (all scenarios)

- TCP v1 or approved read-only mode serves public URL
- Port 8302 ownership is clear
- No silent data loss (incident archives preserved)
- Workbook not auto-modified
- TKP tearsheet unaffected (port 8301)
