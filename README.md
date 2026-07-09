# Tearsheets

Dash/Plotly web tearsheets and tools for the firm's trading programs. This repo hosts
**multiple related production apps** that share modules and a single stylesheet — see
[`docs/REPO_MAP.md`](docs/REPO_MAP.md) for the full map (entrypoints, launchers,
ports, shared modules, state files, and refactor risk notes) before changing layout,
imports, or launchers.

## Apps

| Program | Entrypoint | Port | Launcher |
|---|---|---|---|
| TKP | `tkp_ts.py` | 8301 | `reboot_tkp_ts.bat` |
| TCP v2 (current) | `tcp_ts_v2.py` | 8302 prod / 8312 preview | `reboot_tcp_ts.bat` → `reboot_tcp_ts.ps1` / `reboot_tcp_ts_v2.bat` |
| TCP v1 (legacy, rollback only) | `tcp_ts.py` | 8302 | — |
| AGM / Momentum Pacer | `Momentum Pacer/mp_ts.py` | 8304 | `reboot_mp_ts.bat` |
| Y&Q | `yq_ts.py` | 8303 | `reboot_yq_ts.bat` |
| tsgen | `tsgen.py` | 8077 | `run_tsgen.bat` |
| Gold Maker | `Gold_Maker_ts.py` | 8075 | `reboot_gold_maker.bat` |

Launcher filenames and ports are load-bearing (external orchestration references
them) — do not rename or repurpose them casually.

## Setup

1. Python 3.10 virtualenv at `.venv310` (the TKP/TCP/Gold Maker launchers use it;
   the AGM and Y&Q launchers use the `python` on PATH, and `run_tsgen*.bat`
   hardcodes the system Python — see the repo map's launcher table):
   ```
   pip install -r requirements.txt
   ```
2. Run an app via its launcher (from the repo root), e.g.:
   ```
   reboot_tkp_ts.bat
   ```

Several apps depend on gitignored, machine-local data files (workbooks, CSV state,
`.env` credential files) — a fresh clone will not fully reproduce production
behavior. See `docs/REPO_MAP.md` §5.

## Tests

Run from the repo root, per-file (not the whole directory in one process — see
`docs/REPO_MAP.md` §6):

```
.venv310\Scripts\python.exe -m pytest tests/test_tcp_foundation.py -q
```

Fleet-wide boot check (imports every app in an isolated subprocess; no servers
started, missing machine-local data reported as SKIP):

```
.venv310\Scripts\python.exe scripts\smoke_all.py
```

## Other contents

- `assets/` — shared stylesheet served by every app
- `docs/` — repo map, TCP contracts/acceptance docs, Algominds v2 contracts
- `scripts/` — acceptance, audit, and state-seeding tooling
- `tv_vadi_convert.py`, `spx_data_test.py`, `make_csv.py`, etc. — one-off utilities
  (not services)
