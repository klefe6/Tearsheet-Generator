# OVH VPS — Official migration target

**Purpose:** Single authoritative record of the purchased OVH VPS used as the deployment target for TKP, TCP, and AGM tearsheet migration. Operational facts only; no credentials.

**Related docs:** `OVH_TKP_TCP_AGM_DEPLOYMENT_PLAN.md`, `OVH_TKP_TCP_AGM_CURRENT_STATE.md`, `OVH_TKP_TCP_AGM_FILE_MANIFEST.json`

**Last updated:** 2026-10-01 (documentation only; no server access performed for this record)

---

## Provider

| Field | Value |
|-------|--------|
| Provider | OVHcloud US |
| Product line | VPS |
| Plan | VPS-3 2027 |
| Commitment | None |
| Automatic renewal | Enabled |

---

## Server identity

| Field | Value |
|-------|--------|
| OVH hostname | `vps-c0d9d928.vps.ovh.us` |
| Region (marketing) | Virginia / US East |
| OpenStack zone | `os-us-east-va-2` |

Use the OVH control panel for the current public IPv4 and IPv6 assignments. This repository’s migration docs do not treat host IP addresses as routine non-secret metadata, so they are **not** duplicated here.

---

## Compute

| Field | Value |
|-------|--------|
| vCPU | 6 |
| RAM | 12 GB |

---

## Storage

| Field | Value |
|-------|--------|
| Primary disk | 100 GB |
| Additional disk | Disabled |

---

## Operating system

| Field | Value |
|-------|--------|
| OS | Windows Server 2025 Standard (Desktop experience) |

---

## Canonical filesystem root

| Field | Value |
|-------|--------|
| Canonical OVH root | `C:\HC` |
| Superseded planned root | `C:\H&C` (never created on this VPS) |
| Abandoned draft root | `E:\H&C` (assumed a second volume) |

`C:\HC` is authoritative for all TKP / TCP / AGM deployment paths on this server. It is defined
once by `tearsheet_paths.VPS_ROOT`; all app, data, config, secrets, log, and backup roots derive
from that constant. Older migration records that cite `C:\H&C` describe the earlier planned
design and are retained as historical audit material.

---

## Backup / recovery

| Field | Value |
|-------|--------|
| Snapshot | Enabled |
| Automated backup | Premium |

Recovery links, backup credentials, and OVH API tokens are **not** stored in this repository.

---

## Network

| Field | Value |
|-------|--------|
| Primary DNS name (OVH) | `vps-c0d9d928.vps.ovh.us` |
| OpenStack zone | `os-us-east-va-2` |
| Public IPv4 / IPv6 | Record in OVH manager only (not in git) |

Initial tearsheet services are intended to bind **127.0.0.1** on ports 8301 (TKP), 8302 (TCP), and 8304 (AGM). Inbound exposure of those ports on the VPS firewall is out of scope for first private deployment; ingress is planned via Cloudflare tunnel after reconciliation, not direct RDP-to-app exposure.

---

## Security notes

Do **not** commit or paste into migration docs:

- Windows Administrator password
- RDP password
- OVH recovery / install links
- OVH account credentials
- OVH API tokens
- Cloudflare tunnel tokens or API keys
- Application admin tokens, session secrets, or Glenn uploader ingest tokens

Store credentials in a password manager or OVH/Cloudflare secret stores. On the VPS, use `C:\HC\secrets\` with restrictive ACLs as described in the deployment plan.

---

## Intended initial workload

Private deployment and reconciliation (pilot order per deployment plan):

| Program | Public port (loopback) | Entry point (on VPS, planned) |
|---------|------------------------|-------------------------------|
| **TKP** | 8301 | `C:\HC\apps\tkp\tkp_ts.py` |
| **TCP** | 8302 (pilot first) | `C:\HC\apps\tcp\tcp_ts_v2.py` |
| **AGM** / Momentum Pacer | 8304 | `C:\HC\apps\agm\Momentum Pacer\mp_ts.py` |

Staff/admin ports 8321 / 8322 / 8324 are optional and deferred unless explicitly required later.

---

## Out of scope for first deployment

- **Y&Q** tearsheet (port 8303)
- **Main `hughesandco.ltd` website** and SiteGround migration
- **Unrelated H&C applications** (Morning Prep, Order Flow, Signal Analyzer, HomePage dashboard, Glenn uploader Fly deployment, Manager fleet launcher on the laptop, etc.)
- **DNS cutover** and **production Cloudflare tunnel** changes for existing public hostnames until reconciliation passes
- **Production data authority transfer** (uploader target URLs) until cutover phase

---

## Secret-handling rule

1. Migration documentation may name environment variables and configuration **keys** only.
2. Secret **values** live outside git: OVH panel, Fly secrets, `C:\HC\secrets\` on the VPS, or operator password manager.
3. If a path under protected business document folders is required for TKP, supply files via `C:\AI_HANDOFF` or merge path-portability code — do not reference or copy from restricted folders in automation.

---

## Current deployment status

| Item | Status |
|------|--------|
| VPS purchased | **Yes** |
| Windows initial setup complete | **Unknown** (not verified from this documentation update) |
| H&C software installed | **No** |
| H&C code deployed | **No** |
| Production data copied | **No** |
| DNS changed | **No** |
| Cloudflare changed | **No** |
| Production cutover performed | **No** |

Update this table when verified milestones complete (e.g. after first RDP confirmation, after pilot TCP reconcile).
