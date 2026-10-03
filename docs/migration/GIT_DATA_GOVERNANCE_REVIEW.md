# Git data governance review

**Audit date:** 2026-10-03  
**Branch audited:** `refactor/github-vps-deployment-structure`  
**Rule:** Adding patterns to `.gitignore` does **not** remove already-tracked files.

## Already tracked — should probably not remain in Git

| Path | Classification | Risk | Recommended action |
|------|----------------|------|--------------------|
| `Momentum Pacer/data/daily_balances/balances_210TGG51_20OCT2025_07JUL2026.csv` | **F/E production data** | Account balance extract; client identifier in filename | Stop tracking after explicit approval; keep on disk only |
| `Momentum Pacer/data/benchmarks/GSPC_daily.csv` | **G cache / market data** | Low sensitivity but regenerable | Prefer download/cache on VPS; untrack when approved |
| `Momentum Pacer/data/benchmarks/NDX_daily.csv` | **G cache** | Same as GSPC | Same |

## Correctly gitignored but present on laptop production

| Pattern | Notes |
|---------|--------|
| `daily_returns_secret_state.json` | TKP financial state |
| `tcp_daily_returns_secret_state.json` | TCP state |
| `momentum_pacer_manual_daily_rows.json` | AGM manual rows |
| `yq.csv` / `*.xlsx` | Y&Q + workbooks |
| `.tcp_production.env`, `.tkp_production.env` | Launcher-loaded secrets/config |
| `glenn_uploader_ingest_*_audit.jsonl` | Ingest audit |

## Safe tracked fixtures

| Path | Classification |
|------|----------------|
| `tests/fixtures/tcp_golden_rows.json` | **I** synthetic test fixture |
| `docs/migration/*_MANIFEST.json` | **D** deployment metadata (no secrets) |

## Explicit flag: AGM balances CSV

The pinned balances file **`balances_210TGG51_20OCT2025_07JUL2026.csv`** is **still tracked** under `Momentum Pacer/data/daily_balances/`.
This violates the target rule that production account extracts must not ship via GitHub.

**Do not `git rm` or rewrite history without explicit approval.**

## Secrets in repository history

No new secret values were added in this reorganization branch. Populated `.env` files remain gitignored.
Review any historical commits separately if a full secret scrub is required (out of scope).
