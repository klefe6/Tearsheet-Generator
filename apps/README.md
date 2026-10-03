# Repository application layout (GitHub)

This folder documents the **canonical application names** used for GitHub → VPS deployment.
Laptop production still runs from the **repository root** and `.worktrees\live-deploy-main`
with frozen entrypoint filenames (`tkp_ts.py`, `tcp_ts_v2.py`, `yq_ts.py`, `Momentum Pacer\mp_ts.py`).

| App | Repo entrypoint (authoritative) | VPS target (`HC_APP_ENV=vps-production`) |
|-----|----------------------------------|------------------------------------------|
| tkp | `tkp_ts.py` | `C:\H&C\apps\tkp\tkp_ts.py` |
| tcp | `tcp_ts_v2.py` | `C:\H&C\apps\tcp\tcp_ts_v2.py` |
| agm | `Momentum Pacer\mp_ts.py` | `C:\H&C\apps\agm\Momentum Pacer\mp_ts.py` |
| yq | `yq_ts.py` | `C:\H&C\apps\yq\yq_ts.py` |
| shared | `tearsheet_paths.py` + gate modules | `C:\H&C\apps\shared\` |

Physical `git mv` into `apps/<name>/` is **incremental** (see `docs/reorganization/file-classification.md`).
Deployment scripts copy the manifest-listed sources without requiring production to restart.
