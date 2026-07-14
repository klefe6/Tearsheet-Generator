# Migration Sequence — One Application Per Commit, Zero Breakage

Order (as requested): **Y&Q → TKP → TCP → AGM → shared extraction.**
Every phase = one commit on a dedicated branch, one restart cycle, one gate run
(regression-plan.md), and one documented rollback (risks-and-blockers.md §rollback).

## The invariant technique: root shims + anchored paths

1. **Path anchoring first, movement second.** Any module whose runtime file paths derive
   from `__file__` gets a one-line refactor to derive them from an explicit
   `REPO_ROOT = Path(__file__).resolve().parent` computed **in the root shim** (or an
   already-root-anchored constant like `tcp_config.REPO_ROOT`), verified
   behavior-identical BEFORE the file moves. Known cases:
   - `tkp_ts.py:251-252` → `daily_returns_secret_state.json` (production state!)
   - `yq_ts.py:418` → `yq.csv`
   - `mp_ts.py:89,1265` → fee workbook + manual-rows JSON (anchor to the
     `Momentum Pacer` dir explicitly, not to the moving file)
   - `mp_ts.py:2291` assets folder; `algominds_daily_balances.py:42-50`;
     `algominds_benchmark_daily.py:55-67`
   - `tcp_ts_v2.py:165,195-196` already resolves vs `tcp_config` REPO_ROOT — verify only.
2. **Root shim** with the exact old module name:
   `from apps.<app>.<module> import *  # noqa: F401,F403` + explicit re-export of
   `__all__`-less privates that tests import, + `if __name__ == "__main__": main()`.
   Bats, tests, and `sys.modules` consumers keep working unchanged.
3. **Never move**: production data, env files, launchers, `assets/` (file-classification.md §9, §12).
4. **`git mv` only** (rename-tracking), one app per commit, no mixed commits.

## Phase 0 — Preconditions (blocking; no reorg commit until all green)
- P0.1 Commit or shelve the dirty working tree (29 entries; includes AGM drawdown WIP + uploader FE/BE WIP). A reorg on a dirty tree makes rollback ambiguous.
- P0.2 **Merge or explicitly park the three uploader-ingest branches**
  (`feature/glenn-uploader-downstream-export`, `chore/uploader-professional-cors`,
  `feature/uploader-export-rollback`). They modify all three entrypoints and add root
  modules; merging after the reorg = guaranteed conflicts on every file that moved.
- P0.3 Tag baseline `pre-reorg-baseline` at the merged tip.
- P0.4 Capture golden outputs (regression-plan.md §2) while all four sites run.
- P0.5 Scaffolding commit: create `apps/{tkp,tcp,agm,yq}/__init__.py`, `shared/`,
  `config/`, `ops/`, `data/development-only/`, commit `docs/reorganization/`. No moves.

## Phase 1 — Y&Q (smallest closure: 1 shared import, no auth, no writes)
Commit `reorg(yq): move yq_ts body to apps/yq with root shim`
1. Anchor `yq.csv` path to repo root (`yq_ts.py:418`).
2. `git mv` body → `apps/yq/yq_app.py`; root `yq_ts.py` = shim.
3. Move `yq.xlsx`, `Y&QInvestments_DDoc_CTA_2025_03.pdf` → `apps/yq/` (unreferenced).
4. `yq.csv` STAYS at root (production data, gitignored).
Gates: G-YQ (regression-plan). External check: `reboot_yq_ts.bat` untouched, port 8303,
dashboard card green, `yq-ts.hcresearch.ltd` serves.

## Phase 2 — TKP
Commit `reorg(tkp): move tkp_ts body to apps/tkp with root shim`
1. Anchor state-file dir (`:251-252`) to repo root — **the single most dangerous line in
   the whole migration**: if it silently re-anchors to `apps/tkp/`, TKP boots with an
   EMPTY ledger and looks "fine". Gate G-TKP-2 exists precisely for this.
2. `git mv` body → `apps/tkp/tkp_app.py`; root shim.
3. No other file moves (TKP owns nothing else).
Gates: G-TKP. External: `reboot_tkp_ts.bat`/staff ps1 untouched; 8301/8321.

## Phase 3 — TCP
Commit `reorg(tcp): move tcp v2 + exclusive state modules to apps/tcp`
1. `git mv` `tcp_ts_v2.py` body → `apps/tcp/tcp_app.py`; root shim.
2. `git mv` `tcp_runtime_state.py`, `tcp_state.py` → `apps/tcp/` + root shims
   (consumers: scripts/seed_tcp_state.py, scripts/tcp_acceptance.py, tests — all resolve
   via shims; migrate their imports in the same commit if trivial).
3. Quarantine (do not delete): `tcp_ts.py`, `tcp_ts_runtime_launch.py` → leave in place,
   mark obsolete in docs; deletion is a separate, later decision (rollback bak still
   references tcp_ts.py).
4. Verify `resolve_state_paths` still hits `%LOCALAPPDATA%` (env) and repo root (default).
Gates: G-TCP incl. full-ledger replay parity. External: bat/ps1 untouched; 8302/8312/8322;
watch the purity tests (`test_tcp_foundation.py:14,31`) and the no-hardcoded-8302 test.

## Phase 4 — AGM
Commit `reorg(agm): move algominds cluster to apps/agm; extract mp_ts body`
1. Anchor `Momentum Pacer` data paths (fee xlsx, manual-rows JSON, balances, benchmarks)
   to an explicit `MP_DATA_DIR` constant that keeps pointing at `Momentum Pacer/`.
2. `git mv` the 11 algominds runtime modules + `algominds_daily_accounting_ui.py` +
   `algominds_v2*` → `apps/agm/`; root shims for each (mp_ts.py's `sys.path` bridge
   `mp_ts.py:30-32` makes root shims resolvable unchanged).
3. Extract `mp_ts.py` body → `apps/agm/agm_app.py`; `Momentum Pacer/mp_ts.py` becomes the
   shim (bat contract intact: `reboot_mp_ts.bat` cds into `Momentum Pacer` and runs it).
4. Target-tree root `mp_ts.py`: ADD as a second thin shim only if wanted; if added,
   `reboot_mp_ts.bat` may later be simplified — internal change, bat name/path frozen.
   `Momentum Pacer\` directory is retained regardless (HomePage `debug.py:256` + data home).
5. `program_account_stats.py` stays at root for now (moves in Phase 5 to shared/accounting).
Gates: G-AGM. External: bat/ps1 untouched; 8304/8324.

## Phase 5 — Shared extraction (one bucket per commit, slowest phase)
Order chosen to start with leaves and end with the config/runtime-mode cycle:
- 5a `shared/formatting`: tearsheet_header, tearsheet_disclosure, tearsheet_date_defaults
  (disclosure shim is permanent — Gold_Maker/tsgen also import it).
- 5b `shared/reporting`: tcp_dashboard + tcp_drawdown (move as a pair — import cycle),
  then tcp_public_sections, tcp_daily_values, tearsheet_portal.
- 5c `shared/accounting`: tcp_ledger, tcp_calculations, program_account_stats.
- 5d `shared/benchmarks`: tcp_benchmarks.
- 5e `shared/authentication`: tearsheet_gate_ui, tearsheet_gate_auth, tearsheet_local_admin, tcp_admin.
- 5f `config/` + `shared/utilities`: tcp_config + tearsheet_runtime_mode **in one commit**
  (mutual lazy imports tcp_config:127,133 ⇄ runtime_mode:116,156).
After EACH bucket: full gate suite, one real restart cycle of all four apps via the bats.
Root shims are retained until a full production reboot + one week of dashboard-green.

## Phase 6 — Housekeeping (optional, separate commits)
- 6a `scripts/development/` moves (file-classification §6).
- 6b `data/development-only/` moves — `tsgen.py:22-37` and `tv_vadi_convert.py:10-14`
  path updates land IN THE SAME COMMIT as the CSV/XLSX moves.
- 6c Archive `run_all_services.bat` (broken), logs, CURSOR_PATCH.md.

## Explicit non-goals
Renaming `tcp_*` shared modules to neutral names; deleting legacy `tcp_ts.py`;
moving launchers into `ops/`; changing any port, route, schema, or env-file location;
touching `Manager`/`HomePage` repos. Each is possible later as its own coordinated change.
