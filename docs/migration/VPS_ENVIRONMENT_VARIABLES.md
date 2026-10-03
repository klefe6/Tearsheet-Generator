# Windows VPS Environment Variables

Every environment variable relevant to VPS path portability and service
configuration. **No secret values appear in this document.**

Precedence for every path key:

```text
explicit HC_* / app-specific env override   (highest)
        ↓
HC_APP_ENV profile default (local-* or vps-*)
        ↓
current laptop-compatible default            (lowest)
```

With `HC_APP_ENV` unset and no `HC_*` overrides set, every key resolves to the
exact path used on the laptop today.

## Profile selector

| Environment key | Purpose | Laptop default | VPS value | Secret? | Required? |
|---|---|---|---|---|---|
| `HC_APP_ENV` | Selects layout profile | unset → `local-production` | `vps-production` (or `vps-sandbox`) | No | Yes on VPS |

Valid values: `local-dev`, `local-production`, `vps-sandbox`, `vps-production`.

## Layout roots (resolved by `tearsheet_paths.py`)

| Environment key | Purpose | Laptop default | VPS resolution | Secret? | Required? |
|---|---|---|---|---|---|
| `HC_DEPLOY_ROOT` | App code root anchor | module parent (checkout) | `C:\HC\apps\<app>` (per service) | No | No |
| `HC_APPS_ROOT` | Application-code root | checkout | `C:\HC\apps` | No | No |
| `HC_DATA_ROOT` | Authoritative data root | checkout | `C:\HC\data` | No | No |
| `HC_PRODUCTION_DATA_ROOT` | Production data root | checkout | `C:\HC\data` | No | No |
| `HC_SANDBOX_DATA_ROOT` | Sandbox data root | checkout | `C:\HC\data\sandbox` | No | No |
| `HC_CONFIG_ROOT` | Non-secret config root | checkout | `C:\HC\config` | No | No |
| `HC_SECRETS_ROOT` | Secret material root | checkout | `C:\HC\secrets` | No | No |
| `HC_LOG_ROOT` | Log root | checkout | `C:\HC\logs` | No | No |
| `HC_CACHE_ROOT` | Regenerable cache root | checkout | `C:\HC\data` | No | No |
| `HC_BACKUP_ROOT` | Backup root | checkout | `C:\HC\backups` | No | No |
| `HC_WEBSITE_ROOT` | Static website root | checkout | `C:\HC\website` | No | No |

## Per-program data roots

| Environment key | Purpose | Laptop default | VPS resolution | Secret? | Required? |
|---|---|---|---|---|---|
| `HC_TKP_DATA_ROOT` | TKP data root | checkout | `C:\HC\data\tkp` | No | No |
| `HC_TCP_DATA_ROOT` | TCP state root | checkout | `C:\HC\data\tcp` | No | No |
| `HC_AGM_DATA_ROOT` | AGM data root | `Momentum Pacer\` | `C:\HC\data\agm` | No | No |
| `HC_YQ_DATA_ROOT` | Y&Q data root | repo root | `C:\HC\data\yq` | No | No |

## Per-file overrides (authoritative inputs / state)

| Environment key | Purpose | Laptop default | VPS resolution | Secret? | Required? |
|---|---|---|---|---|---|
| `HC_TKP_STATE_PATH` | TKP daily-returns state JSON | `<checkout>\daily_returns_secret_state.json` | `C:\HC\data\tkp\daily_returns_secret_state.json` | No | No |
| `HC_TKP_SOURCE_WORKBOOK` | TKP source workbook | protected-folder xlsx (verbatim) | `C:\HC\data\tkp\tkp_source_workbook.xlsx` | No | No |
| `HC_AGM_MANUAL_STATE_PATH` | AGM manual daily-rows JSON | `Momentum Pacer\momentum_pacer_manual_daily_rows.json` | `C:\HC\data\agm\momentum_pacer_manual_daily_rows.json` | No | No |
| `HC_AGM_FEE_WORKBOOK` | AGM fee workbook | `Momentum Pacer\Momentum Fee Calculation.xlsx` | `C:\HC\data\agm\Momentum Fee Calculation.xlsx` | No | No |
| `HC_AGM_PINNED_CSV` | AGM pinned balances CSV | `Momentum Pacer\data\daily_balances\...csv` | `C:\HC\data\agm\data\daily_balances\...csv` | No | No |
| `HC_AGM_BENCHMARK_CACHE_DIR` | AGM benchmark cache dir | `Momentum Pacer\data\benchmarks` | `C:\HC\data\agm\data\benchmarks` | No | No |
| `HC_TCP_INGEST_AUDIT_PATH` | TCP ingest audit JSONL | `<checkout>\glenn_uploader_ingest_tcp_audit.jsonl` | `C:\HC\logs\ingest\glenn_uploader_ingest_tcp_audit.jsonl` | No | No |
| `HC_AGM_INGEST_AUDIT_PATH` | AGM ingest audit JSONL | `Momentum Pacer\glenn_uploader_ingest_agm_audit.jsonl` | `C:\HC\logs\ingest\glenn_uploader_ingest_agm_audit.jsonl` | No | No |
| `YQ_CSV_PATH` | Y&Q CSV (highest precedence) | sibling/repo `yq.csv` | `C:\HC\data\yq\yq.csv` | No | No |
| `HC_DIRTY_ROOT` | Launcher guard + Y&Q CSV default anchor | `C:\Coding Projects\Tearsheet Generator` | (n/a on VPS) | No | No |

## App-specific (TCP) — existing overrides, still honoured

TCP has its own robust override mechanism; on the VPS the `HC_TCP_DATA_ROOT`
profile now supplies the default base directory, so these need only be set to
override individual files.

| Environment key | Purpose | Laptop default | VPS value | Secret? | Required? |
|---|---|---|---|---|---|
| `TCP_V2_WORKBOOK_PATH` | TCP source workbook | protected-folder `tcp_alex.xlsx` | `C:\HC\data\tcp\tcp_alex.xlsx` | No | Recommended |
| `TCP_V2_STATE_PATH` | TCP active state JSON | `<base>\tcp_daily_returns_secret_state.json` | under `C:\HC\data\tcp\` (default) | No | No |
| `TCP_V2_STATE_BACKUP_PATH` | TCP backup JSON | `<base>\...backup.json` | under `C:\HC\data\tcp\` | No | No |
| `TCP_V2_STATE_LOCK_PATH` | TCP lock file | `<base>\...lock` | under `C:\HC\data\tcp\` | No | No |
| `TCP_V2_STATE_MODE` | `workbook` / `json_active` | `workbook` | as configured | No | No |
| `TCP_V2_BENCHMARK_CACHE_PATH` | TCP benchmark cache | `<checkout>\_runtime\...` | `C:\HC\data\tcp\_runtime\...` (if set) | No | No |
| `TCP_V2_BIND_PORT` | TCP bind port | `8302` prod | `8302` | No | No |
| `TCP_V2_ADMIN_TOKEN` | TCP staff admin password | shared local default | set per environment | **Yes** | Yes (staff) |
| `TCP_V2_SESSION_SECRET` | TCP Flask session signing key | local default | set per environment | **Yes** | Yes (staff) |

## Runtime mode / ports

| Environment key | Purpose | Laptop default | VPS value | Secret? | Required? |
|---|---|---|---|---|---|
| `TEARSHEET_MODE` | `legacy`/`public`/`staff`/`portal` | unset → `legacy` | `public` (public sites), `staff` (staff ports) | No | No |
| `TKP_BIND_PORT` | TKP bind port | `8301` (public) / `8321` (staff) | same | No | No |
| `AGM_BIND_PORT` | AGM bind port | `8304` (public) / `8324` (staff) | same | No | No |

## Secrets policy

* Secret **values** are never committed to Git and never appear in these docs
  or in `paths_identity_summary()` diagnostics (which expose directory paths
  only).
* On the VPS, secret material belongs under `C:\HC\secrets\` and/or is injected
  as process environment by the NSSM service definition — not baked into source.
