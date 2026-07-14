# Dependency Map — Tearsheet Generator Reorganization Audit

Read-only audit, 2026-07-13. Repo `C:\Coding Projects\Tearsheet Generator` @ `a5beb25`
(branch `fix/agm-nav-title-account-stats`, working tree dirty — 29 entries).
`.worktrees/`, `.venv310/`, `node_modules/`, `__pycache__/` excluded. Every claim
carries file:line evidence gathered from the live checkout.

---

## 1. TKP — `tkp_ts.py`, port 8301 (staff 8321)

### Local import closure (17 modules, all shared — TKP owns no private module)

Direct (`tkp_ts.py:37-66`): `tearsheet_disclosure`, `tearsheet_gate_ui`,
`tearsheet_gate_auth`, `tcp_admin`, `tearsheet_runtime_mode`, `tearsheet_portal`,
`tearsheet_header`, `tearsheet_date_defaults`, `tearsheet_local_admin`.

Transitive: `tearsheet_gate_ui→tearsheet_disclosure` (:14);
`tearsheet_gate_auth→tcp_config` (:13);
`tcp_admin→tcp_calculations, tcp_public_sections, tcp_ledger, tearsheet_date_defaults` (:18,34,35,36);
`tcp_calculations→tcp_ledger` (:14);
`tcp_public_sections→tcp_dashboard, tearsheet_gate_auth, tearsheet_disclosure, tearsheet_gate_ui, tcp_drawdown, tearsheet_header` (:14-26) + lazy `tcp_daily_values` (:848);
`tcp_dashboard→tcp_ledger` (:17) + lazy `tcp_benchmarks, tcp_drawdown` (:395-396);
`tcp_drawdown→tcp_dashboard` (:18, cyclic);
`tcp_daily_values→tcp_admin, tcp_ledger, tcp_public_sections` (:14,21,22);
`tcp_config⇄tearsheet_runtime_mode` (lazy, tcp_config:127,133 / runtime_mode:116,156);
`tearsheet_local_admin→tearsheet_runtime_mode` (:45).

Full set: `tearsheet_{disclosure,gate_ui,gate_auth,runtime_mode,portal,header,date_defaults,local_admin}` +
`tcp_{admin,config,calculations,public_sections,ledger,dashboard,drawdown,daily_values,benchmarks}`.

### Data
| File | Access | Where defined |
|---|---|---|
| `daily_returns_secret_state.json` (repo root, gitignored, 404 KB PRODUCTION STATE) | R/W | `tkp_ts.py:248,251-252` — path = `dirname(abspath(__file__))` ⚠ moves with the file defining it |
| `...Hughes & Company - Documents\...\TKP\VADI\Copy of tkp_alex_old1.xlsx` | R (frozen at row 715, `FORCE_LAST_EXCEL_ROW`, :371) | `tkp_ts.py:243-245` hardcoded |
| `...\Branded Logo\Trianle-Only-Logo.png` | R | `tkp_ts.py:80` hardcoded |
| `assets/styles.css` (repo root) | R (Dash default assets dir) | `tkp_ts.py:1839-1842` |
| `daily_returns.xlsx` | browser download only | :3435, :4054 |

### Env vars
`TEARSHEET_MODE`, `TKP_BIND_PORT` (runtime_mode:45,102-105), `TKP_ADMIN_TOKEN`,
`TKP_SESSION_SECRET` (gate_auth:54-55 → tcp_config:198-224),
`TEARSHEET_LOCAL_DIRECT_ADMIN`, `TEARSHEET_STAFF_ALLOWED_HOSTS` (local_admin:47-86).

### Routes
`/admin` (:3346), `/admin/logout` (:3364), `/healthz` (:3370), `/monthly`→404
(register_monthly_backup_404, :1848 / runtime_mode:177-179), plus Dash defaults.
**No uploader ingest route in this checkout** (grep `register_uploader_ingest` = 0 hits).

### External calls
yfinance `yf.download` (:1547,1564), quantstats `download_returns` (:156,1189). No subprocess, no scheduler.

### Bind
`app.run(debug=is_legacy(), port=resolve_tkp_bind_port())` (:4146) — no `host=` → 127.0.0.1.

---

## 2. TCP — `tcp_ts_v2.py`, port 8302 (preview 8312, staff 8322)

### Production entrypoint resolution (evidence chain)
- `reboot_tcp_ts.bat:4` → `reboot_tcp_ts.ps1`
- `reboot_tcp_ts.ps1:21-25` → imports `.local_dev.env` then `.tcp_production.env`, runs `.venv310\Scripts\python.exe tcp_ts_v2.py`
- `.tcp_production.env:2` → `TCP_V2_BIND_PORT=8302`
- `tcp_ts_v2.py:1228,1240` → `resolve_bind_port(cfg)`; `tcp_config.py:61-62` preview=8312, production=8302
- Guard test: `tests/test_tcp_access_daily_values.py:447` forbids literal 8302 in v2 source
- Legacy `tcp_ts.py:2239` (`port=8302`, pre-2026-07-04 cutover — see `reboot_tcp_ts.bat.bak-20260704-cutover:9`) and orphan `tcp_ts_runtime_launch.py` are NOT production; tests actively forbid importing `tcp_ts` (`tests/test_tcp_foundation.py:14,31`, `tests/test_tcp_state.py:511`).

### Local import closure (19 modules)
Direct (`tcp_ts_v2.py:23-157,287`): all 8 `tearsheet_*` + `tcp_{admin,config,benchmarks,dashboard,ledger,runtime_state,drawdown,public_sections,daily_values,state}`.
TCP-EXCLUSIVE: `tcp_runtime_state` (→tcp_admin,tcp_config,tcp_dashboard,tcp_ledger,tcp_state :12-16), `tcp_state` (→tcp_ledger :19).
Does NOT touch `algominds_*`, `program_account_stats`, `mp_ts`, `tcp_ts`.

### Data
| File | Access | Where |
|---|---|---|
| State JSON active/backup/lock (`tcp_daily_returns_secret_state.*`) | R/W atomic (`tcp_state.py:425-492`, `os.replace`) | names `tcp_config.py:57-59`; default resolve vs REPO_ROOT (`tcp_ts_v2.py:165,195-196`); **production overridden to `%LOCALAPPDATA%\HughesCompany\TCP\state\...` via `.tcp_production.env:3-5`** |
| `...\TCP\tcp_alex.xlsx` sheet `NAV` (seed/fallback) | R only | default `tcp_config.py:12-15`; override `TCP_V2_WORKBOOK_PATH` |
| `_runtime/tcp_benchmark{,_btc,_eth}_cache.json` | R/W | `tcp_config.py:95-106`; SPXTR overridden to AppData (`.tcp_production.env:6`) |
| Logo PNG (same OneDrive path as TKP) | R | `tcp_ts_v2.py:182-185` |
| `_runtime/quarantine/`, `_runtime/tcp_v2_startup*.log` | ops artifacts | launcher redirects; `tcp_config.py:258` forbids state under `_runtime` |

### Env vars
`TCP_V2_{WORKBOOK_PATH,STATE_MODE,STATE_PATH,STATE_BACKUP_PATH,STATE_LOCK_PATH,ALLOW_WORKBOOK_FALLBACK,BIND_PORT,BENCHMARK_CACHE_PATH,BENCHMARK_BTC_CACHE_PATH,BENCHMARK_ETH_CACHE_PATH,ADMIN_TOKEN,SESSION_SECRET,SKIP_BENCHMARK_FETCH}` (tcp_config.py:90-231, tcp_ts_v2.py:344) + `TEARSHEET_MODE`, `TEARSHEET_LOCAL_DIRECT_ADMIN`, `TEARSHEET_STAFF_ALLOWED_HOSTS`.

### Routes
`/admin` (:1123), `/admin/login` (:1147), `/admin/logout` (:1157), `/healthz` (:1208), `/monthly`→404 (:1196). **No ingest route in this checkout.**

### External calls
quantstats `download_returns` only (`tcp_benchmarks.py:218-221`), cache-first, atomic write (:294-298). v2 does not import yfinance. No subprocess/scheduler.

---

## 3. AGM — `Momentum Pacer/mp_ts.py`, port 8304 (staff 8324)

### sys.path bridge (critical for the move plan)
`mp_ts.py:30-32`: `sys.path.insert(0, parent.parent)` → repo root importable from the
subdirectory. Assets: `assets_folder = _TS_ROOT/"assets"` (:2291). Launchers `cd` into
`Momentum Pacer` first (`reboot_mp_ts.bat:2`, `reboot_mp_staff.ps1:32`).

### Local import closure
- **AGM-exclusive (11)**: `algominds_{portal_registry,daily_balances,benchmark_daily,daily_fees,daily_accounting,monthly_summary,account_stats,monthly_stats,fee_payment_evidence,drawdown_semantics}` + `program_account_stats` (imported only by `algominds_account_stats.py:21`).
  Internal edges: `daily_accounting→benchmark_daily,daily_balances,daily_fees` (:34-36); `daily_fees→benchmark_daily,fee_payment_evidence` (:60-61); `monthly_summary→daily_fees` (:42); `account_stats→daily_fees,program_account_stats` (:20-21).
- **Shared (17)**: same 8 `tearsheet_*` + 9 `tcp_*` (via `tcp_admin` + `tcp_public_sections`, `mp_ts.py:35,49,68`). AGM does NOT import `tcp_runtime_state`/`tcp_state`.
- **NOT reachable from mp_ts.py**: `algominds_v2/` package, `algominds_v2_*.py` root modules, `algominds_daily_accounting_ui.py` (tests only), `Momentum Pacer/calc_engine.py` (standalone).

### Data
| File | Access | Where |
|---|---|---|
| `Momentum Pacer/Momentum Fee Calculation.xlsx` | R | `mp_ts.py:89-90` |
| `Momentum Pacer/data/daily_balances/balances_210TGG51_20OCT2025_07JUL2026.csv` | R | `algominds_daily_balances.py:24,42-50` (stale `..._02JUL2026.csv` copies exist in that dir and repo root — inactive) |
| `Momentum Pacer/data/benchmarks/{GSPC,NDX}_daily.csv` | R/W cache | `algominds_benchmark_daily.py:55-86` |
| `Momentum Pacer/momentum_pacer_manual_daily_rows.json` | W on admin edit (not yet on disk) | `mp_ts.py:1262-1285` |
| `agm_daily_performance.xlsx` | browser download only | `mp_ts.py:3118` |

### Env vars
`MP_TS_PRODUCTION` (:3321), `AGM_BIND_PORT` (runtime_mode:109-111), `AGM_ADMIN_TOKEN`,
`AGM_SESSION_SECRET` (gate_auth:59-63), `AGM_BENCHMARK_CACHE_ONLY` (benchmark_daily:138),
`TEARSHEET_MODE`, `TEARSHEET_LOCAL_DIRECT_ADMIN`, `TEARSHEET_STAFF_ALLOWED_HOSTS`.
(Other `AGM_*` identifiers in mp_ts.py are Dash IDs/constants, not env reads.)

### Routes
`/admin` (:3251), `/admin/logout` (:3287), `/monthly`→404 (:3293), `/healthz` (:3301). **No ingest route.**

### External calls
yfinance `^GSPC`/`^NDX` (`algominds_benchmark_daily.py:89-99`), cache-first, failure→cache fallback (:144-147). No subprocess/scheduler.

---

## 4. Y&Q — `yq_ts.py`, port 8303

- Import closure: **`tearsheet_disclosure` only** (`yq_ts.py:25`). Everything else stdlib/pip.
- Data: `yq.csv` — `Path(__file__).resolve().parent / "yq.csv"` (:418, read :427 latin-1). ⚠ gitignored (`.gitignore:11 *.csv`) → machine-local production input. Logo `C:\Users\H&CDanHughes\Pictures\yq.png` (:37). `yq.xlsx` and `Y&QInvestments_DDoc_CTA_2025_03.pdf` NOT referenced by code.
- Env vars: none. Auth: none (fully public). Writes: none.
- Bind: `app.run(debug=True, port=8303)` (:2126) — hardcoded port, debug always on, 127.0.0.1.
- Launcher: `reboot_yq_ts.bat` → bare `python yq_ts.py` (system PATH interpreter, NOT `.venv310`).
- Routes: Dash defaults only; no /healthz, no /admin.

---

## 5. Shared-module consumer matrix

| Module | TKP | TCP v2 | AGM | Y&Q | Others |
|---|---|---|---|---|---|
| tearsheet_disclosure | ✓ | ✓(transitive) | ✓ | ✓ | Gold_Maker_ts:18, tsgen:18, tcp_ts:24 |
| tearsheet_gate_ui / gate_auth | ✓ | ✓ | ✓ | — | |
| tearsheet_runtime_mode / local_admin | ✓ | ✓ | ✓ | — | |
| tearsheet_portal / header / date_defaults | ✓ | ✓ | ✓ | — | |
| tcp_admin, tcp_config, tcp_calculations, tcp_ledger, tcp_dashboard, tcp_drawdown, tcp_public_sections, tcp_daily_values, tcp_benchmarks | ✓ | ✓ | ✓ | — | scripts/, tests/ |
| tcp_runtime_state, tcp_state | — | ✓ | — | — | scripts/seed_tcp_state.py, scripts/tcp_acceptance.py, tests |
| algominds_* (10) + program_account_stats | — | — | ✓ | — | tests |
| assets/styles.css | ✓ | ✓ | ✓ | ✓ | Gold_Maker, tsgen |

Naming warning: the `tcp_*` prefix is historical — 9 of the 11 `tcp_*` modules are
**tri-app shared infrastructure** (auth manager, config, ledger, dashboard bits), not TCP-private.

## 6. Non-app root Python (same repo, out of 4-app scope but bat-launched)
- `Gold_Maker_ts.py` — port 8075 (`:849`, debug=True), launched by `reboot_gold_maker.bat`; hardcoded OneDrive logo/CSV (:23,:48).
- `tsgen.py` — port 8077 (`:843`, debug=True), launched by `run_tsgen.bat` which hardcodes `C:\Coding Projects\Tearsheet Generator\tsgen.py`; hardcodes 4 CSV paths + one OneDrive path (:22-25,:37).

## 7. Glenn Uploader (see external-contracts.md for the full proof)
Live tree: FastAPI backend (`uploader/backend/app`, port 8091) + Vite frontend (5173).
**Zero coupling to the tearsheets in the running code** — no HTTP transport
(`downstream_export.py` production stub returns `transport_not_implemented`; no urllib/requests import),
no cross-imports, no shared files, no subprocess. The HTTP ingest bridge
(`tearsheet_uploader_ingest.py`, `POST /api/uploader/ingest-daily-row`) exists ONLY on
unmerged branches (`feature/glenn-uploader-downstream-export`, `chore/uploader-professional-cors`,
`feature/uploader-export-rollback`) and in `.worktrees/`. The only trace in the live tree is
pre-provisioned env vars in `.local_dev.env:3-6` that nothing reads.
