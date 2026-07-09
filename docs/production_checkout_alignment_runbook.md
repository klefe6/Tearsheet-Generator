# Production Checkout Alignment Runbook (PR 0)

**Purpose.** The live tearsheet fleet (TKP 8301, TCP v2 8302, Y&Q 8303, AGM 8304,
tsgen 8077) runs whatever code the **production root checkout**
(`C:\Coding Projects\Tearsheet Generator`) contained when each process started.
The 2026-07-09 audit found the fleet serving three different stale code vintages,
duplicate processes on two ports, and one uncommitted local edit in production.
This runbook is the repeatable procedure to (A) inventory reality, (B) establish
checkout truth, (C) verify env/auth without exposing secrets, (D) back up state,
(E) align the checkout, and (F) restart one app at a time with verification and
rollback. **Run it before any sandbox/production hardening work and before every
future planned restart.**

**Read-only until Phase E.** Phases A–D change nothing. Phases E–F change the
checkout and restart services and require explicit operator approval. Nothing in
this runbook modifies production state/data/env files (Phase D only *copies*
state files to backups).

**Companion documents.**

- `docs/production_restart_safety_checklist.md` — the per-restart checkbox list.
- `scripts/audit_live_tearsheet_processes.py` — read-only preflight (Phase A/B
  automated; exits non-zero on the blocking conditions).
- `docs/tcp_production_cutover_runbook.md` / `docs/tcp_production_rollback_runbook.md`
  — TCP-specific procedures; TCP steps below defer to them where they overlap.
- `docs/REPO_MAP.md` §5 — the authoritative state-file map.

**Findings as of 2026-07-09** (embedded for context — always re-verify; do not
assume this table is still true):

| Port | App | Live PIDs | Started | Interpreter | Elevated | Code vintage served |
|---|---|---|---|---|---|---|
| 8301 | TKP | **35252 + 65564 (duplicate)** | 07-08 08:41 / 16:00 | ? / `C:\Python310` | yes / no | `feature/tearsheet-gate-ui-consistency` era |
| 8302 | TCP v2 | **3876 + 67796 (duplicate)** | 07-08 15:11 / 16:39 | ? / `C:\Python310` | yes / no | mixed: gate-ui era / `copy/agm…` @ `6ff8b06` |
| 8303 | Y&Q | 38008 | 07-06 21:44 | `C:\Python313` | no | `integration/tcp-v2-final-acceptance` era |
| 8304 | AGM | 45184 | 07-08 20:25 | ? | yes | `6ff8b06` **+ uncommitted 2-line `mp_ts.py` edit** |
| 8077 | tsgen | 38800 | 07-06 21:44 | `C:\Python310` (hardcoded) | no | root code via absolute path |

Root checkout: `copy/agm-profile-section-copy` @ `6ff8b06`, dirty
(`Momentum Pacer/mp_ts.py`, `tests/test_agm_password_gate.py`), **14 commits
behind** `origin/main` @ `b6c0173`. `tearsheet_runtime_mode.py` (PR #19),
`scripts/smoke_all.py` and `pytest.ini` (PR #22) are **absent** from that
checkout. Visible TKP/TCP processes were launched with bare system Python, i.e.
**not** via the `.ps1` launchers that source the production env files.

---

## Phase A — Read-only live-process inventory

### A1. Automated preflight

```powershell
cd "C:\Coding Projects\Tearsheet Generator"
python scripts\audit_live_tearsheet_processes.py
```

Non-zero exit = at least one blocking condition (duplicate listeners, dirty
tracked files, missing env file, missing `tearsheet_runtime_mode.py`). The
script prints no secrets and modifies nothing. (Until the checkout is aligned,
the script is *expected* to fail — that is the point: it must pass before any
restart.)

### A2. Manual inventory (also the source of truth if the script is unavailable)

Listeners on the production ports:

```powershell
netstat -ano | findstr "LISTENING" | findstr ":8301 :8302 :8303 :8304 :8077 :8075"
```

Process details for every PID found (repeat the filter for each PID):

```powershell
Get-CimInstance Win32_Process -Filter "ProcessId=<PID>" |
  Select-Object ProcessId, CreationDate, ExecutablePath, CommandLine | Format-List
```

Record per PID: **port, PID, command line, interpreter path, start time**, and
elevation. **Empty `ExecutablePath`/`CommandLine` from a non-elevated shell means
the process is elevated** — inspect it from an elevated PowerShell instead.
Windows does not expose another process's `cwd` cheaply; infer it from the
command line + launcher conventions (every launcher `cd`s to the repo root, or
`Momentum Pacer\` for AGM) and confirm from an elevated session with
`(Get-Process -Id <PID>).Path` plus handle inspection only if needed.

Expected app per port: 8301 `tkp_ts.py`, 8302 `tcp_ts_v2.py`, 8303 `yq_ts.py`,
8304 `mp_ts.py`, 8077 `tsgen.py`, 8075 `Gold_Maker_ts.py` (normally *not*
running). **Any PID that cannot be mapped to a specific app/port/command is a
stop condition.**

### A3. Duplicate-process detection

More than one unique PID LISTENING on the same production port = duplicate
(Werkzeug sets `SO_REUSEADDR`, so on Windows a second instance binds
successfully and traffic distribution becomes non-deterministic). A
`debug=True` app (TKP, Y&Q) legitimately shows a reloader parent+child — those
share a start time within seconds and identical command lines. **Two PIDs with
start times hours apart or mixed elevation are two independent instances**:
treat as a stop condition until each one's origin is understood.

### A4. Which process is actually serving traffic?

While issuing a request, watch which PID holds the ESTABLISHED connection:

```powershell
Start-Job { Invoke-WebRequest -Uri http://127.0.0.1:<port>/ -UseBasicParsing | Out-Null }
netstat -ano | findstr ":<port>" | findstr "ESTABLISHED"
```

The PID on the ESTABLISHED rows answered that request. Repeat several times —
with duplicates present, different PIDs may answer different requests.

To fingerprint the *code vintage* being served (works for all Dash apps):

```powershell
curl.exe -s http://127.0.0.1:<port>/_dash-layout -o layout.json
```

Search the JSON for **build-distinguishing data** (a dollar figure, a note
string added by a specific commit) — not labels or calendar dates, which appear
in every build. Dash JSON-escapes `/` as `/`; normalize before substring
checks. For TCP, `curl.exe -s http://127.0.0.1:8302/healthz` reports
`app`, `port`, `debug`, `state_mode`, and `state_revision` directly.

---

## Phase B — Checkout truth

All commands run in `C:\Coding Projects\Tearsheet Generator`.

### B1. Current branch/SHA and distance from main

```powershell
git branch --show-current
git rev-parse --short HEAD
git fetch origin                 # read-only; updates refs only
git rev-list --count HEAD..origin/main   # commits main has that the checkout lacks
git log --oneline HEAD..origin/main      # what they are
```

### B2. Runtime-relevant diff vs main

```powershell
git diff --stat HEAD origin/main -- tkp_ts.py tcp_ts_v2.py "Momentum Pacer/mp_ts.py" yq_ts.py tsgen.py Gold_Maker_ts.py tearsheet_*.py tcp_*.py algominds_*.py
```

Read the actual diffs for anything listed. **If any commit on
`HEAD..origin/main` contains a behavior change that was not explicitly reviewed
and approved for production, STOP** — resolve with the team before aligning.
(As of 2026-07-09 the pending behavior changes are intended fixes: PR #17 AGM
wording, PR #18 AGM monthly-stats derivation, PR #19 adds `/monthly`→404 to
TKP/TCP. Re-derive this list every time.)

### B3. Uncommitted production edits

```powershell
git status --porcelain
```

- ` M` / `M ` / `D ` etc. on **tracked** files = uncommitted production edits.
  **Stop condition** — identify the owner (another working session may own the
  edit; on 2026-07-09 the `mp_ts.py` edit belonged to a concurrent Claude
  session). The owner lands or reverts it; do not stash someone else's work.
- `??` untracked files: harmless *unless* the same path exists on `origin/main`
  (then `git checkout main` will refuse). Detect and compare:

```powershell
git status --porcelain | Where-Object { $_ -match '^\?\?' } | ForEach-Object {
  $f = $_.Substring(3).Trim('"')
  git cat-file -e "origin/main:$f" 2>$null
  if ($LASTEXITCODE -eq 0) {
    $local = git hash-object "$f"; $main = git rev-parse "origin/main:$f"
    if ($local -eq $main) { "IDENTICAL (safe to delete): $f" } else { "DIFFERS (STOP - unmerged local work): $f" }
  }
}
```

Only delete untracked files reported IDENTICAL. **DIFFERS = stop condition.**

### B4. Runtime-mode module presence

```powershell
Test-Path .\tearsheet_runtime_mode.py     # must be True after alignment
Test-Path .\scripts\smoke_all.py          # ditto (PR #22)
Test-Path .\pytest.ini                    # ditto
```

If `False` before alignment, that confirms the checkout predates PR #19/#22 —
expected pre-alignment, blocking post-alignment.

---

## Phase C — Env & auth verification (never print secret values)

### C1. Env files exist (existence + variable NAMES only)

```powershell
Get-Item .tkp_production.env, .tcp_production.env | Select-Object Name, Length
Select-String -Path .tkp_production.env -Pattern '^set "([A-Za-z0-9_]+)=' | ForEach-Object { $_.Matches[0].Groups[1].Value }
Select-String -Path .tcp_production.env -Pattern '^set "([A-Za-z0-9_]+)=' | ForEach-Object { $_.Matches[0].Groups[1].Value }
```

Expected names — TKP: `TKP_ADMIN_TOKEN`, `TKP_SESSION_SECRET`. TCP:
`TCP_V2_STATE_MODE`, `TCP_V2_BIND_PORT`, `TCP_V2_STATE_PATH`,
`TCP_V2_STATE_BACKUP_PATH`, `TCP_V2_STATE_LOCK_PATH`,
`TCP_V2_BENCHMARK_CACHE_PATH`, `TCP_V2_ADMIN_TOKEN`, `TCP_V2_SESSION_SECRET`.
Missing file or missing name = **stop condition**. Never `cat` these files.

### C2. Launchers source the env files

```powershell
Select-String -Path reboot_tkp_ts.ps1, reboot_tcp_ts.ps1 -Pattern 'production\.env'
```

Both `.ps1` launchers must parse their env file before starting Python. The
`.bat` variants (`reboot_tkp_ts.bat`, `reboot_tcp_ts_v2.bat`) do **not** source
env files — for production restarts of TKP and TCP, **only the `.ps1` path (or
`reboot_tcp_ts.bat`, which shims to the `.ps1`) is canonical.** AGM's
`reboot_mp_ts.bat` sets `MP_TS_PRODUCTION=1` only (no tokens — AGM currently
falls back to source defaults by design; scheduled for the later auth-hardening
PR, not fixed here). Y&Q has no env at all.

### C3. Detect a live app running on the default admin token (no token printed)

Background: `tcp_admin.py` ships a hardcoded fallback constant
(`DEFAULT_SIBLING_ADMIN_TOKEN`) used by TKP/TCP/AGM whenever `*_ADMIN_TOKEN` is
unset. If a production process was started without its env file, its gate
accepts that source-code default.

Operator check (manual, uses the value from source without writing it anywhere):

1. Read the constant's value from `tcp_admin.py` locally. Do not paste it into
   docs, chat, tickets, or shell history (in the browser only).
2. Open the app's gate (reveal the login via the hidden trigger), and attempt a
   login with that default value.
3. **If login succeeds, the app is on the default token — stop condition**:
   plan an expedited restart via the canonical `.ps1` launcher (which sources
   the real token) and treat the app's admin surface as exposed until then.
4. A failed login attempt has no side effects.

Heuristic without probing: if the live PID's interpreter is not
`.venv310\Scripts\python.exe` and its parent chain shows no `.ps1` wrapper, the
env file was almost certainly not sourced (this is exactly the 2026-07-09 TKP
finding).

### C4. Interpreter policy — one variable at a time

Live processes currently run on **system** Python (`C:\Python310`,
`C:\Python313`), while the `.ps1` launchers specify `.venv310`. Changing code
*and* interpreter in one restart confounds any regression. Policy:

- Before restarting via `.ps1`, prove `.venv310` can serve the fleet:
  `.venv310\Scripts\python.exe scripts\smoke_all.py` (imports every app in a
  subprocess with that interpreter). If smoke passes, the venv is safe and the
  `.ps1` launchers are the canonical path (they also fix env sourcing).
- If smoke fails on the venv, restart with the same interpreter the app used
  before (record it in Phase A) and treat venv standardization as a separate,
  later change.

---

## Phase D — State snapshots before ANY restart (copy only)

Back up to a dated folder **outside the repo**. Copy — never move, never edit.

```powershell
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$dest = "C:\ProdBackups\tearsheets\$stamp"
New-Item -ItemType Directory -Force $dest | Out-Null
cd "C:\Coding Projects\Tearsheet Generator"

# TKP admin state (repo root)
Copy-Item daily_returns_secret_state.json      "$dest\" -ErrorAction Stop
Copy-Item daily_returns_secret_state.json.bak* "$dest\" -ErrorAction SilentlyContinue

# AGM manual rows + data (Momentum Pacer)
Copy-Item "Momentum Pacer\momentum_pacer_manual_daily_rows.json" "$dest\" -ErrorAction Stop
Copy-Item "Momentum Pacer\data" "$dest\agm_data" -Recurse -ErrorAction Stop
Copy-Item "Momentum Pacer\Momentum Fee Calculation.xlsx" "$dest\" -ErrorAction Stop

# TCP v2 production state: resolve the directory from .tcp_production.env
# WITHOUT printing values (extract the path vars only, locally):
$tcpState = (Select-String -Path .tcp_production.env -Pattern '^set "TCP_V2_STATE_PATH=(.+)"$').Matches[0].Groups[1].Value
Copy-Item (Split-Path $tcpState) "$dest\tcp_state" -Recurse -ErrorAction Stop

# Verify — every backup must exist and be non-empty:
Get-ChildItem $dest -Recurse -File | Select-Object FullName, Length
```

**Any missing or zero-byte backup = stop condition.** Also record (text file in
`$dest`): current branch + SHA, the Phase A process table, and TCP's
`/healthz` output — this is the rollback reference.

---

## Phase E — Align the production checkout (approval required)

Prerequisites (every one must hold — see stop conditions):

1. Phase B3 shows **zero modified tracked files** (owners have landed/reverted
   their edits — coordinate, don't force).
2. Every untracked collision file is verified IDENTICAL and removed (B3).
3. Phase B2 review complete: main contains only reviewed changes.
4. Phase D backups verified.

Then:

```powershell
git checkout main
git pull --ff-only origin main
git rev-parse --short HEAD        # record: this is the aligned production SHA
python scripts\audit_live_tearsheet_processes.py   # env/module/dirty checks must now pass
```

**The production root checkout on `main` is henceforth the single source of
truth for production code.** Rules going forward: production never runs from a
feature branch or a dirty tree; all feature work happens in `.worktrees/`
(never checkout branches in the root); the root only moves by `git pull
--ff-only origin main` immediately before a planned restart.

Note: aligning the checkout changes **nothing** about running processes — they
keep serving their loaded code until restarted (Phase F).

---

## Phase F — Controlled restart, one app at a time (approval required per app)

Order (rationale): **Y&Q first** (read-only app, no state writes — safest
canary), then **TKP** (highest-value fix: default-token + duplicate), then
**TCP v2** (best verification tooling; external tunnel `tcp-ts.hcresearch.ltd`),
then **AGM** (elevated; requires the concurrent session's edit landed; external
tunnel `agm-ts.hcresearch.ltd`), then **tsgen** (optional). Complete each app's
verification before starting the next. Never restart two apps at once.

Per app — use `docs/production_restart_safety_checklist.md` as the checkbox
version:

1. **Pre-capture**: current PIDs on the port, `/_dash-layout` fingerprint (and
   `/healthz` for TCP), screenshot if useful.
2. **Stop ALL instances on the port** (this is where duplicates are removed).
   From an **elevated** PowerShell when any instance is elevated:
   `taskkill /PID <pid> /F` for each PID. Confirm the port is free:
   `netstat -ano | findstr :<port>` → no LISTENING rows.
3. **Relaunch via the canonical launcher**:
   - TKP: `reboot_tkp_ts.ps1` (sources `.tkp_production.env`)
   - TCP: `reboot_tcp_ts.bat` (shims to `reboot_tcp_ts.ps1`)
   - Y&Q: `reboot_yq_ts.bat`
   - AGM: `reboot_mp_ts.bat` from an elevated console (needs
     `MP_TS_PRODUCTION=1`, which it sets)
   - tsgen: `run_tsgen.bat`
4. **Verify immediately**:
   - exactly ONE new PID LISTENING on the port (plus reloader child only where
     `debug=True` still applies), start time = now, expected interpreter;
   - HTTP 200 on `/` (all apps); TCP `/healthz` fields match pre-capture except
     intended differences; layout fingerprint shows the expected new-build
     marker and none of the stale markers;
   - AGM only: gate CSS loads (mp_ts must pass the repo-root `assets_folder` —
     a 404 on `assets/styles.css` means a launch-directory problem);
   - external URLs after TCP/AGM restarts: `https://tcp-ts.hcresearch.ltd`,
     `https://agm-ts.hcresearch.ltd` still answer (tunnel config lives outside
     this repo and should need no change).
5. **Browser caveat**: an already-open authenticated tab keeps stale DOM after
   a restart (old admin controls, modals that no-op). Hard-refresh (F5) and
   re-authenticate before judging the new build.

### Post-restart smoke (after each app, and once more after the last)

```powershell
.venv310\Scripts\python.exe scripts\smoke_all.py
```

plus targeted pytest for the app just restarted (run specific files from the
repo root, never the whole `tests/` directory in one process; set `TMP`/`TEMP`
to a writable dir first):

- TKP: `tests\test_tkp_password_gate.py`
- TCP: `tests\test_tcp_v2_shell.py` (baseline: `test_tcp_foundation.py` has
  **9 known-red failures on the ops machine** — only failures beyond those are
  real)
- AGM: `tests\test_agm_password_gate.py`, `tests\test_agm_daily_fees.py`
- Y&Q: `tests\test_yq_smoke.py`

### Rollback (per app, if verification fails)

1. Stop the new process (`taskkill /PID <pid> /F`, elevated if needed).
2. Return the checkout to the recorded pre-alignment SHA:
   `git checkout <recorded-SHA>` (detached HEAD is fine for an emergency serve).
3. Restore that app's state files from the Phase D backup (copy back only the
   affected app's files; TCP: follow `docs/tcp_production_rollback_runbook.md`).
4. Relaunch via the same launcher; verify with step 4 above against the
   pre-capture fingerprint.
5. Leave the fleet in a **consistent, recorded** state (which SHA each app
   serves) and stop — do not continue restarting other apps until the failure
   is understood.

---

## Stop conditions — halt immediately, escalate, change nothing further

1. Duplicate processes still present on any production port and not fully
   explained (owner, launch time, code vintage all understood).
2. Root checkout dirty with **tracked app-file edits** (someone's uncommitted
   work — find the owner; never stash/discard someone else's edits).
3. An untracked file that collides with `origin/main` **differs** from main's
   copy (unmerged local work).
4. Production env file missing, or missing an expected variable name, or a
   launcher no longer sources it.
5. Default admin token detected on any live gate (C3) — expedite that app's
   restart; do not proceed with unrelated steps first.
6. `smoke_all.py` fails, or targeted tests fail beyond the documented
   known-red baseline (`test_tcp_foundation.py` = 9 on the ops machine).
7. Any listening process cannot be mapped to a specific app/port/command line.
8. Any Phase D backup missing, zero-byte, or unverifiable.
9. Any commit on `HEAD..origin/main` contains a behavior change that was not
   explicitly reviewed for production (B2).
10. Elevated access unavailable when an elevated process must be stopped.
11. Post-restart verification mismatch (health/fingerprint/CSS) — execute the
    rollback for that app, then stop.
12. The audit script exits non-zero at a point where the runbook says it must
    pass.

## Expected end state

| Check | Target |
|---|---|
| Listeners | exactly one process per port (plus reloader child only where debug still applies) |
| Checkout | root on `main`, clean, SHA recorded, `tearsheet_runtime_mode.py` present |
| Env | both `.env` files present; TKP/TCP relaunched via `.ps1`, real tokens active (default-token login fails) |
| Interpreters | per Phase C4 policy, recorded per app |
| Smoke | `smoke_all.py` PASS ×6; targeted tests green minus known-red baseline |
| External URLs | `tcp-ts` / `agm-ts` `.hcresearch.ltd` answering |
| Backups | dated snapshot retained with pre-alignment SHA + process table |

Only after this end state is reached does the sandbox/production hardening
track (TEARSHEET_ENV foundation, PR 1+) begin.
