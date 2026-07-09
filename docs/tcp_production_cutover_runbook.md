# TCP v2 Production Cutover Runbook

Executable procedure for promoting JSON-backed TCP v2 to production port **8302**.  
**Do not run this document until Step 11 blockers are resolved and Kevin approves cutover.**

---

## 1. Scope

### Changes on cutover day

| Item | Action |
| ---- | ------ |
| `reboot_tcp_ts.bat` | Point launcher at `tcp_ts_v2.py` instead of `tcp_ts.py` |
| Production environment | Set `TCP_V2_*` variables (state paths, secrets, `json_active`, bind port 8302) |
| Production JSON state | Seed revision 1 from **current** workbook at cutover window |
| Process on port 8302 | Stop v1, start v2 |

### Does not change

| Item | Notes |
| ---- | ----- |
| Cloudflare | `tcp-ts.hcresearch.ltd` → `localhost:8302` unchanged |
| Manager `service_config.py` | Still launches `reboot_tcp_ts.bat` on port 8302 |
| HomePage `debug.py` | Still references same bat and port |
| `tcp_ts.py` | Preserved as rollback source (do not delete) |
| `tkp_ts.py` / TKP JSON | Untouched |
| Workbook | Read-only for v2; no Excel writeback |
| Preview port 8312 | Not used in production |

---

## 2. Preconditions

- [ ] Step 10 acceptance passed (`7de8ba1` or later merged to submodule `main`)
- [ ] Submodule PR merged; recorded merge SHA
- [ ] Parent repository remote access restored
- [ ] Fresh parent submodule pointer PR merged (not stale `f53de23`)
- [ ] `scripts/preflight_tcp_cutover.py --production-ready` returns **GO**
- [ ] `scripts/audit_tcp_acceptance.py parity` returns **PASS** on cutover day
- [ ] Production secrets provisioned (not in git)
- [ ] Production state directory created and writable
- [ ] Rollback owner available for maintenance window
- [ ] Workbook freeze approved by data owner

---

## 3. GitHub merge sequence

1. **Submodule PR**
   - Base: `main`
   - Head: `feature/tcp-v2-migration`
   - URL: https://github.com/klefe6/Tearsheet-Generator/compare/main...feature/tcp-v2-migration?expand=1
2. Confirm CI/tests green and PR approved.
3. Merge submodule PR (recommend **merge commit** or **squash** per team policy; record resulting SHA).
4. Record submodule `main` SHA: `SUBMODULE_MAIN_SHA=____________`
5. **Parent integration branch** (new branch from parent `main`):
   ```bash
   cd "C:\Coding Projects"
   git checkout main
   git pull origin main
   git checkout -b chore/tcp-v2-submodule-pointer
   cd "Tearsheet Generator"
   git fetch origin
   git checkout <SUBMODULE_MAIN_SHA>
   cd ..
   git add "Tearsheet Generator"
   git commit -m "chore(tcp-v2): advance Tearsheet Generator submodule to production cutover"
   git push -u origin chore/tcp-v2-submodule-pointer
   ```
6. Open parent PR; merge only after pointer SHA verified.
7. **Do not use** local parent commit `f53de23` — it points to submodule `bc041cf` (Step 2 only).

---

## 4. Release artifact

| Field | Value |
| ----- | ----- |
| Repository | `Tearsheet-Generator` |
| Branch after merge | `main` |
| Verify commit | Submodule merge SHA from step 3 |
| Verification | `git rev-parse HEAD` in submodule checkout matches merge SHA |
| Preflight | `python scripts/preflight_tcp_cutover.py --check --expected-commit <SHA> --production-ready` |

Optional tag (cutover day, after smoke pass):

```bash
git tag -a tcp-v2-cutover-YYYYMMDD -m "TCP v2 production cutover"
git push origin tcp-v2-cutover-YYYYMMDD
```

---

## 5. Maintenance / freeze window

| Item | Guidance |
| ---- | -------- |
| Start time | Schedule with operators (not pre-filled) |
| Operator | Named engineer + rollback owner |
| Workbook freeze | No edits to `tcp_alex.xlsx` from T−30 min through seed validation |
| Communication | Notify stakeholders that TCP admin may be briefly unavailable |
| Abort threshold | Any workbook checksum change after dry-run → **abort** |

---

## 6. Backups (before cutover)

Record in cutover log (no secrets):

| Artifact | Action |
| -------- | ------ |
| Workbook | Copy `tcp_alex.xlsx` to dated backup location |
| `reboot_tcp_ts.bat` | Record SHA-256 of committed version |
| `tcp_ts.py` | Record SHA-256 of **committed HEAD** (rollback source) |
| Manager/HomePage configs | Snapshot or note current commit |
| Existing production JSON | If any, copy to incident archive |
| Logs | Snapshot `Manager/logs` TCP-related entries |
| Git SHAs | Parent HEAD, submodule HEAD |

---

## 7. Production runtime layout

Use a **dedicated production state directory** (not repo root preview path, not `_runtime/`, not TKP).

Recommended layout:

```text
%LOCALAPPDATA%\HughesCompany\TCP\state\
  tcp_daily_returns_secret_state.json          (active)
  tcp_daily_returns_secret_state.backup.json   (backup)
  tcp_daily_returns_secret_state.lock          (lock)
```

### Environment variables (cutover day)

```bat
set TCP_V2_STATE_MODE=json_active
set TCP_V2_BIND_PORT=8302
set TCP_V2_STATE_PATH=%LOCALAPPDATA%\HughesCompany\TCP\state\tcp_daily_returns_secret_state.json
set TCP_V2_STATE_BACKUP_PATH=%LOCALAPPDATA%\HughesCompany\TCP\state\tcp_daily_returns_secret_state.backup.json
set TCP_V2_STATE_LOCK_PATH=%LOCALAPPDATA%\HughesCompany\TCP\state\tcp_daily_returns_secret_state.lock
set TCP_V2_WORKBOOK_PATH=<absolute path to tcp_alex.xlsx>
set TCP_V2_ADMIN_TOKEN=<from secure store>
set TCP_V2_SESSION_SECRET=<from secure store>
set PYTHONIOENCODING=utf-8
```

Secrets: store in OS/user-scoped secure location readable only by the service account. Rotate by updating env and restarting v2.

---

## 8. Production seed (dynamic values)

**Do not hard-code row count, latest date, or NAV.** Capture from the frozen workbook at cutover time.

### 8.1 Freeze and record workbook

```powershell
cd "C:\Coding Projects\Tearsheet Generator"
.\.venv310\Scripts\python.exe -c "
from pathlib import Path
from tcp_config import load_config
from tcp_ledger import load_ledger
import hashlib
cfg = load_config()
p = Path(cfg.workbook_path)
print('checksum', hashlib.sha256(p.read_bytes()).hexdigest())
print('size', p.stat().st_size)
print('mtime', p.stat().st_mtime)
ledger = load_ledger(cfg.workbook_path, cfg.sheet_name)
m = ledger.metadata
print('rows', m.completed_row_count)
print('first', m.first_completed_date)
print('latest', m.latest_completed_date)
print('nav', ledger.completed_records[-1].fields['nav-x1'])
"
```

Save output as `CUTOVER_WORKBOOK_BASELINE`.

### 8.2 Calculator replay (must be 100%)

```powershell
.\.venv310\Scripts\python.exe -m pytest tests/test_tcp_calculations.py::test_full_ledger_replay_passes -q
```

### 8.3 Seed dry-run

```powershell
.\.venv310\Scripts\python.exe scripts\seed_tcp_state.py --dry-run ^
  --output "%LOCALAPPDATA%\HughesCompany\TCP\state\tcp_daily_returns_secret_state.json" ^
  --expected-row-count <ROWS> ^
  --expected-latest-date <YYYY-MM-DD> ^
  --expected-latest-nav <NAV>
```

### 8.4 Workbook change guard

Re-record workbook checksum immediately before `--seed`. If it differs from step 8.1 → **abort cutover**.

### 8.5 Backup existing production JSON (if any)

```powershell
copy "%LOCALAPPDATA%\HughesCompany\TCP\state\tcp_daily_returns_secret_state.json" ^
     "%LOCALAPPDATA%\HughesCompany\TCP\state\archive\pre_cutover_<timestamp>.json"
```

### 8.6 Seed revision 1

```powershell
.\.venv310\Scripts\python.exe scripts\seed_tcp_state.py --seed ^
  --output "%LOCALAPPDATA%\HughesCompany\TCP\state\tcp_daily_returns_secret_state.json" ^
  --expected-row-count <ROWS> ^
  --expected-latest-date <YYYY-MM-DD> ^
  --expected-latest-nav <NAV>
```

### 8.7 Validate persisted JSON

```powershell
.\.venv310\Scripts\python.exe -c "
from pathlib import Path
from tcp_state import load_state, validate_state
p = Path(r'%LOCALAPPDATA%\HughesCompany\TCP\state\tcp_daily_returns_secret_state.json')
env = load_state(p)
validate_state(env)
print('revision', env['revision'], 'rows', len(env['records']))
"
```

---

## 9. Pre-switch canary (non-production port)

Use production state paths but temporary bind port **8312**:

```bat
set TCP_V2_BIND_PORT=8312
call reboot_tcp_ts_v2.bat
```

Verify (read-only):

- [ ] `http://127.0.0.1:8312/` → HTTP 200
- [ ] `http://127.0.0.1:8312/healthz` → `data_source=json`, correct revision/rows/date/NAV
- [ ] Admin login works; **no mutation** during canary unless authorized
- [ ] Production v1 still on 8302

Stop canary on 8312 before switch.

---

## 10. Switch (selected mechanism)

**Strategy: launcher target change** (preferred over renaming `tcp_ts.py`).

### 10.1 Stop production v1 on 8302

Use Manager, HomePage debug restart, or controlled `taskkill` per operations standard.  
Confirm port 8302 is free before starting v2.

### 10.2 Update `reboot_tcp_ts.bat` (cutover day only)

```bat
@echo on
setlocal
cd /d "%~dp0"
echo BAT_DIR=%~dp0
echo CWD=%CD%
set PYTHONIOENCODING=utf-8
set TCP_V2_STATE_MODE=json_active
set TCP_V2_BIND_PORT=8302
REM Production state paths and secrets loaded from secure env / wrapper
call .venv310\Scripts\activate.bat
python tcp_ts_v2.py
```

Alternative: keep bat minimal and set all `TCP_V2_*` in a **non-committed** `tcp_production_env.bat` called by operators.

### 10.3 Rollback switch

Restore committed `reboot_tcp_ts.bat` that runs `python tcp_ts.py`.

---

## 11. Start v2 on port 8302

```bat
cd /d "C:\Coding Projects\Tearsheet Generator"
call reboot_tcp_ts.bat
```

Verify:

- [ ] Process listening on 8302
- [ ] `debug=False` (no reloader child duplication from Flask debug)
- [ ] `/healthz` reports `data_source=json`

---

## 12. Immediate smoke tests

| Check | Expected |
| ----- | -------- |
| https://tcp-ts.hcresearch.ltd | HTTP 200 |
| `/healthz` | 200, `data_source=json`, revision 1 (post-seed) |
| Latest date/NAV | Match cutover workbook baseline |
| Monthly table | Renders |
| Daily metrics | Renders |
| NAV chart | Renders |
| Desktop/mobile labels | Correct latest date wording |
| Admin login | Works with production secrets |
| Admin ledger | Row count matches seed |
| Workbook file | Checksum unchanged |

---

## 13. Controlled production mutation canary (optional)

**Only with business owner authorization.**

1. Add agreed temporary next-date row via admin.
2. Verify revision increments, dashboard updates, persistence survives restart.
3. Delete the temporary row immediately.
4. Archive revision history in cutover log.

If financial mutation is not acceptable: rely on pre-switch read-only canary (section 9) only.

---

## 14. Observation window (first 24 hours)

- Process health / no duplicate listeners on 8302
- Error logs in console and `Manager/logs`
- State revision stable unless authorized edits
- Backup file created on first mutation
- Workbook checksum unchanged
- Public and admin routes reachable
- Manager daily restart behavior (v2 should survive `reboot_tcp_ts.bat` relaunch)

---

## 15. Success declaration

Cutover succeeds when:

- Public URL and health checks pass
- Data matches frozen workbook baseline
- Admin auth and ledger operate correctly
- No unplanned workbook or TKP changes
- Rollback procedure verified available
- Observation window complete without incident

---

## 16. Abort and rollback triggers

Immediate rollback if any occur:

- Public URL down > agreed threshold
- Health reports corrupt state with no safe backup
- Row-level parity mismatch vs workbook
- Unplanned workbook mutation during freeze
- Duplicate port 8302 processes
- Admin writes succeed without authentication
- Kevin-directed abort

See `tcp_production_rollback_runbook.md`.

---

## Selected cutover mechanism (summary)

| | |
|-|-|
| **Selected** | Change `reboot_tcp_ts.bat` to launch `tcp_ts_v2.py` with production env |
| **Rejected** | Rename `tcp_ts_v2.py` → `tcp_ts.py` (conflicts with modified local `tcp_ts.py`, higher risk) |
| **Infrastructure** | No Cloudflare/Manager/HomePage code changes required |
| **Rollback** | Restore bat → `python tcp_ts.py`; preserve v2 JSON for investigation |
