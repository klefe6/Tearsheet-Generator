# OVH TCP Pilot Package

**Status: VPS GROUNDWORK BEGUN — no tearsheet has been deployed or started.**

VPS work to date on `HC-PROD-VPS01` is limited to: Git + Python 3.10.11 toolchain install, the
shared venv at `C:\HC\apps\shared\.venv310` with the pinned dependency set installed, a read-only
source checkout, TCP/shared source staged into `C:\HC\apps\`, and NSSM placed in
`C:\HC\deployment\tools\`. **No service has been created or started, no production state or
workbook has been copied, no secret has been created, and Glenn ingest remains disabled.**
Everything below is still the forward-looking input set for the pilot.

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
| VPS path normalization | `1bc440b` (`refactor: normalize OVH VPS root to C:\HC`) — the commit this revision builds on |
| Canonical VPS root | `C:\HC` — see "Canonical root" below |
| Base production commit | `live-main @ 3cfda4fdde5eaa8fae42c87b56d30d34aa717f68` |
| Integrated portability work | 6 commits `6ce7feb → 38eb0a2` (central path config, TKP title reconcile, TKP state/workbook configurable, portable data paths, VPS layout docs/build) |
| Dependency fix | `49f8864` — adds `openpyxl==3.1.5` and `dash-bootstrap-components==2.0.3` to `requirements.txt` |
| Dependency reproducibility | `fix: make OVH Python environment reproducible` — adds `et-xmlfile==2.0.0`; documents the QuantStats/yfinance metadata conflict and the undeclared IPython requirement (see §4) |
| Documentation commits after `49f8864` | `a3c61b3`, `a938b0b`, `9e17622` (migration inventory carry-forward, pilot package + plan alignment, Glenn cutover gate) |
| Canonical source checkout on VPS | `C:\HC\deployment\source\Tearsheet-Generator` (clone of `klefebvre6/Tearsheet-Generator`) |
| Reconciliation baseline captured | `2026-10-01T11:35-04:00` (laptop production, authoritative) |

`49f8864` was the branch tip when this package was first written and is no longer the branch tip.
Three documentation commits landed after it, then the VPS path normalization, then the dependency
reproducibility commit above — which supersedes `49f8864` as the authoritative *dependency* commit.

**Business-logic safety:** the integrated diff is path-centralization plus two pre-approved TKP
chart *title* strings plus the Y&Q resolver delegation (no behavior change when `HC_*` is unset).
No NAV / return / fee / drawdown / benchmark math, chart values, state schema, uploader payload,
or auth logic was changed. Verified by diff review and by the resolver test suite (123 passed).

### Canonical root

| Root | Status |
|---|---|
| `C:\HC` | **Current authoritative OVH VPS root.** Every path in this package resolves under it. |
| `C:\H&C` | Superseded earlier *planned* root. Never created on the live VPS. |
| `E:\H&C` | Abandoned original TKP-lane draft, which assumed a second volume. |

`tearsheet_paths.VPS_ROOT` is the single constant that defines the root; every other VPS path
derives from it, so the root is changed in exactly one place. The earlier `C:\H&C` draft was
superseded because its `&` requires quoting in NSSM `AppEnvironmentExtra` values, service
definitions, and shell invocations.

Historical audit documents that record `C:\H&C` as the design of record at the time they were
written are deliberately left unchanged; they describe a past design, not the live contract.

---

## 1. Why TCP is the pilot

TCP is the only one of the three apps that boots on a clean VPS with **zero code change**:
its production state already lives outside the repository (`%LOCALAPPDATA%\HughesCompany\TCP\state`),
every path is environment-driven (`TCP_V2_STATE_*`, `TCP_V2_BENCHMARK_*`), its writes are atomic
(lock + temp + `os.replace` + backup rotation), and `/healthz` exposes a rich, fully reconcilable
surface. All four independent row counts agree (182) — the cleanest reconciliation surface in the fleet.

---

## 2. Code to deploy

Source: the authoritative checkout of this branch on the VPS,
`C:\HC\deployment\source\Tearsheet-Generator` (cloned from
`https://github.com/klefebvre6/Tearsheet-Generator.git`, branch
`feature/ovh-tkp-tcp-agm-ready`). Copy *from this branch*, not from the dev checkout.
The original authoring worktree on the laptop is no longer the staging source for the VPS.

### 2a. TCP application modules → `C:\HC\apps\tcp\`

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

### 2b. Shared modules → `C:\HC\apps\shared\`

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
requirements.txt            (install with --no-deps — see §4)
```

`PYTHONPATH` for the service = `C:\HC\apps\shared;C:\HC\apps\tcp` (Option A in the plan).

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
| `tcp_daily_returns_secret_state.json` | `%LOCALAPPDATA%\HughesCompany\TCP\state\` | `C:\HC\data\tcp\` | 81,311 B | `7094B6B513999B39F32304350016C6A9EAC4C07321D515821357159FD7934386` | **YES (authoritative)** |
| `tcp_daily_returns_secret_state.backup.json` | same | `C:\HC\data\tcp\` | 80,894 B | `91D0A1EFC8A8EE9252BF31AB5349CBF0B0819C07DB87EC04C768CA97394F9FAB` | optional (app recreates) |
| `tcp_daily_returns_secret_state.lock` | same | — | 83 B | — | **NO — runtime artifact, create locally** |
| `tcp_benchmark_cache.json` (^SP500TR) | `%LOCALAPPDATA%\HughesCompany\TCP\benchmark\` | `C:\HC\data\tcp\benchmark\` | 797,185 B | regenerable | YES (enables offline first boot) |
| `tcp_benchmark_btc_cache.json` (BTC-USD) | same | `C:\HC\data\tcp\benchmark\` | 357,558 B | regenerable | YES |
| `tcp_benchmark_eth_cache.json` (ETH-USD) | same | `C:\HC\data\tcp\benchmark\` | 263,740 B | regenerable | YES |
| `tcp_alex.xlsx` | — | — | — | — | **NO — workbook fallback is disabled on the VPS** |
| `glenn_uploader_ingest_tcp_audit.jsonl` | live worktree root | archive to `C:\HC\backups\tcp\` | 21,279 B | — | NO (VPS starts a fresh file) |

**Authoritative state facts (reconciliation anchors):**
182 records, `state_revision` 83, schema_version 1, first date `2026-01-20`, latest date `2026-09-30`,
latest `NLV` `60667.74`, `nav-x1` `52743.467`, `HWM` `52836.417`.
Record fields: `Date, #, Trading Days, NLV, Cash Balance, Cash Transfers, Day PnL, $PL, Inc. Fee, cumm fee, Loss Carry, HWM, %Net, S net cummulative %, nav-x1`.

**Path resolution is proven.** Under `HC_APP_ENV=vps-production` the central resolver maps
TCP state to `C:\HC\data\tcp` and the ingest audit to `C:\HC\logs\ingest` with no code change
(executed and verified against the resolver on the branch). Explicit `TCP_V2_*` overrides take
precedence over the resolver if set (see §5).

---

## 4. Runtime

| Item | Value |
|---|---|
| Python | **3.10.x 64-bit** to `C:\Python310` (production baseline is 3.10.0; do not use 3.12/3.13) |
| Virtual env | one shared venv `C:\HC\apps\shared\.venv310` |
| Install | `pip install --no-deps -r requirements.txt` — see "Resolver note" below for why `--no-deps` is used |
| Dependency fix | `openpyxl==3.1.5` and `dash-bootstrap-components==2.0.3` are included in `requirements.txt` on this branch (commit `49f8864`). On `live-main` they were missing and had to be installed by hand; that gap is closed. |
| Dependency fix | `et-xmlfile==2.0.0` added to `requirements.txt`. `openpyxl 3.1.5` declares `Requires: et-xmlfile`, but the pin was absent, so `import openpyxl` failed on a clean VPS install until it was installed by hand. `openpyxl` itself is unchanged. |
| Native deps | none beyond the wheels above; TCP uses stdlib `msvcrt` for file locking (Windows built-in) |
| Import smoke test | `...\.venv310\Scripts\python.exe -c "import dash, dash_bootstrap_components, flask, pandas, numpy, plotly, openpyxl; import tearsheet_paths, tcp_config; print('ok')"` |

### Resolver note — QuantStats 0.0.64 vs yfinance 0.2.61 and numpy 2.2.6

`pip install -r requirements.txt` fails with `ResolutionImpossible`, and after installing with
`--no-deps` `pip check` reports exactly two conflicts:

```
quantstats 0.0.64 has requirement numpy<2.0.0,>=1.21.0, but you have numpy 2.2.6.
quantstats 0.0.64 has requirement yfinance>=0.2.65, but you have yfinance 0.2.61.
```

**This is a packaging/reproducibility warning, not a runtime blocker for the TCP pilot.** The pins
are not wrong and must not be "fixed" by upgrading.

*Cause.* PyPI serves **two different wheels for the same version string `0.0.64`**, because the
project was re-uploaded under a differently-cased name:

| Wheel | Uploaded | Size | Declares |
|---|---|---|---|
| `QuantStats-0.0.64-py2.py3-none-any.whl` | 2024-10-25 | 45,751 B | `numpy>=1.16.5`, `yfinance>=0.1.70` |
| `quantstats-0.0.64-py2.py3-none-any.whl` | 2025-07-14 | 78,735 B | `numpy<2.0.0,>=1.21.0`, `yfinance>=0.2.65` |

The 2024 wheel's requirements are **satisfied** by the pinned `numpy==2.2.6` and
`yfinance==0.2.61`. The 2025 re-upload tightened them, and modern pip prefers the normalized
lowercase name, so a fresh install picks the 2025 wheel and the pinned set then looks
self-contradictory. The conflict is an artifact-selection problem, not a version problem.

*Known-working in production.* `OVH_TKP_TCP_AGM_CURRENT_STATE.md` §"Verified installed versions"
records, queried from the live laptop venv, `numpy==2.2.6`, `yfinance==0.2.61`,
`quantstats==0.0.64` — the exact trio pip metadata rejects. That environment is the one the
reconciliation baseline was produced under. **The pair is therefore documented as
known-working-but-metadata-incompatible, and both pins are left unchanged.** (The laptop venv
cannot be inspected from the VPS; this rests on that recorded verification, not on a live query.)

*Why the pilot is unaffected.* QuantStats is never imported at TCP boot:

- the import is lazy, inside `QuantstatsBenchmarkProvider.download_returns()` (`tcp_benchmarks.py`);
- that provider is only constructed on the **live** fetch path, in `load_symbol_benchmark()`;
- with `TCP_V2_SKIP_BENCHMARK_FETCH=1` the pilot routes to the cache-only loaders
  (`tcp_ts_v2.py`), which read the copied caches and never touch QuantStats;
- the live path wraps the fetch in `except Exception`, so even an outright import failure degrades
  to benchmark status `unavailable` rather than crashing the app (verified on this VPS);
- `use_quantstats` in `tcp_drawdown.py` only selects a drawdown formula — it imports nothing;
- `yfinance` appears in the staged TCP modules only inside a docstring.

### Open gap — QuantStats needs IPython, which nothing declares

Separately discovered on the VPS and **not yet fixed**: `from quantstats import utils` fails with
`ModuleNotFoundError: No module named 'IPython'`. `quantstats/__init__.py` imports `reports`, and
`reports.py` imports from IPython inside a `try/except ImportError` whose fallback *also* imports
from IPython — so IPython is mandatory. **Both** 0.0.64 wheels do this, and **neither** declares
IPython in `Requires-Dist`, so `requirements.txt` cannot have caught it.

Consequence: live benchmark fetching on this VPS would return `unavailable` permanently once
`TCP_V2_SKIP_BENCHMARK_FETCH` is removed. It does **not** block the pilot, which boots cache-only.
Resolution deferred pending approval, since it means adding a dependency rather than correcting a
pin; the laptop venv evidently has IPython present through some other install.

---

## 5. Environment variables

Split by sensitivity. **Names only** below — no secret values are recorded anywhere in git.

### 5a. Non-secret → `C:\HC\config\tcp.env`

```
TCP_V2_STATE_MODE=json_active
TCP_V2_BIND_PORT=8302
TCP_V2_STATE_PATH=C:\HC\data\tcp\tcp_daily_returns_secret_state.json
TCP_V2_STATE_BACKUP_PATH=C:\HC\data\tcp\tcp_daily_returns_secret_state.backup.json
TCP_V2_STATE_LOCK_PATH=C:\HC\data\tcp\tcp_daily_returns_secret_state.lock
TCP_V2_BENCHMARK_CACHE_PATH=C:\HC\data\tcp\benchmark\tcp_benchmark_cache.json
TCP_V2_BENCHMARK_BTC_CACHE_PATH=C:\HC\data\tcp\benchmark\tcp_benchmark_btc_cache.json
TCP_V2_BENCHMARK_ETH_CACHE_PATH=C:\HC\data\tcp\benchmark\tcp_benchmark_eth_cache.json
TCP_V2_ALLOW_WORKBOOK_FALLBACK=false
TCP_V2_SKIP_BENCHMARK_FETCH=1
TEARSHEET_MODE=public
PYTHONIOENCODING=utf-8
GLENN_UPLOADER_INGEST_ENABLED=false
```

Optional/alternative: setting `HC_APP_ENV=vps-production` makes the central resolver derive the
same `C:\HC\data\tcp` and `C:\HC\logs\ingest` locations automatically. The explicit
`TCP_V2_*` overrides above win over the resolver, so they are the primary, unambiguous contract.

Deliberate deviations from the laptop (each intentional):
- `TCP_V2_ALLOW_WORKBOOK_FALLBACK=false` — fail loudly rather than silently serve stale workbook data.
- `TCP_V2_BENCHMARK_BTC/ETH_CACHE_PATH` — unset on the laptop; set explicitly here.
- `TCP_V2_SKIP_BENCHMARK_FETCH=1` — first private boot has no outbound market-data dependency. Remove after reconciliation.
- `GLENN_UPLOADER_INGEST_ENABLED=false` — **critical**; only one host may accept ingest. Enable only at cutover.
- Do **not** set `TEARSHEET_LOCAL_DIRECT_ADMIN` (laptop-only dev convenience).

### 5b. Secret → `C:\HC\secrets\tcp.env` and `C:\HC\secrets\ingest.env` (ACL: service account + Administrators only)

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
nssm install HC-TCP-Public "C:\HC\apps\shared\.venv310\Scripts\python.exe"
nssm set HC-TCP-Public AppParameters "C:\HC\apps\tcp\tcp_ts_v2.py"
nssm set HC-TCP-Public AppDirectory  "C:\HC\apps\tcp"
nssm set HC-TCP-Public AppStdout     "C:\HC\logs\tcp\tcp_stdout.log"
nssm set HC-TCP-Public AppStderr     "C:\HC\logs\tcp\tcp_stderr.log"
nssm set HC-TCP-Public AppRotateFiles 1
nssm set HC-TCP-Public AppRotateBytes 10485760
nssm set HC-TCP-Public Start          SERVICE_AUTO_START
nssm set HC-TCP-Public ObjectName     ".\svc_hc_tearsheets" <password>
nssm set HC-TCP-Public AppEnvironmentExtra <config\tcp.env + secrets\tcp.env + secrets\ingest.env + PYTHONPATH=C:\HC\apps\shared;C:\HC\apps\tcp>
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

**Reconciliation alone does not authorize production ingest.** Passing §7 is required for the private
pilot, but Glenn cutover is a separate mandatory gate (§8). Do not enable VPS ingest until Phase 3
of that lifecycle is executed deliberately.

---

## 8. Glenn uploader cutover — mandatory gate

This section is part of the TCP pilot contract. The VPS pilot **deliberately** starts with
`GLENN_UPLOADER_INGEST_ENABLED=false`. Ingest stays off until Phase 3 of this lifecycle.

### Production data path (confirmed by migration audit)

```
Glenn uploader (Fly.io)
  → TCP_INGEST_URL (Fly config)
  → POST /api/uploader/ingest-daily-row
  → Authorization: Bearer GLENN_UPLOADER_INGEST_TOKEN
  → TCP (tcp_ts_v2.py / tearsheet_uploader_ingest.py)
  → tcp_daily_returns_secret_state.json
  → apply_tcp_recalculation()
```

On the VPS, the bearer token is configured as `GLENN_UPLOADER_INGEST_TOKEN` in
`C:\HC\secrets\ingest.env` (name only in git — **never commit the value**). Glenn's Fly
configuration must use the matching downstream token (`DOWNSTREAM_INGEST_TOKEN` / equivalent in
uploader settings) without recording it in this repository.

### Phase 1 — Private pilot

- **Laptop remains authoritative** for TCP state and for ingest.
- **Glenn continues** sending production updates to the **existing** TCP production target (today:
  laptop tunnel + `tcp-ts.hcresearch.ltd` path to loopback TCP).
- **VPS TCP ingest remains DISABLED** (`GLENN_UPLOADER_INGEST_ENABLED=false`).
- VPS state is only a **reconciled copy** (§7); it must not receive Glenn writes.
- **No dual writers** — at most one host may persist ingest rows at any time.

Covers private boot, loopback `/healthz`, visual parity, and reboot tests before any public cutover.

### Phase 2 — Pre-cutover resync

Do **not** make cutover decisions from an old reconciliation baseline alone.

1. On the **laptop** (authoritative), capture the **latest** TCP state:
   - latest completed date
   - record count
   - `state_revision`
   - SHA-256 of `tcp_daily_returns_secret_state.json`
2. Record those values in a fresh capture (update or supersede
   `OVH_TKP_TCP_AGM_RECONCILIATION_BASELINE.json` for TCP, or a dated cutover worksheet).
3. **Re-copy / resync** that authoritative file to `C:\HC\data\tcp\` on the VPS.
4. **Reconcile the VPS again** (§7 checks against the **new** capture, not the original pilot
   snapshot).
5. **Glenn VPS ingest remains disabled** throughout Phase 2.

### Phase 3 — Glenn cutover

**Preflight (required before enabling production ingest on the VPS):**

From `uploader/backend/` on a machine with Glenn's Fly settings available, run the read-only probe:

```text
python scripts/verify_downstream_ingest.py
python scripts/verify_downstream_ingest.py --strict
```

`verify_downstream_ingest.py` POSTs **`dry_run: true`** probe payloads to each configured ingest URL
(TCP/TKP/AGM). It does not export rows or mark uploader rows exported. For TCP cutover, the TCP
probe must succeed against the **intended production URL** while ingest is still disabled on the VPS
(expect `ingest_disabled` until Phase 3 enablement — plan the probe sequence accordingly: routing
and token checks against the target host, then enable ingest, then re-probe without expecting
`ingest_disabled`). See `docs/downstream_export_go_live_runbook.md` for the full go-live procedure.

**URL strategy — prefer unchanged hostname:**

Determine whether production can keep:

`https://tcp-ts.hcresearch.ltd/api/uploader/ingest-daily-row`

If **Cloudflare** can preserve `tcp-ts.hcresearch.ltd` and route it to the **new VPS** tunnel
(instead of the laptop), **prefer that design** — Glenn may need **no** `TCP_INGEST_URL` change on
Fly.io (only tunnel/DNS/backend target changes on the infrastructure side).

If a **different hostname** is required (e.g. staging hostname first, or a VPS-only name), document
that Fly.io **`TCP_INGEST_URL`** must be updated at cutover to the new HTTPS origin with the same
`/api/uploader/ingest-daily-row` path suffix.

**Cutover rules (non-negotiable):**

| Rule | Requirement |
|---|---|
| Token parity | `GLENN_UPLOADER_INGEST_TOKEN` on the VPS must match Glenn's downstream bearer token. Never record the value in git. |
| Single authoritative ingest target | There must **never** be two authoritative TCP ingest targets. |
| Stop old authority | Laptop (or prior tunnel target) must **stop** being authoritative as the VPS becomes authoritative. |
| Enable VPS ingest only in cutover | Set `GLENN_UPLOADER_INGEST_ENABLED=true` on the VPS **only** as part of the controlled cutover, after resync and preflight — not during Phase 1 or 2. |
| Disable laptop ingest | Set `GLENN_UPLOADER_INGEST_ENABLED=false` on the **laptop** and restart **before or in the same window as** VPS enablement so Glenn cannot double-write. |

Suggested ordering within Phase 3 (adjust only with an explicit rollback plan):

1. Final Phase 2 resync immediately before the window.
2. Repoint Cloudflare / tunnel so `tcp-ts.hcresearch.ltd` → VPS loopback TCP (if using hostname preservation).
3. Disable ingest on the laptop; confirm laptop does not accept new Glenn writes.
4. Run `verify_downstream_ingest.py` (dry-run) against the production URL with VPS routing live.
5. Set `GLENN_UPLOADER_INGEST_ENABLED=true` on the VPS; restart `HC-TCP-Public`.
6. Update `TCP_INGEST_URL` on Fly **only if** the hostname changed in step 2.

### Phase 4 — First live ingest test

After Phase 3, use Glenn to send or submit the **first intended TCP row** through the normal
production workflow (not a manual JSON edit on disk).

Verify **all** of the following:

| Check | Pass criterion |
|---|---|
| HTTP response | Indicates **persisted** success (not dry-run, not rejected) |
| Payload | Correct **date** and correct **NLV / input values** for that row |
| State revision | Increments **exactly** as expected vs pre-ingest `/healthz` |
| Record count | Changes as expected (new date vs update-in-place) |
| State file | `C:\HC\data\tcp\tcp_daily_returns_secret_state.json` updated on disk |
| Recalculation | `apply_tcp_recalculation()` completed; dashboard/chart metrics coherent |
| Public display | Public TCP page reflects the new row / "data current to" label |
| Audit | `C:\HC\logs\ingest\glenn_uploader_ingest_tcp_audit.jsonl` contains the event |
| Laptop isolation | **Old laptop state did NOT** receive the new write (revision/hash unchanged on laptop) |

**If the first live ingest fails:**

- Do **not** manually create competing rows on laptop and VPS.
- Preserve evidence: HTTP response body, NSSM stderr log, audit JSONL tail, `/healthz` before/after.
- Either correct routing/configuration and retry once the single-authority contract is restored, or
  **roll back** the ingest target per the deployment plan (disable VPS ingest, re-enable laptop
  ingest, repoint Cloudflare/tunnel and `TCP_INGEST_URL` if changed).

Production TCP is not "live on VPS" until Phase 4 passes.

---

## 9. Validation performed on this branch (laptop, read-only)

| Suite | Result |
|---|---|
| Resolver / portability / config / Y&Q (`test_tearsheet_paths`, `test_tkp_paths`, `test_vps_portability_paths`, `test_windows_vps_deployment_layout`, `test_tcp_config`, `test_yq_data_current`) | **123 passed** |
| TCP core reconciliation logic (`test_tcp_config`, `test_tcp_calculations`, `test_tcp_golden_fixtures`, `test_tcp_parity_acceptance`) | **61 passed, 13 skipped** (skips are `local_workbook`-marked tests needing the absent local xlsx) |
| Resolver executed under `vps-production` | TCP → `C:\HC\data\tcp`, audit → `C:\HC\logs\ingest`; explicit override precedence confirmed |
| Byte-compile of all 7 modified runtime modules | **clean** |

Not run on this laptop (by design): the full TKP app test set and any test that imports `tkp_ts`
— `tkp_ts.py` opens its source workbook at module import, and on the laptop that path resolves into
the protected H&C Documents folder. Those run on the VPS, where the workbook lives at
`C:\HC\data\tkp`. A few TCP app tests are network-/sleep-bound (`test_tcp_benchmarks` live fetch,
resilience lock timing) and were not forced to completion here; they are environment-bound, not
logic regressions.

---

## 10. Hard stop

This package ends at **"ready to deploy."** It does not touch the OVH VPS, does not RDP, does not
change DNS/Cloudflare/SiteGround, does not generate secrets, does not enable ingest, and does not
create a real `C:\HC` on this laptop. Execution begins only on Kevin's go.
