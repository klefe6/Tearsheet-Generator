# Downstream Export Contract — TKP / TCP / AGM

Status: **design + sandbox implementation only**. No production downstream call
exists yet, and none is enabled by default. This document is the contract that
`app/downstream_export.py` implements against SANDBOX destinations; it is also
the spec a future, separately-reviewed change would use to build a REAL
production ingest path on the TKP/TCP/AGM side.

## Read-side caveat — confirmed by direct code inspection (2026-07-10)

Whether a downstream write would even be *visible* on the live site differs
per app, independent of this contract:

- **TKP**: re-reads its state JSON on every request (`_load_fresh_secret_records`
  is called from `dynamic_layout()`, which the docstring says runs "on every
  page load"). A new row written externally would appear on next browser
  refresh — no TKP process restart needed.
- **AGM**: same — `_render_agm_daily_admin_controls_callback` reloads the
  manual-rows JSON fresh from disk on every callback fire (page/session load).
  No restart needed.
- **TCP v2**: does **NOT** behave this way. `create_app()` loads state and
  builds `app.layout` **once at process start**; the public dashboard is
  driven by a `dcc.Store` baked into that static layout, not a per-request
  disk read. An externally-written row would sit in TCP's state file
  correctly, but **would not appear on the live page until TCP's own process
  is restarted** — even once a real production ingest path exists. This is a
  hard constraint on any future "daily update, no restart" design for TCP
  specifically; it is not something this contract can work around from the
  outside. (Production TCP is confirmed already running with
  `TCP_V2_STATE_MODE=json_active`, i.e. real persistence — the historical
  `seed_tcp_state.py` script is the one existing precedent for writing into
  that state safely, by calling the same hardened `save_state()` all admin
  writes use, rather than a raw file overwrite.)

## Why no real endpoint exists yet

TKP (`tkp_ts.py`), TCP v2 (`tcp_ts_v2.py`), and AGM (`Momentum Pacer/mp_ts.py`)
are live production Dash/Flask apps. None of them currently expose a
standalone HTTP ingest route an external process can POST to — their only
"write" path today is an in-app Dash admin callback that mutates a local
JSON state file, triggered by a human clicking Add Row inside the running app
itself. Building a real ingest endpoint on any of them is a production
app-source change requiring its own review and a restart to take effect —
both out of scope for this pass. See `docs/downstream_sandbox_notes.md` for
per-app specifics gathered while designing this contract.

Until that follow-up lands, this backend's "downstream sandbox destination"
is a set of clearly-labeled **sandbox data files inside this backend's own
`data/` directory** (never inside the TKP/TCP/AGM app trees, never their real
state files) — pattern **#3 (shared data file)** from the preferred list,
scoped entirely to infrastructure this backend owns. A program's live site
never reads these files today; that consumption wiring is the explicit
follow-up this contract hands off to.

## Common envelope

Every export attempt (per program, per date) produces one record:

```json
{
  "batch_id": 42,
  "ts": "2026-07-10T00:00:00+00:00",
  "target_env": "sandbox",
  "program": "TKP",
  "date": "2026-07-09",
  "payload_hash": "sha256:...",
  "status": "success",
  "downstream_response": { "action": "created" },
  "idempotency_key": "TKP:2026-07-09"
}
```

- **Idempotency key**: `"{program}:{date}"`, always. Re-exporting the same
  key is an **upsert** (create-or-update), never a duplicate — the sandbox
  writer and the audit log both key on this string.
- **Date format**: ISO 8601 `YYYY-MM-DD`, matching the uploader backend's own
  `daily_rows.date`.
- **Number format**: plain JSON numbers (floats), no currency symbols, no
  thousands separators — matching `validate_row`'s normalized output.
- **payload_hash**: `sha256` of the canonical (sorted-keys) JSON payload sent,
  so two audit rows can be compared to see if a re-export actually changed
  anything.

## Per-program contract

### TKP

| | |
|---|---|
| Program code | `TKP` |
| Required fields | `date`, `stonex_nlv`, `plus500_nlv` |
| Optional fields | `cash_transfer` (default `0`) |
| Sandbox target | `uploader/backend/data/downstream_sandbox/tkp_rows.json` |
| Production target | **Not configured.** Would be either a new authenticated ingest route added to `tkp_ts.py`, or a direct (locked, atomic) write to `daily_returns_secret_state.json` beside it — decision deferred to the follow-up PR that touches TKP's own source. |
| Auth (sandbox) | None — matches this backend's own sandbox-relaxed philosophy. |
| Auth (production) | Required token (e.g. `Authorization: Bearer <token>`), config-driven, never defaulted on. |
| Idempotency key | `TKP:{date}` |
| Success response | `{"status": "success", "program": "TKP", "date": ..., "action": "created"\|"updated"}` |
| Failure response | `{"status": "failure", "program": "TKP", "date": ..., "error_code": ..., "error_message": ...}` |
| Rollback / retry | No rollback needed — sandbox write is an atomic upsert (temp file + `os.replace`). On failure the uploader row stays `exported=false`; safe to retry the whole batch or just this row later. |

### TCP

| | |
|---|---|
| Program code | `TCP` |
| Required fields | `date`, `stonex_nlv` |
| Optional fields | `cash_transfer` (default `0`) |
| Sandbox target | `uploader/backend/data/downstream_sandbox/tcp_rows.json` |
| Production target | **Not configured.** Note: production TCP v2 only persists its OWN admin edits when its `TCP_V2_STATE_MODE=json_active`; if it's running in the default `workbook` mode, admin writes there are simulation-only today regardless of this contract — a real production path must account for that mode, not assume `json_active`. |
| Auth (sandbox) | None. |
| Auth (production) | Required token, config-driven. |
| Idempotency key | `TCP:{date}` |
| Success / failure response | Same shape as TKP. |
| Rollback / retry | Same as TKP. |

### AGM

| | |
|---|---|
| Program code | `AGM` |
| Required fields | `date`, `tradestation_nlv` |
| Optional fields | `cash_transfer` (default `0`), `fee` (default `0`) |
| Sandbox target | `uploader/backend/data/downstream_sandbox/agm_rows.json` |
| Production target | **Not configured.** AGM's own fee-engine treats `fee` as a documented exclusion from performance (see `algominds_daily_fees.py` / `performance.py` in the uploader backend) — this contract passes `fee` through faithfully but does not assert how AGM's production accounting should interpret it; that's for AGM's own app-side follow-up to decide. |
| Auth (sandbox) | None. |
| Auth (production) | Required token, config-driven. |
| Idempotency key | `AGM:{date}` |
| Success / failure response | Same shape as TKP. |
| Rollback / retry | Same as TKP. |

### Y&Q — excluded

Y&Q has no downstream destination configured (`yq_ts.py` has no write path of
any kind today — it's a read-only tearsheet). Every export batch includes Y&Q
in its per-program status as:

```json
{ "program": "YQ", "status": "skipped", "reason": "destination not configured" }
```

This is never reported as a failure. Y&Q rows remain fully visible/editable
in the Glenn Uploader and continue to appear in `/api/performance` and
`/api/rows/YQ` — only the downstream push is skipped.

## Feature flags (all default to the safest value)

| Flag | Default | Meaning |
|---|---|---|
| `EXPORT_ENABLED` | `false` | Master switch for the ORIGINAL uploader-only export preview (pre-existing). Unrelated to downstream transport being implemented — kept as-is. |
| `EXPORT_DOWNSTREAM_ENABLED` | `false` | Master switch for this new downstream-export feature. When `false`, `/api/export/all` behaves exactly as before (uploader-only dry-run preview) — this contract's code path is never entered. |
| `EXPORT_DRY_RUN` | `true` | When downstream export is enabled, still don't write anywhere — just compute and report what WOULD be sent. |
| `EXPORT_TARGET_ENV` | `sandbox` | `sandbox` or `production`. `production` requires `EXPORT_DOWNSTREAM_ENABLED=true` AND a configured production auth token for every non-skipped program — otherwise the export fails closed (never silently falls back to sandbox, never silently no-ops as success). |
| `EXPORT_INCLUDE_YQ` | `false` | Even if somehow set `true`, YQ has no destination configured, so it is always reported `skipped` regardless of this flag. Flag exists for forward-compatibility once a Y&Q destination exists. |

## Failure semantics

- Downstream export is evaluated **per row** (program, date). One program's
  failure never blocks another program's export in the same batch — the
  batch result reports each program's status independently (`success`,
  `failure`, or `skipped`).
- A row is marked `exported=true` in the uploader's own `daily_rows` table
  **only after** its downstream write succeeds. A failed or skipped row
  keeps `exported=false`, so the next `POST /api/export/all` naturally
  retries it (it's still in `get_unexported_rows()`).
- Every attempt (success, failure, or skip) writes one audit record — nothing
  is silently dropped.
