# Phase 2 Execution Plan (gated)

> Planning only. **Do not execute any gate.** Every production-affecting gate has a rollback. Microsoft 365 DNS preservation is explicit at cutover.

---

## G. Future URL structure

Subdomains under `hughesandco.ltd`. Tearsheet sites are **not** publicly promoted or linked from homepage navigation merely because deployed.

| Hostname | App | Internal port | Public/Private | Auth | Cloudflare Access | Search indexing | Compliance-publication | Exists in staging | Linked from homepage |
|---|---|---|---|---|---|---|---|---|---|
| `hughesandco.ltd` | Homepage | IIS 443 | Public | None | No | Allow | Yes | Yes | n/a (is homepage) |
| `www.hughesandco.ltd` | Homepage | IIS 443 | Public | None | No | Allow (canonical to apex) | Yes | Yes | n/a |
| `tkp.hughesandco.ltd` | TKP public | 8301 | Public | Gate/password per app | No | **noindex** | Controlled | Staging host only | **No** |
| `tcp.hughesandco.ltd` | TCP public | 8302 | Public | Gate/password | No | **noindex** | Controlled | Staging host | **No** |
| `agm.hughesandco.ltd` | AGM public | 8304 | Public | Gate/password | No | **noindex** | Controlled | Staging host | **No** |
| `yq.hughesandco.ltd` | Y&Q public | 8303 | Public | Gate/password | No | **noindex** | Controlled | Staging host | **No** |
| `admin-tkp.hughesandco.ltd` | TKP staff | 8321 | Private | Session/token | **Yes** | noindex | No | Staging host | No |
| `admin-tcp.hughesandco.ltd` | TCP staff | 8322 | Private | Session/token | **Yes** | noindex | No | Staging host | No |
| `admin-agm.hughesandco.ltd` | AGM staff | 8324 | Private | Session/token | **Yes** | noindex | No | Staging host | No |
| (internal) | Dashboard | 8006 | Private | — | n/a (not exposed) | noindex | No | No | No |

Staging note: during validation use temporary hostnames (e.g. `*-staging.hughesandco.ltd` on a parallel Azure tunnel) so nothing collides with live production.

---

## H. Production data layout & file migration

Target root: `E:\H&C\` (see build spec). State leaves the git worktree.

| State item | Current path | Future path | Owner service | Migration method | Backup freq | ACL | Code/config change | Validation |
|---|---|---|---|---|---|---|---|---|
| TKP state JSON | `…\daily_returns_secret_state.json` (repo root, symlinked) | `E:\H&C\data\tkp\daily_returns_secret_state.json` | hc-tkp-* | Copy + verify SHA-256 | Daily (enc) | service RW, admin R | Point `_secret_editor_state_path()` at config path | Row count 847, latest 2026-07-23, hash match |
| TCP state JSON | `…\tcp_daily_returns_secret_state.json` | `E:\H&C\data\tcp\tcp_daily_returns_secret_state.json` | hc-tcp-* | Copy + verify | Daily (enc) | service RW | Set `TCP_V2_STATE_PATH` (+backup/lock paths) | record_count 112, latest 2026-06-24 (stale, expected) |
| AGM manual rows | `…\Momentum Pacer\momentum_pacer_manual_daily_rows.json` | `E:\H&C\data\agm\momentum_pacer_manual_daily_rows.json` | hc-agm-* | Copy + verify | Daily (enc) | service RW | Config path for `_agm_manual_daily_rows_path()` | 10 rows, latest 2026-07-23 |
| AGM fee workbook | `…\Momentum Pacer\Momentum Fee Calculation.xlsx` (symlink) | `E:\H&C\data\agm\sources\Momentum Fee Calculation.xlsx` | hc-agm-* | Copy real file (deref) | On change | service R | `EXCEL_PATH` → config | opens read-only, sheets present |
| **TKP source workbook** | protected folder (`…\TKP\VADI\Copy of tkp_alex_old1.xlsx`) | `E:\H&C\data\tkp\sources\<name>.xlsx` | hc-tkp-* | **Kevin supplies via `C:\AI_HANDOFF`**; copy to VM | On change | service R | Replace hardcoded path (line ~245) with config/env path | opens read-only; TKP boots |
| Y&Q data | `…\yq.csv`, `…\yq.xlsx` | `E:\H&C\data\yq\` | hc-yq-* | Copy + verify | Daily (enc) | service RW | Path config if hardcoded | live value captured (baseline currently unreliable) |
| Uploader DB | Fly.io `/data` (+ local copy) | **stays on Fly.io** | Glenn uploader | none (not migrated) | Fly volume | n/a | none | uploader unaffected |
| Ingest audit JSONL | worktree root + Momentum Pacer | `E:\H&C\logs\ingest\` | apps | Copy (append continues) | Weekly | service RW | audit_path config | appends after ingest |
| Benchmark caches | worktree root | `E:\H&C\data\<app>\cache\` | apps | Copy (regenerable) | Optional | service RW | cache path config | regenerates |

TKP workbook is placed **outside** the source repo and referenced via configuration (resolves Phase 1 B1 + B9).

---

## Gate procedures

Legend — each gate lists: **Preconditions · Actions · Validation · Rollback · Approval · Record · Production affected.**

### Gate 2.0 — Approval & purchase readiness
- **Preconditions:** Phase 1 + 1C reports reviewed.
- **Actions:** Ratify Windows Server 2022 + D4s v5 (4 vCPU/16 GB, 128 GB OS + 128 GB data); select region (residency-confirmed); confirm Azure subscription + payment; confirm current-state backups exist; **obtain the 4 missing handoff inputs** (site ZIP, DNS export, tunnel export, TKP workbook).
- **Validation:** Sign-off checklist complete; handoff package now complete.
- **Rollback:** n/a (no changes).
- **Approval:** Kevin + Dan.
- **Record:** ratified spec, region, subscription ID.
- **Production affected:** No.

### Gate 2.1 — Provision infrastructure
- **Preconditions:** 2.0 approved.
- **Actions:** Create VM, OS + data disks, reserve **Static Standard public IP**, create NSG (deny-by-default; RDP via Bastion/JIT only), enable Azure Backup, create admin access, tag resources.
- **Validation:** VM boots; disks attached; backup enabled; RDP only from allowed source.
- **Rollback:** Deallocate/delete the resource group (nothing production depends on it yet).
- **Approval:** Dan.
- **Record:** resource group, VM name, IP, disk IDs, backup vault.
- **Production affected:** No.

### Gate 2.2 — Secure base server
- **Preconditions:** 2.1 done.
- **Actions:** Windows Update; least-privilege service account; RDP restrictions; Windows Firewall (loopback for app ports); Defender on; timezone; centralized logging; backup agent; directory ACLs on `E:\H&C\`.
- **Validation:** Update clean; firewall rules verified; ACLs correct; test reboot recovers.
- **Rollback:** Re-image from clean snapshot.
- **Approval:** Dan.
- **Record:** baseline config + snapshot ID.
- **Production affected:** No.

### Gate 2.3 — Install runtime
- **Preconditions:** 2.2 done.
- **Actions:** Install **Python 3.10** (match production), Git, create `.venv310`, `pip install -r requirements.txt` (apps) + pinned uploader deps only if hosting locally (it is NOT — uploader stays on Fly.io), IIS + ARR, NSSM, `cloudflared`. Validate native wheels (numpy/scipy/matplotlib/curl_cffi) import.
- **Validation:** `python -c "import dash, pandas, numpy, plotly, matplotlib, scipy"` OK; IIS serves a test page; NSSM present; cloudflared version prints.
- **Rollback:** Uninstall/roll back to 2.2 snapshot.
- **Approval:** Dan.
- **Record:** installed versions.
- **Production affected:** No.

### Gate 2.4 — Deploy applications privately
- **Preconditions:** 2.3 done; state files + workbooks available.
- **Actions:** Deploy a **clean user-owned checkout** of `live-main`@`f540135` to `E:\H&C\apps\`; copy production state to `E:\H&C\data\**` (verify SHA-256 against baseline); relocate TKP/AGM workbooks to `data\*\sources\`; set config/env paths; render secrets from Key Vault; register NSSM services bound to **loopback**; **do not touch DNS**.
- **Validation:** All 8 services listen on their ports (loopback); state hashes match baseline; no service in crash loop; Y&Q runs under `.venv310`.
- **Rollback:** Stop/remove NSSM services; local production remains untouched and authoritative.
- **Approval:** Dan.
- **Record:** deployed commit, service list, state hashes.
- **Production affected:** No (local prod still live; Azure private).

### Gate 2.5 — Reconcile
- **Preconditions:** 2.4 done.
- **Actions:** Compare Azure vs local: latest date/value per app against `PRODUCTION_RECONCILIATION_BASELINE.json`; validate persistence (add/restart round-trip in a non-prod copy), NSSM restart-after-kill and restart-after-reboot; validate calculations (chart/stat parity); validate Glenn ingest in **dry-run** (`accepted:true, dry_run:true, no write`).
- **Validation:** TKP $83,245.09 / 2026-07-23; AGM $43,496.60 / 2026-07-23; TCP $43,007.30 (nav-x1 $44,871.38) / 2026-06-24 (stale, expected — **do not fix**); Y&Q live value captured; services auto-restart.
- **Rollback:** Fix Azure config; local prod unaffected.
- **Approval:** Dan (+ Kevin for value sign-off).
- **Record:** reconciliation diff report.
- **Production affected:** No.

### Gate 2.6 — Deploy static homepage
- **Preconditions:** SiteGround `public_html` archive supplied + classified.
- **Actions:** Copy content to `E:\H&C\website\`; configure IIS site; if PHP/db required, add handler/DB (or keep on SiteGround); test privately.
- **Validation:** Homepage renders; redirects, forms, SSL, assets, favicons, robots/sitemap correct; no mixed-content; no server-side code executed during inspection.
- **Rollback:** Keep SiteGround as the live homepage.
- **Approval:** Kevin + Dan.
- **Record:** site classification, asset inventory.
- **Production affected:** No.

### Gate 2.7 — Parallel ingress
- **Preconditions:** Tunnel export supplied; 2.5/2.6 pass.
- **Actions:** Create a **parallel Azure named tunnel** + **staging hostnames** pointing at IIS/loopback apps; apply Cloudflare Access to admin staging hosts; keep the **existing local tunnel live**.
- **Validation:** Staging hosts reachable + TLS valid; admin hosts require Access; public prod unchanged.
- **Rollback:** Delete staging tunnel/hostnames; zero impact on live tunnel.
- **Approval:** Dan.
- **Record:** staging tunnel ID/hostnames, Access policies.
- **Production affected:** No.

### Gate 2.8 — Cutover readiness
- **Preconditions:** DNS export in hand; staging validated.
- **Actions:** Export current DNS zone; record rollback values (current apex/`www`/app targets); take a final state backup; declare change freeze; obtain approval; **document which records change vs which are preserved (all M365 records preserved)**.
- **Validation:** Rollback file complete; backup verified; M365 records explicitly listed as DO-NOT-TOUCH.
- **Rollback:** n/a (no changes yet).
- **Approval:** Kevin + Dan.
- **Record:** pre-cutover DNS snapshot + rollback table + final backup ID.
- **Production affected:** No.

### Gate 2.9 — DNS cutover
- **Preconditions:** 2.8 approved.
- **Actions:** Change **only** website/application records (apex, `www`, app subdomains) to Azure/Cloudflare targets; **preserve MX, SPF, DKIM, DMARC, autodiscover, and all Microsoft 365 verification records untouched**; lower TTLs beforehand; monitor.
- **Validation:** Website + app hosts resolve to Azure and serve correctly; **email flow unaffected** (send/receive test); Access enforced on admin hosts.
- **Rollback:** Restore prior website/app records from the 2.8 snapshot (M365 records never changed, so email cannot be impacted).
- **Approval:** Kevin + Dan.
- **Record:** post-cutover record values, timestamps.
- **Production affected:** **Yes.**

### Gate 2.10 — Stabilization
- **Preconditions:** 2.9 done.
- **Actions:** Retain SiteGround + local deployment as fallback for a defined window; monitor health/logs/backups; verify auto-restart and daily backups; document final state; then decommission per plan.
- **Validation:** N days stable; backups restorable; reconciliation still matches.
- **Rollback:** Re-point DNS to SiteGround/local (fallbacks retained).
- **Approval:** Kevin + Dan.
- **Record:** stabilization log, final-state doc, decommission date.
- **Production affected:** Yes (monitoring only).

---

## Blocking dependencies for Phase 2 gates

- **Gates 2.0–2.5** need: VM/region ratification + **TKP workbook** (for 2.4/2.5) + state files (available).
- **Gate 2.6** needs: SiteGround `public_html` archive.
- **Gate 2.7** needs: Cloudflare Tunnel export.
- **Gates 2.8–2.9** need: DNS export + explicit M365 preservation list.

All four missing inputs are **not** required to begin infrastructure provisioning, but **are** required before the corresponding deployment/cutover gates.
