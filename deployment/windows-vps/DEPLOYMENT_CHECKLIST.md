# Windows VPS Deployment Checklist

Operational checklist for migrating the H&C tearsheet system to a Windows VPS.
**None of these steps are executed in the layout-preview phase.**

---

## Before server purchase

- [ ] Review `SERVER_MAP.md` and `manifests\` with stakeholders
- [ ] Confirm provider-neutral `C:\H&C\` layout is acceptable
- [ ] Identify backup retention policy for `data\` and `backups\`
- [ ] Confirm Cloudflare Tunnel + Access strategy for staff ports
- [ ] Confirm homepage migration plan (SiteGround → `website\`)

## After receiving VPS credentials

- [ ] RDP/SSH into Windows Server
- [ ] Create operator admin account (non-default)
- [ ] Enable Windows Update baseline
- [ ] Configure Windows Firewall (block public inbound except RDP/tunnel)

## Base Windows configuration

- [ ] Create `C:\H&C\` layout: `Initialize-HCServerLayout.ps1 -Root "C:\H&C"`
- [ ] Validate: `Test-HCServerLayout.ps1 -Root "C:\H&C"`
- [ ] Install Python (same major version as laptop production)
- [ ] Create dedicated service account (optional but recommended)

## Copy application source

- [ ] Deploy Tearsheet Generator code to `C:\H&C\apps\tkp`, `tcp`, `agm`, `yq`
- [ ] Copy shared modules to `C:\H&C\apps\shared`
- [ ] Deploy Manager dashboard to `C:\H&C\apps\dashboard`
- [ ] Install Python dependencies (`pip install -r requirements.txt`)

## Copy production data

- [ ] Copy TKP state + workbook → `C:\H&C\data\tkp\`
- [ ] Copy TCP state + workbook → `C:\H&C\data\tcp\`
- [ ] Copy AGM state + workbook + pinned CSV → `C:\H&C\data\agm\`
- [ ] Copy Y&Q CSV (+ xlsx source) → `C:\H&C\data\yq\`
- [ ] Verify file hashes against laptop production

## Configure environment

- [ ] Copy `hc-vps.env.example` → secure location on VPS (not Git)
- [ ] Set `HC_APP_ENV=vps-production`
- [ ] Fill secret placeholders (admin tokens, session secrets)
- [ ] Dry-run path resolution (`tearsheet_paths.load_tearsheet_paths`)

## Install Python dependencies

- [ ] Create venv or use system Python per service
- [ ] `pip install -r requirements.txt` for each app context
- [ ] Verify imports: `python -c "import tearsheet_paths"`

## Install/configure NSSM

- [ ] Install NSSM on VPS
- [ ] Create 8 services per `manifests\windows-services.json`
- [ ] Set working directory, script, log redirection per service
- [ ] Inject `hc-vps.env` variables into each service environment
- [ ] Set `TEARSHEET_MODE=staff` for staff services only

## Configure IIS/ARR

- [ ] Install IIS + ARR (if using reverse proxy)
- [ ] Configure localhost upstream bindings per `network-map.json`
- [ ] Do **not** expose port 8006 publicly

## Configure parallel Cloudflare Tunnel

- [ ] Install `cloudflared` on VPS
- [ ] Map hostnames per `network-map.json`
- [ ] Enable Cloudflare Access on staff/admin hostnames
- [ ] Test tunnel to localhost ports privately

## Start services privately

- [ ] Start public services (8301–8304) — loopback bind only
- [ ] Verify `/healthz` on each port
- [ ] Start staff services (8321, 8322, 8324) — Access-gated
- [ ] Start dashboard (8006) — internal only

## Reconcile local vs VPS

- [ ] Compare tearsheet output / NAV labels / data-current dates
- [ ] Run read-only reconciliation scripts
- [ ] Document any intentional differences

## Homepage migration

- [ ] Export SiteGround site to `C:\H&C\website\`
- [ ] Validate static assets and links
- [ ] Point `hughesandco.ltd` / `www` to VPS website root
- [ ] Do **not** link compliance-sensitive tear-sheet hostnames from homepage until approved

## Public cutover

- [ ] Final backup of laptop production data
- [ ] Switch DNS for tear-sheet hostnames to Cloudflare Tunnel
- [ ] Monitor health endpoints for 24–48 hours
- [ ] Freeze laptop production writes (or run parallel read-only)

## Rollback

- [ ] Keep laptop production running until VPS is proven stable
- [ ] DNS rollback: point hostnames back to prior targets
- [ ] Stop VPS NSSM services
- [ ] Restore data from `backups\` if VPS data was corrupted
