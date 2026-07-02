# TCP Admin Simulation (Step 8)

Validated: 2026-07-02  
Branch: `feature/tcp-v2-migration`

## Authorization architecture

```text
TCP_V2_ADMIN_TOKEN (environment)
        ↓
server-side constant-time comparison (hmac.compare_digest)
        ↓
Flask signed session stores tcp_v2_admin_authenticated=true
        ↓
Dash layout/callbacks read session server-side only
```

Routes:

- `GET/POST /admin/login` — HTML form, server-validated token
- `GET/POST /admin/logout` — clears session, redirects to `/`

Hidden client stores do **not** grant access. The optional `e`/admin link only navigates to the login route.

## Required environment variables

| Variable | Purpose |
| -------- | ------- |
| `TCP_V2_ADMIN_TOKEN` | Preview admin token (never commit) |
| `TCP_V2_SESSION_SECRET` | Flask session signing secret (never commit) |

When either is missing:

- `admin_auth: not_configured` on `/healthz`
- Login is rejected with a generic message

## Modes

| Mode | Who | Behavior |
| ---- | --- | -------- |
| `public` | Everyone | Read-only workbook-backed dashboard |
| `admin_simulation` | Authenticated admin | Full ledger + simulation modals |

Banner text:

```text
TCP v2 Admin — Simulation Only
No changes will be saved
```

## Ledger table

- Source: `tcp_ledger.load_ledger()` completed records (112 rows)
- Columns: full TCP calculator/state shape (`REQUIRED_HEADERS`)
- Pagination: native, 15 rows/page
- Sorting: native
- Editing: disabled
- Latest row highlighted
- Column visibility checklist filters displayed columns

## Add Row input contract

Manual fields only:

- `Date`
- `Cash Balance`
- `Cash Transfers`
- `#` tranche count

Defaults:

- Cash Transfers = 0
- Tranche count copied from latest row (not inferred from deposit size)

Withdrawals:

- Negative transfers raise controlled `UnsupportedWithdrawal` messaging
- No withdrawal calculation is invented

Calculation preview:

1. Read latest completed workbook row
2. Call `compute_tcp_row()`
3. Display proposed inputs/outputs
4. Label: `Simulation only — not saved`
5. Confirm button: `Calculation Verified` (does not save)

## Delete preview

- Shows actual final completed row
- Shows resulting prior latest date/NAV and dashboard label preview
- Confirmation message: `Deletion simulation complete — no data was changed`
- No rows removed from memory, workbook, or canonical store

## Export

Disabled button:

```text
Export will be enabled after state activation
```

## Non-persistence guarantees

Step 8 does **not**:

- call `save_state`
- create active/backup/lock files
- write Excel
- append/delete ledger rows
- mutate `canonical-nav-store`
- refresh dashboard outputs from proposed rows

## Remains disabled

- Active JSON state
- Real Add Row save
- Real Delete Row
- JSON as authoritative data source
- Production port 8302 changes

## Security limitations before production

- Preview-only secrets via environment variables
- No rate limiting on login route in Step 8
- No audit log persistence
- Single shared admin token model
- Session cookie security depends on `TCP_V2_SESSION_SECRET` strength

## Next activation phase

Activate TCP JSON through an explicit one-time seed and connect authenticated Add/Delete actions to atomic state mutations, while retaining workbook fallback and rollback controls.
