# Downstream Export Go-Live Runbook — Glenn Uploader → TKP / TCP / AGM

Operational procedure for the **first real** Glenn Uploader downstream push. This
document is tooling and process only — it does not enable production by itself.

**Preflight script:** `scripts/verify_downstream_ingest.py` (read-only dry-run probes).

---

## A. Current state

- **Export code is merged** (PR #38: downstream export; PR #39: TKP Plus500 display/backfill).
- **Glenn Uploader Export All** reads **manual `daily_rows` only** — backfilled
  `historical_rows` / `display_rows` are excluded from the export batch.
- **Y&Q** is always skipped with an explicit message; no downstream destination.
- **Export remains disabled by default** until `EXPORT_DOWNSTREAM_ENABLED=true` and
  related env vars are set on the uploader (Fly) and each target tearsheet app.
- **Sandbox file target** (`EXPORT_TARGET_ENV=sandbox`) writes only to this backend's
  `data/downstream_sandbox/` — not used for go-live.
- **Production target** (`EXPORT_TARGET_ENV=production`) POSTs to each app's
  `POST /api/uploader/ingest-daily-row` (`tearsheet_uploader_ingest.py`), with
  `dry_run:true` when `EXPORT_DRY_RUN=true`.

---

## B. Required target-side env vars

Set on **each** tearsheet app process (TKP, TCP v2, AGM) and **restart** that app
after changing env:

| Variable | Value |
|----------|--------|
| `GLENN_UPLOADER_INGEST_ENABLED` | `true` |
| `GLENN_UPLOADER_INGEST_TOKEN` | `<long random token>` (same value the uploader will send) |
| `GLENN_UPLOADER_INGEST_DRY_RUN_ALLOWED` | `true` (required for preflight and first dry-run export) |

Ingest is **inert by default** — deploying the code changes nothing until these
are set. Tokens are compared per request; wrong/missing token → HTTP 401.

---

## C. Required uploader-side env vars (Fly)

On the Glenn Uploader backend (e.g. sandbox first, then production when approved):

| Variable | First pass | Real push |
|----------|------------|-----------|
| `EXPORT_DOWNSTREAM_ENABLED` | `true` | `true` |
| `EXPORT_TARGET_ENV` | `production` | `production` |
| `EXPORT_DRY_RUN` | `true` | `false` |
| `TKP_INGEST_URL` | Full URL to TKP `.../api/uploader/ingest-daily-row` | same |
| `TCP_INGEST_URL` | Full URL to TCP `.../api/uploader/ingest-daily-row` | same |
| `AGM_INGEST_URL` | Full URL to AGM `.../api/uploader/ingest-daily-row` | same |
| `DOWNSTREAM_INGEST_TOKEN` | Same as each target's `GLENN_UPLOADER_INGEST_TOKEN` | same |

Missing `*_INGEST_URL` or token → that program **fails closed** with no HTTP call.

---

## D. Preflight procedure

1. **Restart** TKP, TCP, and AGM with target-side ingest env vars (section B).
2. From `uploader/backend/`, run:
   ```bash
   python scripts/verify_downstream_ingest.py
   ```
3. When all three must pass for go-live gating:
   ```bash
   python scripts/verify_downstream_ingest.py --strict
   ```

### Expected result before first push

| Program | Status |
|---------|--------|
| TKP | `dry_run_validated` |
| TCP | `dry_run_validated` |
| AGM | `dry_run_validated` |

Other statuses (`missing_url`, `missing_token`, `unreachable`, `unauthorized`,
`ingest_disabled`, `rejected_validation`) block go-live until resolved.

### Probe payload notes

- Probes always send **`dry_run: true`** — targets validate and classify
  (`created` / `updated` / `unchanged`) but **must not write** (framework contract
  in `tearsheet_uploader_ingest.py`).
- Default probe date: **`2099-01-01`** — strictly after live ledgers on append-only
  apps (TKP/TCP) and after latest AGM daily row for typical state. If a target
  rejects the date, re-run with `--probe-date YYYY-MM-DD` using a safe later date.
- **TCP field name:** probes use `stonex_nlv` (not `nlv`) — this is the ingest
  contract; it maps to TCP Cash Balance / NLV in `tcp_uploader_ingest.py`.
- Preflight **never** calls `/api/export/all` and **never** marks uploader rows
  exported.

### TKP reachability blocker

TCP and AGM may already have public hostnames. **TKP may not** be reachable from
Fly (e.g. only `localhost:8301` on an ops machine).

If TKP is `missing_url` or `unreachable` from Fly:

1. **Preferred:** Create a TKP **Cloudflare hostname / tunnel** so Fly can POST to
   `https://<tkp-host>/api/uploader/ingest-daily-row`.
2. **Alternative:** Run Glenn Export All from the **ops machine** (or a process on
   the same network as TKP) with uploader env pointing at reachable ingest URLs.
3. **Last resort (explicit approval only):** Temporarily **skip TKP** — leave
   `TKP_INGEST_URL` unset; only TCP/AGM export. Document the gap and backfill TKP
   manually or via a later push.

**Do not attempt a real push** until TKP reachability is solved or TKP skip is
explicitly approved.

---

## E. First dry-run export (uploader UI)

1. Keep `EXPORT_DRY_RUN=true` and `EXPORT_TARGET_ENV=production`.
2. Enter manual daily rows in Glenn Uploader for TKP/TCP/AGM (not historical backfill).
3. Click **Export All** once.

### Expected UI / behavior

- Badge: **Downstream Dry-Run Validated** (per program that accepted).
- **No target mutation** — downstream apps receive `dry_run: true`.
- Uploader rows **not** marked `exported`.
- External HTTP calls **may occur** (dry-run only).
- Y&Q: skipped, no calls.

---

## F. First real push

1. Set `EXPORT_DRY_RUN=false` only after preflight **and** UI dry-run export succeed.
2. Click **Export All** once.
3. Verify on each target:
   - **TKP:** StoneX NLV + Plus500 NLV received (NAV chain derived by TKP's own math).
   - **TCP:** Correct NLV via `stonex_nlv` → Cash Balance / `nav-x1` derivation.
   - **AGM:** TradeStation NLV and `fee` if present (fee only on AGM).
   - **Y&Q:** no push.
4. **Idempotency check:** Click Export All again with the same unexported-none state:
   - Uploader should report **no rows** / **no external calls** for already-exported dates.
   - Re-entering identical values on a new export should yield downstream **`unchanged`**, not duplicates (idempotency by `program:date`).

---

## G. Visibility caveats

| App | After push |
|-----|------------|
| **TKP** | Refreshes state from disk on page load — new row should appear on browser refresh if ingest URL was reachable. |
| **TCP** | State file updates immediately, but **TCP v2 layout is baked at process start** — **restart TCP** to see the new row on the public dashboard. |
| **AGM** | Manual rows update in admin path; **public AGM may remain CSV-driven** depending on current design. |

---

## H. Rollback

Rollback options when a push landed wrong values (rollback procedure):
- **Same-date re-export** with corrected values → downstream **update** (replace latest row), not duplicate.
- **Admin Delete Last Row** on the target app where applicable.
- Use per-app audit JSONL (`glenn_uploader_ingest_*_audit.jsonl`) and ingest
  response `before` / `after` fields to confirm what changed.

---

## I. Safety checklist

- [ ] Do **not** run target app admin edits at the same time as Glenn Export All.
- [ ] Prove **sandbox** dry-run and (if applicable) real-push on scratch fleet before production.
- [ ] Do **not** expose tokens in logs, screenshots, or chat — preflight prints token presence only.
- [ ] Confirm Export All exports **manual `daily_rows` only** (not historical backfill).
- [ ] Do **not** set `EXPORT_DRY_RUN=false` until `verify_downstream_ingest.py --strict` passes for every in-scope program.
- [ ] Resolve or explicitly approve **TKP reachability** before first production push from Fly.

---

## Quick reference — status codes from preflight

| Status | Meaning |
|--------|---------|
| `missing_url` | `*_INGEST_URL` not set on uploader |
| `missing_token` | `DOWNSTREAM_INGEST_TOKEN` not set |
| `unreachable` | Network / DNS / connection failure |
| `unauthorized` | HTTP 401 — token mismatch |
| `ingest_disabled` | HTTP 403 — ingest not enabled on target |
| `dry_run_validated` | HTTP 200, `accepted: true`, `dry_run: true` |
| `rejected_validation` | HTTP 422 or business-rule rejection |
| `unexpected_error` | Other failure |
