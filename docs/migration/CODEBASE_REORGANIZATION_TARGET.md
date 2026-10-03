# Codebase reorganization — target design

## Goals

1. One obvious home per application on the VPS (`C:\H&C\apps\<app>`).
2. One shared module tree (`C:\H&C\apps\shared` + per-app copies or PYTHONPATH).
3. Zero live financial data in Git or under `apps\*\` source trees on VPS.
4. Secrets only under `C:\H&C\secrets\` (never committed).
5. Paths via `tearsheet_paths.load_tearsheet_paths()` and `HC_APP_ENV` profiles.
6. Same Git checkout on laptop and VPS; differences = env files only.
7. Frozen entrypoint **filenames** at repo root until shims prove stable.
8. Per-app JSON manifests under `deployment/windows-vps/manifests/`.
9. Scriptable deploy: `deploy-app.ps1` / `deploy-all.ps1` (dry-run default).

## Repository tree (GitHub)

```
Tearsheet-Generator/
├── apps/                          # Canonical names + README (incremental physical moves)
├── assets/                        # Dash CSS (stays at root until shims move)
├── deployment/
│   └── windows-vps/
│       ├── manifests/             # tkp.json, tcp.json, agm.json, yq.json, shared.json
│       ├── scripts/               # deploy-*, inventory, layout init/test
│       ├── config-templates/
│       └── REBUILD_FROM_GITHUB.md
├── docs/migration/                # Current state, target, governance
├── Momentum Pacer/              # AGM entrypoint (mp_ts.py) — bat contract
├── shared Python modules/         # tearsheet_*, tcp_* (repo root today)
├── tests/
├── uploader/
├── tkp_ts.py, tcp_ts_v2.py, yq_ts.py   # Frozen entrypoints + future shims
└── requirements.txt
```

Physical `git mv` into `apps/tkp/` etc. follows `docs/reorganization/file-classification.md` (root shims mandatory).

## VPS tree (`HC_APP_ENV=vps-production`)

```
C:\H&C\
├── apps\tkp|tcp|agm|yq|shared|uploader
├── data\tkp|tcp|agm|yq
├── config\*.env
├── secrets\*.env
├── logs\...
├── backups\...
└── deployment\                  # Copied from repo or second clone
```

Note: User brief used `C:\HC\`; this repo standardizes on **`C:\H&C\`** (ampersand) to match existing OVH documentation and `tearsheet_paths.VPS_ROOT`.

## Environment profiles

| `HC_APP_ENV` | Deploy root | Data root |
|--------------|-------------|-----------|
| `local-production` (default) | Repo / worktree checkout | Beside checkout (legacy) |
| `local-dev` | Repo checkout | Beside checkout / overrides |
| `vps-production` | `C:\H&C\apps\<app>` | `C:\H&C\data\...` |
| `vps-sandbox` | Same layout | `C:\H&C\data\sandbox\...` |

Override any root with `HC_DEPLOY_ROOT`, `HC_DATA_ROOT`, `HC_TKP_STATE_PATH`, etc.

## Deploy vs operations (must stay separate)

| Operation | Tooling |
|-----------|---------|
| Code deploy | `deploy-app.ps1 -ConfirmDeploy` |
| Data migration | Manual / encrypted copy to `C:\H&C\data` |
| Secrets | Manual files under `C:\H&C\secrets` |
| Service install/restart | NSSM — **not** invoked by deploy scripts |
| Public cutover | Cloudflare/DNS — out of scope |

## Compatibility (laptop production)

- `reboot_*.ps1` continue to run from `live-deploy-main`.
- Dirty root launchers forward or refuse (unchanged).
- No requirement to restart production for this reorganization branch to merge.
