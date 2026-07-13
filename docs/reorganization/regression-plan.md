# Regression Plan — Acceptance Gates Per Phase

Test-runner constraint (pytest.ini): several purity tests assert `tkp_ts`/`tcp_ts` are
absent from `sys.modules` — **run per-file groups, never the whole `tests/` dir in one
process**: `.venv310\Scripts\python.exe -m pytest tests/<file> -q`.

## 1. Universal gate (every phase, after restart via the UNMODIFIED bats)
| # | Check | Pass criterion |
|---|---|---|
| U1 | `reboot_*.bat` launch from Manager path semantics (`cmd /k call <bat>`) | process up, correct interpreter (`.venv310` for TKP/TCP/AGM; PATH python for Y&Q) |
| U2 | Ports | 8301, 8302, 8303, 8304 LISTENING on 127.0.0.1; no listener on 8311/8312 unless preview intentionally running |
| U3 | `GET /healthz` (TKP `tkp_ts.py:3370`, TCP `tcp_ts_v2.py:1208`, AGM `mp_ts.py:3301`) | 200 + JSON `status` ok; Y&Q has no healthz → `GET /` 200 instead |
| U4 | `GET /` full page | 200, title correct, no Dash callback error banner |
| U5 | `GET /monthly` (TKP/TCP/AGM) | 404 (register_monthly_backup_404) |
| U6 | `/admin` gate | unauthenticated → gate/login, not the admin table |
| U7 | HomePage dashboard | all four cards green; Start/Kill/Reboot buttons still resolve their bats |
| U8 | Staff launchers (spot-check one per phase) | 8321/8322/8324 bind, `TEARSHEET_MODE=staff` honored |
| U9 | Import-purity + smoke: `pytest tests/test_tearsheet_runtime_mode.py tests/test_tearsheet_password_gate.py -q` (per-file) | green |

## 2. Golden captures (Phase 0, while everything runs; diffed after every phase)
- TKP: last 5 rows of the Daily Returns table (NAV/$PL/Perc.Net/HWM/Fee), Cumm Perc. Net,
  Cumm Fee, monthly-calendar year totals. Derived from `daily_returns_secret_state.json`
  — capture via the chain-audit snippet (docs/…/risks §TKP-verifier) not the UI, so the
  gate is headless.
- TCP: `tests/replay_tcp_ledger.py` full replay output — every stored derived field must
  reproduce from raw inputs, byte-for-cent. Store the replay report.
- AGM: outputs of `pytest tests/test_agm_daily_accounting.py tests/test_agm_account_stats.py -q`
  plus the account-stats table first/last rows.
- Y&Q: row count + head/tail of `yq.csv` parse, cumulative return figure on `/`.
- Uploader: `GET /health`, `GET /api/programs` snapshot.

## 3. Per-application gates
### G-YQ (Phase 1)
1. `pytest tests/test_yq_smoke.py -q` green.
2. `yq.csv` still found (log line/absence of the file-not-found branch) — proves path anchoring.
3. `/` renders chart + table; golden cumulative return matches.
4. `reboot_yq_ts.bat` byte-identical (`git diff --stat` empty for it).

### G-TKP (Phase 2)
1. **G-TKP-2 (state anchoring — critical):** after restart, `/healthz` and the daily table
   show 838+ rows and the golden last-row values. A fresh/empty table = the `__file__`
   re-anchoring failure → immediate rollback.
2. `pytest tests/test_tkp_add_row_modal.py tests/test_tkp_password_gate.py -q` green.
3. `pytest tests/test_tcp_tkp_visual_parity.py -q` green.
4. Admin add-row + delete-last round-trip on a COPY of the state file (never live), diff = one row.
5. `TKP_BIND_PORT`/staff 8321 spot check.

### G-TCP (Phase 3)
1. `python tests/replay_tcp_ledger.py` parity report identical to golden.
2. Per-file: `tests/test_tcp_ledger.py`, `tests/test_tcp_state.py`, `tests/test_tcp_daily_values_collapse.py`,
   `tests/test_tcp_access_daily_values.py` (incl. `test_port_8302_never_used_in_tcp_v2_source`
   — confirm it still scans the MOVED source), `tests/test_tcp_foundation.py` (purity).
3. State path resolution: with `.tcp_production.env` → %LOCALAPPDATA% paths; without → repo-root JSON. Log lines verify.
4. Admin login/logout (`/admin/login`) + one simulated add-row via `tcp_admin` simulation tests.
5. Preview launcher `reboot_tcp_ts_v2.bat` still binds 8312, untouched by prod env.

### G-AGM (Phase 4)
1. Per-file: `tests/test_agm_daily_accounting.py`, `tests/test_agm_daily_fees.py`,
   `tests/test_agm_account_stats.py`, `tests/test_agm_daily_balances.py`,
   `tests/test_agm_benchmark_daily.py`, `tests/test_agm_password_gate.py`,
   `tests/test_agm_portal_registry.py`, `tests/test_program_account_stats.py`.
2. Fee workbook + balances CSV + benchmark caches load from `Momentum Pacer/` (anchoring proof: golden account-stats row match).
3. Manual-rows add/delete round-trip on a scratch copy → full recompute returns table (AGM's delete recomputes — keep it that way).
4. Benchmark fetch path: with `AGM_BENCHMARK_CACHE_ONLY=1`, boots offline from CSV caches.

### G-SHARED (each 5x bucket)
1. ALL of G-YQ/G-TKP/G-TCP/G-AGM (shared modules touch every app).
2. Root-shim import check: `python -c "import tearsheet_disclosure, tcp_admin, ..."` for every moved name.
3. Gold_Maker + tsgen boot check (they import tearsheet_disclosure): `python -c "import Gold_Maker_ts"` is NOT safe (runs app) — instead grep-verify shim presence + launch Gold Maker once per 5a/5e bucket.

## 4. Glenn Uploader export gate (every phase that touches root files; cheap)
1. `cd uploader/backend && .venv/Scripts/python -m pytest -q` (with `--basetemp` on this machine) — full suite green.
2. Live check: `GET /health`, `GET /api/programs`, `POST /api/rows/TKP` on a scratch `DATABASE_PATH`, `POST /api/export/all` (dry-run default) → sandbox JSON written, uploader DB rows marked per contract.
3. Post-ingest-merge (when P0.2 lands): `verify_downstream_ingest.py --strict` dry-run probes against TKP/TCP/AGM ingest routes return `dry_run_validated`; one real ingest round-trip on scratch state per app; `glenn_uploader_ingest_*_audit.jsonl` appended.

## 5. Calculation-comparison rule
A phase passes only if every golden number is **identical to the cent / basis point**.
Any drift — even "obviously better" — fails the phase: this migration must be
calculation-neutral by construction; fixes ride separate commits.

## 6. Acceptance sign-off checklist per phase
- [ ] Gates green (attach outputs)
- [ ] `git diff --stat pre-phase..post-phase` contains ONLY intended renames/shims
- [ ] Launchers byte-identical (unless the phase explicitly edits an internal bat)
- [ ] One full logon-simulation: run Manager `launch_all_services.py` phases manually or via `launch_all.bat` on a quiet window; dashboard all-green
- [ ] Rollback rehearsal documented (risks-and-blockers.md) — revert SHA identified before merge
