# Production Restart Safety Checklist

Print-and-tick companion to `docs/production_checkout_alignment_runbook.md`
(section references point there). Use one copy per app per restart. **If any
box cannot be ticked, stop — see the runbook's stop conditions.**

App: ________  Port: ________  Date/time: ________  Operator: ________

## 1. Preflight (read-only — no service impact)

- [ ] `python scripts\audit_live_tearsheet_processes.py` run; output attached.
      Exit code recorded: ____ (must be 0 before a restart; non-zero only
      acceptable while executing the alignment runbook itself)
- [ ] All PIDs on this port inventoried (PID / start time / interpreter /
      command line / elevated?) — Runbook A2
- [ ] Duplicates on this port: none, or each one explained and slated for
      termination in step 3 — A3
- [ ] Serving PID identified (ESTABLISHED-row check) — A4
- [ ] Root checkout branch = `main`, clean (`git status --porcelain` empty),
      SHA recorded: ____________ — B1/B3, Phase E
- [ ] `git fetch origin` done; `HEAD..origin/main` count = 0 (checkout is
      current) — B1
- [ ] `tearsheet_runtime_mode.py`, `scripts\smoke_all.py`, `pytest.ini`
      present — B4
- [ ] Env file for this app exists with expected variable names (names only —
      never print values) — C1; n/a for Y&Q/tsgen
- [ ] Canonical launcher confirmed to source the env file — C2
      (TKP: `reboot_tkp_ts.ps1` · TCP: `reboot_tcp_ts.bat`→`.ps1` ·
      AGM: `reboot_mp_ts.bat` [elevated] · Y&Q: `reboot_yq_ts.bat` ·
      tsgen: `run_tsgen.bat`)
- [ ] Default-token exposure checked (C3) — gate login with the source default
      FAILS (or app has no gate)
- [ ] Interpreter decision recorded per C4 policy: ______________________
- [ ] `.venv310\Scripts\python.exe scripts\smoke_all.py` → all PASS (when the
      venv is the chosen interpreter)

## 2. Backups (copy-only — no service impact)

- [ ] Dated backup folder created outside the repo: ____________________ — D
- [ ] This app's state files copied and verified non-empty
      (TKP: `daily_returns_secret_state.json` [+ `.bak`] ·
      AGM: manual-rows JSON + `Momentum Pacer\data` + fee workbook ·
      TCP: state dir resolved from env [do not print values] ·
      Y&Q/tsgen: n/a — no writable state)
- [ ] Rollback reference saved in the backup folder: pre-restart SHA, process
      table, `/healthz` output (TCP), layout fingerprint

## 3. Restart (approval required — operator action)

- [ ] Explicit approval to restart THIS app recorded: ________________
- [ ] Pre-capture done: current PIDs, `/_dash-layout` fingerprint,
      `/healthz` (TCP) — F1
- [ ] ALL instances on the port stopped (elevated console if any PID is
      elevated); `netstat` shows no LISTENING rows on the port — F2
- [ ] Relaunched via the canonical launcher only — F3
- [ ] No other app restarted concurrently

## 4. Verify (immediately after)

- [ ] Exactly ONE new PID LISTENING (plus reloader child only where
      `debug=True` applies); start time = now; expected interpreter — F4
- [ ] HTTP 200 on `/`
- [ ] TCP only: `/healthz` fields match pre-capture except intended changes;
      `state_revision` sane; `debug: false`; `port: 8302`
- [ ] Layout fingerprint: expected new-build marker present, stale markers
      absent (normalize `/` → `/` before substring checks)
- [ ] AGM only: `assets/styles.css` loads (gate CSS not 404)
- [ ] External URL answers (TCP: `https://tcp-ts.hcresearch.ltd` ·
      AGM: `https://agm-ts.hcresearch.ltd`)
- [ ] Browser hard-refresh + re-authenticate done before judging admin UI
      (stale-DOM gotcha)
- [ ] `smoke_all.py` re-run → all PASS
- [ ] App-specific tests green (run specific files, never whole `tests/`;
      set `TMP`/`TEMP` writable first):
      TKP `test_tkp_password_gate.py` · TCP `test_tcp_v2_shell.py`
      (known-red baseline: `test_tcp_foundation.py` = 9 on ops machine) ·
      AGM `test_agm_password_gate.py` + `test_agm_daily_fees.py` ·
      Y&Q `test_yq_smoke.py`
- [ ] Default-token login still FAILS post-restart (TKP/TCP/AGM)

## 5. Sign-off / rollback

- [ ] Result: ☐ VERIFIED — record new PID + SHA, proceed to next app
             ☐ FAILED — rollback executed per runbook (stop new process,
               `git checkout <recorded SHA>`, restore this app's state from
               backup, relaunch, re-verify), fleet state recorded, work
               STOPPED pending investigation
- [ ] Fleet log updated: which SHA each live app now serves

Notes: ________________________________________________________________
