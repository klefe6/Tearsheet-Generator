# Repo Map — Tearsheet Generator

Documentation only. This file maps the repository **as it is**, ahead of any future
reorganization. Nothing in this PR changes runtime behavior, file locations, imports,
launchers, ports, routes, or data.

- Verified against: `main` @ `da4c881` (merge of PR #19, tearsheet runtime modes), 2026-07-09.
- Machine context (live ports, elevated processes, untracked files) reflects the ops
  machine on that date and can drift; re-verify before relying on it.

---

## 1. App entrypoints

| Program | Entrypoint | Default port | Port override (env) | Debug behavior | Status |
|---|---|---|---|---|---|
| TKP | `tkp_ts.py` | 8301 | `TKP_BIND_PORT` | `debug=True` always | **LIVE production** |
| TCP v2 (current) | `tcp_ts_v2.py` | 8312 (preview default) | `TCP_V2_BIND_PORT` (=8302 in production) | `cfg.debug`, default off | **LIVE production** on 8302 |
| TCP v1 (legacy) | `tcp_ts.py` | 8302 | none | `debug=True` | Not running — kept as the documented **rollback source** for TCP v2 |
| AGM / Momentum Pacer | `Momentum Pacer/mp_ts.py` | 8304 (host `127.0.0.1`) | `AGM_BIND_PORT` | `MP_TS_PRODUCTION=1` disables debug/reloader | **LIVE production** |
| Y&Q | `yq_ts.py` | 8303 | none | `debug=True` | **LIVE** |
| tsgen | `tsgen.py` | 8077 | none | `debug=True` | **LIVE** (launched via `run_tsgen.bat`) |
| Gold Maker | `Gold_Maker_ts.py` | 8075 | none | `debug=True` | Launchable, not currently running |
| (ad hoc) | `spx_data_test.py` | 8076 | none | `debug=True` | One-off test script, not a service |
| Algominds v2 preview | `algominds_v2_preview_app.py` | 8311 / 8313 observed | — | — | **Not on `main`** — exists only in `.worktrees/algominds-v2-preview-shell` (draft PRs #12/#14) |

Port conventions:

- The tearsheet project owns the **83xx block** on this machine. Other projects own
  neighboring blocks (e.g. 8401 = TWIFO — never reuse it).
- `tearsheet_runtime_mode.py` reserves future **staff** ports 8321/8322/8324 and
  **portal** ports 8331/8332/8334 (TKP/TCP/AGM respectively). These are planned, not
  launched. `TEARSHEET_MODE` defaults to `legacy` = exactly today's behavior.
- TCP v2 preview convention: 8312 (`reboot_tcp_ts_v2.bat`).

Import-time side effects worth knowing: `tkp_ts`, `tcp_ts`, `yq_ts`, `tsgen`, and
`mp_ts` all read their workbook/CSV data **at import time**, and `tkp_ts` performs a
live yfinance fetch (`^SP500TR`) on import that can transiently fail. `tcp_ts_v2` is
deliberately side-effect-free on import (enforced by tests).

## 2. Launchers and ports

All launchers live at repo root. Every one except `run_tsgen*.bat` self-locates with
`cd /d "%~dp0"` (or `$PSScriptRoot`), so the repo folder can in principle move — but the
**launcher must stay next to its target script**, and the script filename is hardcoded
inside each launcher.

| Launcher | Interpreter | Env | Runs | Port | Role |
|---|---|---|---|---|---|
| `reboot_tkp_ts.bat` | `.venv310` activate + `python` | none | `tkp_ts.py` | 8301 | Production TKP |
| `reboot_tcp_ts.bat` | shim → PowerShell | — | `reboot_tcp_ts.ps1` | — | Production TCP entry (name is load-bearing, see below) |
| `reboot_tcp_ts.ps1` | `.venv310\Scripts\python.exe` | parses `.tcp_production.env` (sets `TCP_V2_*`), `PYTHONIOENCODING=utf-8` | `tcp_ts_v2.py` | 8302 | Production TCP v2 |
| `reboot_tcp_ts_v2.bat` | `.venv310` activate + `python` | `PYTHONIOENCODING=utf-8` only | `tcp_ts_v2.py` | 8312 | TCP v2 **preview** (explicitly does not affect 8302) |
| `reboot_mp_ts.bat` | bare `python` from PATH (no venv) | `MP_TS_PRODUCTION=1` | `Momentum Pacer\mp_ts.py` (cd's into the subfolder) | 8304 | Production AGM |
| `reboot_yq_ts.bat` | bare `python` from PATH (no venv) | none | `yq_ts.py` | 8303 | Production Y&Q |
| `reboot_gold_maker.bat` | `.venv310` activate + `python` | none | `Gold_Maker_ts.py` | 8075 | Gold Maker (idle) |
| `run_tsgen.bat` / `run_tsgen_user.bat` | **hardcoded** `C:\Python310\python.exe` | none | **absolute path** `C:\Coding Projects\Tearsheet Generator\tsgen.py` | 8077 | Live tsgen. The two files are byte-identical duplicates; both break if the repo folder or system Python location changes |
| `run_all_services.bat` | bare `python` | none | `launch_all_services.py` | — | **BROKEN** — `launch_all_services.py` does not exist in the repo |

Service/orchestration facts:

- There is **no** Windows service, Task Scheduler entry, or startup definition inside
  this repo. Production launches are operator-run `.bat` files.
- **External** orchestrators (outside this repo) invoke `reboot_tcp_ts.bat` by name:
  a Manager `service_config.py` and a HomePage `debug.py`. A Cloudflare tunnel maps
  `tcp-ts.hcresearch.ltd` → `localhost:8302`. Launcher filenames and the repo path are
  therefore **load-bearing** and must not be renamed casually.
- The TKP (8301), AGM (8304), and 8311-preview processes have historically run
  **elevated**; restarting them requires an elevated session.
- Live processes keep serving whatever code they loaded at start. After merging code
  changes, an app serves stale behavior until its (possibly elevated) restart —
  compare the process start time against the commit time before concluding a feature
  is broken.

## 3. Shared modules and coupling

Flat, root-level imports everywhere (no package structure). Shared layers:

**`tearsheet_*` (shared by TKP + TCP v2 + AGM):**

- `tearsheet_disclosure` — disclosure text. **Universal**: imported by every program,
  including Y&Q, Gold Maker, tsgen, and legacy `tcp_ts.py`.
- `tearsheet_gate_ui`, `tearsheet_gate_auth` — the shared gate screen + admin login.
  Note `tearsheet_gate_auth` **imports `tcp_config`**, so TKP/AGM transitively depend
  on TCP configuration code.
- `tearsheet_header`, `tearsheet_portal`, `tearsheet_date_defaults` — shared header
  date block, `/admin` portal pages, Add-Row date default.
- `tearsheet_runtime_mode` (new in PR #19) — `TEARSHEET_MODE` parsing (default
  `legacy`), `TKP_BIND_PORT`/`AGM_BIND_PORT` resolvers, planned staff/portal port
  tables, per-strategy session cookie names for non-legacy modes, and the shared
  `/monthly` → 404 route registration. Safe to import (no side effects).

**`tcp_*` stack (TCP v2's modular decomposition):** `tcp_config`, `tcp_admin`,
`tcp_benchmarks`, `tcp_calculations`, `tcp_daily_values`, `tcp_dashboard`,
`tcp_drawdown`, `tcp_ledger` (lowest-level leaf), `tcp_public_sections`,
`tcp_runtime_state`, `tcp_state`. `tcp_dashboard` and `tcp_drawdown` import each
other (one side lazily).

**Cross-program couplings (the key refactor constraint):**

- `tkp_ts.py` and `Momentum Pacer/mp_ts.py` both **import `tcp_admin`** (for
  `AdminAuthManager`), which transitively pulls in large parts of the TCP stack.
- `tearsheet_gate_auth` → `tcp_config` (as above).
- Consequence: "TCP-named" modules are in practice **shared infrastructure** for all
  three gated tearsheets. Moving or renaming them affects TKP and AGM, not just TCP.

**AGM v1 modules (root level, consumed only by `mp_ts.py`):**
`algominds_benchmark_daily`, `algominds_daily_accounting`, `algominds_daily_balances`,
`algominds_daily_fees`, `algominds_fee_payment_evidence`, `algominds_monthly_summary`,
`algominds_monthly_stats` (new in PR #18), `algominds_portal_registry`.

**Subdirectory import mechanism:** `mp_ts.py` lives in `Momentum Pacer/` and
bootstraps root imports via `sys.path.insert(0, <repo root>)` computed from
`Path(__file__).resolve().parent.parent`. It is the only app below the root and the
template for how any future moved app must behave.

**Algominds v2 (built, not wired):** root `algominds_v2_*.py` modules plus the
`algominds_v2/` package (`fee_engine`, `fee_ledger`). No `*_ts` entrypoint on `main`
imports any of it; active development happens in `.worktrees/` branches (draft PRs).

**Dead / production-dead code:**

- `Momentum Pacer/calc_engine.py` — imported by nothing (despite the old README
  describing it as the engine; corrected in this PR).
- `algominds_daily_accounting_ui.py`, `algominds_v2_account_state_paths.py`,
  `algominds_v2_daily_source.py` — imported only by their own tests.
- Root one-off utilities imported by nothing: `make_csv.py`, `create_csv_part1.py`,
  `setup_blue_whale_data.py`, `update_blue_whale_data.py`, `spx_data_test.py`,
  `tv_vadi_convert.py`, `test_read_excel.py`.

## 4. Assets / static behavior

- Single stylesheet: `assets/styles.css` at repo root. No `templates/` directory
  exists; all UI is Dash-generated. Admin login/portal pages are inline
  `render_template_string` HTML (in `tcp_ts_v2.py`, `tcp_admin.py`,
  `tearsheet_portal.py`).
- Root-level apps rely on **Dash's default assets convention**: Dash serves the
  `assets/` directory **relative to the app file's own directory** (not the cwd).
  They also list `"/assets/styles.css"` in `external_stylesheets`.
- `mp_ts.py` must pass an **explicit** `assets_folder=<repo root>/assets` because
  `Momentum Pacer/` has no assets dir of its own — without it the gate CSS 404s.
  Any app moved out of the root in the future needs the same treatment.
- Dash serves assets from disk per request: CSS edits reach live apps without
  restarts (code edits do not).

## 5. State / data files — do not move casually

These files are found by `__file__`-relative resolution, absolute paths, or launcher
cwd. Moving the code that anchors them (or the files themselves) silently orphans
state — apps start "fresh" rather than erroring.

| File | Role | How it is found | Notes |
|---|---|---|---|
| `daily_returns_secret_state.json` (+ `.bak`) | TKP admin daily-returns state | Beside `tkp_ts.py` via `__file__` | Gitignored. **No file locking, non-atomic writes** — single-writer only |
| `tcp_daily_returns_secret_state.json` | TCP v2 preview state | Repo root | Gitignored. Production TCP state lives under `%LOCALAPPDATA%\HughesCompany\TCP\state\` via `TCP_V2_STATE_*` env vars; those writes are locked (msvcrt) + atomic |
| `Momentum Pacer/momentum_pacer_manual_daily_rows.json` | AGM admin manual rows | Beside `mp_ts.py` via `__file__` | Gitignored. No locking |
| `Momentum Pacer/Momentum Fee Calculation.xlsx` | AGM fee-engine payment-reconciliation reference | Beside `mp_ts.py` | Gitignored (`*.xlsx`), **exists only on the ops machine**. If absent, `mp_ts` silently degrades (wrong crystallized-fee figures) — copy it into any fresh worktree before running AGM fee tests |
| `Momentum Pacer/data/daily_balances/*.csv` | AGM daily source of truth (TradeStation export) | `__file__`-relative; filename pinned by `DAILY_BALANCES_FILENAME` in `algominds_daily_balances.py` | **Force-tracked** despite the `*.csv` gitignore. The dated filename constant must be bumped per new export. A stale duplicate export sits at repo root |
| `Momentum Pacer/data/benchmarks/*.csv` | AGM benchmark cache (^GSPC/^NDX) | `__file__`-relative | Force-tracked. `AGM_BENCHMARK_CACHE_ONLY=1` forces offline (set by tests) |
| `_runtime/` | Benchmark caches, quarantine, local snapshots | **cwd-relative** default in `tcp_benchmarks` (production callers pass absolute paths) | Gitignored. `tcp_config` explicitly rejects state paths inside `_runtime/` |
| `.tkp_production.env`, `.tcp_production.env` | Admin credentials + TCP state paths | Parsed by the `.ps1` launchers | Gitignored, **ops-machine-only, contain secrets** — never commit |
| `tcp_alex.xlsx` (external), TKP VADI workbook, logo PNGs, `yq.png` | Source workbooks / images | **Absolute `C:\...` paths** in source (`TCP_V2_WORKBOOK_PATH` is the only env-overridable one) | Tied to this machine/user profile |
| `yq.csv` / `yq.xlsx`, `Trade_Results*.csv`, `trades.xlsx`, `blue_whale_data*.csv` | Y&Q / tsgen / utility inputs | Repo root, some read at import time | Gitignored (blanket `*.csv`/`*.xlsx`) — present locally only |

Known untracked-but-load-bearing local files (observed 2026-07-09; candidates for the
"git hygiene" PR): `reboot_tkp_ts.ps1`, `reboot_tcp_ts.bat.bak-20260704-cutover`,
`tcp_ts_runtime_launch.py` (a divergent local fork of `tcp_ts.py` pointing at a
`_runtime` workbook snapshot; not used by any launcher),
`docs/tcp_production_cutover_runbook.md`, `docs/tcp_production_rollback_runbook.md`,
`docs/tcp_release_checklist.md`, `TCP v2 Implementation Plan.md`,
`scripts/tcp_cutover_preflight.py`, `scripts/preflight_tcp_cutover.py`,
`scripts/agm_merge_audit_smoke.py`, and three `tests/test_tcp_*.py` files.

## 6. Tests and smoke scripts

- `tests/` holds ~56 test files (~1,080 tests). Coverage by program: TCP (largest by
  far), AGM, Algominds v2, shared gate/date modules, TKP (small). **Zero coverage:**
  `yq_ts.py`, `Gold_Maker_ts.py`, `tsgen.py`.
- **No `pytest.ini`/`pyproject.toml` exists.** The suite must be run from the repo
  root as `.venv310\Scripts\python.exe -m pytest tests/<files> -q` (the `-m` form puts
  the repo root on `sys.path`; `tests/conftest.py` adds `Momentum Pacer/`).
- **Do not run the whole `tests/` directory in one process.** Purity tests assert
  `tkp_ts`/`tcp_ts` are absent from `sys.modules`, and any earlier test file that
  imports them poisons the session. Run per-file groups instead.
- `tests/conftest.py` sets test admin credentials and `AGM_BENCHMARK_CACHE_ONLY=1`
  at import time.
- **Layout-enforcing tests** (will trip on any file move; must be updated in the same
  PR as a move): `test_tcp_foundation.py` (asserts `tcp_ts.py`/`tkp_ts.py` exist at
  repo root; golden-fixture workbook identity), `test_tcp_v2_shell.py` and
  `test_tcp_state.py` (read source files by path and assert content),
  `test_tcp_access_daily_values.py` / `test_tcp_mobile_responsive.py` (assert the
  string `8302` never appears in `tcp_ts_v2.py` source), `test_tcp_public_ui_parity.py`
  + `scripts/audit_tcp_public_ui.py` (parse entrypoints from committed git HEAD by
  path). All test files hardcode `REPO_ROOT = Path(__file__).resolve().parent.parent`.
- Tests marked `local_workbook` skip when `tcp_alex.xlsx` is absent (safe on fresh
  clones). AGM tests require the force-tracked CSVs (present in a clean checkout) and
  degrade if the gitignored fee workbook is missing.
- `scripts/` (tracked): `seed_tcp_state.py`, `tcp_acceptance.py`,
  `audit_tcp_acceptance.py`, `audit_tcp_public_ui.py`, `_v1_baseline_worker.py`.
  Untracked ops-machine scripts: `tcp_cutover_preflight.py`,
  `preflight_tcp_cutover.py`, `agm_merge_audit_smoke.py` (hardcodes expected row
  counts/dates — goes stale daily).
- Known broken/stale: `run_all_services.bat` (missing target), the old
  `Momentum Pacer/README.md` content (corrected in this PR), root-level ad-hoc
  scripts (`spx_data_test.py`, `test_read_excel.py`) that sit outside `tests/`.
- Windows quirk: pytest `tmp_path` can hit `PermissionError` on the default
  `%TEMP%\pytest-of-...` dir — point `TMP`/`TEMP` at a writable directory first.

## 7. Refactor risk notes

Why the current layout is load-bearing:

1. **Flat imports** — every app imports shared modules by bare root-level name; there
   are also ~13 `sys.path.insert` sites across `mp_ts.py`, `tests/`, and `scripts/`.
2. **Launchers hardcode script names and cwd** — `%~dp0`-relative `cd` + bare
   `python <script>.py`. External orchestrators and runbooks reference
   `reboot_tcp_ts.bat` and the absolute repo path by name.
3. **State lives beside code** — TKP state JSON next to `tkp_ts.py`, AGM state/workbook
   inside `Momentum Pacer/`. Moving an entrypoint silently orphans its state.
4. **Dash assets convention** — asset resolution follows the app file's directory;
   moved apps 404 their CSS unless given an explicit `assets_folder`.
5. **Layout-enforcing tests** — see §6; moves trip them by design.
6. **Absolute machine paths** — workbooks, logos, `C:\Python310`, `%LOCALAPPDATA%`
   state; only TCP v2's workbook/state paths are env-overridable.
7. **Live services + elevation** — seven processes serve this repo; two require
   elevated restarts; a half-restarted fleet runs two versions at once.

What must NOT move yet: the four live entrypoints, `Momentum Pacer/` itself,
`assets/`, launcher filenames, all state/data files in §5, and `tcp_ts.py` (rollback
path for TCP v2).

Prerequisites before ANY file move: root import shims for moved modules; explicit
`assets_folder` on all apps; a single repo-root path anchor for state files; updating
layout-enforcing tests in the same PR as the move; a green pre/post smoke run.

## 8. Staged plan (summary)

| Stage | Content | Behavior change |
|---|---|---|
| **PR 1 (this)** | `docs/REPO_MAP.md`, README refresh, Momentum Pacer README correction | None (docs only) |
| PR 2 | Git hygiene: commit untracked load-bearing files (launcher `.ps1`, cutover/rollback runbooks, preflight scripts + tests); document/quarantine `tcp_ts_runtime_launch.py` and `run_all_services.bat` | None |
| PR 3 | Safety net: `pytest.ini`, a smoke script (import-boot checks for TKP/TCP/AGM/Y&Q), first minimal tests for `yq_ts`/`tsgen` | None |
| PR 4+ | Compatibility anchors before any moves: explicit `assets_folder` everywhere, `__file__`-anchored `_runtime` default, root import shims when a shared module first moves | None (verified by tests) |
| Later | Program moves only if a concrete need forces them — one program per PR, launcher + state-path + test updates in the same PR | Zero intended |
| Future | **Glenn Daily Entry Hub** — additive package (per-program daily-entry contracts: Date, NLV, Cash Transfer; Fee for AGM only). Explicitly **not** part of these PRs | New feature, additive only |
