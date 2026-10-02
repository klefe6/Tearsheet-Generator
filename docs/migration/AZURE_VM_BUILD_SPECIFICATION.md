# Azure VM Build Specification (Phase 1C)

> Evidence-based design derived from the Phase 1 audit + Phase 1C verification. No Azure resources were provisioned. No prices are asserted (verify against current official Azure pricing separately).

## Ratification status (2026-07-26)

**RATIFIED — starting production configuration approved by owner:**
- OS: **Windows Server 2022 Datacenter**
- VM: **D4s v5** (4 vCPU / 16 GB RAM)
- OS disk: **128 GB Premium SSD** · Data disk: **128 GB Premium SSD (separate)**
- Public IP: **Static Standard** · Backup: **Azure Backup enabled**
- Ingress: **Cloudflare Tunnel → IIS/ARR → private app ports**
- Process management: **NSSM services** · Admin protection: **Cloudflare Access**
- Resizable later without redesign (see §2 resize triggers).

**Still pending (required to close Gate 2.0):** Azure **region** (residency-confirmed), subscription/payment confirmation, and the four owner-supplied inputs (TKP workbook, SiteGround ZIP, DNS export, Cloudflare Tunnel export).

This ratifies infrastructure Gates 2.0–2.3 to proceed. Application deployment/cutover (Gates 2.4/2.6–2.9) remains blocked on the four missing inputs.

---

## 1. Operating system

**Azure Windows Server 2022 Datacenter (Gen2)** — latest LTSC widely available on Azure at time of writing; ratify 2025 only if the subscription/region offers it and app deps are re-validated.

Rationale (from Phase 1): Windows-only launchers (`.ps1`/`.bat`, `launch_all_services.py` + `service_config.py`), NTFS junction/symlink layout, admin-owned worktree, and Windows-hosted Excel sources make a **same-OS lift-and-shift** the lowest-risk path for financially material calculations.

---

## 2. VM sizing

**Starting size (unchanged from the given assumption; evidence supports it):**

| Attribute | Value | Justification |
|---|---|---|
| Series | **D4s v5** (or D4as v5 AMD) | General-purpose, 4 vCPU / 16 GB, premium-SSD capable |
| vCPU | **4** | 8 concurrent Python/Dash processes + IIS + cloudflared; Dash apps are light but pandas/plotly/matplotlib rendering is bursty |
| RAM | **16 GB** | Each app ~150–400 MB resident; 8 apps + OS + IIS + benchmark caches fit with headroom |
| OS disk | **128 GB Premium SSD (P10)** | OS + Python + IIS + runtimes |
| Data disk | **Separate 128 GB Premium SSD (P10)**, mounted e.g. `E:` | Production state, backups, deployment packages, logs (keeps state off the OS disk and out of any git worktree) |
| Public IP | **1 Static (Standard SKU)** | Stable ingress; required if any direct HTTPS is used; also stabilizes RDP allowlisting |
| Accelerated networking | Enabled | Lower latency for tunnel + ingress |

**Availability:** Single VM initially (matches current single-machine posture). Enable **Azure Backup** for VM-level restore. Consider an availability zone assignment for future resilience; multi-VM/HA is out of scope for lift-and-shift.

**Region selection criteria:** (1) client/regulatory data residency (Kevin to confirm), (2) proximity to primary user base and Cloudflare edge, (3) availability of Dsv5 + Premium SSD + zones, (4) consistency with any existing Azure footprint. Do not finalize region until residency is confirmed.

### Estimated resource headroom & resize triggers

- Expected steady CPU: low-to-moderate (Dash idle is cheap; spikes on chart render / benchmark refresh / ingest recalculation).
- **Resize triggers:** sustained CPU > 70% for 15 min; page-load p95 > 2s under normal load; memory > 80% (14 GB) sustained; data disk > 75% used; ingest recalculation latency regressions. First step up: **D8s v5** (8 vCPU/32 GB) and/or larger premium data disk (P15/P20).

---

## 3. Disk / storage layout

Data disk (`E:`) holds everything stateful; OS disk (`C:`) holds runtimes only.

```text
E:\H&C\
  apps\        # deployment checkout of live-deploy-main (user-owned, clean)
    tkp\  tcp\  agm\  yq\  shared\  dashboard\
  data\        # production state (NOT inside any git worktree)
    tkp\  tcp\  agm\  yq\  sources\   # sources\ holds relocated Excel workbooks
  config\      # non-secret config, fleet runtime json, service defs
  secrets\     # restricted .env rendered from Key Vault (ACL-locked)
  logs\        # per-service stdout/stderr + restart logs
  backups\     # daily encrypted state snapshots + pre-cutover backups
  website\     # SiteGround homepage static content (IIS site root)
  deployment\  # packages, zips, checksums, runbooks
  temp\        # scratch (never authoritative)
```

Production state must **not** live only inside a Git worktree (Phase 1 B4). State files move to `E:\H&C\data\<app>\` and apps reference them via config/env.

---

## 4. Network configuration

- **NSG inbound (deny-by-default):**
  - 443/tcp: allow (only if direct HTTPS ingress is used; otherwise closed — tunnel is outbound).
  - 80/tcp: allow only for ACME/redirect if direct ingress used; else closed.
  - 3389/tcp (RDP): allow **only** from a named admin IP / Bastion; never `0.0.0.0/0`.
  - All app ports (8301–8304, 8321/8322/8324, 8006, 8091): **never** inbound from Internet — loopback only.
- **Cloudflare Tunnel is outbound** (connector dials out), so no public inbound ports are required for the tearsheets — preferred model.
- Prefer **Azure Bastion** or JIT VM access for RDP instead of a persistent open port.
- Outbound: allow 443 to Cloudflare, Fly.io (uploader ingest), yfinance/market data, Windows Update, Key Vault.

---

## 5. Web ingress (compared)

| Option | Pros | Cons | Verdict |
|---|---|---|---|
| Cloudflare Tunnel → local app ports | Matches current model; no public inbound; TLS + Access at edge | Ingress cloud-managed; per-host config | **Primary (recommended)** |
| IIS reverse proxy (ARR) in front of apps | Windows-native; centralizes TLS/routing/headers; can host homepage | Adds a component to manage | **Recommended companion** (proxy on VM; tunnel points at IIS 443) |
| IIS + Cloudflare Tunnel | Best of both: one internal 443 endpoint, edge Access | Slightly more setup | **Recommended combined design** |
| Direct Azure public IP + HTTPS | Simple | Exposes VM directly; must manage certs, WAF, DDoS | Avoid unless tunnel unavailable |
| Nginx on Windows | Familiar to some | Non-native on Windows; weaker support | Reject (prefer IIS) |

**Recommended ingress design:** **Cloudflare Tunnel → IIS (ARR reverse proxy) on `127.0.0.1:443` → loopback app ports.** IIS terminates internal TLS/host routing and serves the static homepage; Cloudflare provides public HTTPS + Access for admin hosts. App ports stay private. Run a **parallel Azure tunnel** during validation (do not disturb the live local tunnel).

---

## 6. Application services (per process)

Run **each app as an NSSM-managed Windows service** (one per public app + one per staff app + dashboard). NSSM gives: auto-start on boot, auto-restart on failure, single-instance, stdout/stderr redirection to `E:\H&C\logs\`, a controlled working directory, and independent restarts — directly resolving Phase 1 B2 (no auto-start/recovery).

| Service | Entry | Working dir | Env source | Port | Auto-start | Auto-restart |
|---|---|---|---|---|---|---|
| hc-tkp-public | `tkp_ts.py` (`TEARSHEET_MODE=public`) | `E:\H&C\apps\...` | `E:\H&C\secrets\tkp.env` | 8301 | Yes | Yes |
| hc-tcp-public | `tcp_ts_v2.py` | " | `tcp.env` | 8302 | Yes | Yes |
| hc-yq-public | `yq_ts.py` (**use `.venv310`**, not global python) | " | `common.env` | 8303 | Yes | Yes |
| hc-agm-public | `Momentum Pacer\mp_ts.py` (`MP_TS_PRODUCTION=1`) | AGM dir | `agm.env` | 8304 | Yes | Yes |
| hc-tkp-staff | `tkp_ts.py` (`TEARSHEET_MODE=staff`,`TKP_BIND_PORT=8321`) | " | `tkp.env`+`staff.env` | 8321 | Yes | Yes |
| hc-tcp-staff | `tcp_ts_v2.py` (staff) | " | `tcp.env`+`staff.env` | 8322 | Yes | Yes |
| hc-agm-staff | `mp_ts.py` (staff) | AGM dir | `agm.env`+`staff.env` | 8324 | Yes | Yes |
| hc-dashboard | `debug.py` | `HomePage` | `dashboard.env` | 8006 (bind **127.0.0.1**) | Optional | Yes |
| hc-cloudflared | tunnel connector | — | tunnel creds (Key Vault) | — | Yes | Yes |

Notes: keep `launch_all_services.py` / `service_config.py` as an operator convenience, but the **authoritative** start mechanism becomes NSSM services (not manual launch). Rebind dashboard to loopback (was `0.0.0.0` — Phase 1 B8). The **Glenn uploader stays on Fly.io** and is **not** installed as a VM service.

---

## 7. Static homepage

Serve the SiteGround content as an **IIS static site on the VM** (site root `E:\H&C\website\`), fronted by the same Cloudflare Tunnel/IIS ingress. This keeps one operational surface. **Reclassify after the `public_html` archive arrives** — if it needs PHP or a database, add the PHP handler / DB accordingly (or keep it on SiteGround until resolved). A separate Azure Static Web App is an option only if the site proves fully static and decoupling is desired; not required for lift-and-shift.

---

## 8. Security model

- Secrets in **Azure Key Vault**; render restricted `E:\H&C\secrets\*.env` at boot via a managed identity; ACL to the service account only (Phase 1 AI-07).
- Fix worktree/`.git` **ownership**: deploy a clean, user-owned checkout (not admin-owned) (Phase 1 B3/AI-04).
- App ports loopback-only; admin via distinct hostnames behind **Cloudflare Access** (Phase 1 B6/AI-09); enable **secure cookies** behind HTTPS.
- RDP via Bastion/JIT + named IP allowlist; Defender AV on; automatic Windows Update (with a controlled reboot window and NSSM auto-start ensuring recovery).
- Daily **encrypted** state backups; data disk encryption (Azure-managed keys or CMK per compliance).

---

## 9. Application → URL mapping (see also PHASE_2 §G)

| App | Internal port | Public host (proposed) | Admin host (proposed) | Access |
|---|---|---|---|---|
| TKP | 8301 / 8321 | `tkp.hughesandco.ltd` | `admin-tkp.hughesandco.ltd` | public / Cloudflare Access |
| TCP | 8302 / 8322 | `tcp.hughesandco.ltd` | `admin-tcp.hughesandco.ltd` | public / Access |
| AGM | 8304 / 8324 | `agm.hughesandco.ltd` | `admin-agm.hughesandco.ltd` | public / Access |
| Y&Q | 8303 | `yq.hughesandco.ltd` | (none) | public |
| Homepage | IIS 443 | `hughesandco.ltd`, `www` | — | public |
| Dashboard | 8006 | (none — internal) | internal only | loopback/VPN |

Tearsheet sites are **not** to be promoted or added to homepage navigation merely because they are deployed (see URL policy in the execution plan).

---

## 10. Backup

- **VM-level:** Azure Backup (daily, 30-day retention minimum).
- **State-level:** daily encrypted snapshot of `E:\H&C\data\**` to `E:\H&C\backups\` + off-VM copy (Blob/immutable), 90-day + monthly archive; quiesce writers for a consistent snapshot where feasible.
- **Config/secrets:** versioned; secrets only in Key Vault.
- Restore validated against `PRODUCTION_RECONCILIATION_BASELINE.json`.
