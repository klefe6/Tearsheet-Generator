# Staff/Admin Ports (8321 / 8322 / 8324)

Dedicated password-free admin instances of the three tearsheets, separate from
the public client ports. Public protection comes from **Cloudflare Access on
dedicated admin hostnames**, not from the in-app password.

## Port / hostname map

| App | Client port | Client hostname            | Staff port | Admin hostname (proposed)     |
|-----|-------------|----------------------------|------------|-------------------------------|
| TKP | 8301        | (none yet)                 | **8321**   | `tkp-admin.hcresearch.ltd`    |
| TCP | 8302        | `tcp-ts.hcresearch.ltd`    | **8322**   | `tcp-admin.hcresearch.ltd`    |
| AGM | 8304        | `agm-ts.hcresearch.ltd`    | **8324**   | `agm-admin.hcresearch.ltd`    |

Convention: tens digit = mode (0 public, 1 preview, 2 staff, 3 portal); last
digit = strategy (1 TKP / 2 TCP / 4 AGM). 8401+ belongs to other projects
(TWIFO) — do not use.

## How a staff instance behaves

Launched with `TEARSHEET_MODE=staff` (see `reboot_*_staff.ps1`):

- Binds **127.0.0.1 only**, on the staff port (launcher forces the port after
  env-file imports; `TKP_BIND_PORT` / `TCP_V2_BIND_PORT` / `AGM_BIND_PORT`
  would otherwise still win over the staff default).
- Every route (`/`, `/admin/tearsheet`, …) renders the **admin tearsheet
  directly** — no disclaimer gate, no in-app password
  (`tearsheet_local_admin.is_staff_direct_admin_request`).
- Request guards, all must pass (fail → normal client gate renders):
  1. `TEARSHEET_MODE=staff` in the process env (never set by client/production
     launchers),
  2. loopback peer address,
  3. Host header loopback **or** listed in `TEARSHEET_STAFF_ALLOWED_HOSTS`
     (comma-separated; set in machine-local `.staff.env`, template
     `.staff.env.example`). A *client* hostname accidentally pointed at a
     staff port is therefore denied.
- Werkzeug debugger is off in staff mode (TKP runs `debug=is_legacy()`; AGM
  staff launcher sets `MP_TS_PRODUCTION=1`; TCP validates `debug=False` for
  the staff port).
- Per-strategy session cookie names (`tkp_session`/`tcp_session`/`agm_session`)
  apply automatically in non-legacy modes — staff instances don't clobber the
  client apps' `session` cookie.
- TCP staff shows production branding/title (`H&C – TCP (Staff)`), not the
  preview banner; state/auth config still comes from `.tcp_production.env`
  (TCP state writes are lock-protected and multi-process safe).

The client ports (8301/8302/8304) are unaffected: they run without
`TEARSHEET_MODE`, keep the disclaimer gate + password, and keep the
loopback-only `/admin/tearsheet` convenience bypass
(`TEARSHEET_LOCAL_DIRECT_ADMIN=1`, loopback peer **and** loopback Host —
tunnel traffic with a public Host header can never trigger it).

## Launch

```
reboot_tkp_staff.ps1   # TKP admin on 127.0.0.1:8321
reboot_tcp_staff.ps1   # TCP admin on 127.0.0.1:8322
reboot_mp_staff.ps1    # AGM admin on 127.0.0.1:8324
```

(`.bat` shims exist for TCP/AGM; run the `.ps1` directly for TKP or add a
matching shim locally.)

Staff launchers import `.local_dev.env`, the app's production env file
(TKP/TCP), then `.staff.env`, and finally **force** `TEARSHEET_MODE=staff` +
the staff port so no env file can override them.

## Cloudflare Tunnel ingress (add to the tunnel config — NOT in this repo)

```yaml
ingress:
  # existing client hostnames stay as-is:
  #   tcp-ts.hcresearch.ltd  -> http://127.0.0.1:8302
  #   agm-ts.hcresearch.ltd  -> http://127.0.0.1:8304
  - hostname: tkp-admin.hcresearch.ltd
    service: http://127.0.0.1:8321
  - hostname: tcp-admin.hcresearch.ltd
    service: http://127.0.0.1:8322
  - hostname: agm-admin.hcresearch.ltd
    service: http://127.0.0.1:8324
  - service: http_status:404
```

## Cloudflare Access policy (required before exposing admin hostnames)

1. Zero Trust → Access → Applications → **Add application** (type:
   self-hosted), one per admin hostname (or one app with all three domains):
   `tkp-admin.hcresearch.ltd`, `tcp-admin.hcresearch.ltd`,
   `agm-admin.hcresearch.ltd`.
2. Policy: **Allow** → Include: *Emails* → only the approved operator
   email(s). Everything else is denied by default.
3. Session duration: short (e.g. 24h or less).
4. Client hostnames (`tcp-ts`, `agm-ts`, future `tkp-ts`) get **no** Access
   application — they stay public with the in-app client gate, as today.

Order of operations: create the Access applications **first**, then add the
tunnel ingress rules, then start the staff instances. Never expose a staff
port without Access in front of it.

## Also required on the ops machine

- `.staff.env` (copy from `.staff.env.example`) with
  `TEARSHEET_STAFF_ALLOWED_HOSTS=tkp-admin.hcresearch.ltd,tcp-admin.hcresearch.ltd,agm-admin.hcresearch.ltd`
  — without it, staff instances only answer loopback-Host requests (i.e.
  local browsing to `http://127.0.0.1:832x` works; tunnel requests are
  denied).

## Known limitation (single-writer rule)

TKP `daily_returns_secret_state.json` and AGM manual-rows JSON have no write
locking. With both a client and a staff process running, **make admin edits
for TKP/AGM on the staff port only** (the client port's password/local-bypass
admin remains capable of writes — avoid using both concurrently for edits).
TCP state is lock-protected and safe.
