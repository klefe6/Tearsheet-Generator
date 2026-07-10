# Daily Update Workflow

## Current (manual, implemented)

1. Glenn opens the Glenn Daily Uploader frontend and enters the day's NLV /
   cash transfer / fee values for TKP, TCP, AGM, and Y&Q (`POST
   /api/rows/{program}` per Enter click — see `docs/downstream_export_contract.md`).
2. The performance chart and last-7-rows tables update immediately from
   `GET /api/performance` and `GET /api/rows/{program}`.
3. Glenn clicks **Export All Changes**. With `EXPORT_DOWNSTREAM_ENABLED=true`
   and `EXPORT_TARGET_ENV=sandbox`, this writes each unexported TKP/TCP/AGM
   row into this backend's own sandbox destination files
   (`data/downstream_sandbox/{program}_rows.json`); Y&Q is reported skipped.
   Every attempt is audited.
4. **Sandbox destinations do not yet feed the live TKP/TCP/AGM sites** — see
   "What's still needed for production" below. Today, step 3 proves the
   export contract and idempotency; it does not change any live page.

## What's still needed before TKP/TCP/AGM pages reflect real exports

This is the explicit, separately-scoped follow-up this contract hands off to
(see `docs/downstream_export_contract.md` → "Why no real endpoint exists yet"):

1. Add a real ingest path on each of TKP/TCP/AGM's own production source —
   either a new authenticated HTTP route, or a direct call into their
   existing hardened persistence function (`tcp_state.save_state` for TCP,
   analogous safe writers would need to be added for TKP/AGM, which
   currently write with no locking/atomicity at all — see the read-side
   caveat below for why this matters more for TCP).
2. Point this backend's `export_url_{tkp,tcp,agm}` / a new
   `EXPORT_TARGET_ENV=production` transport implementation at that path.
3. **TCP-specific blocker, confirmed by direct code inspection**: TCP v2
   builds its public Dash layout ONCE at process start; a row written into
   its state file while the process keeps running will NOT reach the live
   page until TCP is restarted. TKP and AGM re-read their state file on
   every page load, so writes DO surface without a restart for those two.
   Any daily-automation design must account for this TCP asymmetry — either
   accept a periodic TCP restart, or change TCP's own read path to poll its
   state (an app-side change, out of scope here).
4. Get sign-off to flip `EXPORT_TARGET_ENV=production` — an explicit,
   reviewed action gated by `EXPORT_DOWNSTREAM_ENABLED=true` AND a
   configured `DOWNSTREAM_API_TOKEN`. Even with both set, this build's
   `export_row_to_production()` always returns a `transport_not_implemented`
   failure — the transport code itself does not exist yet and would need to
   be written and reviewed as its own change, per program.

## Future: scheduled daily automation (documented, NOT built)

Once the manual flow above is trusted in production, a scheduled export
could remove the "click Export All Changes" step. This is **not implemented
in this pass** — deliberately, per the instruction not to add a production
scheduler without explicit approval. The design, for whenever it's approved:

- A cron-style job (e.g. Windows Task Scheduler or a small `scripts/`
  script) calls `POST /api/export/all` once daily, off-hours.
- Gated by its own flag, e.g. `EXPORT_SCHEDULE_ENABLED=false` by default —
  the job itself checks this and no-ops if unset, so merely having a
  scheduled task registered is not enough to cause an export.
- Every scheduled run produces the same audit trail as a manual click
  (batch id, per-program status, payload hashes) — nothing about automation
  changes the audit contract.
- Alerting: a failed or partial-failure scheduled run should page/notify
  (e.g. a webhook to whatever the team already uses for AGM/TCP incident
  alerts) rather than fail silently — not built yet, flagged as a
  requirement for whoever implements the scheduler.
- The scheduler must never be the mechanism that first enables
  `EXPORT_TARGET_ENV=production` — that flag flip is a separate, manual,
  reviewed action per the critical safety rules this contract was built
  under.
