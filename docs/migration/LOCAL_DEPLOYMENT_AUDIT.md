# Local Deployment Audit — H&C Tearsheet Fleet (Phase 1)

> Read-only audit. No application code, configuration, data, services, or secrets were modified.
> Audit timestamp: 2026-07-24 (local, UTC-4). Auditor: automated Phase 1 pass.

---

## Executive summary

- **Current architecture:** A fleet of Python **Dash/Flask** tearsheet apps, each launched as an individual process by a per-app PowerShell `reboot_*.ps1` script, all running from a single **canonical production worktree**: `C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main` (branch `live-main`, commit `f540135`). Public app ports bind **loopback only** and are exposed to the internet by a **Cloudflare Tunnel** (`cloudflared` running, PID 7812). A separate **service dashboard** (`HomePage\debug.py`, port 8006, binds `0.0.0.0`) provides start/reboot/health control. The **Glenn uploader** is a separate FastAPI + React app deployed to **Fly.io** that pushes daily rows downstream into each tearsheet app's authenticated ingest route.
- **Active application count:** 8 verified listeners in scope (4 public tearsheets, 3 staff/admin tearsheets, 1 dashboard). AGM == "Momentum Pacer" (`mp_ts.py`).
- **Live source path:** `C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main` — **proven** via running process command lines. Y&Q, TKP, TCP, AGM all execute files under this worktree. The repo root (`C:\Coding Projects\Tearsheet Generator`) is intentionally the "dirty dev checkout"; the reboot scripts actively **refuse** to launch from it.
- **Primary data stores:** `daily_returns_secret_state.json` (TKP, 847 rows), `tcp_daily_returns_secret_state.json` (TCP, 112 records), `Momentum Pacer\momentum_pacer_manual_daily_rows.json` (AGM, 10 rows), `yq.csv`/`yq.xlsx` (Y&Q), plus source Excel workbooks. Uploader has its own SQLite `uploader_sandbox.db` (on Fly.io volume + local copy). **None of the production state files are tracked by Git.**
- **Main migration risks:** (1) TKP reads a source workbook **inside the forbidden/OneDrive-synced H&C Documents folder** (hardcoded absolute Windows path); (2) the live worktree's `.git` is **owned by BUILTIN\Administrators** (elevation/ownership coupling); (3) **no automatic restart-on-reboot** mechanism is configured (no Scheduled Task, no Startup entry, PM2 list empty); (4) Cloudflare Tunnel ingress is **cloud-managed** (no local config) so hostname→port mapping is not on disk; (5) production state files are **untracked** and depend on manual backup.
- **Recommended Azure OS:** **Azure Windows Server VM** (evidence-based — see Azure recommendation section). The dependency footprint is heavily Windows-coupled (`.ps1`/`.bat` launchers, `os.startfile`, Windows Excel/OneDrive-synced source paths, admin-owned worktree). A same-OS lift-and-shift minimizes calculation/behavior drift risk for financially material data.
- **Overall migration readiness score:** **5/10 — PASS WITH BLOCKERS.** The system is well-structured and safety-gated, but several hard blockers (protected-folder data source, no auto-start, admin ownership, untracked state) must be resolved before a VM purchase and cutover.
- **Critical blockers:** protected-folder data dependency (TKP source workbook); no auto-start/recovery; admin-owned production worktree blocking normal git ops; unversioned production state with only ad-hoc backups.

---

## Current runtime matrix

Verified via `Get-NetTCPConnection`, `Get-CimInstance Win32_Process`, and `git worktree list`.

| Program | Role | Port (verified) | Bind | Entry point | Runtime | Source path | Data path | Startup method | Auto-restart | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| TKP Tearsheet | Public | 8301 | 127.0.0.1 | `tkp_ts.py` | Python 3.10 / Dash+Flask | `.worktrees\live-deploy-main` | `daily_returns_secret_state.json` | `reboot_tkp_ts.ps1` (via `.bat`) | None configured | LISTENING |
| TCP Tearsheet | Public | 8302 | 127.0.0.1 | `tcp_ts_v2.py` | Python 3.10 / Dash+Flask | `.worktrees\live-deploy-main` | `tcp_daily_returns_secret_state.json` | `reboot_tcp_ts.ps1` | None configured | LISTENING |
| Y&Q Tearsheet | Public | 8303 | 127.0.0.1 | `yq_ts.py` | Python 3.10 (global `python`) / Dash+Flask | `.worktrees\live-deploy-main` | `yq.csv` / `yq.xlsx` | `reboot_yq_ts.bat` (global python) | None configured | LISTENING |
| AGM (Momentum Pacer) | Public | 8304 | 127.0.0.1 | `Momentum Pacer\mp_ts.py` | Python 3.10 / Dash+Flask | `.worktrees\live-deploy-main` | `momentum_pacer_manual_daily_rows.json` + `Momentum Fee Calculation.xlsx` | `reboot_mp_ts.ps1` | None configured | LISTENING |
| TKP Staff/Admin | Staff | 8321 | 127.0.0.1 | `tkp_ts.py` (`TEARSHEET_MODE=staff`) | Python 3.10 | `.worktrees\live-deploy-main` | same as TKP | `reboot_tkp_staff.ps1` | None configured | LISTENING |
| TCP Staff/Admin | Staff | 8322 | 127.0.0.1 | `tcp_ts_v2.py` (staff) | Python 3.10 | `.worktrees\live-deploy-main` | same as TCP | `reboot_tcp_staff.ps1`/`.bat` | None configured | LISTENING |
| AGM Staff/Admin | Staff | 8324 | 127.0.0.1 | `Momentum Pacer\mp_ts.py` (staff) | Python 3.10 | `.worktrees\live-deploy-main` | same as AGM | `reboot_mp_staff.ps1`/`.bat` | None configured | LISTENING |
| Service Dashboard (debug) | Ops | 8006 | 0.0.0.0 | `debug.py` | Python (`HomePage\.venv13`) | `C:\Coding Projects\HomePage` | in-memory + metrics cache | manual / `reboot_homepage.bat` | None configured | LISTENING |

Notes:
- Y&Q has **no** staff/admin port (no 8323); it is public-only. All seven expected tearsheet ports (8301–8304, 8321/8322/8324) plus the dashboard (8006) were verified LISTENING.
- Public processes also expose an `/admin` route on their public port (dashboard health-checks `http://127.0.0.1:8301/admin`, etc.) **in addition** to the dedicated loopback staff processes on 83x1 ports. See Network audit (security concern).
- Y&Q is launched via `reboot_yq_ts.bat` using **global `python`**, not the `.venv310` used by the other apps — an environment-consistency gap.

---

## Repository and worktree state

- **Repository root:** `C:\Coding Projects\Tearsheet Generator`
- **Root checkout branch/commit:** `fix/post-ingest-full-recalculation` @ `8fe8143` — **DIRTY** (pre-existing, not caused by this audit):
  - ` M assets/styles.css`
  - ` M tests/test_tkp_chart_cashflow_performance.py`
  - ` M tkp_ts.py`
  - `?? .pr_body_tkp_label.md`
- **Active production worktree:** `C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main` — branch `live-main` @ `f540135` (from `git worktree list`).
- **Which checkout running processes actually use:** **Proven** = `live-deploy-main`. Every running tearsheet process command line points at files under `...\.worktrees\live-deploy-main\`. The known candidate worktree remains authoritative and is confirmed live.
- **~45 worktrees exist** under `.worktrees\` (feature/PR branches). Only `live-deploy-main` is live. Others were **not touched**.
- **Ownership caveat (BLOCKER):** `git status` inside `live-deploy-main` fails with *"detected dubious ownership … owned by BUILTIN/Administrators … current user AzureAD/H&CDanHughes"*. Git status could **not** be captured for the live worktree without adding a `safe.directory` entry (a config change, which is forbidden and was **not** performed). The live worktree therefore appears to have been created/managed under an elevated/admin context.

---

## Application dependency map

**Per-program entry points (in `live-deploy-main`):**
- TKP: `tkp_ts.py` (225 KB, single-file Dash app; public + `/admin` + staff via `TEARSHEET_MODE`).
- TCP: `tcp_ts_v2.py` (57 KB) with a rich module set: `tcp_config.py`, `tcp_calculations.py`, `tcp_benchmarks.py`, `tcp_daily_values.py`, `tcp_dashboard.py`, `tcp_drawdown.py`, `tcp_ledger.py`, `tcp_public_sections.py`, `tcp_runtime_state.py`, `tcp_state.py`, `tcp_admin.py`, `tcp_uploader_ingest.py`. (Legacy `tcp_ts.py` 115 KB also present but not the live entry point.)
- AGM: `Momentum Pacer\mp_ts.py` + `algominds_*` accounting modules (`algominds_daily_accounting.py`, `algominds_daily_fees.py`, `algominds_daily_balances.py`, `algominds_monthly_summary.py`, `algominds_drawdown_semantics.py`, etc.).
- Y&Q: `yq_ts.py` (112 KB).

**Shared modules (cross-program):**
- `tearsheet_uploader_ingest.py` — shared Glenn ingest framework (used by TKP, TCP v2, AGM).
- `tearsheet_runtime_mode.py` — mode/port/session helpers (`TEARSHEET_MODE`, bind ports, session cookie names) — shared by TKP/TCP/AGM.
- `tearsheet_gate_auth.py`, `tearsheet_gate_ui.py`, `tearsheet_local_admin.py`, `tearsheet_portal.py`, `tearsheet_header.py`, `tearsheet_disclosure.py`, `tearsheet_date_defaults.py` — shared UI/auth/gating.
- `program_account_stats.py` — shared stats.

**Match to planned `apps/{tkp,tcp,agm,yq}` + `shared/` layout:** **Low.** The repo is currently **flat** (all program files and shared modules live at the worktree root, with AGM in a `Momentum Pacer\` subfolder). There is an `algominds_v2\` package and reorg-prep worktrees (`-reorg-prep`, `-reorg-yq`) indicating a planned move, but the live layout does **not** yet match the target structure. Migration should treat the current flat layout as authoritative and defer the reorg.

---

## Persistent data inventory

Metadata only; no client row values were dumped. Structural metadata (counts/dates/schema) recorded per the audit rules.

| Item | Path (live worktree unless noted) | Type | Owner | Purpose | Size | Modified | Git-tracked | Generated | Sensitive | Must migrate | Recurring backup |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `daily_returns_secret_state.json` | repo root (symlinked into worktree) | JSON (847 rows) | TKP | Canonical TKP daily returns/StoneX/NAV editor state | ~399 KB | 2026-07-24 | No (untracked) | Yes (app writes) | **Yes** | **Yes** | **Yes** |
| `tcp_daily_returns_secret_state.json` | repo root | JSON (wrapper, 112 records) | TCP | Canonical TCP NAV/nav-x1 state (revision, source metadata) | ~51 KB | 2026-07-02 | No | Yes | **Yes** | **Yes** | **Yes** |
| `momentum_pacer_manual_daily_rows.json` | `Momentum Pacer\` | JSON (10 rows) | AGM | Manual daily rows merged with TradeStation NLV | ~1.3 KB | 2026-07-24 | No | Yes | **Yes** | **Yes** | **Yes** |
| `Momentum Fee Calculation.xlsx` | `Momentum Pacer\` (symlink → repo root) | Excel | AGM | AGM fee/accounting source (Summary + Sris Fee Calc Detail) | (link) | 2026-07-11 | link | No (source) | **Yes** | **Yes** | **Yes** |
| TKP source workbook | **`…\Hughes & Company - Documents\…\TKP\VADI\Copy of tkp_alex_old1.xlsx`** (forbidden folder) | Excel | TKP | TKP source workbook (hardcoded path) | not inspected | n/a | No | No | **Yes** | **Yes (relocate)** | **Yes** |
| `yq.csv` / `yq.xlsx` | repo root | CSV/Excel | Y&Q | Y&Q source/state | ~28.5 KB / ~47.2 KB | 2026-07-02 | No | mixed | **Yes** | **Yes** | **Yes** |
| `glenn_uploader_ingest_{tkp,tcp,agm}_audit.jsonl` | worktree root + `Momentum Pacer\` | JSONL | Uploader/apps | Per-attempt ingest audit trail | 10–12 KB | 2026-07-24 | Yes (tkp/tcp) | Yes | Low (metadata) | Recommended | Weekly |
| `uploader_sandbox.db` | `uploader\backend\data\` (+ Fly.io `/data` volume) | SQLite | Glenn uploader | Uploader staging store | ~88–90 KB | 2026-07-14 | No (local) | Yes | **Yes** | **Yes** | **Yes** |
| `uploader\backend\backups\*.db` | uploader backend | SQLite | Uploader | Point-in-time uploader DB backups | 440–460 KB each | 2026-07-14/15 | No | Yes | **Yes** | Retain | n/a |
| `tcp_benchmark_cache.json` / `_btc` / `_eth` | worktree root (per `tcp_config.py`) | JSON | TCP | Benchmark market caches (SPX/BTC/ETH) | varies | — | mixed | Yes | No | Regenerable | Optional |

**Reconciliation-relevant schema:**
- TKP schema keys: `_row_id, #Day, Date, Plus500, StoneX, # Trades, $PL, Fee (20%), Cumm Fee, Net P&L, Net P&L / Unit, NAV, Loss Carry, Perc. Net, Cumm Perc. Net, HWM, Deposit`. Range **2023-04-10 → 2026-07-23**.
- TCP wrapper keys: `app, first_completed_date, latest_completed_date, record_count, records, revision, schema_version, source, source_sheet, source_workbook_filename, updated_at`. Records use `NLV, nav-x1, Cash Balance, Cash Transfers, HWM, Inc. Fee, cumm fee, …`. Range **2026-01-20 → 2026-06-24** (112 records; source `tcp_alex.xlsx`).
- AGM keys: `date, actual_nlv, deposit_withdrawal, incentive_fee_paid`. Range **2026-07-11 → 2026-07-23**.

**Concurrency/locking:** the Glenn ingest framework serializes `apply()` with a per-process `threading.Lock`; TCP uses configurable lock file paths (`TCP_V2_STATE_LOCK_PATH`). TKP/AGM state writers are documented single-writer/non-atomic by design.

---

## Windows-specific findings

| Finding | Evidence | Severity | Effort | Classification |
|---|---|---|---|---|
| Hardcoded absolute path into forbidden OneDrive-synced folder | `tkp_ts.py:244-246` (TKP source workbook) | **Critical** | Medium | Needs code change + data relocation |
| `.ps1` launchers with hardcoded `C:\` guards | `reboot_*.ps1` (dirty-root refusal, `.venv310` path) | High | Medium | Needs porting for Linux; works on Windows Server |
| `.bat` launchers | `reboot_*.bat`, `run_all_services.bat`, `reboot_yq_ts.bat` | High | Medium | Windows-only; keep on Win Server |
| `os.startfile` / browser & Docker launch | `HomePage\debug.py` (subprocess, `os.startfile`, `explorer.exe`) | Medium | Medium | Dashboard convenience; not needed headless |
| `cmd.exe /k` interactive launch for Y&Q | process tree (PPID `cmd.exe /k call reboot_yq_ts.bat`) | Medium | Low | Replace with service |
| PM2 (`pm2-windows-startup`) in HKCU Run but **empty process list** | HKCU Run key; `pm2 list` empty | Medium | Low | Startup mechanism unused/incomplete |
| NTFS junction + symlinks for venv/env/state | `.venv310` junction, `.env`/state symlinks → repo root | Medium | Low | Reproduce as bind mounts/copies |
| Admin-owned `.git` in live worktree | `git status` dubious-ownership error | High | Low | Fix ownership before migration |
| `pandas`/Excel reads via `openpyxl`/`read_excel` | `test_read_excel.py`, `mp_ts.py` EXCEL_PATH | Low | Low | Works cross-platform (no COM observed) |
| Loopback + Cloudflare Tunnel exposure | `cloudflared` PID 7812; apps bind 127.0.0.1 | Medium | Low | Re-point tunnel or use reverse proxy |

**No evidence of** `pywin32`, COM automation (`win32com`), registry writes, or UNC paths within the tearsheet apps. Excel is read via pandas/openpyxl, which is cross-platform.

---

## Python and external dependencies

- **Tearsheet apps:** Python **3.10** (`C:\Python310`), venv `.venv310` (junctioned from repo root). `requirements.txt` is **fully pinned** (Dash 3.0.4, Flask 3.0.3, pandas 2.2.3, numpy 2.2.6, plotly 6.1.1, matplotlib 3.10.3, QuantStats 0.0.64, yfinance 0.2.61, scipy 1.15.3, seaborn, peewee, curl_cffi, etc.).
- **Uploader backend:** separate env; `requirements.txt` uses **ranges** (FastAPI, uvicorn[standard], pydantic 2.x, pydantic-settings, pandas, pandas-market-calendars, yfinance) — **not locked**.
- **Dashboard:** distinct venv `HomePage\.venv13` (different Python minor line than 3.10) — an **environment divergence** across apps.
- **Reproducibility gaps / flags:**
  - Y&Q runs under **global `python`**, not `.venv310` — undocumented interpreter.
  - Uploader deps unpinned (ranges) — pin before production.
  - `curl_cffi`, `scipy`, `numpy`, `matplotlib`, `pillow` have native/compiled components — verify wheels on target OS.
  - `yfinance` reaches the network for benchmarks (SPX/NDX/BTC); a cache-only mode exists (`benchmark_cache_only`).
  - Rendering assets: matplotlib/plotly fonts — confirm fonts present on headless server.
  - No Conda/Pipfile detected; dependency source of truth is `requirements.txt` (apps) + uploader `requirements.txt`.

---

## Secrets and configuration map

Names and locations only — **no values were read or printed.** Env is loaded by each `reboot_*.ps1` via an `Import-BatchEnvFile` parser reading `set "NAME=VALUE"` lines from `.env` files (all symlinked to repo-root copies).

| Name | Source location | Consumer | Required/Optional | Suggested Azure destination |
|---|---|---|---|---|
| `GLENN_UPLOADER_INGEST_ENABLED` | `.local_dev.env` | All tearsheet apps (ingest gate) | Required to enable ingest (default off) | VM env var / restricted `.env` |
| `GLENN_UPLOADER_INGEST_TOKEN` | `.local_dev.env` | All tearsheet apps (ingest auth) | Required when ingest enabled | **Azure Key Vault** |
| `GLENN_UPLOADER_INGEST_DRY_RUN_ALLOWED` | (code default true) | All apps | Optional | Non-secret config |
| `TEARSHEET_LOCAL_DIRECT_ADMIN` | `.local_dev.env` | Apps (local admin bypass) | Optional (dev) | Non-secret config (keep off in prod) |
| `TKP_ADMIN_TOKEN` | `.tkp_production.env` | TKP admin auth | Required (prod) | **Azure Key Vault** |
| `TKP_SESSION_SECRET` | `.tkp_production.env` | TKP Flask session | Required (prod) | **Azure Key Vault** |
| `TCP_V2_ADMIN_TOKEN` | `.tcp_production.env` | TCP admin auth | Required (prod) | **Azure Key Vault** |
| `TCP_V2_SESSION_SECRET` | `.tcp_production.env` | TCP Flask session | Required (prod) | **Azure Key Vault** |
| `TCP_V2_BIND_PORT` | `.tcp_production.env` | TCP port override | Optional | App config |
| `TCP_V2_STATE_PATH` / `_BACKUP_PATH` / `_LOCK_PATH` | `.tcp_production.env` | TCP state persistence | Optional (defaults exist) | App config (VM paths) |
| `TCP_V2_STATE_MODE` | `.tcp_production.env` | TCP state mode | Optional | App config |
| `TCP_V2_BENCHMARK_CACHE_PATH` | `.tcp_production.env` | TCP benchmark cache | Optional | App config |
| `TEARSHEET_STAFF_ALLOWED_HOSTS` | `.staff.env` | Staff host-header allowlist | Required (staff) | App config |
| `TKP_BIND_PORT` / `AGM_BIND_PORT` | staff `reboot_*.ps1` (inline) | Port selection | Optional | App config |
| `TEARSHEET_MODE` | `reboot_*.ps1` (inline) | public/staff/legacy switch | Required per process | App config |
| `MP_TS_PRODUCTION` | `reboot_mp_ts.ps1` (inline) | AGM production flag | Required (prod) | App config |
| Uploader: `ADMIN_API_TOKEN`, `DOWNSTREAM_INGEST_TOKEN`, `*_INGEST_URL`, `EXPORT_*`, `CORS_ALLOW_ORIGINS`, `DATABASE_PATH` | `uploader\backend\.env` / `fly.toml` | Uploader backend | mixed (tokens=Key Vault; URLs/flags=config) | Key Vault (tokens) / config (rest) |

**Hardcoded credentials in source:** none observed in the reviewed entry points. Admin auth uses env-provided tokens/session secrets compared constant-time (`secrets.compare_digest`). TKP admin gate uses a password flow via `tearsheet_gate_auth` / `tkp_admin_auth_manager` (password source not printed).

---

## Glenn uploader integration

**Data flow (traced from code, no requests issued):**

```
Glenn uploader (React/Vite frontend)  ── https ──▶  Uploader backend (FastAPI, Fly.io app "glenn-uploader-sandbox", :8091, /data volume)
                                                          │  downstream_export.py (EXPORT_DOWNSTREAM_ENABLED / EXPORT_DRY_RUN gated)
                                                          ▼  POST /api/uploader/ingest-daily-row  (Bearer / X-Glenn-Uploader-Token)
                                        each tearsheet app's Flask server (TKP :8301, TCP :8302, AGM :8304)
                                                          ▼  IngestConfig.apply()  (same code path as admin "Add Row")
                                        save row ▶ recalculate derived values ▶ persist state JSON ▶ refresh public+admin display
```

- **Endpoint (shared):** `POST /api/uploader/ingest-daily-row` registered by `register_uploader_ingest()` (`tearsheet_uploader_ingest.py`).
- **Programs routed:** TKP, TCP, AGM. **Y&Q has no downstream target** and is always reported "skipped" (`config.export_include_yq` default false; no `export_url_yq`).
- **Auth:** `Authorization: Bearer <token>` or `X-Glenn-Uploader-Token`, constant-time compared against each app's `GLENN_UPLOADER_INGEST_TOKEN`. Fail-closed.
- **Gating:** ingest is **off by default**; requires `GLENN_UPLOADER_INGEST_ENABLED=true` **and** a non-empty token, both read per request.
- **Validation/idempotency:** ISO date, numeric coercion, unknown-field rejection; classification created/updated/unchanged by (program, date) — never duplicates. Dry-run performs validation but never writes.
- **Save/export/`exported` state:** uploader backend has `export_status.py`, `downstream_export.py`, `rollback.py`. Real downstream writes require `EXPORT_DOWNSTREAM_ENABLED=true`, `EXPORT_TARGET_ENV=production`, `EXPORT_DRY_RUN=false`, plus per-program `*_INGEST_URL` and a token — otherwise a per-row failure with **no external call** (never silent success). Response echoes `persisted`, `recalculated`, `state_revision`, `latest_display_date`, `storage_target` as durable proof.
- **Audit:** one JSON line per attempt appended to `glenn_uploader_ingest_{program}_audit.jsonl` (last modified 2026-07-24 09:45 — recently active).
- **Transport today:** frontend `VITE_API_BASE_URL=https://uploader.hcresearch.ltd/api`; CORS allows `uploader-sandbox.hcresearch.ltd` and `uploader.hcresearch.ltd`. Targets are Fly.io-hosted; downstream tearsheet targets are **localhost/loopback** on the ops machine (via `*_INGEST_URL`, currently unset in the safe default).

**Target changes required for VPS:**
- Set each app's `*_INGEST_URL` to the VPS-internal address (e.g. `http://127.0.0.1:8301/api/uploader/ingest-daily-row`) — keep downstream traffic loopback/private on the VPS.
- If the uploader stays on Fly.io, the VPS must accept **inbound** ingest calls: prefer a private path (Cloudflare Tunnel / authenticated reverse proxy) rather than opening app ports publicly.
- Provision `GLENN_UPLOADER_INGEST_TOKEN` on each app and matching `DOWNSTREAM_INGEST_TOKEN` on the uploader (Key Vault).
- Decision needed: **one shared ingest gateway** vs **per-app ingest** — current design is **per-app** (recommended to preserve).

---

## Startup and recovery architecture

**Current (as-found):**
- Each app is launched by its own `reboot_*.ps1` (production) / `reboot_*.bat`, which set `TEARSHEET_MODE`, load env from symlinked `.env` files, and run `.venv310\Scripts\python.exe <entry>`. Y&Q uses a `.bat` with global `python` under a persistent `cmd.exe /k` window.
- The **service dashboard** (`HomePage\debug.py`, :8006) maps ~25 services to `.bat` files and offers Start / Reboot / "Restart Down" (health-driven) controls.
- **No automatic restart-on-reboot** is configured: no relevant Scheduled Task, no Startup-folder entries, and PM2 (though registered via `pm2-windows-startup` in HKCU Run) has an **empty process list**. Recovery today is effectively **manual** (operator uses the dashboard) or ad-hoc.
- Duplicate-process prevention / crash detection is provided reactively by the dashboard's health checks + reboot buttons, not by a supervisor.

**Startup dependency order (observed):**
1. Cloudflare Tunnel (`cloudflared`) — provides public reachability.
2. Individual tearsheet processes (order-independent; each binds its own loopback port).
3. Dashboard (`debug.py`) — optional; used to monitor/restart the fleet.
4. Uploader (Fly.io) — independent; only needs the apps reachable when exporting.

**Recommended Azure equivalent:** **NSSM-managed Windows services** (or native Windows Services) — one service per app (public + staff), each with a fixed venv, env file, auto-restart on failure, and start-on-boot. Front with **IIS (ARR) or Nginx** as a reverse proxy terminating HTTPS on 443 and routing to loopback app ports. Keep the dashboard as an internal-only service. This replaces the manual/dashboard recovery model with real supervision.

---

## Network and security audit

**Current exposure:**
- App ports **8301–8304, 8321/8322/8324** bind **127.0.0.1** (loopback only) — not directly reachable from LAN/Internet.
- Dashboard **8006** binds **0.0.0.0** — reachable from LAN (should be restricted).
- Public reachability provided by **Cloudflare Tunnel** (`cloudflared` PID 7812). Ingress hostname→port rules are **not stored locally** (`~/.cloudflared` contains only `cert.pem`), so the mapping is **managed in the Cloudflare Zero Trust dashboard**. Staff ports are intended to sit behind **Cloudflare Access** (per `reboot_tkp_staff.ps1` comment).
- CORS: uploader allows `*.hcresearch.ltd` + localhost dev origins.
- Host-header allowlist for staff via `TEARSHEET_STAFF_ALLOWED_HOSTS`.

**Security concerns:**
- Public app processes also serve an **`/admin` route on the public port** (in addition to dedicated staff processes). Confirm this admin surface is password/session gated and consider removing it from the public process on the VPS.
- Dashboard on `0.0.0.0:8006` with start/kill/reboot controls is powerful; must be firewalled to localhost/VPN on the VPS.
- Session cookie security (`secure_cookies`) is off in legacy mode — enable secure cookies behind HTTPS on the VPS.

**Proposed VPS exposure model:**
- Public: **only 80/443** via IIS/Nginx (HTTPS terminated at proxy; HTTP→HTTPS redirect).
- App ports (83xx) remain **loopback/private**; proxy routes public hostnames to them.
- **Admin/staff routes** protected separately (Cloudflare Access / proxy auth / IP allowlist), on distinct hostnames.
- Uploader ingest reaches apps over a **private** channel only; no app port is opened publicly.
- Dashboard bound to localhost or a management VNet/VPN only.

---

## Reconciliation baseline

Values read read-only for reconciliation anchoring (single latest figures only; no bulk client data dumped).

| Program | Latest data date | Latest value (verified) | Rows | Earliest date | Source | Notes |
|---|---|---|---|---|---|---|
| TKP | **2026-07-23** | StoneX = **$83,245.09** (NAV column = $193,201.40) | 847 | 2023-04-10 | StoneX column in `daily_returns_secret_state.json` | Prior anchor $82,955.48 has advanced to $83,245.09. TKP official source is StoneX-only (Plus500 also present as a column). |
| TCP | **2026-06-24** | NLV = **$43,007.30**; nav-x1 = **$44,871.38**; HWM $50,056.79 | 112 | 2026-01-20 | `tcp_alex.xlsx` (excel_bootstrap), revision 1 | Prior anchor $49,300.55 is a **prior** figure; current latest completed date is 2026-06-24 (TCP not updated as recently as TKP/AGM — verify freshness). |
| AGM | **2026-07-23** | manual `actual_nlv` = **$43,496.60** | 10 (manual) | 2026-07-11 | `Momentum Fee Calculation.xlsx` + manual rows, merged with TradeStation NLV | Prior anchor $44,709.50 (TradeStation) is a prior figure; NLV moves daily. |
| Y&Q | 2026-07-02 (file mtime) | not extracted (CSV/Excel source) | — | — | `yq.csv` / `yq.xlsx` | Public-only; no downstream export. |

Gross/net & fees: TKP has `Fee (20%)`, `Net P&L`, `Perc. Net`; TCP computes fees (`Inc. Fee`, `cumm fee`, fee-net `nav-x1`); AGM computes incentive fees. Benchmarks (SPX/BTC/ETH) are integrated with on-disk caches. **Data was not modified to force any match.**

---

## Backup and restore plan

| Class | Items | Frequency | Retention | Encrypt | App stop for consistency? | Restore order | Validation |
|---|---|---|---|---|---|---|---|
| 1. Source code | `live-deploy-main` worktree (branch `live-main` @ `f540135`) | On change (git) | Full history | No | No | 1 | `git status` clean, commit matches |
| 2. Production state | TKP/TCP/AGM state JSON, Y&Q csv/xlsx | **Daily** (post-market) | 90 days + monthly archive | **Yes** | Preferred (quiesce writers) | 3 | Row counts & latest dates match matrix |
| 3. Databases | `uploader_sandbox.db` (+ Fly.io volume) | Daily | 30 days | Yes | Preferred | 4 | Schema + record count check |
| 4. Configuration | `.env` files, `tearsheet_fleet_runtime.json`, `reboot_*.ps1/.bat`, `fly.toml`, frontend `.env.*` | On change | Indefinite | Yes (env) | No | 2 | Launchers resolve; ports bind |
| 5. Secrets | `*_ADMIN_TOKEN`, `*_SESSION_SECRET`, ingest tokens | On rotation | Current + prior | **Yes (Key Vault)** | No | 2 | Auth succeeds post-restore |
| 6. Static assets | `assets/`, source workbooks (incl. relocated TKP VADI xlsx, AGM xlsx) | On change | Indefinite | Yes (client data) | No | 3 | App renders; charts populate |
| 7. Logs | `_restart_logs/`, `_runtime/`, ingest `*_audit.jsonl` | Weekly | 1 year | No | No | 8 | Present, appended |
| 8. Generated output | benchmark caches, exports | Weekly / regenerable | 30 days | No | No | last | Regenerates on run |
| 9. SiteGround homepage content | (external) | On change | Indefinite | No | No | independent | Page loads |
| 10. DNS configuration | Cloudflare zone + Tunnel ingress, `hcresearch.ltd` records | On change (export) | Current + prior | No | No | independent | Hostnames resolve to VPS |

**Restore drill (design only, do not execute):** provision VM → restore code (class 1) → restore config+secrets (4,5) → restore state+DB (2,3) → restore assets (6) → start services (NSSM) → verify each app's latest date/value against the reconciliation matrix → verify a **dry-run** Glenn ingest returns `accepted:true, dry_run:true` with no write → cut DNS/Tunnel (10).

---

## Azure recommendation

**Recommendation: Azure Windows Server VM (lift-and-shift), Ubuntu deferred.**

Evidence for Windows Server:
- All launchers are Windows PowerShell/Batch (`reboot_*.ps1`, `*.bat`), with hardcoded `C:\` guard paths and NTFS junction/symlink layout.
- The dashboard uses Windows-centric process control (`os.startfile`, `explorer.exe`, Docker Desktop) — trivial to keep working on Windows.
- The live worktree `.git` is admin-owned (Windows ACLs) — a same-OS move avoids re-deriving permission models.
- TKP/AGM source workbooks are Excel files (one currently inside a OneDrive-synced Windows folder). Same-OS reduces path/format risk on **financially material** calculations.
- Python deps are pinned for the apps and are cross-platform, but native packages (numpy/scipy/matplotlib/curl_cffi) are already validated on this Windows build; re-validating on Linux adds risk without payoff for Phase 2.

Ubuntu is viable **later** (the apps are Dash/Flask + pandas, and the uploader already runs in Linux Docker on Fly.io), but requires porting all launchers to systemd, replacing junctions/symlinks with mounts, relocating Excel sources, and re-validating numeric parity — none of which should gate the first migration. **Choose Windows Server for Phase 2; revisit Ubuntu as a cost optimization after parity is proven.**

---

## Migration blockers

| ID | Blocker | Severity |
|---|---|---|
| B1 | TKP source workbook hardcoded inside forbidden OneDrive-synced H&C Documents folder (`tkp_ts.py:244-246`) — will not exist on VPS | **Critical** |
| B2 | No automatic restart-on-reboot (no Scheduled Task / Startup / active PM2); recovery is manual | **Critical** |
| B3 | Live worktree `.git` owned by BUILTIN\Administrators — blocks normal git ops for the user | High |
| B4 | Production state files untracked by Git; only ad-hoc/manual backups | High |
| B5 | Cloudflare Tunnel ingress is cloud-managed (no local config) — hostname→port map must be reproduced/re-pointed | High |
| B6 | `/admin` served on public ports in addition to staff processes — admin attack surface | High |
| B7 | Y&Q uses global `python` (not `.venv310`); uploader deps unpinned — environment drift | Medium |
| B8 | Dashboard binds `0.0.0.0:8006` with kill/reboot powers — must be locked down | Medium |
| B9 | AGM source `Momentum Fee Calculation.xlsx` present as symlink; ensure real file migrates | Medium |
| B10 | TCP latest completed date (2026-06-24) lags TKP/AGM (2026-07-23) — confirm intended before cutover | Low/verify |

---

## Recommended Phase 2 (do not perform yet)

1. **Resolve B1:** relocate the TKP source workbook out of the protected folder into a VPS-owned data directory and parameterize the path via env; obtain the exact file from Kevin (do not browse the folder).
2. Choose VM size (see final note) and provision an **Azure Windows Server** VM in the appropriate region; attach a managed data disk for state.
3. Fix `.git`/worktree **ownership** and adopt a clean deployment checkout (no dirty root on the VPS).
4. Stand up **NSSM services** (one per app + staff) with auto-start/auto-restart; front with **IIS/Nginx** on 443.
5. Move secrets to **Azure Key Vault**; template `.env` from Key Vault at boot.
6. Reproduce **Cloudflare Tunnel/Access** (or reverse-proxy) ingress; keep app ports private.
7. Establish **daily encrypted state backups** + a tested restore drill.
8. Point uploader `*_INGEST_URL` at the VPS-internal endpoints; validate with **dry-run** ingest.
9. Reconcile each app's latest date/value against this baseline before DNS cutover.

---

*End of Phase 1 audit. No production code, data, services, or secrets were changed. The three files under `docs/migration/` are the only artifacts created and remain uncommitted.*
