# TCP v2 Release and Cutover Checklist

Use with `scripts/preflight_tcp_cutover.py` and `docs/tcp_production_cutover_runbook.md`.

---

## GitHub

- [ ] Submodule PR exists (base `main`, head `feature/tcp-v2-migration`)
- [ ] Acceptance commit included (`7de8ba1` or later)
- [ ] No runtime JSON, backups, locks, or secrets in PR
- [ ] Tests green on PR
- [ ] PR approved by reviewer(s)
- [ ] Submodule merge SHA recorded: `________________`
- [ ] Parent remote access verified (`git ls-remote` succeeds)
- [ ] Fresh parent pointer branch created (not `f53de23`)
- [ ] Parent pointer PR approved
- [ ] Parent pointer merged

**Submodule PR URL:** https://github.com/klefe6/Tearsheet-Generator/compare/main...feature/tcp-v2-migration?expand=1

---

## Data

- [ ] Workbook freeze communicated
- [ ] Workbook checksum recorded at cutover
- [ ] Calculator replay 100%
- [ ] Seed dry-run passed with dynamic row/date/NAV expectations
- [ ] Production seed revision 1 completed
- [ ] Production state checksum recorded
- [ ] Backup file status documented (absent or valid)
- [ ] TKP state isolation confirmed (no TCP path collision)

---

## Runtime

- [ ] Production secrets configured (not in git)
- [ ] `TCP_V2_STATE_PATH` / backup / lock configured (production directory)
- [ ] `TCP_V2_STATE_MODE=json_active`
- [ ] `TCP_V2_BIND_PORT=8302` for production
- [ ] `debug=False` verified
- [ ] `.venv310` Python verified
- [ ] Port 8302 ownership documented pre-cutover
- [ ] Temporary canary port 8312 available
- [ ] Logs destination available (`Manager/logs`)
- [ ] Rollback `reboot_tcp_ts.bat` + `tcp_ts.py` verified

---

## Preflight and deployment

- [ ] `python scripts/preflight_tcp_cutover.py --check --production-ready` → GO
- [ ] `python scripts/audit_tcp_acceptance.py parity` → PASS
- [ ] Backups complete (workbook, bat, configs, JSON)
- [ ] Pre-switch canary on 8312 passed (read-only)
- [ ] Launcher switch applied (`reboot_tcp_ts.bat` → `tcp_ts_v2.py`)
- [ ] Public smoke pass on 8302
- [ ] Admin smoke pass
- [ ] Mutation canary decision recorded (executed / skipped / N/A)
- [ ] Observation period complete

---

## Rollback readiness

- [ ] `tcp_ts.py` present (committed HEAD documented)
- [ ] v1 launcher content preserved or restorable from git
- [ ] v1 restart command tested or documented
- [ ] Incident archive path prepared
- [ ] Reconciliation owner identified

---

## Known cutover blockers (pre-resolution)

- [ ] Parent repository remote (`order-flow-website`) accessible
- [ ] Submodule PR merged
- [ ] Production secrets provisioned
- [ ] Production state directory prepared
- [ ] Deployed v1 build positively identified (optional parity confirmation)

---

## Working-tree artifacts (do not commit)

See Step 11 inventory in preflight report. Never stage:

- `daily_returns_secret_state.json` (TKP)
- `tcp_daily_returns_secret_state.json` (preview)
- `tcp_ts.py` local modifications
- `_runtime/` quarantine archives
