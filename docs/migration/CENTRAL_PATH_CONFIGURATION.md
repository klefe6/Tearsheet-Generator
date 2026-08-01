# Central Path Configuration

> Compatibility-preserving path resolution for laptop and future Windows VPS deployments.
> Implemented on `feature/central-path-config` from `live-main` @ `3cfda4f`.

## Status

- **Code and financial data have not been physically moved.**
- **The VPS has not been provisioned.**
- **Uploader production/sandbox separation remains unresolved.**
- **Current laptop defaults remain authoritative** when no overrides are set.

## Precedence

For each setting:

```text
non-empty environment variable
→ HC_APP_ENV profile default (when applicable)
→ current laptop compatibility default
```

Unset `HC_APP_ENV` defaults to **`local-production`**.

## Recognized environments

| `HC_APP_ENV` | Purpose |
|---|---|
| `local-dev` | Developer checkout; same path defaults as `local-production` |
| `local-production` | **Default** — current laptop fleet |
| `vps-sandbox` | Private Azure VM parity preparation |
| `vps-production` | Cutover target |

Invalid or explicitly empty `HC_APP_ENV` values raise `ValueError`.

## Root settings

| Key | Purpose |
|---|---|
| `HC_APP_ENV` | Environment profile selector |
| `HC_DEPLOY_ROOT` | Canonical deployment checkout root |
| `HC_DATA_ROOT` | General data root |
| `HC_PRODUCTION_DATA_ROOT` | Production mutable data root |
| `HC_SANDBOX_DATA_ROOT` | Sandbox mutable data root |
| `HC_LOG_ROOT` | Log root (ingest audit fallbacks) |
| `HC_CACHE_ROOT` | Cache root |
| `HC_BACKUP_ROOT` | Backup root |
| `HC_DIRTY_ROOT` | Main dirty checkout guard target (launchers) |

## Application settings (this lane)

| Key | Consumer | Laptop default |
|---|---|---|
| `HC_AGM_DATA_ROOT` | AGM derived paths | `{deploy_root}/Momentum Pacer` |
| `HC_YQ_DATA_ROOT` | Y&Q CSV when set | `C:\Coding Projects\Tearsheet Generator` |
| `HC_AGM_PINNED_CSV` | AGM TradeStation CSV | `{agm_root}/data/daily_balances/balances_210TGG51_20OCT2025_07JUL2026.csv` |
| `HC_AGM_BENCHMARK_CACHE_DIR` | AGM benchmark caches | `{agm_root}/data/benchmarks` |
| `HC_TCP_INGEST_AUDIT_PATH` | TCP ingest audit JSONL | `{deploy_root}/glenn_uploader_ingest_tcp_audit.jsonl` |
| `HC_AGM_INGEST_AUDIT_PATH` | AGM ingest audit JSONL | `{agm_root}/glenn_uploader_ingest_agm_audit.jsonl` |
| `YQ_CSV_PATH` | Y&Q monthly CSV (existing) | Highest precedence when set |

TCP state/workbook paths remain in `tcp_config.py` (`TCP_V2_*`).

## VPS profile defaults (not active until `HC_APP_ENV` is set)

| Setting | `vps-sandbox` / `vps-production` |
|---|---|
| Data root | `E:\H&C\data` |
| Log root | `E:\H&C\logs` |
| AGM data | `E:\H&C\data\agm` |
| Y&Q CSV | `E:\H&C\data\yq\yq.csv` |
| Ingest audits (when `HC_LOG_ROOT` set) | `E:\H&C\logs\ingest\` |

## Authoritative inputs (must already exist)

These paths are resolved but **never created** by the configuration module:

- AGM pinned TradeStation CSV
- Y&Q monthly CSV
- TKP/TCP/AGM financial state (deferred in this lane)
- Fee workbooks and protected-folder sources (deferred)

Missing configured authoritative inputs must fail clearly in application code — not silently fall back to fixtures.

## Directories that may be explicitly created

Use `tearsheet_paths.ensure_non_authoritative_directories()` only for:

- ingest audit log parent directories
- regenerable benchmark cache directories

Never call implicitly on import.

## Local development example

```powershell
# Optional — defaults match current laptop without any of these set
$env:HC_APP_ENV = "local-dev"
$env:HC_DEPLOY_ROOT = "C:\Coding Projects\Tearsheet Generator\.worktrees\live-deploy-main"
```

## Future VPS sandbox example

```powershell
$env:HC_APP_ENV = "vps-sandbox"
$env:HC_DEPLOY_ROOT = "E:\H&C\apps\tearsheets"
$env:HC_DATA_ROOT = "E:\H&C\data"
$env:HC_LOG_ROOT = "E:\H&C\logs"
$env:HC_AGM_PINNED_CSV = "E:\H&C\data\agm\data\daily_balances\balances_210TGG51_20OCT2025_07JUL2026.csv"
# Secrets via Key Vault-rendered env files — never commit tokens
```

## Future VPS production example

```powershell
$env:HC_APP_ENV = "vps-production"
$env:HC_PRODUCTION_DATA_ROOT = "E:\H&C\data"
$env:HC_SANDBOX_DATA_ROOT = "E:\H&C\data\sandbox"
$env:HC_TCP_INGEST_AUDIT_PATH = "E:\H&C\logs\ingest\glenn_uploader_ingest_tcp_audit.jsonl"
```

## Safe diagnostics

```python
from tearsheet_paths import load_tearsheet_paths, paths_identity_summary

summary = paths_identity_summary(load_tearsheet_paths())
# Contains resolved paths and app_env only — no secrets
```

## Rollback

1. Discard uncommitted changes in the isolated worktree, or `git revert` the path-config commit.
2. Restart affected apps via unchanged launchers (no change required if commit not deployed).
3. Production data was never moved; no data restore is needed for rollback.

## Module

- **Resolver:** `tearsheet_paths.py` (repo root)
- **Tests:** `tests/test_tearsheet_paths.py`
