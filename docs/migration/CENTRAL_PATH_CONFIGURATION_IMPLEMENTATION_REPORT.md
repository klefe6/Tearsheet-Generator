# Central Path Configuration Implementation Report

> Isolated worktree: `feature/central-path-config` from `live-main` @ `3cfda4f`
> Timestamp: 2026-08-01 (local, UTC-4)
> Read-only toward production: no service restarts, no data moves, no commits staged.

---

## 1. Executive verdict

**PASS — compatibility-preserving path foundation implemented in isolation.**

A pure `tearsheet_paths.py` module and five low-risk consumers were converted without touching `tkp_ts.py`, financial calculations, mutable state writers, uploader export behavior, or running services. Default resolution matches current laptop paths exactly for all converted consumers.

TKP integration remains **deferred** (Part 1C) due to dirty deployed title-only changes with no path overlap — safe to exclude from this commit.

---

## 2. Baseline and dirty-file assessment

| Item | Finding |
|---|---|
| Base commit | `3cfda4fdde5eaa8fae42c87b56d30d34aa717f68` (`live-main`) |
| Implementation branch | `feature/central-path-config` in `.worktrees/central-path-config` |
| Deployed worktree dirty `tkp_ts.py` | Two title-only hunks (~lines 1889, 4172); **no path overlap** |
| Other deployed dirt | `GSPC_daily.csv` modified; unrelated untracked backup artifacts |
| This lane touches `tkp_ts.py`? | **No** |

---

## 3. Configuration architecture

```text
tearsheet_paths.py (pure resolver, repo root)
  ├─ resolve_hc_app_env()
  ├─ resolve_deploy_root() / resolve_dirty_root()
  ├─ per-path resolvers (AGM CSV, benchmark cache, ingest audits, Y&Q CSV)
  ├─ load_tearsheet_paths() → TearsheetPaths dataclass
  ├─ paths_identity_summary() → safe diagnostics
  └─ ensure_non_authoritative_directories() → explicit mkdir only

Consumers (Part 1B):
  tcp_ts_v2.py          → resolve_tcp_ingest_audit_path()
  mp_ts.py              → resolve_agm_ingest_audit_path()
  algominds_daily_balances.py → resolve_agm_pinned_csv()
  algominds_benchmark_daily.py → resolve_agm_benchmark_cache_dir()
  reboot_yq_ts.ps1      → HC_DIRTY_ROOT / HC_YQ_DATA_ROOT (optional overrides)
```

Precedence: **env override → `HC_APP_ENV` profile → laptop default**.

TCP state/workbook paths remain delegated to `tcp_config.py` (`TCP_V2_*`).

---

## 4. Configuration keys

See [`CENTRAL_PATH_CONFIGURATION.md`](CENTRAL_PATH_CONFIGURATION.md).

Active in this lane: `HC_APP_ENV`, `HC_DEPLOY_ROOT`, `HC_DATA_ROOT`, `HC_PRODUCTION_DATA_ROOT`, `HC_SANDBOX_DATA_ROOT`, `HC_LOG_ROOT`, `HC_CACHE_ROOT`, `HC_BACKUP_ROOT`, `HC_AGM_DATA_ROOT`, `HC_YQ_DATA_ROOT`, `HC_AGM_PINNED_CSV`, `HC_AGM_BENCHMARK_CACHE_DIR`, `HC_TCP_INGEST_AUDIT_PATH`, `HC_AGM_INGEST_AUDIT_PATH`, `HC_DIRTY_ROOT`, `YQ_CSV_PATH`.

---

## 5. Compatibility defaults

| Setting | Laptop default (normalized) |
|---|---|
| `deploy_root` | `{worktree}/` (module parent) |
| `dirty_root` | `C:\Coding Projects\Tearsheet Generator` |
| `yq_csv_path` | `C:\Coding Projects\Tearsheet Generator\yq.csv` |
| `agm_pinned_csv` | `{worktree}/Momentum Pacer/data/daily_balances/balances_210TGG51_20OCT2025_07JUL2026.csv` |
| `agm_benchmark_cache_dir` | `{worktree}/Momentum Pacer/data/benchmarks` |
| `tcp_ingest_audit_path` | `{worktree}/glenn_uploader_ingest_tcp_audit.jsonl` |
| `agm_ingest_audit_path` | `{worktree}/Momentum Pacer/glenn_uploader_ingest_agm_audit.jsonl` |

VPS profiles map to `E:\H&C\` per Azure build spec; **not active by default**.

---

## 6. Consumers converted

| Consumer | File | Change |
|---|---|---|
| TCP ingest audit | `tcp_ts_v2.py` | `resolve_tcp_ingest_audit_path(deploy_root=REPO_ROOT)` |
| AGM ingest audit | `Momentum Pacer/mp_ts.py` | `resolve_agm_ingest_audit_path(deploy_root=parent.parent)` |
| AGM pinned CSV | `algominds_daily_balances.py` | `default_csv_path()` → `resolve_agm_pinned_csv()` |
| AGM benchmark cache | `algominds_benchmark_daily.py` | `cache_dir()` → `resolve_agm_benchmark_cache_dir()` |
| Y&Q launcher | `reboot_yq_ts.ps1` | Optional `HC_DIRTY_ROOT` / `HC_YQ_DATA_ROOT`; defaults unchanged |

---

## 7. Consumers deferred

| Consumer | Reason |
|---|---|
| TKP state JSON | Financial R/W; dirty `tkp_ts.py`; `__file__` anchor |
| TKP workbook | Protected folder; missing handoff |
| TKP ingest audit | Same file as deferred TKP block |
| TKP/TCP logos | Not in Part 1B scope |
| AGM manual JSON | Financial R/W continuation ledger |
| AGM fee workbook | Higher blast radius |
| TCP state/workbook | Already env-able via `tcp_config`; financial |
| Uploader DB/paths | Write/export risk; user deferred |
| Remaining launchers | After Y&Q pattern proven |
| Y&Q body move (`feature/reorg-yq-phase1`) | Parked per delta report |

---

## 8. Tests and results

| Test suite | Result |
|---|---|
| `tests/test_tearsheet_paths.py` (29 tests) | **PASS** |
| `test_agm_daily_balances.py::test_does_not_mutate_source_csv` | **PASS** |
| `test_agm_benchmark_daily.py::test_local_cache_covers_agm_csv_range` | **PASS** |
| `test_agm_benchmark_daily.py::test_cache_only_env_blocks_fetch` | **PASS** |
| `test_uploader_ingest_framework.py::test_apply_rejection_and_audit_trail` | **PASS** |
| Import check (`tearsheet_paths`, `algominds_*`) | **PASS** |
| Live GET `/healthz` 8301, 8302, 8304 (unchanged services) | **200, 200, 200** |

Excluded per plan: `test_tcp_v2_shell.py::test_canonical_store_is_memory_only`, export/delete/replay suites, fleet restarts.

---

## 9. Default-path parity evidence

| Consumer | Before (no overrides) | After (no overrides) | Equal? |
|---|---|---|---|
| TCP ingest audit | `{REPO_ROOT}/glenn_uploader_ingest_tcp_audit.jsonl` | same via resolver | **Yes** |
| AGM ingest audit | `{REPO_ROOT}/Momentum Pacer/glenn_uploader_ingest_agm_audit.jsonl` | same via resolver | **Yes** |
| AGM pinned CSV | `{REPO_ROOT}/Momentum Pacer/data/daily_balances/balances_210TGG51_20OCT2025_07JUL2026.csv` | same via resolver | **Yes** |
| AGM benchmark cache | `{REPO_ROOT}/Momentum Pacer/data/benchmarks` | same via resolver | **Yes** |
| Y&Q launcher dirty root | `C:\Coding Projects\Tearsheet Generator` | same (no `HC_DIRTY_ROOT`) | **Yes** |
| Y&Q launcher CSV env | `C:\Coding Projects\Tearsheet Generator\yq.csv` | same (no `HC_YQ_DATA_ROOT`) | **Yes** |

Verified via unit tests with normalized `Path.resolve()` comparison.

---

## 10. Financial behavior parity

| Area | Assessment |
|---|---|
| TKP | **Untouched** — no calculation, workbook, or state changes |
| TCP drawdown / benchmarks | **Untouched** — only ingest audit path resolution changed |
| AGM CSV → manual JSON → calculations | **Preserved** — pinned CSV resolver points to same file; `test_does_not_mutate_source_csv` passes |
| Y&Q source period / stale warning | **Untouched** — launcher sets same `YQ_CSV_PATH` default |
| Uploader export / DB | **Untouched** — no uploader files modified |

Protected AGM continuity values were not re-exported or rewritten.

---

## 11. Files changed

### New (untracked)

- `tearsheet_paths.py`
- `tests/test_tearsheet_paths.py`
- `docs/migration/CENTRAL_PATH_CONFIGURATION.md`
- `docs/migration/CENTRAL_PATH_CONFIGURATION_IMPLEMENTATION_REPORT.md`

### Modified

- `tcp_ts_v2.py` (+3/-1)
- `Momentum Pacer/mp_ts.py` (+7/-2)
- `algominds_daily_balances.py` (+10/-6)
- `algominds_benchmark_daily.py` (+13/-3)
- `reboot_yq_ts.ps1` (+16/-2)

**Diff-stat (tracked only):** 5 files, +35 insertions, -14 deletions

**Excluded from this lane:** `tkp_ts.py`, all unrelated dirty root files, uploader tree, financial state files.

---

## 12. Remaining path blockers

1. TKP state `__file__` anchor and workbook protected-folder dependency
2. AGM manual JSON and fee workbook path abstraction
3. Logo paths (`TEARSHEET_LOGO_PATH`, `YQ_LOGO_PATH`)
4. Glenn split checkout + unmerged launcher
5. Uploader prod/sandbox shared Fly deployment
6. Manager/HomePage fleet path duplication
7. NSSM service manifest and VPS `E:\H&C\` env rendering

---

## 13. Rollback procedure

1. Delete `.worktrees/central-path-config` or discard uncommitted changes.
2. If merged later: `git revert <commit-sha>` on a clean branch.
3. Restart apps via unchanged launchers only if the commit was deployed.
4. No financial data restore required — data paths unchanged on disk.

---

## 14. Proposed isolated commit

**Can commit without `tkp_ts.py`:** **Yes**

```
refactor: centralize portable path configuration

Add tearsheet_paths resolver with HC_* env keys and laptop-compatible
defaults. Wire low-risk consumers (ingest audit logs, AGM pinned CSV,
AGM benchmark cache, Y&Q launcher overrides) without changing financial
calculations or mutable state paths. TKP integration deferred.
```

Stage only:

```text
tearsheet_paths.py
tests/test_tearsheet_paths.py
tcp_ts_v2.py
Momentum Pacer/mp_ts.py
algominds_daily_balances.py
algominds_benchmark_daily.py
reboot_yq_ts.ps1
docs/migration/CENTRAL_PATH_CONFIGURATION.md
docs/migration/CENTRAL_PATH_CONFIGURATION_IMPLEMENTATION_REPORT.md
```

---

## 15. Recommended next lane

1. **Reconcile deployed `tkp_ts.py` title drift** (operator decision) on a separate branch.
2. **Wire TKP state path** via `TKP_STATE_PATH` / `HC_TKP_DATA_ROOT` with G-TKP-2 row-count gate.
3. **Obtain TKP workbook via `C:\AI_HANDOFF`** before any workbook path change.
4. **Merge canonical Glenn launcher** pinned to `live-deploy-main`.
5. **Execute uploader separation plan** (design-only until approved).

---

## Consumer matrix

| Consumer | Previous resolution | New configuration key | Default path identical | Override tested | Status |
|---|---|---|---|---|---|
| TCP ingest audit | `REPO_ROOT/glenn_uploader_ingest_tcp_audit.jsonl` | `HC_TCP_INGEST_AUDIT_PATH` | Yes | Yes | Converted |
| AGM ingest audit | `mp_ts dir/glenn_uploader_ingest_agm_audit.jsonl` | `HC_AGM_INGEST_AUDIT_PATH` | Yes | Yes | Converted |
| AGM benchmark cache | `__file__/Momentum Pacer/data/benchmarks` | `HC_AGM_BENCHMARK_CACHE_DIR` | Yes | Yes | Converted |
| AGM pinned CSV | `__file__/Momentum Pacer/data/daily_balances/…csv` | `HC_AGM_PINNED_CSV` | Yes | Yes | Converted |
| Y&Q launcher dirty root | Hard-coded main repo root | `HC_DIRTY_ROOT` | Yes | Config test | Converted |
| Y&Q launcher CSV seed | `Join-Path dirtyRoot yq.csv` | `HC_YQ_DATA_ROOT` | Yes | Config test | Converted |
| TKP state/workbook/audit | `tkp_ts.py` inline | `HC_TKP_*` (planned) | — | — | **Deferred** |
| Uploader DB | Fly `/data/...` | `HC_UPLOADER_DATABASE` (planned) | — | — | **Deferred** |

---

## Financial / deployment safety review (GPT-5.6 Sol)

| Check | Result |
|---|---|
| No financial calculation changes | Pass |
| No financial data rewrites | Pass |
| No file/data moves | Pass |
| No service restarts performed | Pass |
| No uploader writes/exports | Pass |
| Default path parity for converted consumers | Pass |
| AGM source precedence unchanged | Pass |
| TKP excluded from diff | Pass |
| Running health endpoints unaffected | Pass (8301/8302/8304 → 200) |

**Review verdict:** Safe to commit as an isolated path-configuration change. Deploy only after operator review; restart not required for validation of this uncommitted worktree.

---

### Lane Progress

* **Done:** Central path module; 5 safe consumers; 33 passing targeted tests; documentation; implementation report; safety review
* **Working:** None (awaiting operator commit decision)
* **Remaining:** TKP wiring; logos; manual JSON; uploader separation; Glenn launcher; VPS env rendering
* **Completion:** Path configuration lane ≈ **60%** (foundation + safe consumers); full portability ≈ **35%**
* **Next best action:** Commit isolated change from `feature/central-path-config`; then wire TKP state path on a separate branch after dirty-file reconciliation

| Lane | Status | Completion % | Blockers | Current commit | Next action |
|---|---|---:|---|---|---|
| Central path configuration | Implemented (uncommitted) | 60% | TKP deferred; workbook handoff | `3cfda4f` base | Review diff; commit isolated files |
| TKP path integration | Deferred | 0% | Dirty deployed file; missing workbook | `3cfda4f` | Reconcile title drift; add `TKP_STATE_PATH` |
| Y&Q body move | Parked | 10% | Path lane should land first | `a8bc22d` off-branch | Do not merge yet |
| Uploader separation | Runbook only | 15% | Shared Fly app | Jul 30 evidence | Execute under freeze |
| VPS cutover | Blocked | 15% | Path config + handoff inputs | Azure spec ratified | Private VM prep after TKP paths |
