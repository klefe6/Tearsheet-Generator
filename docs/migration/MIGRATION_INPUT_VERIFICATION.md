# Migration Input Verification (Phase 1C)

> Read-only verification. No Azure/DNS/remote changes, no code/data changes, no access to the protected company Documents folder.
> Timestamp: 2026-07-26 (local, UTC-4).

---

## Readiness verdict (summary)

**PASS WITH BLOCKERS** — The Azure Windows Server architecture and Phase 2 plan can be finalized from Phase 1 evidence, and the reconciliation baseline was verified from live production state (read-only). **However, the `C:\AI_HANDOFF` package is effectively empty** (only a placeholder `README.txt`). None of the four expected migration inputs — SiteGround `public_html` archive, DNS export, Cloudflare Tunnel export/screenshots, and the TKP source workbook — were supplied. Sections B, C, D, and E therefore could **not** be verified. These missing inputs **block deployment and DNS cutover**, but **do not block VM provisioning** (Gate 2.0–2.4 can proceed once the VM decision is ratified).

---

## A. Handoff package inventory

Path inspected (recursively): `C:\AI_HANDOFF` only.

| Filename | Rel path | Type | Size | Modified | SHA-256 | Purpose | Sensitivity | Readable | Complete | Expected |
|---|---|---|---|---|---|---|---|---|---|---|
| README.txt | `\README.txt` | text/plain | 321 B | 2026-07-14 12:37 | `11E9B3DC7A698086DA405856181E2D3D0FDB6199F1451F6B97CE9156140CDC27` | Folder usage placeholder/instructions | None | Yes | Yes (as placeholder) | Not a migration artifact |

`README.txt` content is purely instructional (how to drop files into the handoff folder; do not browse the protected folder). No secrets.

### Missing items (expected per Phase 1, not present)

| Expected item | Category | Blocking |
|---|---|---|
| SiteGround `public_html` ZIP | Website content | Blocks Gate 2.6 (homepage deploy) |
| SiteGround DNS export / screenshots | DNS records | Blocks Gate 2.8–2.9 (cutover) |
| Cloudflare Tunnel export / screenshots | Ingress mapping | Blocks Gate 2.7 (parallel ingress) |
| TKP source workbook (`Copy of tkp_alex_old1.xlsx` or export) | TKP data source | Blocks Gate 2.4/2.5 (TKP deploy + reconcile) |
| SiteGround configuration screenshots | Hosting config | Blocks Gate 2.6/2.9 |

No extraction was necessary (nothing to extract). No temporary analysis directory was created.

---

## B. SiteGround website package findings

**Status: CANNOT VERIFY — no `public_html` archive supplied.**

- Archive root structure: N/A
- Entry file / `index.*` / `.htaccess` / `.well-known`: N/A
- Static vs PHP vs database: **Undetermined — requires additional investigation.**
- Website classification: **UNKNOWN pending the SiteGround content export.**

Conclusion: The website cannot be classified (fully static / static+third-party / PHP / database) until the `public_html` archive (or a crawl export) is provided. This is a **deployment blocker** for the homepage, but not for VM provisioning.

---

## C. DNS findings

**Status: CANNOT VERIFY — no DNS export or screenshots supplied.**

Phase 1 background states SiteGround nameservers currently appear authoritative and Microsoft 365 handles email. Those assertions **could not be independently confirmed** in this phase because no zone export was provided, and active DNS lookups that could change remote state / require login were out of scope (and none were performed).

The record table below is a **required-evidence template** to be completed once the export arrives. **No records were invented.**

| Type | Name | Value classification | TTL | Purpose | Website | M365/email | Preserve | Change later |
|---|---|---|---|---|---|---|---|---|
| A/ALIAS | `hughesandco.ltd` (apex) | (to supply) | — | Website apex | Yes | No | Until cutover | **Yes (cutover)** |
| CNAME | `www` | (to supply) | — | Website www | Yes | No | Until cutover | **Yes (cutover)** |
| MX | `hughesandco.ltd` | (to supply) | — | Email routing (M365) | No | **Yes** | **Yes — DO NOT TOUCH** | No |
| TXT (SPF) | `hughesandco.ltd` | (to supply) | — | Email auth | No | **Yes** | **Yes** | No |
| CNAME/TXT (DKIM) | `selector._domainkey` | (to supply) | — | Email auth | No | **Yes** | **Yes** | No |
| TXT (DMARC) | `_dmarc` | (to supply) | — | Email policy | No | **Yes** | **Yes** | No |
| CNAME | `autodiscover` | (to supply) | — | M365 autodiscover | No | **Yes** | **Yes** | No |
| CNAME/TXT | `enterpriseregistration` / `enterpriseenrollment` / MS verification | (to supply) | — | M365 verification | No | **Yes** | **Yes** | No |
| CAA | `hughesandco.ltd` | (to supply) | — | Cert issuance policy | Maybe | No | Review | Maybe |
| SRV | `_sip`/`_sipfederationtls` (if present) | (to supply) | — | Teams/Skype | No | **Yes** | **Yes** | No |
| CNAME (app subdomains) | `tkp/tcp/agm/yq` (if any today) | (to supply) | — | Tearsheet apps (Cloudflare) | Yes | No | Review | Maybe |

**Explicit preservation rule:** All **MX, SPF (TXT), DKIM, DMARC, autodiscover, and Microsoft 365 verification** records **must remain untouched** during website cutover. Only apex/`www`/website-app records change.

**SiteGround authoritative DNS:** **Unconfirmed** (requires the registrar/nameserver evidence). Flagged as a cutover-planning input.

---

## D. Cloudflare Tunnel findings

**Status: CANNOT VERIFY — no tunnel export or screenshots supplied.**

Phase 1 confirmed (independently, read-only): a `cloudflared` process is running (PID observed in Phase 1), apps bind loopback, and `~/.cloudflared` contains only `cert.pem` (ingress is **cloud-managed** — no local `config.yml`). The hostname→port ingress rules live in the Cloudflare Zero Trust dashboard and were **not exported** into the handoff.

Required mapping (template — to complete from the export):

| Public hostname | Tunnel | Destination service | Local port | Access policy | Migration requirement |
|---|---|---|---|---|---|
| (to supply) | (name/ID to supply) | TKP public | 8301 | none/public | Recreate on Azure |
| (to supply) | " | TCP public | 8302 | none/public | Recreate on Azure |
| (to supply) | " | Y&Q public | 8303 | none/public | Recreate on Azure |
| (to supply) | " | AGM public | 8304 | none/public | Recreate on Azure |
| (to supply) | " | TKP staff | 8321 | **Cloudflare Access** | Recreate + Access policy |
| (to supply) | " | TCP staff | 8322 | **Cloudflare Access** | Recreate + Access policy |
| (to supply) | " | AGM staff | 8324 | **Cloudflare Access** | Recreate + Access policy |

- Tunnel name / ID: **unknown (not supplied).**
- Tokens/certificates: **not recorded** (and must never be printed).
- Machine/path/IP dependency: cannot confirm without the export; the tunnel is credential-based (not IP-pinned), so a **new named tunnel on Azure** is feasible.

**Recommended approach (lowest risk):** **Run a parallel Azure tunnel** (new named connector on the VM, new staging hostnames) during validation while the existing local tunnel keeps production live. Cut hostnames over only after reconciliation passes. Do **not** replace or delete the working tunnel until Azure is validated. (Reuse of the same tunnel is possible but riskier because a connector move affects live routing.)

---

## E. TKP workbook findings

**Status: NOT SUPPLIED — no workbook copy present in `C:\AI_HANDOFF`.** The protected folder was **not** accessed.

Cannot record: filename/size/hash, sheet names, macro/external-link/data-connection presence, named ranges, used ranges, formula dependencies. From Phase 1 source evidence only: `tkp_ts.py` references `…\TKP\VADI\Copy of tkp_alex_old1.xlsx` (a hardcoded path inside the protected folder) and reads workbooks via pandas/openpyxl (no COM automation observed), which suggests **Python reads the workbook directly** and a **configurable VPS path can replace the hardcoded path** — but this must be confirmed against the actual file.

Conclusion: **UNKNOWN pending controlled inspection of a supplied copy.** Provide the exact file via `C:\AI_HANDOFF` (or confirm TKP now runs from the StoneX/state-JSON only and the workbook is legacy).

---

## Security concerns observed

- `C:\AI_HANDOFF\README.txt` contains **no secrets**.
- No files under `AI_HANDOFF` were modified.
- No secret values from production `.env` files, tunnel tokens, or certificates were read or printed in this phase.

---

## Readiness verdict (detail)

- **Architecture & Phase 2 plan:** READY (evidence-based, produced in the companion deliverables).
- **Reconciliation baseline:** READY (verified read-only from live state; see `PRODUCTION_RECONCILIATION_BASELINE.json`).
- **Deployment inputs (site/DNS/tunnel/workbook):** **NOT READY** — handoff package incomplete.
- **Net:** Proceed to ratify VM + region and provision infrastructure (Gates 2.0–2.4) in parallel with collecting the four missing inputs, which are required before homepage deploy, ingress, and DNS cutover.
