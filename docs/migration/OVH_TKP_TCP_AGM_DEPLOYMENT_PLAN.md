# OVH TKP / TCP / AGM Deployment Plan

**Status: PLAN ONLY. Nothing in this document has been executed.**

Companion to `OVH_TKP_TCP_AGM_CURRENT_STATE.md`, `OVH_TKP_TCP_AGM_FILE_MANIFEST.json`, **`OVH_VPS_TARGET.md`** (authoritative purchased-server record), and **`OVH_TCP_PILOT_PACKAGE.md`** (exact first-pilot deployment inputs).

**Pilot: TCP.** Then TKP, then AGM. The reasoning is in the current-state report; the short version is that TCP is the only one of the three whose production data paths are already environment-driven and whose state already lives outside the repository, so it can boot on a clean VPS with zero code changes.

### Integration status (deployment-ready branch)

The code for this migration is integrated on branch **`feature/ovh-tkp-tcp-agm-ready`** (tip `49f8864`), built on `live-main @ 3cfda4f`. It folds in the six path-portability commits (`6ce7feb → 38eb0a2`) that centralize all data paths through `tearsheet_paths.py`, plus one dependency-completeness commit (`49f8864`) that adds the two missing packages to `requirements.txt`. The integrated diff is path-centralization only (plus two pre-approved TKP chart *title* strings and a no-op Y&Q resolver delegation) — no NAV/return/fee/drawdown/benchmark math, chart values, state schema, uploader payload, or auth logic changed. Validated read-only on the laptop: resolver/portability/config suite **123 passed**, TCP core reconciliation logic **61 passed / 13 skipped** (local-workbook skips), all modified modules byte-compile, and the resolver was executed under `vps-production` to confirm the `C:\H&C` mappings. Deploy *from this branch*, not from `live-main`.

### Official OVH target (purchased)

| Field | Value |
|-------|--------|
| Provider | OVHcloud US |
| Plan | VPS-3 2027 |
| Hostname | `vps-c0d9d928.vps.ovh.us` |
| Region | Virginia / US East |
| OpenStack zone | `os-us-east-va-2` |
| OS | Windows Server 2025 Standard (Desktop) |
| vCPU | 6 |
| RAM | 12 GB |
| Storage | 100 GB (additional disk disabled) |
| Snapshot | Enabled |
| Automated backup | Premium |
| Commitment | None; automatic renewal enabled |

Public IPv4/IPv6 are assigned in the OVH control panel and are **not** recorded in git (see `OVH_VPS_TARGET.md` → Network). Deployment status (purchased vs. software installed vs. cutover) is maintained in **`OVH_VPS_TARGET.md` → Current deployment status**.

---

## Target filesystem layout

```
C:\H&C\
├── apps\
│   ├── shared\
│   │   ├── .venv310\                       one shared Python 3.10 environment
│   │   ├── assets\
│   │   │   └── styles.css                  the only static asset any app needs
│   │   ├── tearsheet_runtime_mode.py
│   │   ├── tearsheet_local_admin.py
│   │   ├── tearsheet_gate_auth.py
│   │   ├── tearsheet_gate_ui.py
│   │   ├── tearsheet_disclosure.py
│   │   ├── tearsheet_header.py
│   │   ├── tearsheet_portal.py
│   │   ├── tearsheet_date_defaults.py
│   │   └── tearsheet_uploader_ingest.py
│   ├── tcp\                                pilot
│   │   ├── tcp_ts_v2.py
│   │   ├── tcp_config.py
│   │   ├── tcp_runtime_state.py
│   │   ├── tcp_state.py
│   │   ├── tcp_ledger.py
│   │   ├── tcp_calculations.py
│   │   ├── tcp_dashboard.py
│   │   ├── tcp_drawdown.py
│   │   ├── tcp_benchmarks.py
│   │   ├── tcp_daily_values.py
│   │   ├── tcp_admin.py
│   │   ├── tcp_public_sections.py
│   │   └── tcp_uploader_ingest.py
│   ├── tkp\
│   │   └── tkp_ts.py
│   └── agm\
│       ├── algominds_daily_balances.py     root-level: reaches into Momentum Pacer\data
│       ├── algominds_benchmark_daily.py    root-level: reaches into Momentum Pacer\data
│       ├── algominds_daily_fees.py
│       ├── algominds_daily_accounting.py
│       ├── algominds_monthly_summary.py
│       ├── algominds_account_stats.py
│       ├── algominds_monthly_stats.py
│       ├── algominds_fee_payment_evidence.py
│       ├── algominds_drawdown_semantics.py
│       ├── algominds_portal_registry.py
│       ├── program_account_stats.py
│       └── Momentum Pacer\
│           └── mp_ts.py
├── data\
│   ├── tcp\
│   │   ├── tcp_daily_returns_secret_state.json
│   │   ├── tcp_daily_returns_secret_state.backup.json
│   │   ├── tcp_daily_returns_secret_state.lock      created at runtime
│   │   └── benchmark\
│   │       ├── tcp_benchmark_cache.json
│   │       ├── tcp_benchmark_btc_cache.json
│   │       └── tcp_benchmark_eth_cache.json
│   ├── tkp\
│   │   ├── daily_returns_secret_state.json
│   │   └── tkp_source_workbook.xlsx                 requires Kevin to supply
│   └── agm\
│       ├── momentum_pacer_manual_daily_rows.json
│       ├── Momentum Fee Calculation.xlsx
│       ├── daily_balances\
│       │   └── balances_210TGG51_20OCT2025_07JUL2026.csv
│       └── benchmarks\
│           ├── GSPC_daily.csv
│           └── NDX_daily.csv
├── config\                                 non-secret, readable by operators
│   ├── tcp.env
│   ├── tkp.env
│   ├── agm.env
│   └── staff.env
├── secrets\                                ACL-restricted to the service account + Administrators
│   ├── tcp.env
│   ├── tkp.env
│   ├── agm.env
│   └── ingest.env
├── logs\
│   ├── tcp\     tcp_stdout.log, tcp_stderr.log, glenn_uploader_ingest_tcp_audit.jsonl
│   ├── tkp\     tkp_stdout.log, tkp_stderr.log, glenn_uploader_ingest_tkp_audit.jsonl
│   └── agm\     agm_stdout.log, agm_stderr.log, glenn_uploader_ingest_agm_audit.jsonl
├── backups\
│   ├── tcp\
│   ├── tkp\
│   └── agm\
└── deployment\
    ├── requirements.txt
    ├── nssm\                               nssm.exe plus per-service install scripts
    ├── validation\                         optional one-time pytest copies
    └── baseline\                           OVH_TKP_TCP_AGM_RECONCILIATION_BASELINE.json
```

### Two deviations from the generic layout, driven by the actual code

**AGM is not a flat app directory.** `mp_ts.py` lives in a `Momentum Pacer` subfolder while the `algominds_*` modules it imports live one level up and build paths as `Path(__file__).parent / "Momentum Pacer" / "data" / ...`. The layout above preserves that parent-child relationship exactly. Flattening it breaks the pinned CSV and benchmark cache paths.

**`shared\` must be importable, and that includes the TCP modules.** All three apps use flat `import tcp_admin`-style imports with no package structure. Because `tcp_admin` transitively imports `tcp_config`, `tcp_public_sections`, `tcp_calculations`, `tcp_ledger`, `tcp_dashboard`, and `tcp_drawdown`, TKP and AGM cannot import at all unless that TCP module set is on the path. Two workable options:

- **Option A (recommended for the pilot):** set `PYTHONPATH=C:\H&C\apps\shared;C:\H&C\apps\tcp` in each NSSM service environment. One copy of every module, no duplication.
- **Option B:** copy the shared and TCP module set into each app directory. Simpler path handling, but three copies to patch.

Decide this at step 4 and keep it consistent across all three apps.

---

## Step 1 — Prepare the Windows VPS

Not executed. Target instance: **`vps-c0d9d928.vps.ovh.us`** (`os-us-east-va-2`, VPS-3 2027). Connect using credentials from OVH / your password manager only — never commit them.

1. RDP in and confirm the build matches `OVH_VPS_TARGET.md`: Windows Server 2025 Standard (Desktop), 6 vCPU, 12 GB RAM, 100 GB disk, US East (Virginia).
2. Apply all pending Windows Updates and reboot.
3. Set the timezone. **Use the same timezone as the laptop (UTC-4 / US Eastern).** Several code paths and all the date comparisons in the reconciliation baseline are timezone-sensitive — TCP stamps `updated_at` in UTC but the state dates are local business dates.
4. Create a dedicated low-privilege local service account, for example `svc_hc_tearsheets`. Grant "Log on as a service". Do not use an administrator account to run the services.
5. Confirm the OVH snapshot and premium backup are both enabled and note the schedule.
6. Confirm outbound HTTPS works (needed for `pip`, and for `quantstats` / `yfinance` benchmark downloads).
7. Leave inbound firewall closed to 8301 / 8302 / 8304. **These apps bind loopback only and must never be exposed directly.** Public access will come later via a Cloudflare tunnel.
8. Install nothing else yet — no Cloudflare tunnel, no DNS change.

**Verification:** `systeminfo`, `Get-TimeZone`, and a successful `Invoke-WebRequest https://pypi.org` from the server.

---

## Step 2 — Create `C:\H&C`

Not executed. **Do not create this directory until step 1 is signed off** (hard safety rule 22 applies to the current inventory phase, not to the future execution of this plan).

1. Create the full tree exactly as laid out above.
2. ACLs:
   - `C:\H&C\apps` — read and execute for the service account; write for Administrators only.
   - `C:\H&C\data` — read and write for the service account. All three apps write here.
   - `C:\H&C\logs` — read and write for the service account.
   - `C:\H&C\config` — read for the service account.
   - **`C:\H&C\secrets` — read for the service account only, plus Administrators. Remove inherited permissions and remove `Users`.** This directory holds the admin tokens, session secrets, and the ingest token.
   - `C:\H&C\backups` — write for Administrators and whatever backup job you add.
3. Exclude `C:\H&C\data` from any file-sync or indexing agent. The whole point of this migration is to get authoritative state out of a sync-managed folder.

**Verification:** `icacls C:\H&C\secrets` shows no `Users` entry.

---

## Step 3 — Install the runtime

Not executed.

1. Install **Python 3.10.x 64-bit** to `C:\Python310`, matching production. Do not install 3.12 or 3.13 — the current reconciliation baseline was produced under `numpy 2.2.6` / `pandas 2.2.3` / `quantstats 0.0.64` on 3.10.0, and changing the interpreter during a migration means you can no longer tell a migration bug from a version bug.
2. Create the shared virtual environment:
   `C:\Python310\python.exe -m venv C:\H&C\apps\shared\.venv310`
3. `python -m pip install --upgrade pip`
4. `pip install -r C:\H&C\deployment\requirements.txt`
5. **`openpyxl==3.1.5` and `dash-bootstrap-components==2.0.3` are now in `requirements.txt`** on the deployment-ready branch (commit `49f8864`), so step 4 installs them. Without them every app fails at import. (On `live-main` they were missing and had to be installed by hand — that gap is closed on this branch. If you ever deploy from `live-main` directly, install them manually.)
6. Download `nssm.exe` to `C:\H&C\deployment\nssm\`.
7. `pip freeze > C:\H&C\deployment\vps_freeze.txt` and diff it against a `pip freeze` taken from the laptop venv. Investigate any difference before proceeding.

**Decision point:** one shared venv, as recommended. All three apps are pinned to an identical dependency set, there are no conflicts to isolate, and TKP and AGM already import TCP modules — per-app environments would mean three copies of the same packages and triple the patching surface for no benefit.

**Verification:** `C:\H&C\apps\shared\.venv310\Scripts\python.exe -c "import dash, dash_bootstrap_components, flask, pandas, numpy, plotly, openpyxl, yfinance, quantstats; print('ok')"`

---

## Step 4 — Deploy pilot code (TCP)

Not executed.

1. Source of truth is the **deployment-ready branch `feature/ovh-tkp-tcp-agm-ready` (tip `49f8864`)**, based on `live-main @ 3cfda4fdde5eaa8fae42c87b56d30d34aa717f68`. Use the branch worktree, which already contains the portability + dependency work. The exact file list is in `OVH_TCP_PILOT_PACKAGE.md` §2.
2. Copy the TCP code package per the manifest: `tcp_ts_v2.py` plus the twelve `tcp_*` modules into `C:\H&C\apps\tcp\`.
3. Copy the shared module package into `C:\H&C\apps\shared\`, **including the central resolver `tearsheet_paths.py`** (now required — `tcp_ts_v2.py` and `tcp_config.py` import it) and `assets\styles.css` from the branch, not the dev checkout.
4. **Resolve all reparse points.** The live worktree contains five links back into the dev checkout. Use a link-following copy or copy from the real targets. A plain `xcopy` or a non-link-aware robocopy will produce zero-byte files.
5. Explicitly do **not** copy: `tcp_ts.py` (legacy monolith whose `__main__` block would bind 8302 and conflict), `.git`, `.worktrees/`, `__pycache__/`, `tests/`, `backups/`, `_runtime/`, `_restart_logs/`, any `reboot_*` launcher, any `.env` file, or any other application.
6. Set the `PYTHONPATH` decision from the layout section.
7. Verify no file in `C:\H&C\apps` is zero bytes and that no reparse points survived the copy.

**Verification:** `C:\H&C\apps\shared\.venv310\Scripts\python.exe -c "import tcp_config; print(tcp_config.load_config())"` with the config env loaded — it should print a `TCPConfig` without touching the network or the workbook.

---

## Step 5 — Copy pilot data (TCP)

Not executed. **Copy, never move. The laptop remains authoritative until cutover.**

1. Quiesce writes: confirm no uploader export is running and no operator has the admin UI open. Do **not** stop the laptop service — just pick a quiet window.
2. Re-hash the source immediately before copying and compare against the baseline:
   `C:\Users\H&CDanHughes\AppData\Local\HughesCompany\TCP\state\tcp_daily_returns_secret_state.json`
   expected `7094B6B513999B39F32304350016C6A9EAC4C07321D515821357159FD7934386` (81,311 bytes, 182 records, revision 83).
   **If the hash has changed, the laptop has taken new data since the baseline. Re-capture the baseline before continuing.**
3. Copy to `C:\H&C\data\tcp\tcp_daily_returns_secret_state.json`.
4. Copy the backup file to `C:\H&C\data\tcp\tcp_daily_returns_secret_state.backup.json` (optional; the app recreates it on first write).
5. **Do not copy the `.lock` file.** It is a runtime artifact and must be created locally.
6. Copy the three benchmark caches from `...\HughesCompany\TCP\benchmark\` to `C:\H&C\data\tcp\benchmark\`. This lets you first-boot with `TCP_V2_SKIP_BENCHMARK_FETCH=1` and no outbound market-data dependency. Do **not** copy the stale July duplicates from `_runtime\`.
7. Do not copy `tcp_alex.xlsx`. In `json_active` mode the workbook is only a fallback, and step 6 below disables that fallback deliberately.
8. Do not copy the ingest audit JSONL. Archive it to `C:\H&C\backups\tcp\` for retention if you want the history; the VPS starts a fresh file.
9. Re-hash the destination and confirm it matches the source byte for byte.

**Verification:** source and destination SHA-256 match.

---

## Step 6 — Configure the pilot environment

Not executed.

Create `C:\H&C\config\tcp.env` with non-secret values:

```
TCP_V2_STATE_MODE=json_active
TCP_V2_BIND_PORT=8302
TCP_V2_STATE_PATH=C:\H&C\data\tcp\tcp_daily_returns_secret_state.json
TCP_V2_STATE_BACKUP_PATH=C:\H&C\data\tcp\tcp_daily_returns_secret_state.backup.json
TCP_V2_STATE_LOCK_PATH=C:\H&C\data\tcp\tcp_daily_returns_secret_state.lock
TCP_V2_BENCHMARK_CACHE_PATH=C:\H&C\data\tcp\benchmark\tcp_benchmark_cache.json
TCP_V2_BENCHMARK_BTC_CACHE_PATH=C:\H&C\data\tcp\benchmark\tcp_benchmark_btc_cache.json
TCP_V2_BENCHMARK_ETH_CACHE_PATH=C:\H&C\data\tcp\benchmark\tcp_benchmark_eth_cache.json
TCP_V2_ALLOW_WORKBOOK_FALLBACK=false
TCP_V2_SKIP_BENCHMARK_FETCH=1
TEARSHEET_MODE=public
PYTHONIOENCODING=utf-8
GLENN_UPLOADER_INGEST_ENABLED=false
```

Four of those lines are deliberate changes from the laptop and each has a reason:

- **`TCP_V2_ALLOW_WORKBOOK_FALLBACK=false`** — the laptop leaves this at its default of `true`. On the VPS a missing or corrupt JSON state would then silently fall back to the workbook and serve read-only stale data that looks plausible. Fail loudly instead.
- **`TCP_V2_BENCHMARK_BTC_CACHE_PATH` / `..._ETH_CACHE_PATH`** — unset on the laptop, where they default to siblings of the SPXTR override. Set them explicitly so the behavior is not implicit.
- **`TCP_V2_SKIP_BENCHMARK_FETCH=1`** — for the first private boot, so the app comes up on copied caches with no network dependency. Remove it once reconciliation passes.
- **`GLENN_UPLOADER_INGEST_ENABLED=false`** — **critical.** The VPS must not accept ingest while the laptop is still authoritative, or the two will diverge. Enable it only at cutover.

Create `C:\H&C\secrets\tcp.env` containing `TCP_V2_ADMIN_TOKEN` and `TCP_V2_SESSION_SECRET`. Transfer the values out of band (password manager, not chat, not a file copy). Create `C:\H&C\secrets\ingest.env` with `GLENN_UPLOADER_INGEST_TOKEN`, ready but inert while ingest is disabled.

Do **not** set `TEARSHEET_LOCAL_DIRECT_ADMIN`. It is set to `1` on the laptop via `.local_dev.env` and has no business on a server.

**Verification:** `icacls C:\H&C\secrets\tcp.env` shows only the service account and Administrators.

---

## Step 7 — Create the pilot NSSM service

Not executed.

```
nssm install HC-TCP-Public "C:\H&C\apps\shared\.venv310\Scripts\python.exe"
nssm set HC-TCP-Public AppParameters "C:\H&C\apps\tcp\tcp_ts_v2.py"
nssm set HC-TCP-Public AppDirectory  "C:\H&C\apps\tcp"
nssm set HC-TCP-Public AppStdout     "C:\H&C\logs\tcp\tcp_stdout.log"
nssm set HC-TCP-Public AppStderr     "C:\H&C\logs\tcp\tcp_stderr.log"
nssm set HC-TCP-Public AppRotateFiles 1
nssm set HC-TCP-Public AppRotateBytes 10485760
nssm set HC-TCP-Public Start          SERVICE_AUTO_START
nssm set HC-TCP-Public ObjectName     ".\svc_hc_tearsheets" <password>
nssm set HC-TCP-Public AppEnvironmentExtra <contents of config\tcp.env + secrets\tcp.env + secrets\ingest.env>
nssm set HC-TCP-Public AppExit Default Restart
nssm set HC-TCP-Public AppThrottle   10000
nssm set HC-TCP-Public AppStopMethodConsole 5000
```

Three settings matter specifically for these apps:

- **Process-tree termination.** The venv `python.exe` is a launcher stub that spawns the base interpreter as a child. NSSM must kill the whole tree or restarts leak orphaned listeners holding port 8302.
- **`AppExit Default Restart` with `AppThrottle 10000`.** Auto-restart is the main capability the laptop lacks. The 10-second throttle stops a boot-time failure (missing state, bad ACL) from becoming a restart storm.
- **`AppRotateFiles`.** Neither TCP nor the other apps rotate anything themselves; TCP's `logging.basicConfig` writes to stderr with no file handler.

Do **not** create `HC-TCP-Staff` yet. Port 8322 has no listener today, `Manager\startup_contract.json` classifies it as manual only, and running a staff process alongside the public one is an unnecessary variable during a pilot.

**Verification:** `nssm dump HC-TCP-Public` reviewed before first start. Confirm no secret value appears in any log.

---

## Step 8 — Start privately

Not executed. **Private means loopback and RDP only. No tunnel, no DNS, no public hostname.**

1. `nssm start HC-TCP-Public`
2. `Get-NetTCPConnection -State Listen | Where LocalPort -eq 8302` — confirm it is bound to **127.0.0.1**, not `0.0.0.0`.
3. `Invoke-WebRequest http://127.0.0.1:8302/healthz` from an RDP session.
4. Read `C:\H&C\logs\tcp\tcp_stderr.log` end to end. Confirm no `StateNotFound`, no `StateLoadError`, no workbook-fallback warning, and no benchmark warnings beyond the expected skip-fetch notice.
5. Load `http://127.0.0.1:8302/` in a browser on the server and confirm the page renders, the title is `H&C - TCP`, the NAV chart draws, and the drawdown table populates.
6. Confirm the firewall still blocks inbound 8302.

**Expected `/healthz` on a correct deployment:** `state_revision: 83`, `record_count: 182`, `completed_rows: 182`, `first_completed_date: 2026-01-20`, `latest_completed_date: 2026-09-30`, `data_source: json`, `state_mode: json-active`, `state_writable: true`, `recovery_status: normal`, `adapter_status: ok`, `debug: false`, `port: 8302`.

**Stop conditions.** Roll back and diagnose rather than pushing forward if: `data_source` is `workbook` or `workbook_fallback`; `recovery_status` is anything but `normal`; `state_writable` is `false` (an ACL problem); `/healthz` returns 503 (no snapshot); or `port` is 8312 (the env file was not applied and the preview default won).

---

## Step 9 — Reconcile against local

Not executed.

Compare the VPS against `OVH_TKP_TCP_AGM_RECONCILIATION_BASELINE.json`. For TCP every one of these must match exactly:

| Check | Expected |
|---|---|
| `/healthz` `state_revision` | `83` |
| `/healthz` `record_count` and `completed_rows` | `182` |
| `/healthz` `first_completed_date` | `2026-01-20` |
| `/healthz` `latest_completed_date` | `2026-09-30` |
| `/healthz` `data_source` | `json` |
| `/healthz` `state_mode` | `json-active` |
| `/healthz` `state_writable` | `true` |
| State file SHA-256 | `7094B6B513999B39F32304350016C6A9EAC4C07321D515821357159FD7934386` |
| State file size | 81,311 bytes |
| Latest record `Date` | `2026-09-30` |
| Latest record `NLV` | `60667.74` |
| Latest record `nav-x1` | `52743.467` |
| Latest record `HWM` | `52836.417` |
| Page `<title>` | `H&C - TCP` |
| Source commit | `3cfda4fdde5eaa8fae42c87b56d30d34aa717f68` |

Then do a visual side-by-side of the laptop on `http://127.0.0.1:8302/` and the VPS on its loopback: monthly performance calendar, NAV chart end point, drawdown table, and the "data current to" header label.

**Note on the state hash.** It will only match if the laptop has taken no new data since the baseline. If the laptop has ingested a new day, re-capture the baseline and re-copy. Treat a hash mismatch as "re-sync needed", not as a VPS defect — but never as something to ignore.

**Reconciliation is the gate.** Do not proceed to step 10 with any unexplained difference.

---

## Step 10 — Reboot-test service recovery

Not executed. This step validates the capability the laptop does not have.

1. Full `Restart-Computer`. On the way back up, with **no interactive logon**, confirm 8302 is listening and `/healthz` is correct. This is the single most important improvement over the current setup, where startup depends on a user Startup-folder item.
2. Hard-kill test: `Stop-Process` the listener PID. Confirm NSSM restarts it within the throttle window and `/healthz` recovers.
3. Kill the venv stub parent rather than the child and confirm no orphan is left holding port 8302. This is where a missing process-tree-kill setting shows up.
4. Verify log rotation triggers and that stdout and stderr are both captured.
5. Confirm `tcp_daily_returns_secret_state.lock` is created and released cleanly and that no `.tmp` files are left in `C:\H&C\data\tcp\`.
6. Re-run the step 9 checks after the reboot. The state hash must be unchanged — a resident app with ingest disabled must not have written anything.
7. Take an OVH snapshot and label it as the known-good pilot baseline.

Steps 8–10 are **Phase 1 (private pilot)** of the Glenn uploader lifecycle below. Passing step 9 does **not** permit enabling VPS ingest.

---

## Glenn uploader lifecycle — mandatory gate (TCP)

**Plan only — not executed.** This gate is mandatory for TCP production cutover. Full detail and checklists
also live in `OVH_TCP_PILOT_PACKAGE.md` §8. The VPS pilot keeps
`GLENN_UPLOADER_INGEST_ENABLED=false` until Phase 3.

### Production path (migration audit)

```
Glenn uploader (Fly.io) → TCP_INGEST_URL
  → POST https://<host>/api/uploader/ingest-daily-row
  → Bearer GLENN_UPLOADER_INGEST_TOKEN
  → TCP → tcp_daily_returns_secret_state.json → apply_tcp_recalculation()
```

### Phase 1 — Private pilot

- Laptop remains **authoritative**; Glenn keeps sending to the **existing** production TCP target.
- VPS ingest **disabled**; VPS state is a reconciled copy only (**no dual writers**).
- Maps to steps 8–10 (private start, reconcile, reboot-test).

### Phase 2 — Pre-cutover resync

- Do not cut over using an **old** baseline snapshot.
- Capture latest laptop TCP state: latest date, record count, `state_revision`, state file SHA-256.
- Re-copy authoritative state to the VPS; reconcile again against the **new** capture.
- Glenn on VPS remains **disabled**.

### Phase 3 — Glenn cutover

**URL:** Prefer keeping  
`https://tcp-ts.hcresearch.ltd/api/uploader/ingest-daily-row`  
if Cloudflare can route that hostname to the VPS (Glenn may need **no** `TCP_INGEST_URL` change). If a
different hostname is required, document that Fly.io **`TCP_INGEST_URL`** must change at cutover (same
path suffix).

**Contract:**

- `GLENN_UPLOADER_INGEST_TOKEN` on the VPS must match Glenn's downstream bearer token; **never** commit values.
- **One** authoritative ingest target only; laptop must stop being authoritative as VPS becomes authoritative.
- Enable `GLENN_UPLOADER_INGEST_ENABLED=true` on the VPS **only** in this controlled window (after Phase 2 resync).
- Disable ingest on the laptop in the same window.

**Preflight utility (required):** `uploader/backend/scripts/verify_downstream_ingest.py` — read-only
`dry_run: true` probes per program; does not export or mark rows exported. Run from `uploader/backend/`
before and after routing changes; use `--strict` for go-live. See
`docs/downstream_export_go_live_runbook.md`. Run safe preflight **before** enabling production ingest on
the VPS (token/URL/routing); re-run after `GLENN_UPLOADER_INGEST_ENABLED=true` to confirm TCP accepts
probes without `ingest_disabled`.

### Phase 4 — First live ingest test

After cutover, submit the first real TCP row through Glenn's normal workflow. Verify: persisted HTTP
response; correct date/NLV; `state_revision` and record count; VPS state file updated; recalculation and
public display; ingest audit line; **laptop state did not** take the write.

On failure: no competing manual rows; preserve logs/responses; fix config or execute documented rollback
(disable VPS ingest, restore laptop ingest authority, revert Cloudflare/`TCP_INGEST_URL` if changed).

**Production TCP on the VPS is not declared live until Phase 4 passes.**

---

## Step 11 — Deploy the remaining two tearsheets

Not executed.

### 11a — TKP (second)

**TKP has a blocking prerequisite and cannot be deployed until it is resolved.** `tkp_ts.py:244` hardcodes a path into `C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents\...` and calls `sys.exit(1)` at import if the file is missing or unreadable (lines 379–387 and 444–452). There is no environment override on `live-main`.

Pick one route before touching the VPS:

- **Route A (recommended): deploy from the integrated branch.** `feature/ovh-tkp-tcp-agm-ready` already contains the path-portability work (`tearsheet_paths.py` with `HC_TKP_SOURCE_WORKBOOK` / `HC_TKP_STATE_PATH`, plus `HC_APP_ENV=vps-production` → `C:\H&C\data\tkp`). This was executed and verified on the branch: under the VPS profile the TKP state resolves to `C:\H&C\data\tkp\daily_returns_secret_state.json` and the workbook to `C:\H&C\data\tkp\tkp_source_workbook.xlsx`, and an explicit VPS workbook override does **not** fall back to the protected folder. The `sys.exit(1)` import blocker on `live-main` is therefore resolved by this branch. Kevin still supplies the workbook *file* itself (data, not code) via `C:\AI_HANDOFF`.
- **Route B: supply the workbook.** Kevin places the file in `C:\AI_HANDOFF`, it is copied to `C:\H&C\data\tkp\tkp_source_workbook.xlsx`, and the single literal in `tkp_ts.py` is pointed at it. Smaller change, but it leaves a hardcoded absolute path in production.

Route A is better. It also fixes AGM's path situation for free in step 11b.

Then: copy `tkp_ts.py`, copy the state JSON (431,598 bytes, SHA-256 `93575C2F...`, 896 records), place the workbook, create `C:\H&C\config\tkp.env` and `C:\H&C\secrets\tkp.env` with `TKP_ADMIN_TOKEN` and `TKP_SESSION_SECRET`, install `HC-TKP-Tearsheet` on 8301 with ingest disabled, and start privately.

Two TKP-specific cautions:

- **No benchmark cache, no skip flag.** TKP downloads benchmarks via `quantstats` and `yfinance` on every boot. The first VPS start will hit the network. If that fails, the benchmark columns degrade — check the rendered page, not just `/healthz`.
- **Resolve the row-count discrepancy first.** `/healthz` reports `rows_loaded: 766` while the state JSON holds 896 records. They come from different sources (the Excel-derived NAV frame bounded by `FORCE_LAST_EXCEL_ROW = 715` versus the full persisted editor table). Until that is explained, `rows_loaded` is not a usable VPS-versus-laptop check — compare both numbers independently and expect 766 and 896.

### 11b — AGM (third)

1. Copy `Momentum Pacer\mp_ts.py` into `C:\H&C\apps\agm\Momentum Pacer\` and the eleven root-level `algominds_*` and `program_account_stats` modules into `C:\H&C\apps\agm\`. **Preserve that parent-child relationship** — `algominds_daily_balances.py` and `algominds_benchmark_daily.py` build paths as `Path(__file__).parent / "Momentum Pacer" / "data" / ...`.
2. Do not copy `Momentum Pacer\calc_engine.py` (legacy, unimported).
3. **Resolve the fee workbook symlink.** The live-worktree entry is a 0-byte `SymbolicLink`; the real 365,554-byte file is at `C:\Coding Projects\Tearsheet Generator\Momentum Pacer\Momentum Fee Calculation.xlsx`. Copy from the real target. Hash the destination and confirm it is **not** `B63A1CBEA8A7F81803D695784FF2DD38383DA6BCE84F50CFEB98C9CCFE851A1E` — that is the hash of an empty file.
4. Copy the manual rows JSON (7,658 bytes, SHA-256 `62612BD2...`, 59 rows), the pinned CSV (17,852 bytes, SHA-256 `D4B5B781...`), and the two benchmark CSVs.
5. **Generate real AGM secrets.** `AGM_ADMIN_TOKEN` and `AGM_SESSION_SECRET` are not set in production today and fall back to code defaults. Create `C:\H&C\secrets\agm.env` with fresh values — this is a security improvement, so verify the admin login still works afterwards.
6. Create `C:\H&C\config\agm.env` with `MP_TS_PRODUCTION=1`, `AGM_BIND_PORT=8304`, `AGM_BENCHMARK_CACHE_ONLY=1` for the first boot, `PYTHONIOENCODING=utf-8`, and `GLENN_UPLOADER_INGEST_ENABLED=false`.
7. Install `HC-AGM-Tearsheet` with `AppDirectory` set to `C:\H&C\apps\agm\Momentum Pacer` — the current launcher `cd`s there before starting, and the working directory matters.
8. Start privately and reconcile.

---

## Step 12 — Reconcile each

Not executed.

| Check | TKP expected | AGM expected |
|---|---|---|
| `/healthz` `status` | `ready` | `ready` |
| `/healthz` counts | `rows_loaded: 766` | `daily_rows: 184`, `months_loaded: 10`, `daily_fee_days: 166`, `spx_daily_rows: 208` |
| `/healthz` error fields | `admin_auth: configured` | `load_error`, `benchmark_load_error`, `daily_fees_load_error` all `null` |
| State record count | 896 | 59 manual rows |
| State SHA-256 | `93575C2F3F6B924D716A648B0AE0E957E6FD7FBF31A4B582EF3BA56BEB8A7D3D` | `62612BD23E730B94AC70A5DBDB4B98E1A8079D9721E2515D411C252157CBD5B6` |
| Latest date | `2026-09-30` | `2026-09-30` |
| Latest authoritative value | NAV `$194,537.69`, HWM `$194,562.81` | `actual_nlv` `43737.57` |
| Page `<title>` | `H&C - TKP` | `Algominds - Momentum Pacer` |
| Source commit | `3cfda4f...` | `3cfda4f...` |

For AGM also confirm the fee workbook actually loaded (a 0-byte symlink copy shows up as a `load_error`, not a crash) and that the first manual row date is still `2026-07-11`, which proves the CSV and manual JSON are still adjacent rather than overlapping.

Reboot-test each new service as in step 10 before moving on.

---

## Step 13 — Configure staging ingress

Not executed.

The current `Cloudflared` Windows service on the laptop is **remotely managed via a tunnel token embedded in the service binary path**, so the hostname-to-port ingress mapping lives in the Cloudflare dashboard, not on the machine (`%USERPROFILE%\.cloudflared` holds only `cert.pem`). That means the VPS needs its own tunnel and its own dashboard ingress rules; there is no local config file to copy.

1. Install `cloudflared` on the VPS and create a **new, separate** tunnel. Do not reuse the laptop's tunnel or token.
2. Add **staging** hostnames only — something like `tcp-ts-vps.hcresearch.ltd` → `http://127.0.0.1:8302`. Do **not** touch `tcp-ts.hcresearch.ltd` or any other live hostname.
3. Put Cloudflare Access in front of every staging hostname so only you can reach it.
4. Keep the inbound Windows firewall closed. The tunnel connects outbound; the app stays on loopback.
5. Verify each staging hostname resolves and serves the correct app, then re-run the step 9 and 12 reconciliation checks through the tunnel rather than loopback — this catches `Host` header and cookie-`Secure` issues that loopback testing hides.
6. Leave `GLENN_UPLOADER_INGEST_ENABLED=false` on the VPS throughout this step.

This step changes nothing about existing DNS or existing tunnels. The live hostnames continue pointing at the laptop.

---

## Step 14 — Prepare production cutover

Not executed. **This step executes Glenn lifecycle Phases 2–4 for TCP** (see mandatory gate above). It is
not a substitute for that gate.

Per-app cutover sequence, one app at a time, starting with TCP:

1. Announce a freeze window. Confirm no uploader export is in flight.
2. **Phase 2 — final resync.** Re-hash laptop `tcp_daily_returns_secret_state.json`; record latest date,
   record count, `state_revision`, and SHA-256; re-copy to the VPS if anything moved; reconcile against
   the **new** capture (not the original pilot baseline).
3. **Routing decision.** Prefer repointing Cloudflare so `tcp-ts.hcresearch.ltd` → VPS tunnel (ingest URL
   unchanged). If hostname must change, plan the Fly.io `TCP_INGEST_URL` update for step 7.
4. Run `uploader/backend/scripts/verify_downstream_ingest.py` (and `--strict` when appropriate) with
   dry-run probes **before** enabling VPS ingest — confirms URL, token, and routing without mutating
   uploader export state.
5. Repoint production Cloudflare (`tcp-ts.hcresearch.ltd`) from laptop tunnel to VPS tunnel when using
   hostname preservation.
6. Set `GLENN_UPLOADER_INGEST_ENABLED=false` on the **laptop** and restart. Then set
   `GLENN_UPLOADER_INGEST_ENABLED=true` on the VPS and restart `HC-TCP-Public`. **Exactly one host may
   accept ingest.** Remove `TCP_V2_SKIP_BENCHMARK_FETCH` on the VPS when live benchmarks are desired.
7. Update Fly.io `TCP_INGEST_URL` **only if** step 3 required a new hostname (same
   `/api/uploader/ingest-daily-row` suffix). Do not rotate `DOWNSTREAM_INGEST_TOKEN` unless planned;
   VPS `GLENN_UPLOADER_INGEST_TOKEN` must stay in sync — never commit token values.
8. Re-run `verify_downstream_ingest.py` after VPS ingest is enabled; then execute **Phase 4 — first live
   ingest test** (one real Glenn row; verify persistence, revision, recalculation, public page, audit,
   and that laptop state did not update).
9. Watch for one full business day: `/healthz` revision increments after the day's ingest, the audit
   JSONL grows, `recovery_status` stays `normal`, no `.tmp` files accumulate, and the public page shows
   the new date.
10. Keep the laptop running read-only, ingest disabled, as a warm rollback for at least one week.
    Rollback: disable VPS ingest, re-enable laptop ingest, repoint Cloudflare (and `TCP_INGEST_URL` if
    changed).
11. Only after all three apps are cut over and stable should the staff services, the retirement of
    `Manager\launch_all_services.py` for these three entries, and the `C:\H&C\backups` job be considered.

### Cutover risks to have an answer for in advance

| Risk | Mitigation |
|---|---|
| Both hosts accepting ingest simultaneously | Enforce the step 3 and 4 ordering strictly; verify with `/healthz` revision on both before and after |
| Laptop takes new data between final sync and DNS flip | Keep the freeze window short; re-hash immediately before the flip, not the day before |
| Uploader retries against the old host | The uploader makes one attempt per row with no retry loop, and failed rows are not marked exported, so re-export is safe — but only because the ingest endpoints are idempotent per date (`unchanged` still reports `persisted=True`) |
| TKP cannot start because of the protected-folder workbook | Resolve at step 11a. Do not reach cutover with this open |
| AGM silently loads an empty fee workbook | Hash the destination file after copying; `B63A1CBE...` means you copied the symlink |
| Non-atomic TKP/AGM writes corrupted by an NSSM restart mid-write | Do not restart those services during the uploader's daily window; consider merging an atomic-write fix before cutover |
| Secrets exposed in NSSM dumps or logs | Review `nssm dump` output and grep the logs for token names before going live |

---

## What this plan deliberately does not do

- Does not touch DNS or Cloudflare for any existing hostname.
- Does not migrate Y&Q (8303), the HomePage dashboard (8006), `hughesandco.ltd`, SiteGround, Morning Prep, Order Flow, Signal Analyzer, or any other H&C application.
- Does not migrate or modify the Glenn uploader application itself; only one configuration value per app changes, and only at cutover.
- Does not create staff services on 8321 / 8322 / 8324.
- Does not deploy `tcp_ts.py` or `Momentum Pacer\calc_engine.py`.
- Does not copy a virtual environment between machines.
- Does not read, list, or traverse `C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents`. The one file TKP needs from there must be supplied by Kevin via `C:\AI_HANDOFF`, or made unnecessary by merging the path-portability work.
