# Codebase reorganization — current state inventory

**Captured:** 2026-10-03 (read-only audit; production not restarted)  
**Repository:** `C:\Coding Projects\Tearsheet Generator`  
**Remote:** `klefebvre6/Tearsheet-Generator`

## Git context

| Item | Value |
|------|--------|
| Working branch (audit start) | `fix/post-ingest-full-recalculation` @ `9bba414` |
| Reorganization branch | `refactor/github-vps-deployment-structure` |
| Production worktree | `C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main` |
| Production branch | `live-main` @ `3cfda4f` (per worktree list) |
| Dirty root checkout | Only `?? .pr_body_tkp_label.md` at audit start |
| Production worktree git access | Blocked for current user (dubious ownership — Administrators own `.git`) |

Fleet runtime config (Manager): `C:\Coding Projects\Manager\tearsheet_fleet_runtime.json` points `runtime_root` at `live-deploy-main`.

## Application matrix

| Application | Entrypoint | Source location (authoritative) | Data location (authoritative) | Config | Port | Startup | Shared deps | Git-tracked production data? | Git-tracked secrets? | VPS portability | Target location |
|-------------|------------|--------------------------------|------------------------------|--------|------|---------|-------------|------------------------------|----------------------|-----------------|-----------------|
| **TKP** | `tkp_ts.py` | `live-deploy-main\tkp_ts.py` (+ dirty root for dev) | `live-deploy-main\daily_returns_secret_state.json`; workbook via `HC_TKP_SOURCE_WORKBOOK` / OneDrive path in `tearsheet_paths.py` | `.tkp_production.env`, `.local_dev.env` | 8301 (8321 staff) | `reboot_tkp_ts.ps1` / `.bat` | tearsheet_* , `tcp_admin` | No (state gitignored) | No | Partial — `tearsheet_paths.py` merged | `C:\HC\apps\tkp` |
| **TCP** | `tcp_ts_v2.py` | `live-deploy-main\tcp_ts_v2.py` | `tcp_daily_returns_secret_state.json` (+ backup/lock); workbook `tcp_alex.xlsx` | `.tcp_production.env` (`TCP_V2_BIND_PORT=8302`) | 8302 (8322 staff) | `reboot_tcp_ts.ps1` | `tcp_*` modules, tearsheet_* | No | No | Best pilot — docs + healthz baseline | `C:\HC\apps\tcp` |
| **AGM** | `Momentum Pacer\mp_ts.py` | `live-deploy-main\Momentum Pacer\` + root `algominds_*.py` | `momentum_pacer_manual_daily_rows.json`, fee XLSX, balances CSV | `MP_TS_PRODUCTION=1` in `reboot_mp_ts.ps1` | 8304 (8324 staff) | `reboot_mp_ts.ps1` | tearsheet_* , `tcp_public_sections` | **Yes — balances CSV tracked** | No | Blocked on data governance | `C:\HC\apps\agm` |
| **Y&Q** | `yq_ts.py` | `live-deploy-main\yq_ts.py` | `yq.csv` at dirty root (`YQ_CSV_PATH`) | `reboot_yq_ts.ps1` | 8303 | `reboot_yq_ts.bat` → PS1 | `tearsheet_disclosure`, `tearsheet_paths` | No (`yq.csv` gitignored) | No | Medium — global python on laptop | `C:\HC\apps\yq` |
| **Uploader** | Fly.io backend + local scripts | `uploader\backend\`, `uploader\frontend\` | `uploader\backend\data\` SQLite; Fly `/data` | Fly secrets (out of repo) | 8091 (Fly) | `reboot_glenn_uploader.bat` | Downstream export to tearsheet ingest URLs | No DB in Git | No | Separate pipeline — not in 830x VPS pilot | `C:\HC\apps\uploader` (future) |
| **Other** | `Gold_Maker_ts.py`, `tsgen.py` | Repo root | Various CSV/XLSX dev files | bat launchers | n/a | `reboot_gold_maker.bat`, `run_tsgen.bat` | Shared disclosure | Mixed dev CSVs | No | Out of 4-app VPS scope | Stay in repo root |

## Duplicate copies — which is authoritative?

| Artifact | Authoritative copy | Stale / dev copies |
|----------|-------------------|-------------------|
| Production runtime code | `.worktrees\live-deploy-main` @ `live-main` | Dirty `C:\Coding Projects\Tearsheet Generator` (launcher refuses production start) |
| TKP state JSON | `live-deploy-main\daily_returns_secret_state.json` | Root copy may exist in dirty tree — do not treat as authoritative |
| Y&Q CSV | Dirty root `yq.csv` (per `tearsheet_paths.DEFAULT_DIRTY_ROOT`) | Worktree may symlink/copy — launcher sets `YQ_CSV_PATH` |
| TCP state | Worktree root JSON (production listener cwd) | Preview copies under `_runtime/` / tests |
| AGM balances CSV | On-disk under `Momentum Pacer\data\` | **Also in Git** — should not be |

## Classification table (selected paths)

| File / directory | Classification | Should be in Git? | Target location | Action |
|------------------|----------------|-------------------|-----------------|--------|
| `tkp_ts.py`, `tcp_ts_v2.py`, `yq_ts.py` | A SOURCE | Yes | `apps/*/ ` via deploy copy; root shim until moved | Deploy manifest lists files |
| `tearsheet_paths.py` | B SHARED | Yes | `apps/shared` on VPS | Merged on reorg branch |
| `assets/styles.css` | C STATIC | Yes | Per-app `assets/` on VPS | Copied with each app |
| `deployment/windows-vps/**` | D DEPLOY TEMPLATE | Yes | `C:\HC\deployment` | Clone + run scripts |
| `daily_returns_secret_state.json` | E PRODUCTION DATA | No | `C:\HC\data\tkp` | Migrate separately |
| `.tcp_production.env` | F SECRET/CONFIG | No | `C:\HC\config` + secrets | Manual on VPS |
| `_runtime/` | G CACHE | No | `C:\HC\data\tcp\_runtime` | Regenerate |
| `glenn_uploader_ingest_*.jsonl` | H LOG | No | `C:\HC\logs\ingest` | Optional migrate |
| `tests/fixtures/*` | I TEST | Yes | Stay in repo | Keep |
| `Momentum Pacer/data/daily_balances/*.csv` | E/F | **No** | `C:\HC\data\agm` | Reported — needs untrack approval |
| `tcp_ts.py` | J OBSOLETE | Yes (historical) | Exclude from deploy | DO NOT run on VPS |

## Tests, requirements, startup

- **Tests:** `tests/` (pytest.ini `testpaths=tests`); layout tests `test_windows_vps_deployment_layout.py`, `test_tearsheet_paths.py`
- **Requirements:** `requirements.txt` (repo root); uploader frontend has separate `package.json`
- **Startup:** Windows reboot `reboot_*.ps1` / `.bat` at repo root; Manager `tearsheet_fleet_runtime.json`; HomePage `debug.py` service map (external repo)

## Port verification (this audit session)

Loopback listeners on 8301–8304 were **not observed** at audit time on this host (may be stopped or running under different session). No restart or port changes were made during reorganization work.
