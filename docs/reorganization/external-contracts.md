# External Contracts — What Must Not Break

Read-only audit, 2026-07-13. "External" = anything outside this repo that references a
path, port, route, or schema inside it. These are the invariants for the reorganization.

---

## 1. Contract matrix

| # | Consumer | Provider | Method | Exact path / URL / module | Payload / schema | Data written | Failure behavior | Migration requirement |
|---|---|---|---|---|---|---|---|---|
| C1 | Manager `launch_all_services.py` (via `service_config.py:189-195`) | TKP | spawn `cmd /k call <bat>`; health-check port | `C:\Coding Projects\Tearsheet Generator\reboot_tkp_ts.bat` | n/a | none | `.exists()` guard → silent "not found"; health timeout 120 s | **Bat path+name frozen.** Internals may change. |
| C2 | Manager (`service_config.py:196-201`) | TCP | same | `...\reboot_tcp_ts.bat` | n/a | none | as C1 | Bat frozen |
| C3 | Manager (`service_config.py:202-207`) | Y&Q | same | `...\reboot_yq_ts.bat` | n/a | none | as C1, timeout 90 s | Bat frozen |
| C4 | Manager (`service_config.py:208-213`) | AGM | same | `...\reboot_mp_ts.bat` | n/a | none | as C1 | Bat frozen |
| C5 | Manager (`service_config.py:184-188`, `:214-219`) | tsgen / Gold Maker | same | `...\run_tsgen.bat`, `...\reboot_gold_maker.bat` | n/a | none | as C1 | Bats frozen; `run_tsgen.bat` internally hardcodes absolute `tsgen.py` path |
| C6 | HomePage `debug.py` dashboard (SERVICE_BAT_FILES `:285-314`, SERVICE_PORTS `:317-346`) | all four + uploader + tsgen + Gold Maker | button-click spawn `cmd /s /k call <bat>` + kill-by-PID/port | same 6 bats + `...\reboot_glenn_uploader.bat` (`:313`) | n/a | PID files | button reports "not found" | Bats frozen |
| C7 | HomePage `debug.py:256` | AGM | folder reference (Open-folder / LOC metrics) | `...\Tearsheet Generator\Momentum Pacer` | n/a | none | stale link only (cosmetic) | Keep `Momentum Pacer\` dir, or coordinate a 1-line HomePage edit |
| C8 | HomePage `debug.py:278` | Uploader | folder reference | `...\Tearsheet Generator\uploader` | n/a | none | cosmetic | Keep `uploader\` dir |
| C9 | Windows logon | Manager | **Startup-folder** `HC Launch All Services.cmd` (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`, live 2026-07-13) → `startup_launch_all_services.ps1` → `launch_all_services.py` | `Manager\setup_autostart.bat` prefers Scheduled Task onlogon (`:18-24`) but falls back to Startup-folder `.cmd` (`:35-40`) when task creation fails | n/a | logs | Scheduled Task **not present** on live host (schtasks query failed) | No change needed; it reaches this repo only via C1-C5 |
| C10 | Cloudflare tunnel (`Manager\cloudflare_tunnel_config.yaml:56-90`) | all four | hostname→localhost:port | `tkp-ts→8301, tcp-ts→8302, yq-ts→8303, agm-ts→8304` (+tgm 8075, ts-generator 8077) | n/a | none | 502 on dead port | **Ports frozen** (8301/8302/8303/8304) |
| C11 | Browsers / clients | each app | HTTP routes | `/`, `/admin`, `/admin/login` (TCP), `/admin/logout`, `/healthz`, `/monthly`(404), Dash `/_dash-*` | Dash callbacks | app state | n/a | **Routes frozen** |
| C12 | Uploader frontend (only caller) | Uploader backend | HTTP | `/health`, `/api/programs`, `/api/performance`, `/api/rows/{program}` GET/POST, `/api/rows/{program}/last` DELETE, `/api/export/all`, `/api/audit` (`main.py`) | per-program fields from `programs.py:33-88` | uploader's own SQLite + `data/downstream_sandbox/*.json` | FastAPI 4xx/5xx | Uploader routes frozen; internal to `uploader/` |
| C13 | Staff operators | TKP/TCP/AGM staff instances | `reboot_tkp_staff.ps1` / `reboot_tcp_staff.ps1` / `reboot_mp_staff.ps1` → ports 8321/8322/8324, `TEARSHEET_MODE=staff` | repo-internal launchers; hostnames in `.staff.env:9` (`tkp-admin/tcp-admin/agm-admin.hcresearch.ltd`) | n/a | same state as prod (TCP staff edits real state, lock-protected) | n/a | Launcher names frozen (operator muscle-memory + tunnel), internals may change |
| C14 | TKP/TCP/AGM processes | env files | file read at launch | `.local_dev.env`, `.tkp_production.env`, `.tcp_production.env`, `.staff.env` at repo root (loaded by ps1 launchers) | `set "K=V"` lines | n/a | missing file silently skipped | **Root env-file locations frozen** |
| C15 | TCP process | Windows profile | state/benchmark override paths | `%LOCALAPPDATA%\HughesCompany\TCP\{state,benchmark}\...` (`.tcp_production.env:3-6`) | JSON | TCP state | fail-fast validation | Outside repo — unaffected by reorg |

## 2. Glenn Uploader ↔ tearsheets: integration status (canonical baseline)

**Baseline:** `origin/main` @ `6cbfc37` + `chore/uploader-professional-cors` +
`feature/uploader-export-rollback` (integrated on `chore/tearsheet-reorg-prep` @ `b76a2e4`,
tagged `pre-tearsheet-reorganization-2026-07` at `6cbfc37`).

Verdict per channel on the integrated prep branch:

- **HTTP ingest: PROVEN (merged).** `feature/glenn-uploader-downstream-export` (PR #38)
  added `tearsheet_uploader_ingest.py` and per-app ingest routes on TKP/TCP/AGM entrypoints.
  Uploader `downstream_export.py` POSTs to configured `tkp/tcp/agm_ingest_url`.
- **Rollback: PROVEN (integrated).** `feature/uploader-export-rollback` adds
  `uploader/backend/app/rollback.py` and `/api/export/rollback` saga.
- **Professional CORS + trading calendar: PROVEN (integrated).**
  `chore/uploader-professional-cors` allows `uploader.hcresearch.ltd` origin and
  `trading_calendar.py` for entry-date selection.
- **Y&Q:** always `skipped` (`NO_DESTINATION_PROGRAMS={"YQ"}`).
- **Deployment isolation:** Fly app `glenn-uploader-sandbox` (fly.toml); tearsheet repo
  is not in the Docker image.

**Frozen contracts after integration:**

- Ingest route: `POST /api/uploader/ingest-daily-row` (Bearer auth).
- Response schema: `{accepted,dry_run,program,date,action,before,after}`.
- Payload schema: TKP (`stonex_nlv` req, `plus500_nlv`+`cash_transfer` opt); TCP
  (`stonex_nlv` req, `cash_transfer` opt); AGM (`tradestation_nlv` req,
  `cash_transfer`+`fee` opt).
- Env names: `GLENN_UPLOADER_INGEST_{ENABLED,TOKEN,DRY_RUN_ALLOWED}`.
- Root modules: `tearsheet_uploader_ingest.py`, `tcp_uploader_ingest.py`.

## 3. Frozen-surface summary (the zero-breakage checklist)

1. Repo location `C:\Coding Projects\Tearsheet Generator` (hardcoded: `service_config.py:47`, `debug.py:243`).
2. Seven root launchers by exact name: `reboot_tkp_ts.bat`, `reboot_tcp_ts.bat`, `reboot_yq_ts.bat`, `reboot_mp_ts.bat`, `reboot_gold_maker.bat`, `run_tsgen.bat`, `reboot_glenn_uploader.bat` (+ staff ps1 trio by convention).
3. Ports 8301/8302/8303/8304 (+8321/8322/8324 staff, 8075, 8077, 5173, 8091).
4. Routes per app (C11) and uploader API (C12).
5. Subfolders `Momentum Pacer\` (debug.py:256) and `uploader\` (debug.py:278).
6. Root env files (C14) and TKP state JSON at repo root (`daily_returns_secret_state.json` — production data, path derived from `tkp_ts.py.__file__`).
7. Visible page behavior (calc outputs, tables, charts) — gated by regression plan.
