# OVH Migration Phase 1 — Current State of TKP / TCP / AGM

**Report type:** read-only production inventory
**Captured:** 2026-10-01, 11:23–11:40 local (UTC-4), laptop `AzureAD/H&CDanHughes`
**Target server (not touched in this phase):** OVHcloud US VPS-3, Windows Server 2025 Standard Desktop, 6 vCore / 12 GB RAM / 100 GB, US-East (Virginia), premium backup + snapshot enabled.

Nothing was deployed, restarted, modified, or copied. No request was sent to any ingest endpoint. The protected folder `C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents` was never read, listed, or traversed — paths pointing into it are recorded verbatim from source code only.

---

## Executive summary

All three public tearsheets are live and healthy right now, served by three separate Python processes out of a single git worktree:

`C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main`

That worktree is pinned to branch `live-main` at commit `3cfda4fdde5eaa8fae42c87b56d30d34aa717f68`.

Seven findings drive the whole migration plan:

1. **`tearsheet_paths.py` does not exist in production.** The central path-portability work is real and fairly complete, but it lives only on unmerged feature branches (`feature/vps-portability-completion` is the furthest along). Production still resolves paths from `__file__`, hardcoded literals, and a partial set of `TCP_V2_*` environment variables. A repo-wide grep of the live worktree for `tearsheet_paths`, `HC_DATA_ROOT`, and `HC_APP_ENV` returns zero matches.

2. **TKP cannot start without a workbook inside the protected OneDrive folder.** `tkp_ts.py` hardcodes the path at line 244 and calls `sys.exit(1)` at module import if the file is absent or unreadable (lines 379–387, and again in the exception handlers at 444–452). There is no environment override on `live-main`. This is a hard, boot-blocking dependency and it is the single reason TKP is not the migration pilot.

3. **TCP is already most of the way portable.** It runs in `json_active` mode, its state, backup, lock, and benchmark cache paths all come from environment variables, and its production state already lives *outside* the repo at `C:\Users\H&CDanHughes\AppData\Local\HughesCompany\TCP\`. In `json_active` mode the workbook is only consulted if the JSON state is missing or corrupt, so TCP boots from JSON alone.

4. **The "live" worktree is not self-contained.** Five reparse points inside it point back into the dirty development checkout, including the AGM fee workbook. A naive file copy would silently produce zero-byte files. These must be resolved to their real targets before packaging.

5. **The Glenn uploader ingest token is configured through a file called `.local_dev.env`.** All three production launchers load it, and it is what sets `GLENN_UPLOADER_INGEST_ENABLED=true` plus the shared token. The naming is misleading and should be corrected during migration, not carried over.

6. **AGM has no production environment file.** `reboot_mp_ts.ps1` loads only `.local_dev.env`, so `AGM_ADMIN_TOKEN` and `AGM_SESSION_SECRET` are never set and fall back to the non-secret development defaults compiled into `tcp_config.py`. This needs a real secret on the VPS.

7. **The staff/admin ports are not required for migration.** Ports 8321 / 8322 / 8324 have no listener, and `Manager\startup_contract.json` explicitly classifies all three as "manual only". They are a password-free convenience surface, not part of the daily update path.

**Pilot recommendation: TCP.** Readiness: TKP **NOT READY**, TCP **READY WITH MINOR BLOCKERS**, AGM **READY WITH MINOR BLOCKERS**.

---

## Live runtime table

Evidence: `Get-NetTCPConnection -State Listen` cross-referenced with `Win32_Process` command lines, plus live `GET /healthz`.

| Field | TKP | TCP | AGM / Momentum Pacer |
|---|---|---|---|
| Program | TKP | TCP (v2) | AGM / Momentum Pacer |
| Role | public tearsheet | public tearsheet | public tearsheet |
| Port | 8301 | 8302 | 8304 |
| Bind address | 127.0.0.1 | 127.0.0.1 | 127.0.0.1 |
| PID (listener) | 40464 | 41172 | 41212 |
| Parent PID | 26944 | 41152 | 41192 |
| Entry-point file | `tkp_ts.py` | `tcp_ts_v2.py` | `Momentum Pacer\mp_ts.py` |
| Source worktree | `...\.worktrees\live-deploy-main` | same | same |
| Working directory | worktree root | worktree root | `...\live-deploy-main\Momentum Pacer` |
| Interpreter (listener) | `C:\Python310\python.exe` | same | same |
| Interpreter (launched as) | `...\live-deploy-main\.venv310\Scripts\python.exe` | same | same |
| Effective `sys.prefix` | `C:\Coding Projects\Tearsheet Generator\.venv310` | same | same |
| Python version | 3.10.0 (tags/v3.10.0:b494f59, MSC v.1929 64-bit) | same | same |
| Launcher | `reboot_tkp_ts.bat` → `reboot_tkp_ts.ps1` | `reboot_tcp_ts.bat` → `.ps1` | `reboot_mp_ts.bat` → `.ps1` |
| Health endpoint | `GET /healthz` | `GET /healthz` | `GET /healthz` |
| Health result | `200` `{"app":"tkp","status":"ready","rows_loaded":766,"admin_auth":"configured"}` | `200`, `state_revision: 83`, `latest_completed_date: 2026-09-30` | `200` `{"status":"ready","daily_rows":184,"months_loaded":10}` |
| Page title | `H&C - TKP` | `H&C - TCP` | `Algominds - Momentum Pacer` |
| Uptime at capture | 52.7 min | 52.7 min | 52.7 min |
| Working set | 235.5 MB | 224.5 MB | 158.6 MB |
| Startup method | Startup-folder `HC Launch All Services.cmd` → `Manager\startup_launch_all_services.ps1` → `launch_all_services.py` | same | same |
| Restart behavior | none — no auto-restart on crash | none | none |

### Why there are two Python processes per app

Each app shows a venv `python.exe` as the parent and `C:\Python310\python.exe` as the actual listener. This is normal Windows venv behavior: `.venv310\Scripts\python.exe` is a launcher stub that spawns the base interpreter with the venv's `site-packages` active. `sys.prefix` inside the running app resolves to the venv, confirmed directly. On the VPS, NSSM should point at the venv `python.exe`; the child-process indirection is harmless but means NSSM must be configured to kill the whole process tree.

### Out of scope, recorded for completeness

| Port | PID | What it is | Status |
|---|---|---|---|
| 8303 | 41432 | Y&Q tearsheet (`yq_ts.py`) | **Out of scope** — explicitly excluded |
| 8006 | 7216 | HomePage dashboard (`C:\Coding Projects\HomePage\debug.py`, Python 3.13) | **Out of scope** |

### Staff / admin ports

| Port | Expected service | Listener found | Verdict |
|---|---|---|---|
| 8321 | TKP staff | **none** | not required for migration |
| 8322 | TCP staff | **none** | not required for migration |
| 8324 | AGM staff | **none** | not required for migration |

`Manager\startup_contract.json` lists all three under `manual_only_ports` with the comment "manual only (reboot_*_staff.ps1)".

**What each staff service actually does.** There is no separate staff codebase. Each staff launcher starts *the same entry-point file* in a second process with `TEARSHEET_MODE=staff` and a forced staff port. In staff mode, `tearsheet_local_admin.is_staff_direct_admin_request()` grants an admin session on every route without a password, provided the peer is loopback and the `Host` header is loopback or listed in `TEARSHEET_STAFF_ALLOWED_HOSTS` (currently `tkp-admin.hcresearch.ltd,tcp-admin.hcresearch.ltd,agm-admin.hcresearch.ltd`). It is intended to sit behind Cloudflare Access.

**Is staff operationally required? No, for all three.** Every write path — add row, delete last row, recalculate, and uploader ingest — is registered on the same Flask app that serves the public port. The daily update flow runs through `POST /api/uploader/ingest-daily-row` against the public process, or through the gate-password admin UI on the public port. Staff is a convenience that removes the password prompt. Carrying it to the VPS is optional and should be deferred until after the public tearsheets reconcile.

One caveat worth flagging: TKP and AGM write their JSON state non-atomically with a plain `open(path, "w")`. Running a staff process and a public process against the same state file concurrently is a genuine last-writer-wins hazard. TCP is safe here — it uses a lock file plus temp-and-rename.

---

## TKP architecture

**Entry point:** `tkp_ts.py` (225,397 bytes) — a single large Dash-on-Flask module. There is no separate `tkp_calculations.py`; the business math lives in the entry point.

**Server:** `dash.Dash` with Flask underneath via `app.server`. `app.run(port=resolve_tkp_bind_port(), debug=is_legacy())` with no `host=` argument, so Werkzeug binds loopback. Port resolution: explicit `TKP_BIND_PORT` wins, else 8321 when `TEARSHEET_MODE=staff`, else 8301. The production launcher sets only `TEARSHEET_MODE=public`, which also forces `debug=False`.

**Routes**

| Path | Method | Surface | Purpose |
|---|---|---|---|
| `/` | GET | public | Dash tearsheet, behind a click-through disclaimer gate |
| `/healthz` | GET | public | readiness JSON: `status`, `rows_loaded`, `admin_auth` |
| `/admin` | GET | admin session | portal HTML (diagnostics; account registry is empty for TKP) |
| `/admin/logout` | GET | admin session | clears session |
| `/api/admin/recalculate` | POST | admin session | runs `apply_tkp_recalculation()`; 401 if unauthenticated |
| `/api/uploader/ingest-daily-row` | POST | bearer token | Glenn uploader ingest |
| `/monthly` | GET | — | deliberate 404; monthly workbook is backend-only |
| `/assets/<path>` | GET | public | Dash static from the shared `assets/` directory |

**Authentication.** Public access is a disclaimer accept. Hidden admin is reached by clicking the "e" in the gate notice to reveal a password field, checked by `tcp_admin.AdminAuthManager.login` using an HMAC compare. Session key `tkp_admin_authenticated`, cookie `tkp_session`. Credentials come from `TKP_ADMIN_TOKEN` and `TKP_SESSION_SECRET` via `tearsheet_gate_auth.load_tkp_admin_auth_settings()` → `tcp_config.resolve_sibling_admin_auth_settings()`. Both are set in `.tkp_production.env`. If unset, the code silently falls back to non-secret development defaults in `tcp_config.py` — acceptable today because the production env file supplies real values.

**Module graph.** Direct first-party imports: `tearsheet_disclosure`, `tearsheet_gate_ui`, `tearsheet_gate_auth`, `tearsheet_runtime_mode`, `tearsheet_portal`, `tearsheet_header`, `tearsheet_local_admin`, `tearsheet_uploader_ingest`, `tcp_admin`, `tcp_config`, `tearsheet_date_defaults`.

Importing `tcp_admin` transitively pulls in `tcp_public_sections`, `tcp_calculations`, `tcp_ledger`, `tcp_dashboard`, and `tcp_drawdown`. **These are TCP modules that TKP does not use for any business logic** — they are loaded purely as an import side effect of sharing `AdminAuthManager`. They must still be present on disk for TKP to import, which is why `shared/` in the VPS layout has to include the TCP module set. Worth untangling later, out of scope now.

**Calculations, all in `tkp_ts.py`:** `_compute_new_row` (P&L, 20% fee, cumulative fee, net P&L, NAV, loss carry, HWM); `_performance_series_from_secret_rows` and `_canonical_nav_rows_to_series` (non-compounded NAV chain); `_daily_returns_from_secret_rows` (net P&L over a $150k baseline); `_glenn_aligned_daily_return*` (uploader-parity formula); `_monthly_returns_from_nav_series`; `calculate_period_metrics`; `drawdown_profile` / `_build_max_dd_df`; and `propagate_dashboard` / `apply_tkp_recalculation` as the post-write refresh.

**Templates, static, charts.** UI is built inline as Dash components — no Jinja page templates. The `/admin` portal is a `render_template_string` of `tearsheet_portal.PORTAL_HTML`. The only static file is the shared `assets/styles.css`. Charts are Plotly (`plotly.graph_objs`). The header logo is base64-encoded from a PNG under the protected marketing folder; a missing file is caught and degrades to an empty logo.

**State loading and writing**

| Path | Access | How it is built |
|---|---|---|
| `daily_returns_secret_state.json` | read/write | `os.path.join(os.path.dirname(os.path.abspath(__file__)), SECRET_EDITOR_STATE_FILENAME)` — relative to `__file__`, no env override |
| TKP source workbook | **read, boot-critical** | hardcoded absolute literal at `tkp_ts.py:244` |
| Logo PNG | read, optional | hardcoded absolute literal at `tkp_ts.py:81` |
| `glenn_uploader_ingest_tkp_audit.jsonl` | append | `Path(__file__).resolve().parent / ...` |

The workbook is read at import in two passes: `openpyxl.load_workbook` to find the last populated row (with `FORCE_LAST_EXCEL_ROW = 715` as a floor), then `pd.read_excel` for columns C/N and again for A:S. After that, if `daily_returns_secret_state.json` loads successfully, the JSON rows override the Excel rows for the table and chart. The workbook is never written.

**Uploader ingest.** `POST /api/uploader/ingest-daily-row`, program `TKP`, required field `stonex_nlv`, optional `plus500_nlv` and `cash_transfer`, unknown fields rejected. Applies to the latest row only — older dates are rejected with 422. Writes `daily_returns_secret_state.json`, then `on_persisted` fires `apply_tkp_recalculation(authoritative_date=...)`. A 3-second `dcc.Interval` reloads the browser-side store. Audit appends to `glenn_uploader_ingest_tkp_audit.jsonl`.

**Benchmarks.** Downloaded live via `quantstats.utils.download_returns` for the `BENCHMARKS` list, plus `yfinance.download("^SP500TR")` for the drawdown comparison. **TKP has no benchmark cache file** — every boot hits the network. On a fresh VPS with no cache to fall back on, a network failure at startup degrades the benchmark columns.

**Logging.** No `logging` configuration at all; `print()` to stdout/stderr only. Under NSSM this redirects cleanly to files.

**Backups and temp files.** None. State is a single-file overwrite.

---

## TCP architecture

**Entry point:** `tcp_ts_v2.py` (57,830 bytes). The older `tcp_ts.py` (115,482 bytes) is **legacy and not in the runtime graph** — `tcp_ts_v2.py` does not import it, `docs/reorganization/file-classification.md` marks it obsolete, and `tests/test_tcp_foundation.py` actively forbids importing it. Do not deploy it.

TCP is the best-factored of the three: a thin entry point over a set of single-purpose modules.

**Server.** `create_app()` builds the Dash/Flask app (and is also called at import). `app.run(debug=cfg.debug, port=bind_port)` with no `host=`, so loopback. Port comes from `TCP_V2_BIND_PORT`, set to 8302 in `.tcp_production.env`; the unset default is preview port 8312. `tcp_config` validates that port 8302 requires `debug=False`.

**Routes**

| Path | Method | Surface | Purpose |
|---|---|---|---|
| `/` | GET | public | Dash tearsheet behind the disclaimer gate |
| `/healthz` | GET | public | rich health JSON; **503 if no snapshot** |
| `/admin` | GET | admin session | portal HTML |
| `/admin/login` | GET, POST | — | token form login |
| `/admin/logout` | GET, POST | admin session | clears session |
| `/api/admin/recalculate` | POST | admin session | reload JSON and rebuild derived state |
| `/api/uploader/ingest-daily-row` | POST | bearer token | Glenn uploader ingest |
| `/monthly` | GET | — | deliberate 404 |

The `/healthz` payload is the most useful reconciliation surface in the fleet: `state_revision`, `record_count`, `first_completed_date`, `latest_completed_date`, `data_source`, `state_mode`, `state_writable`, `recovery_status`, `adapter_status`, and the resolved `port`.

**Authentication.** Same shared gate as TKP. `TCP_V2_ADMIN_TOKEN` / `TCP_V2_SESSION_SECRET`, session key `tcp_v2_admin_authenticated`, and `secure_cookies=is_production_runtime(cfg)` so the cookie is marked Secure on the production port.

**Modules**

| Module | Role |
|---|---|
| `tcp_config.py` | env-backed `TCPConfig`; port, state path, benchmark cache, workbook, auth resolution |
| `tcp_runtime_state.py` | chooses workbook vs JSON snapshot; `persist_add_row` / `persist_delete_last_row` |
| `tcp_state.py` | versioned JSON envelope, `StateFileLock` (via `msvcrt`), atomic save, backup rotation |
| `tcp_ledger.py` | read-only Excel `NAV` sheet loader into validated `LedgerRecord`s |
| `tcp_calculations.py` | `compute_tcp_row` — NLV, P&L, fees, `nav-x1`, HWM, cumulative % |
| `tcp_dashboard.py` | `propagate_tcp_dashboard` — monthly calendar, daily metrics, NAV Plotly figure, date labels |
| `tcp_drawdown.py` | drawdown table vs SPXTR / BTC / ETH at $50k nominal exposure |
| `tcp_benchmarks.py` | benchmark fetch, normalization, and disk cache with ready/stale/unavailable status |
| `tcp_daily_values.py` | daily values table, paging, Excel export payload |
| `tcp_admin.py` | `AdminAuthManager`, Flask session config, ledger editor UI |
| `tcp_public_sections.py` | static public layout blocks and CSS class constants |
| `tcp_uploader_ingest.py` | TCP-specific ingest `apply()` glue |

Shared with the other apps: `tearsheet_gate_auth`, `tearsheet_gate_ui`, `tearsheet_disclosure`, `tearsheet_header`, `tearsheet_runtime_mode`, `tearsheet_local_admin`, `tearsheet_portal`, `tearsheet_uploader_ingest`, `tearsheet_date_defaults`.

**Templates, static, charts.** Dash components in Python, `render_template_string` for login and portal, shared `assets/styles.css`, Plotly charts. Logo from a hardcoded literal under the protected folder, optional.

**State.** `REPO_ROOT = Path(__file__).resolve().parent` is the fallback base, but production overrides every path by environment variable:

| Env key | Current value |
|---|---|
| `TCP_V2_STATE_MODE` | `json_active` |
| `TCP_V2_STATE_PATH` | `C:\Users\H&CDanHughes\AppData\Local\HughesCompany\TCP\state\tcp_daily_returns_secret_state.json` |
| `TCP_V2_STATE_BACKUP_PATH` | `...\TCP\state\tcp_daily_returns_secret_state.backup.json` |
| `TCP_V2_STATE_LOCK_PATH` | `...\TCP\state\tcp_daily_returns_secret_state.lock` |
| `TCP_V2_BENCHMARK_CACHE_PATH` | `...\TCP\benchmark\tcp_benchmark_cache.json` |

Writes go through `save_state`: acquire the lock, copy the prior valid active file to the backup, write to `tempfile.mkstemp(...".tmp", dir=path.parent)`, then `os.replace`. This is the only crash-safe write path in the fleet.

In `json_active` mode `load_runtime_snapshot` reads the JSON first and only calls `_load_workbook_snapshot` on `StateNotFound` or `StateLoadError`, gated by `allow_workbook_fallback` (default `True`). **With valid JSON state present, TCP never touches the workbook**, which is why TCP has no protected-folder boot dependency.

**Uploader ingest.** Program `TCP`, required `stonex_nlv`, optional `cash_transfer` (negatives rejected), mapped to Cash Balance and Cash Transfers. Revision-guarded: a stale revision is rejected. Idempotency is explicit — same date with same values returns `unchanged`, same date with new values deletes the last row and re-adds, a newer date appends, and interior or older dates are rejected. Audit appends to `glenn_uploader_ingest_tcp_audit.jsonl` at the repo root.

**Benchmarks.** `^SP500TR`, `BTC-USD`, `ETH-USD` via `quantstats.utils.download_returns`, cached to disk with atomic `.tmp` + `os.replace`. `TCP_V2_SKIP_BENCHMARK_FETCH=1` switches to cache-only — very useful for a first private VPS boot with no outbound market-data access yet.

**Logging.** `logging.basicConfig(level=logging.INFO)` with logger `tcp_ts_v2`, writing to stderr. No file handler.

---

## AGM / Momentum Pacer architecture

**Entry point:** `Momentum Pacer\mp_ts.py` (165,673 bytes). It inserts the worktree root onto `sys.path` (`_TS_ROOT = Path(__file__).resolve().parent.parent`) so it can import the shared `tearsheet_*` and `algominds_*` modules that live one level up. The launcher also `cd`s into `Momentum Pacer` first.

`Momentum Pacer\calc_engine.py` is **legacy and unused** — nothing imports it. Do not deploy it.

**Server.** `app.run(host="127.0.0.1", port=resolve_agm_bind_port(), ...)` — the only app that passes `host` explicitly. Port from `AGM_BIND_PORT`, default 8304 public / 8324 staff. Debug and reloader are disabled when `MP_TS_PRODUCTION` is truthy, which `reboot_mp_ts.ps1` sets to `1`.

**Routes**

| Path | Method | Surface | Purpose |
|---|---|---|---|
| `/` | GET | public / staff | Dash tearsheet |
| `/healthz` | GET | public | `months_loaded`, `daily_rows`, `daily_fee_days`, `spx_daily_rows`, `benchmark_ticker`, and three error fields |
| `/admin` | GET | admin session | participating-accounts portal |
| `/admin/logout` | GET | admin session | clears session |
| `/api/admin/recalculate` | POST | admin session | rebuild display state from disk |
| `/api/uploader/ingest-daily-row` | POST | bearer token | Glenn uploader ingest |
| `/monthly` | GET | — | deliberate 404 |

**Authentication.** Same shared pattern. Keys are `AGM_ADMIN_TOKEN` and `AGM_SESSION_SECRET`, session key `agm_admin_authenticated`. **Neither is set in production today** — see the configuration inventory below.

**Modules.** AGM-specific `algominds_*` set, all living at the worktree root rather than inside `Momentum Pacer`: `algominds_daily_balances` (pinned TradeStation CSV loader), `algominds_benchmark_daily` (^GSPC / ^NDX cache plus yfinance), `algominds_daily_fees` (daily incentive-fee accrual and month-end crystallization), `algominds_daily_accounting` (`actual_nlv`, `accrued_unpaid_fees`, `client_net_value`), `algominds_monthly_summary`, `algominds_account_stats`, `algominds_monthly_stats`, `algominds_fee_payment_evidence`, `algominds_drawdown_semantics`, `algominds_portal_registry`, and `program_account_stats`. Plus the same shared `tearsheet_*` set and, via `tcp_admin`, the same incidental TCP module pull-in as TKP.

**Fee logic.** $30k nominal, graduated slab bands against monthly benchmark dollars, 50% when the benchmark is at or below zero, accrued daily and crystallized monthly. Payments are only recognized with evidence from `algominds_fee_payment_evidence` plus a manual `incentive_fee_paid` entry.

**State.** Everything resolves relative to `__file__` with no environment override anywhere:

| Path | Access | How built |
|---|---|---|
| `Momentum Pacer\Momentum Fee Calculation.xlsx` | read | `BASE_DIR / "Momentum Fee Calculation.xlsx"` |
| `Momentum Pacer\momentum_pacer_manual_daily_rows.json` | read/write | `os.path.join(os.path.dirname(os.path.abspath(__file__)), ...)` |
| `Momentum Pacer\data\daily_balances\balances_210TGG51_20OCT2025_07JUL2026.csv` | read | `Path(__file__).parent / "Momentum Pacer" / "data" / ...` from `algominds_daily_balances.py`, filename pinned in the constant `DAILY_BALANCES_FILENAME` |
| `Momentum Pacer\data\benchmarks\{GSPC,NDX}_daily.csv` | read/write | `Path(__file__).parent / "Momentum Pacer" / "data" / "benchmarks"` from `algominds_benchmark_daily.py` |
| `Momentum Pacer\glenn_uploader_ingest_agm_audit.jsonl` | append | relative to `mp_ts.py` |

Note the shape of the `algominds_*` paths: those modules sit at the worktree root and reach *down* into `Momentum Pacer\data\...`. The directory relationship between the shared modules and the AGM data tree must be preserved exactly, or those two paths break.

**AGM has no protected-folder dependency.** Its workbook and CSV are inside the worktree. That is a real portability advantage over TKP.

**Manual daily rows.** `agm_add_manual_daily_row` validates that the date is after the latest CSV or manual row, appends, saves, and then calls `recalculate_agm_display_state_from_disk`. The pinned TradeStation CSV is never written by the app; refreshing it is an out-of-band step that requires editing the `DAILY_BALANCES_FILENAME` constant. Two paths reach `agm_add_manual_daily_row`: the authenticated admin "Add Row" control and the uploader ingest endpoint. Since ingest is enabled, **the staff UI is not strictly required** for the daily flow.

**Uploader ingest.** Program `AGM`, required `tradestation_nlv`, optional `cash_transfer` and `fee` (stored as `incentive_fee_paid`). Replaces the newest manual row only and never overwrites CSV rows. On a failed replace it restores the prior manual list.

**Benchmarks.** `^GSPC` (fee benchmark) and `^NDX` (chart), cached as CSV, fetched from yfinance when the cached range does not cover the requested window. `AGM_BENCHMARK_CACHE_ONLY=1` forces cache-only — the AGM equivalent of TCP's skip-fetch flag and the right setting for first VPS boot.

**Logging.** `print()` and `traceback.print_exc()` only. No file handler.

**Write safety.** `momentum_pacer_manual_daily_rows.json` is written with a plain `open(path, "w")` — no lock, no temp-and-rename, no backup. Along with TKP, this is the weakest durability in the fleet.

---

## Persistent-data table

Sizes, timestamps, and SHA-256 values captured 2026-10-01 at ~11:35 local. Git tracking determined from the live worktree `.gitignore`, where `*.xlsx`, `*.csv`, the state JSONs, the `.env` files, `_runtime/`, and `glenn_uploader_ingest_*_audit.jsonl` are all ignored.

### TKP

| Field | `daily_returns_secret_state.json` | TKP source workbook | Logo PNG | `glenn_uploader_ingest_tkp_audit.jsonl` |
|---|---|---|---|---|
| Current path | `...\live-deploy-main\daily_returns_secret_state.json` | `C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents\3_Advisors Marketing (Tearsheets, PitchBooks, etc)\1. Tearsheet Project\TKP\VADI\Copy of tkp_alex_old1.xlsx` *(literal from source; never opened)* | `...\Hughes & Company - Documents\2_Hughes & Company Marketing\Branded Logo\Trianle-Only-Logo.png` *(literal from source; never opened)* | `...\live-deploy-main\glenn_uploader_ingest_tkp_audit.jsonl` |
| Type | JSON array, 896 records | xlsx | png | JSONL |
| Purpose | authoritative daily returns ledger | boot-time NAV + A:S daily table source | header branding | ingest audit trail |
| Access | read/write | read only | read only | append |
| Size | 431,598 B | not measured (protected) | not measured (protected) | 22,248 B |
| Last modified | 2026-10-01 08:38:36 | unknown | unknown | 2026-10-01 08:38:38 |
| SHA-256 | `93575C2F3F6B924D716A648B0AE0E957E6FD7FBF31A4B582EF3BA56BEB8A7D3D` | n/a | n/a | `3BF22518B514E44F90917058A475F032221FA95531E66031E18B54D2EE7C0205` |
| Tracked by Git | No | No | No | No |
| Backup required | **Yes** | **Yes** | No | Yes |
| Sensitive | **Yes** | **Yes** | No | **Yes** |
| Hardcoded | partly (`__file__`-relative) | **Yes** | **Yes** | partly (`__file__`-relative) |
| Env key today | none | **none** | none | none |
| Proposed VPS path | `C:\HC\data\tkp\daily_returns_secret_state.json` | `C:\HC\data\tkp\tkp_source_workbook.xlsx` | `C:\HC\apps\shared\assets\logo.png` | `C:\HC\logs\tkp\glenn_uploader_ingest_tkp_audit.jsonl` |
| Required for initial deploy | **Yes** | **Yes — boot-blocking** | No | No |

### TCP

| Field | `tcp_daily_returns_secret_state.json` | `.backup.json` | `.lock` | benchmark caches (3) | `glenn_uploader_ingest_tcp_audit.jsonl` | `tcp_alex.xlsx` |
|---|---|---|---|---|---|---|
| Current path | `C:\Users\H&CDanHughes\AppData\Local\HughesCompany\TCP\state\` | same dir | same dir | `C:\Users\H&CDanHughes\AppData\Local\HughesCompany\TCP\benchmark\` | `...\live-deploy-main\` | protected folder literal in `tcp_config.py:12-15` |
| Type | JSON envelope, 182 records, revision 83 | JSON | lock | JSON | JSONL | xlsx |
| Access | read/write | write | read/write | read/write | append | read (fallback only) |
| Size | 81,311 B | 80,894 B | 83 B | 797,185 / 357,558 / 263,740 B (SPXTR / BTC / ETH) | 21,279 B | not measured |
| Last modified | 2026-10-01 08:38:38 | 2026-10-01 08:38:38 | 2026-10-01 08:38:38 | 2026-10-01 11:23:58–59 | 2026-10-01 08:38:38 | unknown |
| SHA-256 | `7094B6B513999B39F32304350016C6A9EAC4C07321D515821357159FD7934386` | `91D0A1EFC8A8EE9252BF31AB5349CBF0B0819C07DB87EC04C768CA97394F9FAB` | n/a | not hashed (regenerable) | `9902F43FA3CD4050A818666CF7ABAED1E7A73D12BE5F4BBEFA9B0BBDDD1A4C19` | n/a |
| Tracked by Git | No | No | No | No | No | No |
| Backup required | **Yes** | No (derived) | No | No (regenerable) | Yes | No, while `json_active` holds |
| Sensitive | **Yes** | **Yes** | No | No | **Yes** | **Yes** |
| Hardcoded | No | No | No | No | partly | **Yes** (default; overridable) |
| Env key today | `TCP_V2_STATE_PATH` | `TCP_V2_STATE_BACKUP_PATH` | `TCP_V2_STATE_LOCK_PATH` | `TCP_V2_BENCHMARK_CACHE_PATH` (+ BTC/ETH keys) | none | `TCP_V2_WORKBOOK_PATH` |
| Proposed VPS path | `C:\HC\data\tcp\tcp_daily_returns_secret_state.json` | `...\.backup.json` | `...\.lock` | `C:\HC\data\tcp\benchmark\` | `C:\HC\logs\tcp\` | not deployed initially |
| Required for initial deploy | **Yes** | No | No | Recommended (lets you boot cache-only) | No | **No** |

Stale duplicates of the three benchmark caches also sit in `...\live-deploy-main\_runtime\` from July. They are superseded by the `HughesCompany\TCP\benchmark` copies and should not be migrated.

### AGM

| Field | `momentum_pacer_manual_daily_rows.json` | `Momentum Fee Calculation.xlsx` | pinned balances CSV | `GSPC_daily.csv` / `NDX_daily.csv` | `glenn_uploader_ingest_agm_audit.jsonl` |
|---|---|---|---|---|---|
| Current path | `...\live-deploy-main\Momentum Pacer\` | `...\live-deploy-main\Momentum Pacer\` — **symlink** to `C:\Coding Projects\Tearsheet Generator\Momentum Pacer\Momentum Fee Calculation.xlsx` | `...\Momentum Pacer\data\daily_balances\balances_210TGG51_20OCT2025_07JUL2026.csv` | `...\Momentum Pacer\data\benchmarks\` | `...\Momentum Pacer\` |
| Type | JSON array, 59 rows | xlsx | CSV | CSV | JSONL |
| Purpose | manual daily NAV / transfers / fees paid | fee-engine reconciliation reference and starting capital | pinned TradeStation daily balances | benchmark cache | ingest audit trail |
| Access | read/write | read only | read only | read/write | append |
| Size | 7,658 B | **0 B as the link; 365,554 B at the target** | 17,852 B | 6,371 / 5,730 B | 23,124 B |
| Last modified | 2026-10-01 08:38:38 | link 2026-07-11 19:30:14; target 2026-05-05 15:27:28 | 2026-07-11 19:30:08 | 2026-07-30 / 2026-07-11 | 2026-10-01 08:38:39 |
| SHA-256 | `62612BD23E730B94AC70A5DBDB4B98E1A8079D9721E2515D411C252157CBD5B6` | **do not trust `B63A1C...`** — that is the hash of the empty reparse point, not the workbook | `D4B5B781BDD3FA80707A1A00D7FF663ECFA7E75D7621B09FA14A345683B017A9` | `928E8B6A...` / `49D07010...` | `A986DB156444C4203E4F520B72AD6515A2321812017C6A83E7CC3B11E2E6EA4A` |
| Tracked by Git | No | No | No | No | No |
| Backup required | **Yes** | **Yes** | **Yes** | No (regenerable) | Yes |
| Sensitive | **Yes** | **Yes** | **Yes** | No | **Yes** |
| Hardcoded | `__file__`-relative | `__file__`-relative | `__file__`-relative + pinned filename constant | `__file__`-relative | `__file__`-relative |
| Env key today | none | none | none | none | none |
| Proposed VPS path | `C:\HC\data\agm\momentum_pacer_manual_daily_rows.json` | `C:\HC\data\agm\Momentum Fee Calculation.xlsx` | `C:\HC\data\agm\daily_balances\balances_210TGG51_20OCT2025_07JUL2026.csv` | `C:\HC\data\agm\benchmarks\` | `C:\HC\logs\agm\` |
| Required for initial deploy | **Yes** | **Yes** | **Yes** | Recommended | No |

### Reparse-point inventory — read this before packaging

The live worktree contains five reparse points pointing back into the dirty development checkout. Any copy tool that does not follow links will produce empty files.

| Link in live worktree | Kind | Target |
|---|---|---|
| `.venv310` | Junction | `C:\Coding Projects\Tearsheet Generator\.venv310` |
| `.local_dev.env` | SymbolicLink | `C:\Coding Projects\Tearsheet Generator\.local_dev.env` |
| `.tcp_production.env` | SymbolicLink | `C:\Coding Projects\Tearsheet Generator\.tcp_production.env` |
| `.tkp_production.env` | SymbolicLink | `C:\Coding Projects\Tearsheet Generator\.tkp_production.env` |
| `Momentum Pacer\Momentum Fee Calculation.xlsx` | SymbolicLink | `C:\Coding Projects\Tearsheet Generator\Momentum Pacer\Momentum Fee Calculation.xlsx` |

### Known data-quality observations — documented, not fixed

1. **TKP row-count mismatch.** `daily_returns_secret_state.json` holds 896 records, but `/healthz` reports `rows_loaded: 766`. The two numbers come from different sources — the JSON is the full persisted editor table while `rows_loaded` reflects the Excel-derived NAV frame bounded by `FORCE_LAST_EXCEL_ROW = 715`. Reconcile this *before* trusting a VPS-vs-laptop row-count comparison for TKP, or compare both numbers independently.
2. **AGM fee workbook is stale relative to the data.** Target last modified 2026-05-05, while manual rows run through 2026-09-30. This is probably by design (the workbook is a reconciliation reference, not a live feed), but confirm before migrating.
3. **AGM pinned CSV covers 20 Oct 2025 – 07 Jul 2026** per its filename, while manual rows start 2026-07-11. The CSV and the manual JSON are adjacent, not overlapping. Preserve both.
4. **Orphan env file.** `C:\Users\H&CDanHughes\AppData\Local\HughesCompany\TCP\production.env` (553 B, 2026-07-04) is not loaded by any current launcher. Treat as stale; do not migrate without review.
5. **`assets/styles.css` differs between checkouts.** The dirty checkout shows it modified (`M assets/styles.css` in `git status`), while the live worktree copy is dated 2026-08-01. Package the **live worktree** copy, not the dirty one.

---

## Python / runtime dependencies

**One shared virtual environment serves all four tearsheets today:** `C:\Coding Projects\Tearsheet Generator\.venv310`, reached from the live worktree through the `.venv310` junction.

| Property | Value |
|---|---|
| Interpreter | `C:\Coding Projects\Tearsheet Generator\.venv310\Scripts\python.exe` |
| Base interpreter | `C:\Python310` |
| Version | 3.10.0 (tags/v3.10.0:b494f59, Oct 4 2021, MSC v.1929 64-bit) |
| Requirements file | `...\live-deploy-main\requirements.txt`, 51 fully pinned entries |

**Verified installed versions** (queried from the live venv): `dash==3.0.4`, `dash-bootstrap-components==2.0.3`, `flask==3.0.3`, `Werkzeug==3.0.6`, `pandas==2.2.3`, `numpy==2.2.6`, `plotly==6.1.1`, `openpyxl==3.1.5`, `yfinance==0.2.61`, `quantstats==0.0.64`, `markupsafe==3.0.2`, `scipy==1.15.3`, `matplotlib==3.10.3`, `seaborn==0.13.2`, `tabulate==0.9.0`, `requests==2.32.3`, `pytest==8.4.2`.

**Gaps in `requirements.txt`**

| Package | Status | Note |
|---|---|---|
| `openpyxl` | **absent from `requirements.txt`** but installed at 3.1.5 and imported directly by `tkp_ts.py`, `mp_ts.py`, and `tcp_ledger.py` | **Must be added to the VPS install set.** Every workbook read fails without it. |
| `dash-bootstrap-components` | **absent from `requirements.txt`** but installed at 2.0.3 and imported as `dbc` by all three apps | **Must be added.** |
| `pytest` | installed at 8.4.2, not in `requirements.txt` | needed only if you want to run the test suite on the VPS for validation |
| `matplotlib`, `seaborn`, `scipy`, `tabulate` | in `requirements.txt` | pulled in by `quantstats`; keep them |

**Other runtime requirements**

- **Workbook library:** `openpyxl` only. No Excel installation and no COM automation anywhere.
- **Charts:** Plotly rendered client-side as JSON; no server-side image export, so no Kaleido or Orca and no headless browser.
- **Fonts:** none required. All typography is CSS, and `matplotlib` is never used to render a figure in the request path.
- **Local binaries:** none beyond Python itself. `tcp_state.py` uses `msvcrt` for file locking — standard library, Windows-only, fine on Server 2025.
- **Browser:** not needed. The launchers do not open a browser.
- **Outbound network:** required for benchmarks on first boot unless you use the cache-only flags (`TCP_V2_SKIP_BENCHMARK_FETCH=1`, `AGM_BENCHMARK_CACHE_ONLY=1`). TKP has no such flag and no cache, so it will attempt yfinance/quantstats downloads at every start.

**Recommendation: one shared virtual environment at `C:\HC\apps\shared\.venv310`.** It is safe and it is what production already does. All three apps are pinned to identical versions of an identical dependency set, there is no version conflict to isolate, and because TKP and AGM both import TCP modules through `tcp_admin`, per-app environments would mean three copies of the same packages plus triple the patching surface. Use Python 3.10.x to match production exactly — do not jump to 3.12 or 3.13 during a migration, since `numpy 2.2.6` / `pandas 2.2.3` / `quantstats 0.0.64` behavior is what the current reconciliation baseline was produced under.

Install order on the VPS: `python -m venv`, then `pip install -r requirements.txt`, then explicitly `pip install openpyxl==3.1.5 dash-bootstrap-components==2.0.3`, then `pip freeze` and diff against the laptop's freeze before starting any service.

---

## Configuration / environment inventory

### Configuration sources, in load order

1. `.local_dev.env` — loaded by **all three** production launchers. Real path `C:\Coding Projects\Tearsheet Generator\.local_dev.env`, symlinked into the worktree.
2. `.tkp_production.env` — loaded by `reboot_tkp_ts.ps1` and `reboot_tkp_staff.ps1` only.
3. `.tcp_production.env` — loaded by `reboot_tcp_ts.ps1` and `reboot_tcp_staff.ps1` only.
4. `.staff.env` — loaded by the three `*_staff.ps1` launchers only.
5. Launcher-set variables — `PYTHONIOENCODING`, `TEARSHEET_MODE`, `MP_TS_PRODUCTION`, and forced staff ports.
6. Python constants — `tcp_config.py` defaults, `tearsheet_runtime_mode.py` port defaults, `FORCE_LAST_EXCEL_ROW`, `DAILY_BALANCES_FILENAME`.
7. `Manager\startup_contract.json` and `Manager\tearsheet_fleet_runtime.json` — fleet launcher metadata, not application config.

The env files use batch syntax (`set "KEY=value"`), parsed by a PowerShell `Import-BatchEnvFile` helper with the regex `^set "(.+)"$`. There are no `.env`, YAML, or JSON application config files.

### Variable inventory

No values are printed for anything marked secret.

| Variable | Consumer | Secret | Required | Current source | Future VPS destination | Class |
|---|---|---|---|---|---|---|
| `TEARSHEET_MODE` | all three | No | Yes | launcher (`public` / `staff`) | NSSM per-service env | path/config |
| `TKP_BIND_PORT` | TKP | No | No | unset (defaults 8301) | `C:\HC\config\tkp.env` | network |
| `TCP_V2_BIND_PORT` | TCP | No | Yes | `.tcp_production.env` = `8302` | `C:\HC\config\tcp.env` | network |
| `AGM_BIND_PORT` | AGM | No | No | unset (defaults 8304) | `C:\HC\config\agm.env` | network |
| `MP_TS_PRODUCTION` | AGM | No | Yes | `reboot_mp_ts.ps1` = `1` | NSSM per-service env | path/config |
| `PYTHONIOENCODING` | all three | No | Yes (practically) | launcher = `utf-8` | NSSM per-service env | path/config |
| `TKP_ADMIN_TOKEN` | TKP | **Yes** | Yes | `.tkp_production.env` | `C:\HC\secrets\tkp.env` | secret |
| `TKP_SESSION_SECRET` | TKP | **Yes** | Yes | `.tkp_production.env` | `C:\HC\secrets\tkp.env` | secret |
| `TCP_V2_ADMIN_TOKEN` | TCP | **Yes** | Yes | `.tcp_production.env` | `C:\HC\secrets\tcp.env` | secret |
| `TCP_V2_SESSION_SECRET` | TCP | **Yes** | Yes | `.tcp_production.env` | `C:\HC\secrets\tcp.env` | secret |
| `AGM_ADMIN_TOKEN` | AGM | **Yes** | Yes | **not set — falls back to a code default** | `C:\HC\secrets\agm.env` | secret |
| `AGM_SESSION_SECRET` | AGM | **Yes** | Yes | **not set — falls back to a code default** | `C:\HC\secrets\agm.env` | secret |
| `TCP_V2_STATE_MODE` | TCP | No | Yes | `.tcp_production.env` = `json_active` | `C:\HC\config\tcp.env` | path/config |
| `TCP_V2_STATE_PATH` | TCP | No | Yes | `.tcp_production.env` | `C:\HC\config\tcp.env` | path/config |
| `TCP_V2_STATE_BACKUP_PATH` | TCP | No | Yes | `.tcp_production.env` | `C:\HC\config\tcp.env` | path/config |
| `TCP_V2_STATE_LOCK_PATH` | TCP | No | Yes | `.tcp_production.env` | `C:\HC\config\tcp.env` | path/config |
| `TCP_V2_BENCHMARK_CACHE_PATH` | TCP | No | No | `.tcp_production.env` | `C:\HC\config\tcp.env` | path/config |
| `TCP_V2_BENCHMARK_BTC_CACHE_PATH` | TCP | No | No | unset (sibling of SPXTR override) | `C:\HC\config\tcp.env` | path/config |
| `TCP_V2_BENCHMARK_ETH_CACHE_PATH` | TCP | No | No | unset | `C:\HC\config\tcp.env` | path/config |
| `TCP_V2_WORKBOOK_PATH` | TCP | No | No | unset (hardcoded default in `tcp_config.py`) | `C:\HC\config\tcp.env` | path/config |
| `TCP_V2_ALLOW_WORKBOOK_FALLBACK` | TCP | No | No | unset (default `True`) | **set to `false` on VPS** | path/config |
| `TCP_V2_SKIP_BENCHMARK_FETCH` | TCP | No | No | unset | `C:\HC\config\tcp.env` — `1` for first boot | optional |
| `AGM_BENCHMARK_CACHE_ONLY` | AGM | No | No | unset | `C:\HC\config\agm.env` — `1` for first boot | optional |
| `GLENN_UPLOADER_INGEST_ENABLED` | all three | No | Yes | `.local_dev.env` = `true` | `C:\HC\config\<app>.env` | path/config |
| `GLENN_UPLOADER_INGEST_TOKEN` | all three | **Yes** | Yes | `.local_dev.env` | `C:\HC\secrets\ingest.env` | secret |
| `GLENN_UPLOADER_INGEST_DRY_RUN_ALLOWED` | all three | No | No | `.local_dev.env` = `true` | `C:\HC\config\<app>.env` | optional |
| `TEARSHEET_LOCAL_DIRECT_ADMIN` | all three | No | No | `.local_dev.env` = `1` | **do not migrate** | optional |
| `TEARSHEET_STAFF_ALLOWED_HOSTS` | all three (staff) | No | staff only | `.staff.env` = `tkp-admin.hcresearch.ltd,tcp-admin.hcresearch.ltd,agm-admin.hcresearch.ltd` | `C:\HC\config\staff.env` | network |

### Configuration problems to fix during migration, not carry forward

- **`.local_dev.env` is production configuration under a development name.** It holds the live ingest token and is loaded by every production launcher. On the VPS, split it: non-secret flags into `C:\HC\config\*.env`, the token into `C:\HC\secrets\ingest.env`.
- **`TEARSHEET_LOCAL_DIRECT_ADMIN=1` is set in production.** It is partially mitigated — the bypass additionally requires the `/admin/tearsheet` path, a loopback peer, and a loopback `Host` header — but it should not be set on a server. Leave it out.
- **AGM runs on default credentials.** `reboot_mp_ts.ps1` never loads a production env file, so `AGM_ADMIN_TOKEN` and `AGM_SESSION_SECRET` resolve to `tcp_config.DEFAULT_SIBLING_ADMIN_TOKEN` / `DEFAULT_SIBLING_SESSION_SECRET`. Generate real values for the VPS and create the missing `.agm_production.env` equivalent. (`.gitignore` already anticipates `.agm_production.env`, so this was a planned file that was never created.)
- **Shared ingest token across all three programs.** One `GLENN_UPLOADER_INGEST_TOKEN` authenticates TKP, TCP, and AGM. Per-app tokens on the VPS would contain the blast radius, but that is a behavior change — do not introduce it during the migration itself.

---

## Uploader integration

The Glenn uploader is the `uploader/` subtree of this same repository: a FastAPI backend plus a Vite frontend, deployed to Fly.io (`uploader/fly.toml` app `glenn-uploader-sandbox`, production hostname documented as `uploader.hcresearch.ltd`). It is **in scope for inspection only** — nothing about it was modified and no request was sent.

### Flow

```
Glenn uploader (Fly.io)
  → POST https://<tearsheet-host>/api/uploader/ingest-daily-row
  → Authorization: Bearer <GLENN_UPLOADER_INGEST_TOKEN>
  → shared framework: tearsheet_uploader_ingest.register_uploader_ingest()
      • env gate: GLENN_UPLOADER_INGEST_ENABLED must be true          → 403
      • token compare (constant-time)                                  → 401
      • program must match the endpoint's configured program            → 422
      • date must be ISO YYYY-MM-DD; unknown fields rejected            → 422
      • global per-process _APPLY_LOCK acquired
  → per-app apply()
  → state file written
  → on_persisted → recalculation
  → audit line appended (JSONL)
  → Dash 3-second interval refreshes the public and admin views
```

### Per-program detail

| | TKP | TCP | AGM |
|---|---|---|---|
| Endpoint | `POST /api/uploader/ingest-daily-row` | same | same |
| Program code | `TKP` | `TCP` | `AGM` |
| Auth | bearer `Authorization`, or `X-Glenn-Uploader-Token` | same | same |
| Required field | `stonex_nlv` | `stonex_nlv` | `tradestation_nlv` |
| Optional fields | `plus500_nlv`, `cash_transfer` | `cash_transfer` (negatives rejected) | `cash_transfer`, `fee` → `incentive_fee_paid` |
| Target app | `tkp_ts.py` on 8301 | `tcp_ts_v2.py` on 8302 | `mp_ts.py` on 8304 |
| State file written | `daily_returns_secret_state.json` | `tcp_daily_returns_secret_state.json` | `momentum_pacer_manual_daily_rows.json` |
| Write durability | plain overwrite, **not atomic** | **lock + temp + `os.replace` + backup rotation** | plain overwrite, **not atomic** |
| Recalculation | `apply_tkp_recalculation()` | `apply_tcp_recalculation()` | `recalculate_agm_display_state_from_disk()` |
| Failure behavior | 403 disabled / 401 bad token / 422 validation; a recalculation exception still leaves the row persisted and returns `recalculation_error` | same, plus stale-revision rejection | same, plus restore of the prior manual list on a failed replace |
| Idempotency | same date + same values → `unchanged`; same date + new values → `updated`; newer date → `created`; older or interior → 422 | same, revision-guarded | same; CSV rows never overwritten |
| Retry | uploader makes **one attempt per row** in `export_row_to_production`; no in-code retry loop. Failed rows are not marked exported, so re-export relies on downstream idempotency (`unchanged` still reports `persisted=True`) | same | same |
| Audit log | `glenn_uploader_ingest_tkp_audit.jsonl` (repo root) | `glenn_uploader_ingest_tcp_audit.jsonl` (repo root) | `Momentum Pacer\glenn_uploader_ingest_agm_audit.jsonl` |

### The configuration that changes at cutover

In `uploader/backend/app/config.py` (lines ~90–95), the uploader `Settings` class exposes:

| Field | Env var | Purpose |
|---|---|---|
| `tkp_ingest_url` | `TKP_INGEST_URL` | full ingest URL for TKP |
| `tcp_ingest_url` | `TCP_INGEST_URL` | full ingest URL for TCP |
| `agm_ingest_url` | `AGM_INGEST_URL` | full ingest URL for AGM |
| `downstream_ingest_token` | `DOWNSTREAM_INGEST_TOKEN` (alias `DOWNSTREAM_API_TOKEN`) | bearer sent to the tearsheets |

These are supplied as Fly secrets, not committed values. **When the VPS becomes authoritative, exactly one of these three URLs changes per migrated app** — point it at the VPS hostname with the same `/api/uploader/ingest-daily-row` suffix. `uploader/backend/scripts/verify_downstream_ingest.py` reads the same `Settings` and is the designed preflight check. Nothing was changed.

AGM is **not** purely manual: it has the same ingest endpoint as the other two, writing through `agm_add_manual_daily_row` into the manual JSON and merging with the TradeStation CSV for display.

---

## Startup architecture

### Today

```
Windows logon
  → %APPDATA%\...\Startup\HC Launch All Services.cmd
  → powershell -File C:\Coding Projects\Manager\startup_launch_all_services.ps1
  → C:\Python313\python.exe C:\Coding Projects\Manager\launch_all_services.py   (PID 36276, still resident)
  → per-service launcher from Manager\startup_contract.json
      reboot_tkp_ts.bat → reboot_tkp_ts.ps1 → .venv310\python tkp_ts.py       (8301)
      reboot_tcp_ts.bat → reboot_tcp_ts.ps1 → .venv310\python tcp_ts_v2.py     (8302)
      reboot_mp_ts.bat  → reboot_mp_ts.ps1  → .venv310\python mp_ts.py         (8304)
```

`Manager\tearsheet_fleet_runtime.json` pins `runtime_root` to the live worktree and `dirty_root` to the development checkout, and maps each service to its client launcher, staff launcher, and service subfolder. Each `reboot_*.ps1` enforces that pinning itself: if `$PSScriptRoot` equals the dirty root it refuses to start and tells the operator to use the canonical runtime. That guard is good hygiene locally and becomes dead weight on the VPS, where the dirty root will not exist.

| Property | Current behavior |
|---|---|
| Auto-start | Yes — `auto_start: true` for all three in `startup_contract.json`, triggered by the user Startup folder |
| Requires interactive logon | **Yes** — this is the biggest structural weakness |
| Browser launch | No |
| Duplicate-process prevention | Partial — handled by `launch_all_services.py` port checks, not by the launchers themselves |
| Crash auto-restart | **No.** `launch_all_services.py` has no restart loop for these services; a single `process.poll()` and a `while True` at line 1268 relate to launch sequencing, not supervision. `pm2_monitor*` scripts exist in `Manager\` but are not supervising the tearsheets. |
| Scheduled tasks | None for these services |
| Windows services | None for these services |
| Ingress | `Cloudflared` Windows service, `Automatic`, running, remotely managed via a tunnel token in the service binary path. Ingress hostname-to-port mapping lives in the Cloudflare dashboard, not on this machine (`%USERPROFILE%\.cloudflared` contains only `cert.pem`). |

### Proposed NSSM services on the VPS

Three services for the public tearsheets. Staff services are deliberately omitted from the initial build.

| Property | Service 1 | Service 2 | Service 3 |
|---|---|---|---|
| Service name | `HC-TCP-Tearsheet` | `HC-TKP-Tearsheet` | `HC-AGM-Tearsheet` |
| Program | TCP | TKP | AGM / Momentum Pacer |
| Role | public tearsheet | public tearsheet | public tearsheet |
| Port | 8302 | 8301 | 8304 |
| Python executable | `C:\HC\apps\shared\.venv310\Scripts\python.exe` | same | same |
| Entry point | `C:\HC\apps\tcp\tcp_ts_v2.py` | `C:\HC\apps\tkp\tkp_ts.py` | `C:\HC\apps\agm\Momentum Pacer\mp_ts.py` |
| Working directory | `C:\HC\apps\tcp` | `C:\HC\apps\tkp` | `C:\HC\apps\agm\Momentum Pacer` |
| Environment profile | `C:\HC\config\tcp.env` + `C:\HC\secrets\tcp.env` + `secrets\ingest.env` | `config\tkp.env` + `secrets\tkp.env` + `secrets\ingest.env` | `config\agm.env` + `secrets\agm.env` + `secrets\ingest.env` |
| stdout log | `C:\HC\logs\tcp\tcp_stdout.log` | `C:\HC\logs\tkp\tkp_stdout.log` | `C:\HC\logs\agm\agm_stdout.log` |
| stderr log | `C:\HC\logs\tcp\tcp_stderr.log` | `C:\HC\logs\tkp\tkp_stderr.log` | `C:\HC\logs\agm\agm_stderr.log` |
| Startup type | Automatic | Automatic | Automatic |

Three NSSM settings matter specifically for these apps:

- **`AppStopMethodSkip` / process-tree kill.** Because the venv `python.exe` is a launcher stub that spawns a child, NSSM must terminate the whole tree or you will leak orphaned listeners on restart.
- **`AppExit Default Restart` with a throttle.** This is the capability the laptop lacks entirely. Set `AppThrottle` to at least 10 seconds so a boot-time failure (missing workbook, unreadable state) does not become a restart storm.
- **`AppRotateFiles`** for log rotation, since none of the apps rotate anything themselves.

Replacing the launchers with services also removes the interactive-logon requirement, which is the main reason the current setup cannot survive an unattended reboot cleanly.

---

## Remaining VPS portability blockers

Path portability status per file. "Centralized" means resolved through `tearsheet_paths.py`, which **is not present in production** — so the first column is `No` for every row on `live-main`.

| File | Centralized | Env-controlled | Laptop default preserved | VPS profile defined | VPS target path | Remaining blocker |
|---|---|---|---|---|---|---|
| TKP state JSON | No | No | n/a | on branch only | `C:\HC\data\tkp\daily_returns_secret_state.json` | `__file__`-relative; no env key |
| **TKP source workbook** | No | **No** | n/a | on branch only | `C:\HC\data\tkp\tkp_source_workbook.xlsx` | **hardcoded protected-folder literal, `sys.exit(1)` if missing** |
| TKP logo PNG | No | No | n/a | on branch only | `C:\HC\apps\shared\assets\logo.png` | hardcoded literal; degrades gracefully |
| TKP ingest audit | No | No | n/a | on branch only | `C:\HC\logs\tkp\` | `__file__`-relative |
| TCP state / backup / lock | No | **Yes** | Yes | effectively | `C:\HC\data\tcp\` | none |
| TCP benchmark cache | No | **Yes** | Yes | effectively | `C:\HC\data\tcp\benchmark\` | BTC/ETH keys unset; they default beside the SPXTR override, so set all three explicitly |
| TCP workbook | No | **Yes** | Yes | effectively | not deployed initially | hardcoded default, but overridable and unused in `json_active` |
| TCP ingest audit | No | No | n/a | on branch only | `C:\HC\logs\tcp\` | `REPO_ROOT`-relative |
| AGM manual rows JSON | No | No | n/a | on branch only | `C:\HC\data\agm\` | `__file__`-relative |
| AGM fee workbook | No | No | n/a | on branch only | `C:\HC\data\agm\` | `__file__`-relative **and a symlink into the dirty checkout** |
| AGM pinned CSV | No | No | n/a | on branch only | `C:\HC\data\agm\daily_balances\` | `__file__`-relative from a root-level module reaching into `Momentum Pacer\data\...`; filename pinned in a constant |
| AGM benchmark CSVs | No | No | n/a | on branch only | `C:\HC\data\agm\benchmarks\` | same shape; regenerable |
| AGM ingest audit | No | No | n/a | on branch only | `C:\HC\logs\agm\` | `__file__`-relative |

### Concrete blockers

**Blocker 1 — TKP boot-critical protected-folder workbook. Severity: blocking.**
`tkp_ts.py:244` hardcodes the path; lines 379–387 call `sys.exit(1)` when the file is absent or unreadable, and the `except` handlers at 444–452 do the same for any read failure. There is no env override on `live-main`. TKP cannot start on the VPS until either the portability branch is merged or an identical directory tree is recreated on the server. Recreating the tree is not viable — it is a OneDrive-synced business folder.

**Blocker 2 — the central path module is not in production. Severity: blocking for TKP, minor for TCP and AGM.**
`tearsheet_paths.py` exists on `feature/central-path-config`, `feature/tkp-central-path-config`, `feature/path-portability-integration`, `feature/vps-portability-completion`, and `feature/windows-vps-deployment-layout`, with tests and documentation. `feature/vps-portability-completion` is the most complete and already uses `C:\HC\` as the canonical root (earlier branches and some `docs/migration/` files still say `E:\H&C\` — superseded). None of it is merged into `live-main` (`3cfda4f`). It defines an `HC_APP_ENV` profile selector (`local-dev` / `local-production` / `vps-sandbox` / `vps-production`) plus `HC_DATA_ROOT`, `HC_LOG_ROOT`, `HC_BACKUP_ROOT`, `HC_CACHE_ROOT`, and per-file keys including `HC_TKP_STATE_PATH`, `HC_TKP_SOURCE_WORKBOOK`, `HC_AGM_MANUAL_STATE_PATH`, `HC_AGM_FEE_WORKBOOK`, `HC_AGM_PINNED_CSV`, and `HC_TCP_DATA_ROOT`. Merging it is the cleanest route to a portable TKP.

**Blocker 3 — five reparse points make the live tree non-self-contained. Severity: minor, but a silent-corruption risk.**
Listed in the persistent-data section. Packaging must resolve them to real files.

**Blocker 4 — AGM has no production secrets. Severity: minor.**
Admin token and session secret fall back to code defaults. Create `C:\HC\secrets\agm.env`.

**Blocker 5 — launcher dirty-root guards and the `Manager` dependency. Severity: minor.**
Every `reboot_*.ps1` hardcodes `C:\Coding Projects\Tearsheet Generator` and references `C:\Coding Projects\Manager\tearsheet_fleet_runtime.json`. NSSM replaces this entirely, so the launchers simply should not be deployed.

**Blocker 6 — `openpyxl` and `dash-bootstrap-components` are missing from `requirements.txt`. Severity: minor, but guaranteed to bite.**
A clean `pip install -r requirements.txt` produces an environment where all three apps fail on import.

**Blocker 7 — TKP has no benchmark cache. Severity: minor.**
TKP downloads benchmarks on every boot with no cache and no skip flag, so first boot on a locked-down VPS may produce a degraded tearsheet.

---

## Recommended pilot tearsheet

### Comparison

| Criterion | TKP | TCP | AGM |
|---|---|---|---|
| Dependency complexity | monolithic 225 KB entry point; business logic inline | thin entry point over 12 focused modules | 165 KB entry point plus 11 `algominds_*` modules at the parent level |
| State-file complexity | 896 rows, 17 columns, non-atomic write, no backup | 182 rows, versioned envelope with revision counter, lock + atomic write + backup | 59 manual rows merged with a CSV, non-atomic write, no backup |
| Workbook dependency | **boot-critical, in the protected folder, hardcoded** | optional — only a fallback when JSON is missing; env-overridable | required at boot but inside the repo tree; currently a symlink |
| Uploader complexity | latest-row-only apply | latest-row-only apply **with revision guard** and explicit idempotency | replace-newest-manual-row, must not disturb CSV rows |
| Admin dependency | not required | not required | not required (ingest covers the daily path) |
| Path portability today | **worst** — zero env keys, one blocking hardcoded path | **best** — state, backup, lock, benchmark cache, and workbook are all env-driven, and state already lives outside the repo | middling — no env keys, but no protected-folder dependency |
| Test coverage | TKP tests exist, mostly chart and cashflow | strongest: `test_tcp_foundation`, `test_tcp_runtime_state`, `test_tcp_resilience_acceptance`, `test_tcp_drawdown`, `test_tcp_public_content`, plus golden-fixture extraction | moderate: `test_agm_portal_registry`, `test_program_account_stats` |
| Ease of reconciliation | **hardest** — `/healthz` exposes only `rows_loaded`, which already disagrees with the JSON record count (766 vs 896) | **easiest** — `/healthz` exposes `state_revision`, `record_count`, `first_completed_date`, `latest_completed_date`, `data_source`, `state_writable`, `recovery_status` | moderate — `/healthz` gives `daily_rows`, `months_loaded`, `daily_fee_days`, and explicit error fields |
| Cache-only first boot | **not supported** | `TCP_V2_SKIP_BENCHMARK_FETCH=1` | `AGM_BENCHMARK_CACHE_ONLY=1` |

### Recommendation: migrate TCP first

TCP wins on every axis that determines whether a pilot *teaches you something* versus *gets stuck*.

The decisive factor is that **TCP is the only one of the three that can boot on a clean VPS with no code changes at all.** Its state path, backup path, lock path, and benchmark cache path are already environment variables, and its production state already lives outside the repository at `C:\Users\H&CDanHughes\AppData\Local\HughesCompany\TCP\`. That is exactly the code-and-data separation the `C:\HC\` layout is designed around — TCP has effectively already been through the migration on the laptop. Point the same four variables at `C:\HC\data\tcp\`, copy one JSON file, and it runs.

Second, TCP is the only app whose writes are crash-safe (lock, temp file, atomic rename, backup rotation), which is what you want when you are learning how NSSM restarts behave and how reboot-recovery testing goes. A hard stop mid-write on TKP or AGM can truncate the authoritative state file.

Third, TCP's `/healthz` is purpose-built for exactly the local-versus-VPS comparison this migration needs. `state_revision: 83` plus `record_count: 182` plus `latest_completed_date: 2026-09-30` gives an unambiguous three-way match. TKP's health endpoint gives one number that already disagrees with its own state file.

Fourth, TCP has the deepest test suite, including a resilience-acceptance suite that specifically exercises missing state, corrupt state, and workbook-fallback behavior — the precise failure modes a fresh deployment hits.

### Why not the other two

**TKP is disqualified, not merely deprioritized.** The hardcoded protected-folder workbook with a `sys.exit(1)` on absence means TKP cannot start on the VPS at all until either `feature/vps-portability-completion` is merged or that exact OneDrive directory tree is reproduced on a server that has no business being joined to OneDrive. Choosing TKP as the pilot means the pilot's first task is a code merge into production, which is the opposite of what a pilot is for. The alphabetical-ordering instinct points at exactly the wrong app here.

**AGM is a reasonable second but a poor first.** It has no protected-folder dependency, which is genuinely in its favor. But it has zero environment-driven paths, so every data location is implied by directory structure — including two `algominds_*` modules at the worktree root that reach down into `Momentum Pacer\data\...`, which means the pilot would be simultaneously testing a layout change and a path-resolution assumption. Its fee workbook is currently a symlink into the dirty checkout, its manual-rows write is non-atomic, it has no production secrets, and it fetches benchmarks from yfinance at import. Migrate it third, after TCP has proven the layout and TKP has forced the path-portability merge that AGM will also benefit from.

### Resulting order

1. **TCP** — proves the `C:\HC\` layout, the shared venv, NSSM, and reconciliation with almost no risk and no code change.
2. **TKP** — forces the path-portability merge and the protected-folder workbook decision, the two hardest problems, with the platform already de-risked.
3. **AGM** — inherits the merged path work and the proven layout; its remaining work is mostly data placement and generating real secrets.

---

## Overall readiness

### TKP — NOT READY

| Dimension | Assessment |
|---|---|
| Code portability | **Fail** — boot-critical hardcoded path into the protected folder with `sys.exit(1)` on absence, and no env override on `live-main` |
| Data portability | Partial — the state JSON copies cleanly, but the source workbook is in a folder that cannot be inspected or moved under current rules |
| Dependency reproducibility | Pass, once `openpyxl` and `dash-bootstrap-components` are added |
| Startup reproducibility | Pass — NSSM maps cleanly |
| Configuration completeness | Pass — `.tkp_production.env` supplies both secrets |
| Reconciliation readiness | **Weak** — `rows_loaded: 766` vs 896 JSON records must be explained first |

Blockers: (1) hardcoded protected-folder workbook, boot-blocking; (2) `tearsheet_paths.py` not merged into `live-main`; (3) the 766-vs-896 discrepancy; (4) no benchmark cache and no skip flag.

### TCP — READY WITH MINOR BLOCKERS

| Dimension | Assessment |
|---|---|
| Code portability | **Pass** — all production data paths already env-driven; no protected-folder dependency at boot |
| Data portability | **Pass** — one 81 KB JSON file plus optional caches; state already outside the repo |
| Dependency reproducibility | Pass, with the two missing requirements added |
| Startup reproducibility | Pass |
| Configuration completeness | Pass — both secrets present; needs `TCP_V2_ALLOW_WORKBOOK_FALLBACK=false` and explicit BTC/ETH cache paths |
| Reconciliation readiness | **Strong** — revision 83, 182 records, 2026-09-30, plus a file hash |

Blockers: (1) `openpyxl` and `dash-bootstrap-components` missing from `requirements.txt`; (2) `TCP_V2_ALLOW_WORKBOOK_FALLBACK` defaults to `True` and must be set `false` so a missing JSON fails loudly instead of silently serving stale read-only workbook data; (3) BTC and ETH cache paths are unset and default beside the SPXTR override — set all three; (4) `glenn_uploader_ingest_tcp_audit.jsonl` is `REPO_ROOT`-relative and will land in the code directory unless the audit-path work is merged.

### AGM — READY WITH MINOR BLOCKERS

| Dimension | Assessment |
|---|---|
| Code portability | Partial — no protected-folder dependency, but zero env-driven paths; correctness depends entirely on preserving directory relationships |
| Data portability | Partial — the fee workbook is a symlink into the dirty checkout and must be resolved; the pinned CSV filename is a code constant |
| Dependency reproducibility | Pass, with the two missing requirements added |
| Startup reproducibility | Pass — note the launcher `cd`s into `Momentum Pacer`, so NSSM must set that working directory |
| Configuration completeness | **Fail** — no production env file; admin token and session secret fall back to code defaults |
| Reconciliation readiness | Moderate — 59 manual rows, 184 daily rows, 10 months, latest 2026-09-30 |

Blockers: (1) no `AGM_ADMIN_TOKEN` / `AGM_SESSION_SECRET` in production; (2) the fee workbook symlink must be resolved to its 365,554-byte target before packaging; (3) `algominds_daily_balances.py` and `algominds_benchmark_daily.py` sit at the worktree root and reach into `Momentum Pacer\data\...`, so that relationship must be preserved exactly or those paths break; (4) the pinned CSV filename is the constant `DAILY_BALANCES_FILENAME`, not configuration; (5) non-atomic manual-rows write means a mid-write restart can truncate state.

---

## Appendix — evidence commands used

All read-only.

```
Get-NetTCPConnection -State Listen                       # port ownership
Get-CimInstance Win32_Process                            # command lines, parents, uptime, memory
Get-Item -Force / Get-ChildItem -Force                   # sizes, timestamps, LinkType, Target
Get-FileHash -Algorithm SHA256                           # state-file hashes
Invoke-WebRequest http://127.0.0.1:{8301,8302,8304}/healthz    # health and baseline
Invoke-WebRequest https://{tkp,tcp,agm}-ts.hcresearch.ltd/     # public reachability
.venv310\Scripts\python.exe -c "import sys; ..."         # interpreter and package versions
python -c "import json; ..."                             # state-file metadata only
git -C "C:\Coding Projects\Tearsheet Generator" {branch,log,worktree list,status --short}
```

`git` in the live worktree fails with "dubious ownership" because `.git` there is owned by `BUILTIN\Administrators`. Per the operating constraints, `safe.directory` was **not** added. The live commit was read directly from `.git\worktrees\live-deploy-main\HEAD` (`ref: refs/heads/live-main`) and `git rev-parse live-main` in the main checkout instead.
