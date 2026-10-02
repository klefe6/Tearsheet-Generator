# Local Deployment — Action Items (Phase 1 output)

Read-only audit produced these unresolved items. Nothing here has been executed. Owners are suggested.

---

## Must resolve BEFORE VM purchase

### AI-01 — Relocate TKP source workbook out of the forbidden folder
- **Description:** TKP reads its source workbook from a hardcoded absolute path inside the protected, OneDrive-synced H&C Documents folder.
- **Evidence:** `tkp_ts.py:244-246` references `…\Hughes & Company - Documents\3_Advisors Marketing…\TKP\VADI\Copy of tkp_alex_old1.xlsx`.
- **Risk:** File will not exist on the VPS; TKP may fail to boot or silently fall back. Protected-folder coupling also blocks safe automation.
- **Recommended owner:** Kevin (provide the exact file) + Dan (parameterize path via env).
- **Blocking phase:** VM purchase / sizing (affects data-disk plan).
- **Suggested resolution:** Kevin supplies the file into `C:\AI_HANDOFF`; move it into a VPS-owned data dir; replace the constant with an env-configurable path.

### AI-02 — Decide automatic startup/recovery model
- **Description:** No auto-restart-on-reboot exists (no Scheduled Task, no Startup entry, PM2 list empty). Sizing/OS depends on the chosen supervisor (NSSM/Windows Service vs systemd).
- **Evidence:** `Get-ScheduledTask` (none), Startup folders (empty), `pm2 list` (empty), HKCU Run has `pm2-windows-startup` but no saved processes.
- **Risk:** A VPS reboot would leave all sites down until manual intervention.
- **Recommended owner:** Dan.
- **Blocking phase:** VM purchase (informs OS choice) and deployment.
- **Suggested resolution:** Adopt NSSM-managed Windows services (one per app + staff) with auto-start + auto-restart.

### AI-03 — Confirm Azure OS choice (Windows Server recommended)
- **Description:** Ratify Windows Server vs Ubuntu based on the audit evidence.
- **Evidence:** See `LOCAL_DEPLOYMENT_AUDIT.md` → Azure recommendation.
- **Risk:** Wrong OS choice multiplies porting effort and parity risk for financial calculations.
- **Recommended owner:** Kevin + Dan.
- **Blocking phase:** VM purchase.
- **Suggested resolution:** Approve Windows Server for Phase 2; defer Ubuntu to a later cost-optimization pass.

---

## Must resolve BEFORE deployment

### AI-04 — Fix live worktree `.git` ownership
- **Description:** `live-deploy-main` `.git` is owned by BUILTIN\Administrators; the normal user cannot run git there.
- **Evidence:** `git status` → "detected dubious ownership … owned by BUILTIN/Administrators".
- **Risk:** Deploy/update automation and audits break; encourages unsafe `safe.directory` overrides.
- **Recommended owner:** Dan.
- **Blocking phase:** Deployment.
- **Suggested resolution:** Establish a clean, user-owned deployment checkout on the VPS (do not carry over admin ACLs).

### AI-05 — Version-control or reliably back up production state
- **Description:** TKP/TCP/AGM state JSON and Y&Q csv/xlsx are untracked and depend on ad-hoc backups.
- **Evidence:** `git ls-files`/`check-ignore` → untracked; `backups/` has only two 0-byte reconcile markers.
- **Risk:** Data loss / no clean rollback point on migration.
- **Recommended owner:** Dan.
- **Blocking phase:** Deployment.
- **Suggested resolution:** Daily encrypted snapshots of state files + a private (non-public) state repo or object storage with retention.

### AI-06 — Pin uploader dependencies and standardize Python envs
- **Description:** Uploader `requirements.txt` uses version ranges; Y&Q runs under global `python` not `.venv310`; dashboard uses a different venv (`.venv13`).
- **Evidence:** `uploader/backend/requirements.txt` (ranges); `reboot_yq_ts.bat` (global python); `HomePage\.venv13`.
- **Risk:** Non-reproducible builds; parity drift.
- **Recommended owner:** Dan.
- **Blocking phase:** Deployment.
- **Suggested resolution:** Pin uploader deps (lockfile); run Y&Q under `.venv310`; document each app's interpreter.

### AI-07 — Move secrets to Azure Key Vault
- **Description:** Admin tokens, session secrets, and ingest tokens live in `.env` files (symlinked to repo root).
- **Evidence:** `.tkp_production.env`, `.tcp_production.env`, `.local_dev.env`, `.staff.env` (names only captured).
- **Risk:** Secret sprawl on the VM.
- **Recommended owner:** Dan.
- **Blocking phase:** Deployment.
- **Suggested resolution:** Store secrets in Key Vault; render restricted `.env` at boot; never commit.

### AI-08 — Reproduce Cloudflare Tunnel/Access ingress
- **Description:** Tunnel ingress is cloud-managed; no local config maps hostnames→ports.
- **Evidence:** `~/.cloudflared` has only `cert.pem`; `cloudflared` PID 7812 running.
- **Risk:** Public routing silently breaks on migration if the map is not reproduced.
- **Recommended owner:** Kevin (Cloudflare account) + Dan.
- **Blocking phase:** Deployment / DNS cutover.
- **Suggested resolution:** Export the tunnel ingress config from the Zero Trust dashboard; recreate pointing at the VPS (or use IIS/Nginx reverse proxy).

---

## Must resolve BEFORE DNS cutover

### AI-09 — Lock down admin surfaces
- **Description:** `/admin` is served on public app ports in addition to dedicated staff processes; dashboard binds `0.0.0.0:8006` with kill/reboot powers.
- **Evidence:** dashboard health checks `…:8301/admin`; `debug.py` `app.run(host='0.0.0.0', port=8006)`.
- **Risk:** Admin/dashboard exposure on a public host.
- **Recommended owner:** Dan.
- **Blocking phase:** DNS cutover.
- **Suggested resolution:** Restrict admin to staff hostnames behind Cloudflare Access; bind dashboard to localhost/VPN; enable secure cookies behind HTTPS.

### AI-10 — Reconcile latest values against baseline
- **Description:** Verify each app on the VPS matches the local baseline before cutover.
- **Evidence:** Reconciliation table (TKP 2026-07-23 StoneX $83,245.09; TCP 2026-06-24 NLV $43,007.30; AGM 2026-07-23 NLV $43,496.60).
- **Risk:** Silent calculation drift on migration.
- **Recommended owner:** Dan.
- **Blocking phase:** DNS cutover.
- **Suggested resolution:** Compare latest dates/values + a dry-run Glenn ingest returning `accepted, dry_run, no write`.

### AI-11 — Point uploader `*_INGEST_URL` at the VPS and validate inbound path
- **Description:** Uploader downstream targets must be repointed; decide inbound access model.
- **Evidence:** `uploader/backend/app/config.py` (`tkp/tcp/agm_ingest_url`, export gates).
- **Risk:** Broken or unsafe downstream ingest after migration.
- **Recommended owner:** Dan + Kevin.
- **Blocking phase:** DNS cutover.
- **Suggested resolution:** Set VPS-internal `*_INGEST_URL`; keep app ports private; validate with dry-run before enabling real export.

---

## Can resolve AFTER migration

### AI-12 — Repo reorg to planned `apps/{tkp,tcp,agm,yq}` + `shared/`
- **Description:** Live layout is flat; target structure not yet adopted.
- **Evidence:** flat worktree + reorg-prep worktrees.
- **Risk:** Low (cosmetic/maintainability).
- **Recommended owner:** Dan.
- **Blocking phase:** Post-migration.
- **Suggested resolution:** Perform reorg after parity is proven.

### AI-13 — Retire/repair unused PM2 startup or the stale `launch_all_services.py` reference
- **Description:** `run_all_services.bat` calls `launch_all_services.py` which is not present in the live worktree; PM2 startup registered but unused.
- **Evidence:** `run_all_services.bat:12`; `pm2 list` empty; glob for `launch_all_services.py` found none.
- **Risk:** Operator confusion.
- **Recommended owner:** Dan.
- **Blocking phase:** Post-migration.
- **Suggested resolution:** Remove or fix stale launcher; standardize on the chosen supervisor.

### AI-14 — Prune ~45 stale worktrees before/after imaging
- **Description:** Many feature/PR worktrees exist under `.worktrees\`.
- **Risk:** Larger image; accidental launch from wrong path (mitigated by dirty-root guards).
- **Recommended owner:** Dan.
- **Blocking phase:** Post-migration.
- **Suggested resolution:** Migrate only `live-deploy-main`; archive the rest.

---

## Compliance-dependent items

### AI-15 — Client-data handling & encryption at rest
- **Description:** State files and source workbooks contain client financial data; confirm regulatory retention/encryption obligations.
- **Recommended owner:** Kevin (compliance) + Dan.
- **Suggested resolution:** Encrypt data disk + backups; document retention; restrict access.

### AI-16 — Confirm data residency / region
- **Description:** Choose Azure region consistent with any client/regulatory residency requirements.
- **Recommended owner:** Kevin.
- **Suggested resolution:** Select region before provisioning.

---

## Questions requiring Kevin or Dan

1. **(Kevin)** Please provide the exact TKP source workbook (`Copy of tkp_alex_old1.xlsx`) via `C:\AI_HANDOFF` — the folder must not be browsed. Is this still the live TKP source, or has TKP fully moved to StoneX/state-JSON only?
2. **(Kevin/Dan)** Is TCP intentionally not updated since **2026-06-24** while TKP/AGM are current to 2026-07-23? (Freshness check.)
3. **(Dan)** Should the Glenn uploader stay on Fly.io (inbound to VPS) or be co-located on the VPS? This drives the firewall/ingress design.
4. **(Dan)** Confirm which admin surface is authoritative: the `/admin` route on public ports vs the dedicated staff processes (8321/8322/8324). Can the public-port `/admin` be disabled?
5. **(Kevin)** Who owns the Cloudflare account/tunnel, and can the ingress config be exported for reproduction?
6. **(Dan)** Is the dashboard (`HomePage\debug.py`) required in production, or is it an ops-only tool that can stay off the public VPS?
7. **(Kevin/Dan)** Confirm Azure OS = Windows Server and target VM size (see audit; sizing depends on concurrency + benchmark refresh load).
