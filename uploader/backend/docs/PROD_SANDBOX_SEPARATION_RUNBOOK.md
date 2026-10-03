# Glenn Uploader production/sandbox separation runbook

Status: design only. No Fly, DNS, database, certificate, secret, export, or
deployment mutation is authorized by this document.

## Current state captured 2026-07-30

- `uploader-sandbox.hcresearch.ltd`, `uploader.hcresearch.ltd`, and
  `glenn-uploader-sandbox.fly.dev` resolve to the same Fly addresses:
  `66.241.124.107` and `2a09:8280:1::147:9ad8:0`.
- Both custom hostnames have issued certificates on `glenn-uploader-sandbox`.
- One started Fly machine (version 35, region `iad`) serves both hostnames.
- One encrypted 1 GB volume, `uploader_data`, is mounted at `/data`.
- The app config identifies `APP_ENV=sandbox` and
  `DATABASE_PATH=/data/uploader_sandbox.db`.
- Fly secret names include `AGM_INGEST_URL`, `TCP_INGEST_URL`,
  `TKP_INGEST_URL`, `DOWNSTREAM_INGEST_TOKEN`,
  `EXPORT_DOWNSTREAM_ENABLED`, `EXPORT_DRY_RUN`, and
  `EXPORT_TARGET_ENV`. Secret values were not read or recorded.
- The public `/health` response on both hostnames currently identifies
  `app_env=sandbox`, target `production`, and live downstream writes enabled.
  Secret overrides therefore take precedence over the safe values shown by
  `fly config show`.
- Until a business-approved migration completes, the existing
  `/data/uploader_sandbox.db` on `glenn-uploader-sandbox` is the authoritative
  uploader database. Do not infer that the production hostname represents an
  isolated production datastore.

## Target topology

Keep two independently deployable Fly apps:

### `glenn-uploader-sandbox`

- Hostname: `uploader-sandbox.hcresearch.ltd`
- Dedicated volume: `uploader_sandbox_data`
- Database: `/data/uploader_sandbox.db`
- `APP_ENV=sandbox`
- Frontend build: `VITE_APP_ENV=sandbox`, same-origin API
- Sandbox-only CORS origin plus explicit local development origins
- `EXPORT_DOWNSTREAM_ENABLED=false`
- `EXPORT_DRY_RUN=true`
- `EXPORT_ENABLED=false`
- No production ingest URLs or production ingest token

The sandbox must remain preview-only. Its health response must report
`real_writes_enabled=false` and `export_mode=disabled` or `dry_run`.

### `glenn-uploader-prod`

- Hostname: `uploader.hcresearch.ltd`
- Dedicated volume: `uploader_prod_data`
- Database: `/data/uploader_prod.db`
- `APP_ENV=production`
- Frontend build: `VITE_APP_ENV=production`, same-origin API
- Production hostname only in CORS
- Independent admin and downstream ingest secrets
- Export flags set only after ingest dry-run verification and approval

No volume, SQLite file, machine, application secret, or frontend build artifact
may be shared between the two apps.

## Required isolation controls

1. Create new volumes rather than attaching or cloning the current volume in
   place.
2. Use distinct secret sets. Copying a secret must be an explicit operator
   action; never export secret values into this repository or an audit log.
3. Build each frontend with its matching environment label.
4. Restrict CORS to the matching public hostname. Local origins belong only in
   local or sandbox configuration.
5. Keep sandbox downstream exports disabled and dry-run enforced.
6. Require production authentication for every mutation and rollback route.
7. Verify `/health` configuration before permitting any row entry or export.

## Migration design

The business owner must first choose one of these sources of truth:

- Preserve all rows currently in the shared database as the production seed;
  or
- Keep the existing database as sandbox history and import an independently
  approved production dataset.

For the first option:

1. Put the existing uploader into a short, announced write freeze.
2. Take a Fly volume snapshot and an application-consistent SQLite backup.
3. Record source database hash, row counts by program, export batch counts,
   maximum row IDs, and maximum row date per program.
4. Restore a copy into the new production volume; never move the original.
5. Deduplicate using immutable source row IDs when available. Otherwise use a
   reviewed compound key of program, business date, NLV fields, cash transfer,
   fee, correction state, and source batch.
6. Preserve correction/audit ancestry and exported status. Do not mark an
   unexported row exported merely because an equivalent downstream value
   exists.
7. Reject ambiguous duplicates for manual review rather than selecting one.
8. Recompute and compare program row counts, latest values, performance
   series, export batches, correction links, and audit entries.

Expected write freeze: 15–30 minutes for backup, restore, validation, and DNS
cutover. If validation cannot finish in that window, abort the cutover and
resume the existing app.

## Staged implementation and verification

1. Provision `glenn-uploader-prod`, its volume, machine, and secrets without a
   public custom hostname.
2. Deploy the same reviewed image to both apps with environment-specific
   configuration.
3. Verify production through its temporary `fly.dev` hostname:
   - correct environment banner;
   - isolated empty or migrated database;
   - authentication required;
   - four expected programs;
   - row and audit counts match the approved migration manifest;
   - export disabled first, then production-target dry-run only;
   - no external writes during validation.
4. Remove `uploader.hcresearch.ltd` from the sandbox app only during the
   approved cutover window.
5. Add the hostname/certificate to `glenn-uploader-prod`, update DNS if
   required, and wait for TLS and health checks.
6. Verify the production hostname reaches the production app and the sandbox
   hostname still reaches the sandbox app.
7. Enable real production export only under a separate explicit approval,
   after dry-run classifications and duplicate handling are accepted.

## Rollback

If health, TLS, authentication, migration invariants, or downstream dry-run
checks fail:

1. Keep real export disabled.
2. Remove or stop routing the production hostname to the new app.
3. Restore the previous hostname/certificate association and DNS records.
4. Resume the original shared app and database from the pre-cutover state.
5. Do not merge data written independently after the freeze without a new
   deduplication review.
6. Preserve failed migration artifacts for diagnosis, excluding secrets.

## Approval gate

Stop here. Before any remote action, obtain written approval for:

- the authoritative migration source;
- the maintenance window;
- creation and cost of the new Fly app/volume/IP;
- secret provisioning;
- database copy and deduplication policy;
- certificate/DNS cutover;
- rollback authority; and
- the separate decision to enable real downstream exports.

This runbook does not authorize those actions.
