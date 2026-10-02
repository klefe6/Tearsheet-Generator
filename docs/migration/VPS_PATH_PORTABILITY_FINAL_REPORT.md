# VPS Path Portability — Final Report (Phase P3)

## Executive verdict

**PASS.** All production-relevant path assumptions now resolve through the
single central resolver (`tearsheet_paths.py`). With `HC_APP_ENV` unset and no
`HC_*` overrides, every migrated consumer resolves to the **exact** path it uses
on the laptop today (proven by characterization tests). With
`HC_APP_ENV=vps-production`, the whole system dry-resolves to a coherent,
provider-neutral tree under `C:\H&C\`. No production data was moved or modified,
no service was touched, and the protected folder was never accessed.

* Branch: `feature/vps-portability-completion`
* Base: `feature/path-portability-integration` @ `9c21a97` (central-path
  foundation + TKP title reconciliation + G-TKP-2 TKP path portability)
* Canonical VPS root: `C:\H&C\`
* Provider-neutral: **Yes**

## G-TKP-2 discovery result

G-TKP-2 (TKP state/workbook path portability) **exists, is committed, is clean,
and is pushed**:

* Branch `feature/tkp-central-path-config` @ `ccd7585`
  ("feat: make TKP state and workbook paths configurable"), integrated into the
  base branch as `9c21a97` on top of the current live-main tip `3cfda4f`.
* It routes `HC_TKP_STATE_PATH` and `HC_TKP_SOURCE_WORKBOOK` through the resolver
  and was **not** redone in this phase.

## Phase 1 — Remaining path audit (classification)

| Finding | File | Class | Action |
|---|---|---|---|
| TKP state JSON + source workbook | `tkp_ts.py` | A | Already done (G-TKP-2) — verified |
| AGM manual daily-rows JSON | `Momentum Pacer/mp_ts.py` | A | **Converted** → `HC_AGM_MANUAL_STATE_PATH` |
| AGM fee workbook | `Momentum Pacer/mp_ts.py` | A | **Converted** → `HC_AGM_FEE_WORKBOOK` |
| AGM pinned balances CSV | `algominds_daily_balances.py` | A | Already central (`resolve_agm_pinned_csv`) |
| AGM benchmark cache dir | `algominds_benchmark_daily.py` | A | Already central (`resolve_agm_benchmark_cache_dir`) |
| TCP state active/backup/lock base dir | `tcp_ts_v2.py` | A | **Converted** → `HC_TCP_DATA_ROOT` (env overrides preserved) |
| TCP source workbook | `tcp_config.py` | B | Portable via `TCP_V2_WORKBOOK_PATH`; documented |
| TCP benchmark cache | `tcp_config.py` | B | Regenerable; portable via `TCP_V2_BENCHMARK_CACHE_PATH`; documented |
| Y&Q CSV | `yq_ts.py` | A | Already central (`resolve_yq_csv_path`) |
| Y&Q duplicate resolver + hardcoded default | `yq_data_current.py` | B/D | **Consolidated** to delegate to the central resolver |
| TCP/AGM ingest audit JSONL | `tearsheet_paths.py` | A | VPS now lands under `C:\H&C\logs\ingest\` (laptop unchanged) |
| Program logos (TKP/TCP/Y&Q) | `tkp_ts.py`, `tcp_ts_v2.py`, `yq_ts.py` | B | Cosmetic, graceful fallback; documented (bundle under `apps\shared\` at VPS build) |
| `tsgen.py` hardcoded CSVs | `tsgen.py` | D | Legacy standalone generator, not a production service — untouched |
| `tv_vadi_convert.py` hardcoded paths | `tv_vadi_convert.py` | D | Dev conversion script — untouched |
| Dashboard / launcher paths | external `Manager` repo | D | Out of isolated worktree; captured in manifest `services` |
| `Path(__file__)` / repo-root anchors in tests | `tests/**` | C | Source-relative test scaffolding — correct as-is |

Class key: **A** must convert before VPS · **B** should convert · **C** safe as-is · **D** separate lane.

## Consumers converted

* **AGM / Momentum Pacer** (`mp_ts.py`): manual daily-rows JSON and fee workbook
  now resolve via `resolve_agm_manual_state_path` / `resolve_agm_fee_workbook`.
* **TCP** (`tcp_ts_v2.py`): state active/backup/lock base directory now resolves
  via `resolve_tcp_data_root`; `TCP_V2_STATE_*` per-file overrides still win.
* **Y&Q** (`yq_data_current.py`): duplicate resolver + hardcoded default removed;
  now delegates to the single central resolver.
* **Ingest audit** (`tearsheet_paths.py`): VPS profile now routes TCP/AGM ingest
  audit JSONL under `C:\H&C\logs\ingest\`.

## Consumers deferred (with reason)

* **Program logos** — cosmetic, already fail-safe (empty logo on miss). Bundle
  under `C:\H&C\apps\shared\` during the VPS build; no runtime risk.
* **TCP source workbook / benchmark cache** — already portable via existing
  `TCP_V2_*` env overrides; set at VPS build time.
* **Glenn uploader (Fly.io)** — not moving to the Windows VPS this phase. Its
  production URLs, Fly secrets, export behavior, API schemas, and DB semantics
  were left entirely unchanged.
* **Dashboard / Manager launcher** — lives in the external `Manager` repo,
  outside this isolated worktree. Its service contract is captured in
  `VPS_DEPLOYMENT_MANIFEST.json` (`services`) for the future NSSM step.

## Environment keys added

`HC_APPS_ROOT`, `HC_CONFIG_ROOT`, `HC_SECRETS_ROOT`, `HC_WEBSITE_ROOT`,
`HC_TCP_DATA_ROOT`, `HC_AGM_MANUAL_STATE_PATH`, `HC_AGM_FEE_WORKBOOK`.
(`HC_TKP_*`, `HC_AGM_*`, `HC_YQ_*`, `HC_*_ROOT`, `YQ_CSV_PATH`, `TCP_V2_*` were
pre-existing.)

## Default parity evidence (laptop, `HC_APP_ENV` unset)

Every converted consumer resolves to its current laptop path — proven by
`tests/test_tearsheet_paths.py`, `tests/test_tkp_paths.py`,
`tests/test_yq_data_current.py`, and the new `tests/test_vps_portability_paths.py`.

| Key | Laptop default resolution | Match |
|---|---|---|
| `tkp_state_path` | `<checkout>\daily_returns_secret_state.json` | Yes |
| `tkp_source_workbook` | protected-folder xlsx (verbatim) | Yes |
| `tcp_data_root` (state base) | `<checkout>` | Yes |
| `agm_manual_state_path` | `Momentum Pacer\momentum_pacer_manual_daily_rows.json` | Yes |
| `agm_fee_workbook` | `Momentum Pacer\Momentum Fee Calculation.xlsx` | Yes |
| `agm_pinned_csv` | `Momentum Pacer\data\daily_balances\...csv` | Yes |
| `agm_benchmark_cache_dir` | `Momentum Pacer\data\benchmarks` | Yes |
| `tcp_ingest_audit_path` | `<checkout>\glenn_uploader_ingest_tcp_audit.jsonl` | Yes |
| `agm_ingest_audit_path` | `Momentum Pacer\glenn_uploader_ingest_agm_audit.jsonl` | Yes |
| `yq_csv_path` | `<repo root>\yq.csv` | Yes |

## VPS dry-profile evidence (`HC_APP_ENV=vps-production`)

| Key | VPS resolution |
|---|---|
| `apps_root` | `C:\H&C\apps` |
| `data_root` | `C:\H&C\data` |
| `config_root` | `C:\H&C\config` |
| `secrets_root` | `C:\H&C\secrets` |
| `log_root` | `C:\H&C\logs` |
| `backup_root` | `C:\H&C\backups` |
| `website_root` | `C:\H&C\website` |
| `tkp_data_root` / `tkp_state_path` | `C:\H&C\data\tkp` / `...\daily_returns_secret_state.json` |
| `tcp_data_root` | `C:\H&C\data\tcp` |
| `agm_data_root` / `agm_manual_state_path` | `C:\H&C\data\agm` / `...\momentum_pacer_manual_daily_rows.json` |
| `agm_fee_workbook` | `C:\H&C\data\agm\Momentum Fee Calculation.xlsx` |
| `yq_csv_path` | `C:\H&C\data\yq\yq.csv` |
| `tcp_ingest_audit_path` | `C:\H&C\logs\ingest\glenn_uploader_ingest_tcp_audit.jsonl` |
| `agm_ingest_audit_path` | `C:\H&C\logs\ingest\glenn_uploader_ingest_agm_audit.jsonl` |

No test created any of these real directories; all VPS resolution used mocked
env only.

## Phase 9 — Provider neutrality result

The application configuration depends on **none** of: Azure APIs / disk names /
VM metadata, AWS or Lightsail metadata, OVH APIs, or any provider-specific
environment variables. The deployment contract requires only: Windows Server, a
filesystem rooted at `C:\` (data-disk optional via `HC_DATA_ROOT`), a Python
runtime, and environment configuration. IIS/ARR, NSSM, and Cloudflare Tunnel are
later infrastructure steps, not application dependencies. **No unavoidable
provider dependency found.**

## Test results (focused; broken `pytest_dash` plugin disabled via `-p no:pytest_dash`)

| Suite | Result |
|---|---|
| `test_tearsheet_paths.py` + `test_tkp_paths.py` + `test_yq_data_current.py` | 68 passed |
| `test_vps_portability_paths.py` (new) | 25 passed |
| TCP: config/state/runtime/calculations/uploader_ingest/cutover_preflight | 148 passed, 1 skipped, 1 pre-existing fail\* |
| AGM: daily_fees/monthly_summary/downstream/password_gate/v2_config | pre-existing 9 fail + 6 error\*\* |
| Y&Q + uploader ingest + algominds_v2_config | passed |
| runtime_mode / staff_mode / tcp shells | 144 passed, 1 pre-existing fail\* |

\* `test_valid_configuration_returns_go` (preflight `python_interpreter` /
`parent_pointer_target`) and `test_legacy_layout_still_has_hidden_e[tcp_ts_v2-app]`
(callable layout) reproduce **identically** on the untouched base worktree —
environment-dependent baseline failures, not regressions.

\*\* AGM failures/errors are caused by the untracked data file
`Momentum Fee Calculation.xlsx` being absent from fresh worktrees. The identical
9-failure/6-error signature reproduces on the untouched base worktree; my change
resolves `EXCEL_PATH` to the **same** path (proven by matching tracebacks).
These are part of the known `1209 passed / 36 failed / 24 errors` baseline.

Result: **focused suites pass cleanly; every failure is a pre-existing baseline
failure with an identical signature on the untouched base.**

## Production health results (Phase 11, read-only)

| Port | Service | Result |
|---|---|---|
| 8301 | TKP public | 200 `{"status":"ready","rows_loaded":766}` |
| 8302 | TCP public | 200 `{"active_state":"ready","adapter_status":"ok"}` |
| 8304 | AGM public | 200 `{"app":"algominds-momentum-pacer"}` |
| 8303 | Y&Q public | 200 (Dash app; no JSON `/healthz`) |
| 8006 | Dashboard | 401 (auth-gated → process alive) |
| 8321/8322/8324 | staff | not launched (expected) |

Production remained healthy and untouched while development occurred in the
isolated worktree.

## Rollback

Nothing in production changed. To discard this work entirely:

```text
git branch -D feature/vps-portability-completion
git worktree remove ".worktrees/vps-portability-completion"
```

The live deploy worktree and running services are unaffected regardless.

## Exact next deployment step

1. Provision a Windows Server VPS (any of Lightsail Windows / OVH / Azure).
2. Create the `C:\H&C\` tree per `VPS_FILESYSTEM_LAYOUT.md`.
3. Deploy application code into `C:\H&C\apps\<app>` from Git.
4. Copy authoritative data files into `C:\H&C\data\<app>` (per
   `VPS_DEPLOYMENT_MANIFEST.json > persistent_files`).
5. Set `HC_APP_ENV=vps-production` (+ any `TCP_V2_*` / secret env) in the NSSM
   service definitions.
6. Start services on the documented ports, verify `/healthz`, then wire
   Cloudflare Tunnel and cut over DNS.
