# File Classification — Tearsheet Generator Root (103 entries + subdirs)

Classes: `apps/{tkp,tcp,agm,yq}`, `shared/{accounting,benchmarks,authentication,reporting,formatting,database,utilities}`,
`config`, `scripts/{development,maintenance,migration}`, `ops`, `tests`,
`data/development-only`, **persistent production data (DO NOT MOVE)**,
**compatibility wrapper (root shim stays forever)**, obsolete/uncertain.

"Move" always means: `git mv` the implementation + leave a same-named root shim
(`from <new location> import *`) until every consumer is proven migrated.

## 1. Entrypoints → compatibility wrappers at root
| File | Destination of body | Root file becomes |
|---|---|---|
| `tkp_ts.py` | `apps/tkp/tkp_app.py` | shim + `__main__` guard (after path-anchoring fix — see migration-sequence step T1) |
| `tcp_ts_v2.py` | `apps/tcp/tcp_app.py` | shim + `__main__` guard |
| `yq_ts.py` | `apps/yq/yq_app.py` | shim + `__main__` guard |
| `Momentum Pacer/mp_ts.py` | `apps/agm/agm_app.py` | shim stays at `Momentum Pacer/mp_ts.py` (bat contract); optional root `mp_ts.py` per target tree is an ADDITION, not a move |

## 2. apps/tcp (TCP-exclusive)
`tcp_runtime_state.py`, `tcp_state.py` → `apps/tcp/` (root shims). Consumers: tcp_ts_v2, `scripts/seed_tcp_state.py`, `scripts/tcp_acceptance.py`, tests.

## 3. apps/agm (AGM-exclusive)
`algominds_portal_registry.py`, `algominds_daily_balances.py`, `algominds_benchmark_daily.py`,
`algominds_daily_fees.py`, `algominds_daily_accounting.py`, `algominds_monthly_summary.py`,
`algominds_account_stats.py`, `algominds_monthly_stats.py`, `algominds_fee_payment_evidence.py`,
`algominds_drawdown_semantics.py`, `algominds_daily_accounting_ui.py` (tests-only),
`algominds_v2/` pkg + `algominds_v2_*.py` (8 root modules; tests/docs-only today),
`Momentum Pacer/calc_engine.py` (standalone, unimported).
AGM data stays in `Momentum Pacer/` (see §9/§10).

## 4. apps/yq
`yq.xlsx`, `Y&QInvestments_DDoc_CTA_2025_03.pdf` (both unreferenced by code — safe).
`yq.csv` is production data → §9.

## 5. shared/* (extraction LAST — tri-app blast radius; root shims mandatory)
| Bucket | Modules | Note |
|---|---|---|
| shared/authentication | `tearsheet_gate_auth.py`, `tearsheet_gate_ui.py`, `tearsheet_local_admin.py`, `tcp_admin.py` (AdminAuthManager — misnamed, tri-app) | tcp_admin also carries TCP admin-sim logic → candidate to SPLIT later, not now |
| shared/accounting | `tcp_calculations.py`, `tcp_ledger.py`, `program_account_stats.py` | tcp_calculations/ledger are TCP-flavored but in TKP's closure via tcp_admin |
| shared/benchmarks | `tcp_benchmarks.py` | AGM's `algominds_benchmark_daily.py` is program-specific → apps/agm, NOT shared |
| shared/reporting | `tcp_dashboard.py`, `tcp_drawdown.py`, `tcp_public_sections.py`, `tcp_daily_values.py`, `tearsheet_portal.py` | dashboard⇄drawdown cycle moves as a pair |
| shared/formatting | `tearsheet_header.py`, `tearsheet_disclosure.py`, `tearsheet_date_defaults.py` | disclosure also used by Gold_Maker/tsgen — shim required indefinitely |
| shared/utilities | `tearsheet_runtime_mode.py` | lazy-cycles with tcp_config |
| shared/database | (none today — no shared DB layer exists; TCP state I/O is app-private `tcp_state.py`) | leave bucket empty rather than force-fit |
| config | `tcp_config.py` (sibling admin-auth defaults + TCP config; misnamed) | move to `config/` only WITH `tearsheet_runtime_mode` (lazy cycle) |

## 6. scripts/
- Existing `scripts/` (already correct): `smoke_all.py`, `audit_live_tearsheet_processes.py`, `audit_tcp_*`, `tcp_acceptance.py`, `tcp_cutover_preflight.py`, `preflight_tcp_cutover.py`, `seed_tcp_state.py`, `_v1_baseline_worker.py`, `agm_merge_audit_smoke.py` → `scripts/maintenance` conceptually; no move needed.
- Root strays → `scripts/development/`: `make_csv.py`, `create_csv_part1.py`, `setup_blue_whale_data.py`, `update_blue_whale_data.py`, `tv_vadi_convert.py`, `spx_data_test.py`, `test_read_excel.py` (imports OneDrive workbook at import time — keep OUT of pytest collection, pytest.ini already guards).

## 7. ops (files stay AT ROOT — class is documentary)
Frozen external contract (see external-contracts.md §3): `reboot_tkp_ts.bat/.ps1`,
`reboot_tcp_ts.bat/.ps1`, `reboot_yq_ts.bat`, `reboot_mp_ts.bat`, `reboot_tkp_staff.ps1`,
`reboot_tcp_staff.bat/.ps1`, `reboot_mp_staff.bat/.ps1`, `reboot_glenn_uploader.bat`,
`reboot_gold_maker.bat`, `run_tsgen.bat`, `run_tsgen_user.bat`, `reboot_tcp_ts_v2.bat` (preview).
`ops/` may hold NEW runbooks/copies, never the originals. `docs/` operational runbooks
(production_restart_safety_checklist.md etc.) may move under `ops/` freely (nothing references them by path).

## 8. tests
`tests/` stays (pytest.ini `testpaths=tests`; per-file execution constraint documented in
pytest.ini — several purity tests forbid pre-imported tkp_ts/tcp_ts). Root `pytest.ini` stays.

## 9. Persistent production data — DO NOT MOVE, ever, as part of this reorg
| File | Why |
|---|---|
| `daily_returns_secret_state.json` (+ `.bak`) | TKP production ledger (838 rows, gitignored, no other copy) |
| `tcp_daily_returns_secret_state.json` (root copy) | TCP preview/dev state; production lives in %LOCALAPPDATA% |
| `_runtime/` (benchmark caches, quarantine, startup logs) | TCP ops surface; `tcp_config.py` defaults point here |
| `yq.csv` | Y&Q production input, gitignored → exists only on this machine |
| `Momentum Pacer/Momentum Fee Calculation.xlsx`, `Momentum Pacer/data/**` | AGM production inputs/caches |
| `.tkp_production.env`, `.tcp_production.env`, `.staff.env`, `.local_dev.env` | launcher-loaded at fixed root paths |
| `uploader/backend/data/**` | uploader SQLite + sandbox exports |
| ingest audit `glenn_uploader_ingest_*_audit.jsonl` | will appear at root post-merge of ingest branches |

## 10. data/development-only candidates
`Trade_Results.csv`, `Trade_Results_APFutures.csv`, `Trade_Results_Numberline.csv`,
`Trade_Results_test.csv` (⚠ hardcoded in `tsgen.py:22-24,37` — move only WITH a tsgen.py
path update in the same commit), `blue_whale_data.csv`, `blue_whale_data_part1.csv`,
`VADI.xlsx`, `trades.xlsx`, `CHoCH_+_..._2025-06-13.xlsx` (⚠ `tv_vadi_convert.py:10`),
`Multi-Trigger_Gold_Strategy_..._2025-03-10.xlsx`,
`balances_210TGG51_20OCT2025_02JUL2026.csv` (stale root copy of AGM balances).

## 11. Obsolete / uncertain
| File | Status | Evidence |
|---|---|---|
| `tcp_ts.py` | Obsolete production entrypoint (pre-2026-07-04) | cutover bak `reboot_tcp_ts.bat.bak-20260704-cutover:9`; tests forbid import |
| `tcp_ts_runtime_launch.py` | Orphan near-duplicate of tcp_ts.py | imported by nothing; untracked |
| `reboot_tcp_ts.bat.bak-20260704-cutover` | Rollback artifact — keep until TCP v2 confidence window closes | |
| `run_all_services.bat` | **BROKEN stale copy** — targets `%~dp0launch_all_services.py` which does not exist in this repo (the real one is in Manager) | verified absent |
| `pytest-portal-registry.log`, `CURSOR_PATCH.md`, `TCP v2 Implementation Plan.md` | logs/docs — archive freely | |
| `Gold_Maker_ts.py`, `tsgen.py` | Separate apps sharing the repo — OUT of 4-app scope; do not move (bat contracts C5) | |
| `daily_returns_secret_state.json.bak` | manual backup, Apr 6 — stale but keep (only TKP fallback) | |

## 12. Files that must NOT move yet (external consumers pin the path)
1. All §7 launchers (Manager `service_config.py:184-219`; HomePage `debug.py:285-314`).
2. `tsgen.py` (absolute path inside `run_tsgen.bat`).
3. `Momentum Pacer\` directory itself (HomePage `debug.py:256`) and `uploader\` (debug.py:278).
4. Root env files + `daily_returns_secret_state.json` (loaded/located at fixed root paths).
5. `assets/styles.css` (Dash default assets dir of every root entrypoint — root entrypoints remain, so assets stays at root).
6. Entrypoint names `tkp_ts.py`, `tcp_ts_v2.py`, `yq_ts.py`, `Momentum Pacer/mp_ts.py` (bats run them by name; tests import them; ROOT SHIMS satisfy this).
7. Anything touched by the three unmerged uploader-ingest branches until merged (`tearsheet_uploader_ingest.py`*, `tcp_uploader_ingest.py`*, the three entrypoints). *arrive on merge.
