# OVH TCP Pilot Package

**Status: DEPLOYMENT INPUTS ONLY. Nothing here has been executed on the VPS.**

This is the exact, self-contained input set for the **first private OVH migration (TCP pilot)**.
It is produced from the reviewed deployment-ready branch and is the authoritative answer to
"what do we copy, where does it go, what env do we set, and how do we know it worked."

Companion documents (same folder):
`OVH_TKP_TCP_AGM_CURRENT_STATE.md`, `OVH_TKP_TCP_AGM_FILE_MANIFEST.json`,
`OVH_TKP_TCP_AGM_RECONCILIATION_BASELINE.json`, `OVH_VPS_TARGET.md`,
`OVH_TKP_TCP_AGM_DEPLOYMENT_PLAN.md`.

---

## 0. Integration provenance

| Item | Value |
|---|---|
| Deployment-ready branch | `feature/ovh-tkp-tcp-agm-ready` |
| Branch tip | `49f8864` (`fix: complete Windows VPS runtime dependencies`) |
| Base production commit | `live-main @ 3cfda4fdde5eaa8fae42c87b56d30d34aa717f68` |
| Integrated portability work | 6 commits `6ce7feb → 38eb0a2` (central path config, TKP title reconcile, TKP state/workbook configurable, portable data paths, VPS layout docs/build) |
| Dependency fix | `49f8864` — adds `openpyxl==3.1.5` and `dash-bootstrap-components==2.0.3` to `requirements.txt` |
| Reconciliation baseline captured | `2026-10-01T11:35-04:00` (laptop production, authoritative) |

**Business-logic safety:** the integrated diff is path-centralization plus two pre-approved TKP
chart *title* strings plus the Y&Q resolver delegation (no behavior change when `HC_*` is unset).
No NAV / return / fee / drawdown / benchmark math, chart values, state schema, uploader payload,
or auth logic was changed. Verified by diff review and by the resolver test suite (123 passed).

---

## 1. Why TCP is the pilot

TCP is the only one of the three apps that boots on a clean VPS with **zero code change**:
its production state already lives outside the repository (`%LOCALAPPDATA%\HughesCompany\TCP\state`),
every path is environment-driven (`TCP_V2_STATE_*`, `TCP_V2_BENCHMARK_*`), its writes are atomic
(lock + temp + `os.replace` + backup rotation), and `/healthz` exposes a rich, fully reconcilable
surface. All four independent row counts agree (182) — the cleanest reconciliation surface in the fleet.

---

## 2. Code to deploy

Source: the deployment-ready branch worktree
`C:\Coding Projects\Tearsheet Generator\.worktrees\ovh-tkp-tcp-agm-ready`
(authoritative tip `49f8864`). Copy *from this branch*, not from the dev checkout.

### 2a. TCP application modules → `C:\H&C\apps\tcp\`

```
tcp_ts_v2.py            entry point (bind 8302 in production)
tcp_config.py
tcp_runtime_state.py
tcp_state.py
tcp_ledger.py
tcp_calculations.py
tcp_dashboard.py
tcp_drawdown.py
tcp_benchmarks.py
tcp_daily_values.py
tcp_admin.py
tcp_public_sections.py
tcp_uploader_ingest.py
```

### 2b. Shared modules → `C:\H&C\apps\shared\`

```
tearsheet_paths.py          ← NEW required shared module (central path resolver).
                              tcp_ts_v2.py and tcp_config.py now import it. Omitting it
                              is the single most likely packaging mistake for this pilot.
tearsheet_runtime_mode.py
tearsheet_local_admin.py
tearsheet_gate_auth.py
tearsheet_gate_ui.py
tearsheet_disclosure.py
tearsheet_header.py
tearsheet_portal.py
tearsheet_date_defaults.py
tearsheet_uploader_ingest.py
assets\styles.css           (the only static asset the app needs)
requirements.txt            (now complete — see §4)
```

`PYTHONPATH` for the service = `C:\H&C\apps\shared;C:\H&C\apps\tcp` (Option A in the plan).

### 2c. Must NOT copy

`tcp_ts.py` (legacy monolith; its `__main__` binds 8302 and would conflict), `.git`,
`.worktrees\`, `__pycache__\`, `tests\`, `backups\`, `_runtime\`, `_restart_logs\`,
any `reboot_*` launcher, any `.env` file, any other application, and any virtual environment.

---

## 3. Persistent data to copy (copy, never move — laptop stays authoritative)

All hashes are SHA-256, captured `2026-10-01T11:35-04:00`. **Re-hash the source immediately
before copying.** A changed hash means the laptop took new data since the baseline → re-capture
the baseline and re-copy; it is not a VPS defect.

| File | Source (laptop) | VPS destination | Size | Hash | Copy? |
|---|---|---|---|---|---|
| `tcp_daily_returns_secret_state.json` | `%LOCALAPPDATA%\HughesCompany\TCP\state\` | `C:\H&C\data\tcp\` | 81,311 B | `7094B6B513999B39F32304350016C6A9EAC4C07321D515821357159FD7934386` | **YES (authoritative)** |
| `tcp_daily_returns_secret_state.backup.json` | same | `C:\H&C\data\tcp\` | 80,894 B | `91D0A1EFC8A8EE9252BF31AB5349CBF0B0819C07DB87EC04C768CA97394F9FAB` | optional (app recreates) |
| `tcp_daily_returns_secret_state.lock` | same | — | 83 B | — | **NO — runtime artifact, create locally** |
| `tcp_benchmark_cache.json` (^SP500TR) | `%LOCALAPPDATA%\HughesCompany\TCP\benchmark\` | `C:\H&C\data\tcp\benchmark\` | 797,185 B | regenerable | YES (enables offline first boot) |
| `tcp_benchmark_btc_cache.json` (BTC-USD) | same | `C:\H&C\data\tcp\benchmark\` | 357,558 B | regenerable | YES |
| `tcp_benchmark_eth_cache.json` (ETH-USD) | same | `C:\H&C\data\tcp\benchmark\` | 263,740 B | regenerable | YES |
| `tcp_alex.xlsx` | — | — | — | — | **NO — workbook fallback is disabled on the VPS** |
| `glenn_uploader_ingest_tcp_audit.jsonl` | live worktree root | archive to `C:\H&C\backups\tcp\` | 21,279 B | — | NO (VPS starts a fresh file) |

**Authoritative state facts (reconciliation anchors):**
182 records, `state_revision` 83, schema_version 1, first date `2026-01-20`, latest date `2026-09-30`,
latest `NLV` `60667.74`, `nav-x1` `52743.467`, `HWM` `52836.417`.
Record fields: `Date, #, Trading Days, NLV, Cash Balance, Cash Transfers, Day PnL, $PL, Inc. Fee, cumm fee, Loss Carry, HWM, %Net, S net cummulative %, nav-x1`.

**Path resolution is proven.** Under `HC_APP_ENV=vps-production` the central resolver maps
TCP state to `C:\H&C\data\tcp` and the ingest audit to `C:\H&C\logs\ingest` with no code change
(executed and verified against the resolver on the branch). Explicit `TCP_V2_*` overrides take
precedence over the resolver if set (see §5).

---

## 4. Runtime

| Item | Value |
|---|---|
| Python | **3.10.x 64-bit** to `C:\Python310` (production baseline is 3.10.0; do not use 3.12/3.13) |
| Virtual env | one shared venv `C:\H&C\apps\shared\.venv310` |
| Install | `pip install -r requirements.txt` — **now complete** |
| Dependency fix | `openpyxl==3.1.5` and `dash-bootstrap-components==2.0.3` are included in `requirements.txt` on this branch (commit `49f8864`). On `live-main` they were missing and had to be installed by hand; that gap is closed. |
| Native deps | none beyond the wheels above; TCP uses stdlib `msvcrt` for file locking (Windows built-in) |
| Import smoke test | `...\.venv310\Scripts\python.exe -c "import dash, dash_bootstrap_components, flask, pandas, numpy, plotly, openpyxl; import tearsheet_paths, tcp_config; print('ok')"` |

---

## 5. Environment variables

Split by sensitivity. **Names only** below — no secret values are recorded anywhere in git.

### 5a. Non-secret → `C:\H&C\config\tcp.env`

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

Optional/alternative: setting `HC_APP_ENV=vps-production` makes the central resolver derive the
same `C:\H&C\data\tcp` and `C:\H&C\logs\ingest` locations automatically. The explicit
`TCP_V2_*` overrides above win over the resolver, so they are the primary, unambiguous contract.

Deliberate deviations from the laptop (each intentional):
- `TCP_V2_ALLOW_WORKBOOK_FALLBACK=false` — fail loudly rather than silently serve stale workbook data.
- `TCP_V2_BENCHMARK_BTC/ETH_CACHE_PATH` — unset on the laptop; set explicitly here.
- `TCP_V2_SKIP_BENCHMARK_FETCH=1` — first private boot has no outbound market-data dependency. Remove after reconciliation.
- `GLENN_UPLOADER_INGEST_ENABLED=false` — **critical**; only one host may accept ingest. Enable only at cutover.
- Do **not** set `TEARSHEET_LOCAL_DIRECT_ADMIN` (laptop-only dev convenience).

### 5b. Secret → `C:\H&C\secrets\tcp.env` and `C:\H&C\secrets\ingest.env` (ACL: service account + Administrators only)

```
TCP_V2_ADMIN_TOKEN            # tcp.env   — required in production
TCP_V2_SESSION_SECRET         # tcp.env   — required in production
GLENN_UPLOADER_INGEST_TOKEN   # ingest.env — staged but inert while ingest disabled
```

**Do not rely on compiled defaults.** `resolve_sibling_admin_auth_settings` falls back to a
non-secret `DEFAULT_SIBLING_ADMIN_TOKEN` / `DEFAULT_SIBLING_SESSION_SECRET` when the env vars are
unset. The TCP cutover preflight treats missing env tokens as **NO-GO**, so production must set
real values out of band (password manager — never chat, never committed). Generate the actual
secret values at deploy time; this gate does not generate them.

---

## 6. NSSM service contract — `HC-TCP-Public`

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
nssm set HC-TCP-Public AppEnvironmentExtra <config\tcp.env + secrets\tcp.env + secrets\ingest.env + PYTHONPATH=C:\H&C\apps\shared;C:\H&C\apps\tcp>
nssm set HC-TCP-Public AppExit Default Restart
nssm set HC-TCP-Public AppThrottle   10000
nssm set HC-TCP-Public AppStopMethodConsole 5000
```

Service-specific musts:
- **Process-tree termination** — the venv `python.exe` spawns the base interpreter as a child; NSSM must kill the whole tree or a restart leaks an orphan holding port 8302.
- **`AppExit Default Restart` + `AppThrottle 10000`** — auto-restart is the capability the laptop lacks; the throttle prevents a boot-failure restart storm.
- **Loopback only** — confirm the listener binds `127.0.0.1`, never `0.0.0.0`. Inbound firewall stays closed to 8302.
- Do **not** create `HC-TCP-Staff` (8322) during the pilot.

---

## 7. Reconciliation gate (must pass before anything beyond private boot)

Compare the VPS to `OVH_TKP_TCP_AGM_RECONCILIATION_BASELINE.json`. Every row must match exactly.

| Check | Expected |
|---|---|
| `/healthz` `state_revision` | `83` |
| `/healthz` `record_count` / `completed_rows` / `candidate_rows` | `182` |
| `/healthz` `first_completed_date` | `2026-01-20` |
| `/healthz` `latest_completed_date` | `2026-09-30` |
| `/healthz` `data_source` | `json` |
| `/healthz` `state_mode` | `json-active` |
| `/healthz` `state_writable` | `true` |
| `/healthz` `recovery_status` | `normal` |
| `/healthz` `port` | `8302` |
| State file SHA-256 | `7094B6B513999B39F32304350016C6A9EAC4C07321D515821357159FD7934386` |
| State file size | 81,311 bytes |
| Latest `Date` / `NLV` / `nav-x1` / `HWM` | `2026-09-30` / `60667.74` / `52743.467` / `52836.417` |
| Page `<title>` | `H&C - TCP` |
| Source commit | `3cfda4fdde5eaa8fae42c87b56d30d34aa717f68` |

**Stop conditions (roll back, do not push forward):** `data_source` is `workbook`/`workbook_fallback`;
`recovery_status` ≠ `normal`; `state_writable` false (ACL problem); `/healthz` 503 (no snapshot);
`port` 8312 (env not applied, preview default won); or any state-value mismatch that is not explained
by a documented new-data re-sync.

---

## 8. Validation performed on this branch (laptop, read-only)

| Suite | Result |
|---|---|
| Resolver / portability / config / Y&Q (`test_tearsheet_paths`, `test_tkp_paths`, `test_vps_portability_paths`, `test_windows_vps_deployment_layout`, `test_tcp_config`, `test_yq_data_current`) | **123 passed** |
| TCP core reconciliation logic (`test_tcp_config`, `test_tcp_calculations`, `test_tcp_golden_fixtures`, `test_tcp_parity_acceptance`) | **61 passed, 13 skipped** (skips are `local_workbook`-marked tests needing the absent local xlsx) |
| Resolver executed under `vps-production` | TCP → `C:\H&C\data\tcp`, audit → `C:\H&C\logs\ingest`; explicit override precedence confirmed |
| Byte-compile of all 7 modified runtime modules | **clean** |

Not run on this laptop (by design): the full TKP app test set and any test that imports `tkp_ts`
— `tkp_ts.py` opens its source workbook at module import, and on the laptop that path resolves into
the protected H&C Documents folder. Those run on the VPS, where the workbook lives at
`C:\H&C\data\tkp`. A few TCP app tests are network-/sleep-bound (`test_tcp_benchmarks` live fetch,
resilience lock timing) and were not forced to completion here; they are environment-bound, not
logic regressions.

---

## 9. Hard stop

This package ends at **"ready to deploy."** It does not touch the OVH VPS, does not RDP, does not
change DNS/Cloudflare/SiteGround, does not generate secrets, does not enable ingest, and does not
create a real `C:\H&C` on this laptop. Execution begins only on Kevin's go.
