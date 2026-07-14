# Risks & Blockers — Tearsheet Generator Reorganization

## A. Hard blockers (resolve before Phase 1)

| # | Blocker | Evidence | Resolution |
|---|---|---|---|
| B1 | Dirty working tree: 29 entries on `fix/agm-nav-title-account-stats` (AGM drawdown WIP, uploader FE/BE WIP, launcher edits) | `git status` @ a5beb25 | Land or shelve every change; reorg starts from a clean, tagged tip |
| B2 | Three unmerged uploader-ingest branches modify all three entrypoints and add root modules (`tearsheet_uploader_ingest.py`, `tcp_uploader_ingest.py`, tests) | `git diff --name-only HEAD..feature/glenn-uploader-downstream-export` (and the CORS + rollback branches) | Merge or park them FIRST; else every branch conflicts with moved files |
| B3 | Local `main` is BEHIND the working branch (HEAD contains main + 5) | `git log main..HEAD` non-empty, reverse empty | Decide the canonical branch, reconcile, then branch the reorg from it |
| B4 | Production processes serve from THIS checkout; restarts require the operator (TKP state is a single gitignored file with one stale .bak) | memory of fleet ops + `daily_returns_secret_state.json` mtimes | Schedule each phase's restart window; back up state files (timestamped copies) before every phase |

## B. High risks (designed-around in the sequence; still watch)

| # | Risk | Detail | Mitigation |
|---|---|---|---|
| R1 | TKP state re-anchoring | `tkp_ts.py:251-252` derives the state dir from `__file__`; a moved body silently re-anchors to `apps/tkp/` and TKP boots with an EMPTY production ledger that "works" | Anchor before move; gate G-TKP-2 (838-row check) |
| R2 | Y&Q csv re-anchoring | same pattern `yq_ts.py:418`; `yq.csv` is gitignored → no VCS safety net | anchor first; G-YQ-2 |
| R3 | AGM data re-anchoring | `mp_ts.py:89,1265,2291`, `algominds_daily_balances.py:42-50`, `algominds_benchmark_daily.py:55-67` all resolve vs `__file__`/BASE_DIR | explicit `MP_DATA_DIR`; golden account-stats gate |
| R4 | Import cycles break on partial moves | `tcp_dashboard⇄tcp_drawdown`; `tcp_config⇄tearsheet_runtime_mode` (lazy) | move cycle members in the same commit (5b, 5f) |
| R5 | Purity/guard tests | `test_tcp_foundation.py:14,31` + `test_tcp_state.py:511` forbid importing `tcp_ts`; `test_tcp_access_daily_values.py:447` scans v2 source for literal 8302 — the scanner must be pointed at the moved file or it passes vacuously | update test file-paths in the SAME commit; confirm the 8302-scan still reads real source |
| R6 | Shims and `import *` | modules with no `__all__` won't re-export underscore names; tests import private helpers (e.g. `_compute_new_row`) | shims re-export explicitly: `from apps.tkp.tkp_app import *` PLUS named private imports used by tests |
| R7 | Windows path with space: `Momentum Pacer` | quoting bugs bite any new launcher lines | never rewrite the AGM bat's cd logic casually; keep `%~dp0` patterns |
| R8 | `.local_dev.env` leak into production launchers | every prod ps1 imports `.local_dev.env` BEFORE the prod env (reboot_tcp_ts.ps1:22-24 etc.) — a dev flag on this machine changes prod behavior | pre-existing defect; do NOT fix inside the reorg (behavior must stay identical); log as follow-up |
| R9 | Y&Q runs bare `python` (no venv), debug=True, port hardcoded | `reboot_yq_ts.bat:3`, `yq_ts.py:2126` | pre-existing; unchanged during reorg; follow-up item |
| R10 | tsgen/Gold Maker collateral | both import `tearsheet_disclosure` (Gold_Maker_ts:18, tsgen:18); `run_tsgen.bat` hardcodes an absolute tsgen.py path | permanent root shim for tearsheet_disclosure; tsgen.py/Gold_Maker_ts.py do not move |
| R11 | Dashboard/Manager silent-fail masking | `.exists()` guards mean a broken bat shows as "not found", not an error | U7 gate checks buttons after each phase |
| R12 | `run_all_services.bat` confusion | targets a launcher that doesn't exist in this repo — someone "fixing" it mid-migration would double-launch via Manager AND locally | archive it in Phase 6; note in ops docs |

## C. Environment-variable replacements for hardcoded paths (proposal only — NOT implemented)

| Current hardcoded path | File:line | Proposed env var (default = current value) |
|---|---|---|
| TKP workbook `...\TKP\VADI\Copy of tkp_alex_old1.xlsx` | tkp_ts.py:243-245 | `TKP_WORKBOOK_PATH` |
| Shared logo `...\Branded Logo\Trianle-Only-Logo.png` | tkp_ts.py:80; tcp_ts_v2.py:182-185; Gold_Maker_ts.py:23; tcp_ts.py:36 | `TEARSHEET_LOGO_PATH` (one var, all apps) |
| Y&Q logo `C:\Users\H&CDanHughes\Pictures\yq.png` | yq_ts.py:37 | `YQ_LOGO_PATH` |
| TCP workbook `...\TCP\tcp_alex.xlsx` | tcp_config.py:12-15 | already env-able: `TCP_V2_WORKBOOK_PATH` (default stays) |
| Gold Maker CSV `...\TKP\VADI\GLD_Maker_VADI.csv` | Gold_Maker_ts.py:48 | `GOLD_MAKER_CSV_PATH` |
| tsgen sources (3 repo CSVs + OneDrive `TKP VADI.csv`) | tsgen.py:22-25,37 | `TSGEN_DATA_DIR` + per-program overrides |
| tv_vadi_convert trio (repo xlsx, StrategyOptimizer txt, output) | tv_vadi_convert.py:10-14 | dev script — args/env `TV_VADI_*` |
| test workbook | test_read_excel.py:6 | dev script — leave or param |
| `run_tsgen.bat` SCRIPT_PATH + `C:\Python310\python.exe` | run_tsgen.bat:4-5 | `%~dp0`-relative rewrite (internal bat edit, path frozen) |
| Manager/HomePage `BASE_DIR` | service_config.py:47; debug.py:243 | out of repo — coordinate separately if the repo ever relocates |

Not path-hardcoding but flagged: default sibling admin token + session secret constants in
source (`tcp_config.py:32-34`) used when `*_ADMIN_TOKEN`/`*_SESSION_SECRET` env are unset.

## D. Duplicated / similar modules — share vs keep separate

**Safe to unify under shared/ (already single copies, just moving):** the 8 `tearsheet_*`
modules and 9 tri-app `tcp_*` modules (see dependency-map §5).

**Similar-looking but MUST stay separate (program-specific business rules):**
- `tcp_calculations.compute_tcp_row` vs TKP's `_compute_new_row` (inside tkp_ts.py) vs
  AGM's `algominds_daily_accounting`/`algominds_daily_fees`: three different fee/HWM/
  loss-carry conventions (TCP per-tranche nav-x1; TKP fixed $150k base, 20% daily fee;
  AGM manual-rows + full-recompute). Any "unify the accounting" refactor is out of scope
  and dangerous.
- `algominds_benchmark_daily` (AGM: GSPC/NDX CSV caches) vs `tcp_benchmarks`
  (SPXTR/BTC/ETH JSON caches, quantstats): same theme, different formats + cache
  strategies. Keep both; unification is a design task, not a move.
- `algominds_v2/fee_engine` vs `algominds_daily_fees`: v2 is an unfinished parallel
  system (tests/docs only) — do not merge into the live path.
- `tcp_ts.py` vs `tcp_ts_runtime_launch.py` vs `tcp_ts_v2.py`: keep only v2 live;
  the other two are frozen artifacts until deliberately deleted.

## E. Rollback instructions (per phase)

Preparation (before merging any phase): record `PHASE_SHA=$(git rev-parse HEAD)`;
timestamped copies of `daily_returns_secret_state.json`, `tcp_daily_returns_secret_state.json`,
`Momentum Pacer/momentum_pacer_manual_daily_rows.json` (if present), `yq.csv`, `.env` files
into a dated folder OUTSIDE the repo.

Rollback = three steps, ~2 minutes per app:
1. `git revert <phase-merge-sha>` (phases are pure renames+shims ⇒ revert is clean; if a
   later phase already landed, revert in reverse order — shims guarantee reverts don't
   orphan imports).
2. Restart affected app(s) via their unchanged bats (`reboot_*_ts.bat`), or the dashboard
   Reboot button; production data was never moved, so no data restore is normally needed.
3. Run the phase's gate (regression-plan §3) + U1-U9. If state anomalies appear (G-TKP-2
   fails), restore the timestamped state copy, restart again, re-gate.

Special cases:
- Phase 5f (config/runtime-mode cycle) rollback must revert the single bucket commit —
  never hand-edit one of the two files back.
- If a phase included an internal bat edit (Phase 4 optional, Phase 6b), the revert
  restores the bat; verify with `git diff pre-phase -- '*.bat'` = empty.
- Absolute worst case: `git reset --hard pre-reorg-baseline` on a scratch branch, force
  no one — the tag from P0.3 is the anchor; production data files are untracked and
  therefore untouched by any git operation (that is exactly why they must never be
  `git mv`-ed into the tree during this project).
