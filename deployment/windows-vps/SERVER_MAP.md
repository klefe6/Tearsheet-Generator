# Hughes & Company — Windows VPS Server Map

Primary reference for how the future Windows Server VPS will be organized.

**This is a layout contract, not a live deployment.** On the laptop, open the
visual preview at:

`deployment\windows-vps\filesystem-preview\HC\`

On the VPS (future), the same structure will exist at `C:\HC\`.

---

## Visual layout

```text
C:\HC\
│
├── apps\              SOURCE — replaceable from Git/deployment package
│   ├── tkp\           TKP Dash application (tkp_ts.py)
│   ├── tcp\           TCP Dash application (tcp_ts_v2.py)
│   ├── agm\           AGM / Momentum Pacer (mp_ts.py)
│   ├── yq\            Y&Q Dash application (yq_ts.py)
│   ├── dashboard\     Operator landing (Manager repo — external)
│   └── shared\        Cross-app Python modules, logos, static assets
│
├── data\              PERSISTENT — authoritative financial state (MUST BACK UP)
│   ├── tkp\           TKP state JSON + source workbook
│   ├── tcp\           TCP state JSON + source workbook + benchmark cache
│   ├── agm\           Manual rows JSON, fee workbook, pinned CSV, benchmarks
│   └── yq\            yq.csv (+ yq.xlsx monthly source)
│
├── config\            Non-secret runtime configuration
├── secrets\           Protected secret configuration (never commit values)
├── logs\              Runtime logs (rotate freely — not authoritative state)
│   ├── tkp\ tcp\ agm\ yq\ dashboard\
│   └── ingest\        Glenn uploader ingest audit JSONL
├── backups\           Local backup copies of data\ (copy off-server)
├── website\           hughesandco.ltd marketing/static site
└── deployment\        Scripts, manifests, runbooks (this folder on VPS)
```

---

## SOURCE vs PERSISTENT (the rule that matters)

| Label | Meaning | Examples | Backup? |
|-------|---------|----------|---------|
| **SOURCE / REPLACEABLE** | Application code; redeploy from Git | `apps\tkp\tkp_ts.py` | No |
| **PERSISTENT / MUST BACK UP** | Authoritative financial inputs and state | `data\tkp\daily_returns_secret_state.json` | **Yes** |
| **REGENERABLE** | Safe to rebuild | benchmark caches, most logs | Optional |
| **SECRETS** | Credentials and signing keys | `secrets\`, NSSM env | Yes (secure) |

**Never store authoritative production state inside `apps\`.**

---

## Application quick reference

| App | Code folder | Data folder | Public port | Staff port |
|-----|-------------|-------------|-------------|------------|
| TKP | `apps\tkp` | `data\tkp` | 8301 | 8321 |
| TCP | `apps\tcp` | `data\tcp` | 8302 | 8322 |
| Y&Q | `apps\yq` | `data\yq` | 8303 | — |
| AGM | `apps\agm` | `data\agm` | 8304 | 8324 |
| Dashboard | `apps\dashboard` | — | 8006 (internal) | — |

---

## Persistent files (authoritative)

| Program | File | Environment key |
|---------|------|-----------------|
| TKP | `data\tkp\daily_returns_secret_state.json` | `HC_TKP_STATE_PATH` |
| TKP | `data\tkp\tkp_source_workbook.xlsx` | `HC_TKP_SOURCE_WORKBOOK` |
| TCP | `data\tcp\tcp_daily_returns_secret_state.json` | `TCP_V2_STATE_PATH` |
| TCP | `data\tcp\tcp_alex.xlsx` | `TCP_V2_WORKBOOK_PATH` |
| AGM | `data\agm\momentum_pacer_manual_daily_rows.json` | `HC_AGM_MANUAL_STATE_PATH` |
| AGM | `data\agm\Momentum Fee Calculation.xlsx` | `HC_AGM_FEE_WORKBOOK` |
| AGM | `data\agm\data\daily_balances\balances_*.csv` | `HC_AGM_PINNED_CSV` |
| Y&Q | `data\yq\yq.csv` | `YQ_CSV_PATH` |
| Y&Q | `data\yq\yq.xlsx` | (manual monthly source) |

Full machine-readable list: `manifests\persistent-data-map.json`

---

## Future Windows services (NSSM — not installed yet)

| Service | Port | Role |
|---------|------|------|
| HC-TKP-Public | 8301 | Public tearsheet |
| HC-TCP-Public | 8302 | Public tearsheet |
| HC-YQ-Public | 8303 | Public tearsheet |
| HC-AGM-Public | 8304 | Public tearsheet |
| HC-TKP-Staff | 8321 | Staff/admin |
| HC-TCP-Staff | 8322 | Staff/admin |
| HC-AGM-Staff | 8324 | Staff/admin |
| HC-Dashboard | 8006 | Internal operator |

---

## Hostnames (future — not configured yet)

| Hostname | Target |
|----------|--------|
| hughesandco.ltd / www | Marketing homepage (`website\`) |
| tkp.hughesandco.ltd | localhost:8301 |
| tcp.hughesandco.ltd | localhost:8302 |
| yq.hughesandco.ltd | localhost:8303 |
| agm.hughesandco.ltd | localhost:8304 |
| admin-tkp.hughesandco.ltd | localhost:8321 (Cloudflare Access) |
| admin-tcp.hughesandco.ltd | localhost:8322 (Cloudflare Access) |
| admin-agm.hughesandco.ltd | localhost:8324 (Cloudflare Access) |

Compliance-sensitive public tear-sheet hostnames are **configured-for-future-use**
and **not approved for public homepage linking** until explicitly approved.

---

## How to recreate the empty layout

On the VPS (future):

```powershell
.\deployment\windows-vps\scripts\Initialize-HCServerLayout.ps1 -Root "C:\HC"
.\deployment\windows-vps\scripts\Test-HCServerLayout.ps1 -Root "C:\HC"
```

Environment template: `config-templates\hc-vps.env.example`
