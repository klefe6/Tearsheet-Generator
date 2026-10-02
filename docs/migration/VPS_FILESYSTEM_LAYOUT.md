# Windows VPS Filesystem Layout — `C:\HC\`

Canonical, provider-neutral filesystem contract for deploying the Hughes &
Company tearsheet system to a conventional Windows Server VPS (AWS Lightsail
Windows, OVHcloud Windows VPS, Azure Windows Server, or equivalent).

This document defines the **contract only**. This phase does **not** create,
populate, or move anything on the production machine. The tree is materialised
during the actual VPS build.

The layout is selected at runtime by `HC_APP_ENV=vps-production` (or
`vps-sandbox`) and resolved entirely by `tearsheet_paths.py`. With `HC_APP_ENV`
unset, every path resolves to its existing laptop location — production is
unchanged.

## Canonical tree

```text
C:\HC\
│
├── apps\                # Application source (code only — no authoritative state)
│   ├── tkp\
│   ├── tcp\
│   ├── agm\
│   ├── yq\
│   ├── dashboard\
│   └── shared\          # Shared modules / logos / static assets
│
├── data\                # Authoritative persistent state (BACK UP)
│   ├── tkp\             #   daily_returns_secret_state.json, tkp_source_workbook.xlsx
│   ├── tcp\             #   tcp_daily_returns_secret_state.json (+ .backup/.lock), tcp_alex.xlsx
│   ├── agm\             #   momentum_pacer_manual_daily_rows.json, Momentum Fee Calculation.xlsx, data\...
│   └── yq\              #   yq.csv (+ yq.xlsx source)
│
├── config\              # Non-secret runtime configuration
│
├── secrets\             # Secret material (admin tokens, session secrets) — NEVER in Git
│
├── logs\                # Append-only logs (regenerable)
│   ├── tkp\
│   ├── tcp\
│   ├── agm\
│   ├── yq\
│   ├── dashboard\
│   └── ingest\          #   glenn_uploader_ingest_*_audit.jsonl
│
├── backups\             # Point-in-time copies of data\ (BACK UP target)
│   ├── tkp\
│   ├── tcp\
│   ├── agm\
│   └── yq\
│
├── website\            # Static site / publishing artifacts
│
└── deployment\         # NSSM service definitions, Cloudflare Tunnel config, runbooks
```

### Why `C:\` and not a data disk (`E:\`)

`C:` is the one volume every conventional Windows Server VPS exposes by default.
AWS Lightsail Windows, OVHcloud, and Azure Windows Server do **not** all attach a
second data volume automatically. Anchoring the canonical contract on
`C:\HC\` is therefore the most provider-neutral choice and supersedes the
earlier `E:\H&C` draft from the TKP path lane.

Operators who *do* attach a dedicated data disk can point the data tree at it
without editing source, e.g. `HC_DATA_ROOT=E:\H&C\data` (and, if desired,
`HC_BACKUP_ROOT`, `HC_LOG_ROOT`). Application code never assumes the drive
letter.

## Top-level directory purpose, ownership, and backup

| Directory      | Owner program(s)        | Read/Write | Persistent? | Backup required |
|----------------|-------------------------|------------|-------------|-----------------|
| `apps\`        | deploy/CI               | read-only at runtime | No (redeployable from Git) | No |
| `data\tkp\`    | TKP                     | read/write | Yes (authoritative) | **Yes** |
| `data\tcp\`    | TCP                     | read/write | Yes (authoritative) | **Yes** |
| `data\agm\`    | AGM / Momentum Pacer    | read/write | Yes (authoritative) | **Yes** |
| `data\yq\`     | Y&Q                     | read/write | Yes (authoritative) | **Yes** |
| `config\`      | all                     | read-only at runtime | Yes | Yes (small) |
| `secrets\`     | all                     | read-only at runtime | Yes | Yes (secure) |
| `logs\`        | all                     | write (append) | No (regenerable) | Optional |
| `backups\`     | backup job              | write | Yes (derived) | Is the backup |
| `website\`     | publishing              | read/write | Yes | Optional |
| `deployment\`  | operator                | read-only at runtime | Yes | Yes |

## Persistent vs replaceable content

* **Persistent / authoritative (must be backed up):** everything under `data\`,
  plus `config\` and `secrets\`. Losing these loses real financial state.
* **Replaceable / regenerable:** everything under `apps\` (redeploy from Git),
  `logs\`, and benchmark/return caches under `data\<prog>\...\benchmarks`
  (re-fetched on demand).

## Separation of code and state

Application source lives under `apps\` and must **never** own authoritative
production state. All authoritative files live under `data\`. On the laptop the
two currently coincide inside the checkout; the VPS profile is what finally
separates them. See `VPS_ENVIRONMENT_VARIABLES.md` for the exact keys and
`VPS_DEPLOYMENT_MANIFEST.json` for the machine-readable mapping.
