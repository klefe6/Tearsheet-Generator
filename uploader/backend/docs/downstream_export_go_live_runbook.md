# Downstream Export — Go-Live Runbook

**Status:** Live (production downstream export enabled)  
**Go-live date:** 2026-07-11 (first real push: rows dated 2026-07-11)  
**Last verified:** 2026-07-11 — professional URL, health, idempotency, target state files

---

## URLs

| Role | URL |
|------|-----|
| **Professional uploader (authoritative)** | https://uploader.hcresearch.ltd |
| Sandbox uploader (same Fly app) | https://uploader-sandbox.hcresearch.ltd |
| TKP tearsheet | https://tkp-ts.hcresearch.ltd |
| TCP tearsheet | https://tcp-ts.hcresearch.ltd |
| AGM tearsheet | https://agm-ts.hcresearch.ltd |

Fly app: `glenn-uploader-sandbox` (region `iad`)

---

## Current production export flags (Fly secrets)

| Secret | Go-live value | Meaning |
|--------|---------------|---------|
| `EXPORT_DOWNSTREAM_ENABLED` | `true` | Downstream transport runs on Export All |
| `EXPORT_TARGET_ENV` | `production` | Push to live TKP/TCP/AGM ingest endpoints |
| `EXPORT_DRY_RUN` | **`false`** | **Real writes** — not a preview |
| `TKP_INGEST_URL` | `https://tkp-ts.hcresearch.ltd/api/uploader/ingest-daily-row` | |
| `TCP_INGEST_URL` | `https://tcp-ts.hcresearch.ltd/api/uploader/ingest-daily-row` | |
| `AGM_INGEST_URL` | `https://agm-ts.hcresearch.ltd/api/uploader/ingest-daily-row` | |
| `DOWNSTREAM_INGEST_TOKEN` | *(set on Fly; never commit or print)* | Bearer token for ingest routes |

`EXPORT_ENABLED` (original uploader-only preview layer) remains `false` — downstream export is a separate code path.

---

## What Glenn does daily

1. Open **https://uploader.hcresearch.ltd**
2. Enter daily values per program card; press **Save Daily Row** (or Enter) for each program.
3. Review the performance chart and last-seven-rows tables.
4. Click **Export All Changes** once.
5. Confirm the UI shows a **live export** result (not dry-run) and per-program status.

**Y&Q is always skipped** — there is no downstream ingest path for Y&Q. Rows can be saved in the uploader for chart/table display only; Export All never pushes Y&Q.

---

## First go-live push (2026-07-11) — reference

| Program | Date | Values pushed | Result |
|---------|------|---------------|--------|
| TKP | 2026-07-11 | StoneX NLV 108,000 · Plus500 NLV 86,000 · cash transfer 0 | `created` |
| TCP | 2026-07-11 | StoneX/cash balance 48,000 · cash transfer 0 | `created` |
| AGM | 2026-07-11 | TradeStation NLV 46,000 · cash transfer 0 · fee 0 | `created` |
| Y&Q | — | — | `skipped` |

- `external_calls_made=3`, `dry_run=false`
- Uploader rows marked `exported=true` only after downstream success
- Second Export All: `total_rows=0`, `external_calls_made=0`, idempotent (no duplicates)

---

## TCP restart caveat

**TKP** and **AGM** re-read state from disk on each page load — new rows appear after a browser refresh.

**TCP v2** builds its dashboard layout **once at process start**. An ingest write updates `tcp_daily_returns_secret_state.json` correctly, but the **public TCP page may not show the new row until TCP is restarted**.

After a successful TCP export, if the state file has the row but the public page does not:

1. Confirm the row in `tcp_daily_returns_secret_state.json` (AppData local state).
2. Restart TCP from the deploy worktree (port 8302).
3. Re-check https://tcp-ts.hcresearch.ltd/

See also: `downstream_export_contract.md` (read-side caveat section).

---

## Pre-flight checks (before enabling real export)

```powershell
cd uploader/backend
python scripts/verify_downstream_ingest.py --strict
```

Expect TKP/TCP/AGM ingest probes to return `accepted: true` with `dry_run: true`.

Confirm manual rows exist and are unexported:

```powershell
Invoke-RestMethod https://uploader.hcresearch.ltd/api/rows/tkp
Invoke-RestMethod https://uploader.hcresearch.ltd/api/rows/tcp
Invoke-RestMethod https://uploader.hcresearch.ltd/api/rows/agm
```

---

## Enabling real export

```powershell
fly secrets set EXPORT_DRY_RUN=false -a glenn-uploader-sandbox
```

Wait for Fly to restart the machine, then:

```powershell
Invoke-RestMethod https://uploader.hcresearch.ltd/health
```

Confirm `export_downstream_enabled: true`, `export_dry_run: false`, `export_target_env: production`.

Run **Export All once** through the UI or:

```powershell
# Requires ADMIN_API_TOKEN if configured; sandbox Fly app may allow open mutations
Invoke-RestMethod -Method POST https://uploader.hcresearch.ltd/api/export/all
```

---

## Rollback (immediate — use on any failure or partial failure)

**Step 1 — stop real writes immediately:**

```powershell
fly secrets set EXPORT_DRY_RUN=true -a glenn-uploader-sandbox
```

Wait for restart; confirm `/health` shows `export_dry_run: true`.

**Step 2 — assess damage:**

- Check `POST /api/export/all` response or audit log for per-program `success` / `failure`.
- Rows that failed downstream remain `exported=false` in the uploader (safe to retry after fix).
- Rows that succeeded are already in target state files — **do not delete or mutate target rows** without a separate reviewed procedure.

**Step 3 — verify targets (read-only):**

- TKP: `daily_returns_secret_state.json`
- TCP: `%LOCALAPPDATA%\HughesCompany\TCP\state\tcp_daily_returns_secret_state.json`
- AGM: `Momentum Pacer/momentum_pacer_manual_daily_rows.json`
- Ingest audit logs: `glenn_uploader_ingest_{tkp,tcp,agm}_audit.jsonl`

**Step 4 — communicate:**

- Report which programs succeeded vs failed.
- Leave `EXPORT_DRY_RUN=true` until root cause is fixed and preflight passes again.

To fully disable downstream transport (not just dry-run):

```powershell
fly secrets set EXPORT_DOWNSTREAM_ENABLED=false -a glenn-uploader-sandbox
```

---

## Safety rules (never violate in ops)

- Do **not** modify row values during export troubleshooting.
- Do **not** create fake rows to “test” production ingest.
- Do **not** export `historical_rows` or `display_rows` — only manual `daily_rows`.
- Do **not** touch Y&Q downstream (no path exists).
- Do **not** commit or print `DOWNSTREAM_INGEST_TOKEN` or production `.env` files.

---

## Health checks

```powershell
Invoke-RestMethod https://uploader.hcresearch.ltd/health
Invoke-WebRequest https://tkp-ts.hcresearch.ltd/ -UseBasicParsing
Invoke-WebRequest https://tcp-ts.hcresearch.ltd/ -UseBasicParsing
Invoke-WebRequest https://agm-ts.hcresearch.ltd/ -UseBasicParsing
```

---

## Related docs

- `downstream_export_contract.md` — per-program contract, idempotency, failure semantics
- `SANDBOX_HANDOFF.md` — sandbox-era handoff (pre-go-live; superseded for export behavior)
- `daily_update_workflow.md` — daily entry workflow
