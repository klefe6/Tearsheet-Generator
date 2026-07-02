# TCP v1 → v2 Public Website UI Parity Audit (Step 11A)

**Date:** 2026-07-02  
**Branch:** `feature/tcp-v2-migration`  
**Prior commit:** `7de8ba1` (Step 10 acceptance)  
**Audit type:** Read-only code and layout inventory  
**Cutover planning:** **PAUSED** until public UI parity is addressed

---

## Executive verdict

```text
Backend complete but public UI incomplete — not suitable for public cutover
```

TCP v2 has a mature financial engine, JSON persistence, admin mutations, and a validated dynamic core (monthly table, daily metrics, NAV chart, date labels). The public preview on port **8312** appears visually sparse because large static/content sections from TCP v1 were intentionally deferred after Step 7.

Production cutover runbooks and preflight work (Step 11) remain **locally present and uncommitted**, labeled:

```text
CUTOVER WORK — PAUSED UNTIL UI PARITY
```

---

## Completion estimates

| Area | Completion | Notes |
| ---- | ---------: | ----- |
| Financial engine | **95%** | Ledger, calculator, replay, Excel parity validated |
| Persistence / admin | **90%** | JSON atomic edits, auth, recovery matrix passed |
| Dynamic dashboard core | **85%** | Monthly, daily metrics, NAV, labels — methodology diffs documented |
| Public content parity | **30%** | Core performance blocks only; most narrative/legal cards missing |
| Visual parity | **25%** | Header band, two-column layout, cards, footers absent |
| Mobile parity | **40%** | Date labels responsive; overall page structure not equivalent |
| Deployment readiness | **15%** | Blocked on UI parity + GitHub/parent integration |
| **Entire project** | **~58%** | Prior ~90% estimate over-weighted backend |

---

## Comparison baselines

| Item | Value |
| ---- | ----- |
| TCP v1 reference | `git HEAD:tcp_ts.py` (SHA-256 `83a1252646411f65d7ccad49e1c65ac676f3003be8730bcb8f2b5f83d5bf26dd`) |
| TCP v1 working tree | Modified locally (SHA-256 `d8b768fcd0f5c7f57064fb81ec560245ff65ed8ae27128c3565f6d2c94330f43`); adds `tearsheet_disclosure` integration — **not** committed HEAD |
| TCP v2 inspected | Working tree `tcp_ts_v2.py` at branch `7de8ba1` + uncommitted bind-port helper (Step 11 paused) |
| TCP v2 preview state | Revision 1 JSON, 112 rows, latest `2026-06-24` (preview only) |
| Ports used for audit | Code inspection primary; v2 preview **8312** when running; v1 compare port **8313** not required for this audit |
| Deployed production v1 | **Not positively identified** — HEAD used as rollback baseline |

### Screenshot evidence

Full-page screenshots at desktop/tablet/mobile viewports were **not committed**. Structural evidence is from layout source markers (`scripts/audit_tcp_public_ui.py`). Optional capture path for a future visual acceptance pass:

```text
_audit/screenshots/   (gitignored — do not commit without approval)
```

---

## Why the v2 preview looks empty

v2 `build_preview_layout()` renders:

1. Preview warning banner  
2. Minimal header (logo, firm name, dynamic date labels)  
3. Mode/recovery alert  
4. NAV chart + one footnote  
5. Monthly performance table  
6. Daily metrics card  
7. Preview-only runtime diagnostics + hidden admin shell  

v1 `serve_layout()` additionally renders **~70% more public content**: accept gate, firm description, strategy overview, trading universe, drawdown profile, investor information (terms/fees/account stats), inline disclaimers, disclosure panel, and footer — in a two-column card layout with grey header band.

---

## Section inventory

| Section | v1 (HEAD) | v2 | Classification | Cutover blocker | Effort |
| ------- | --------- | -- | -------------- | --------------: | -----: |
| Accept gate / Important Notice | Yes | No | MISSING_REQUIRED | Yes | M |
| Header grey band + styling | Yes | Partial | PRESENT_BUT_VISUALLY_DIFFERENT | Yes | M |
| Firm description / principals | Yes | No | MISSING_REQUIRED | Yes | S |
| Dynamic date label | Yes (`Last Updated`) | Yes (`Data current to`) | PRESENT_BUT_BEHAVIORALLY_DIFFERENT | No | S |
| NAV chart | Yes | Yes | PRESENT_BUT_BEHAVIORALLY_DIFFERENT | No | M |
| NAV footnotes (2 paragraphs) | Yes | Partial (1) | MISSING_REQUIRED | Yes | S |
| Monthly performance | Yes | Yes | PRESENT_BUT_BEHAVIORALLY_DIFFERENT | No | S |
| Strategy Overview (BTC/ETH copy) | Yes | No | MISSING_REQUIRED | Yes | L |
| Trading Universe & Risk Profile | Yes | No | MISSING_REQUIRED | Yes | L |
| Daily performance metrics | Yes | Yes | PRESENT_BUT_BEHAVIORALLY_DIFFERENT | No | S |
| Maximum Drawdown Profile table | Yes | No | MISSING_REQUIRED | Yes | L |
| Investor Information card | Yes | No | MISSING_REQUIRED | Yes | M |
| Account Stats (proprietary/client) | Yes | No | MISSING_REQUIRED | Yes | M |
| Terms & Fees table | Yes | No | MISSING_REQUIRED | Yes | M |
| H&C / general disclaimer paragraphs | Yes | No | MISSING_REQUIRED | Yes | S |
| Important Disclosure panel | Yes | No | MISSING_REQUIRED | Yes | M |
| Footer contact | Yes | No | MISSING_REQUIRED | Yes | S |
| Drawdown chart (Plotly) | Code only | No | MISSING_OPTIONAL | No | M |
| Benchmark NAV trace | No in layout | No | NEEDS_KEVIN_DECISION | No | M |
| Public Daily Returns table | No | No | MATCHES_V1 | No | S |
| Preview banner / diagnostics | No | Yes | INTENTIONAL_V2_IMPROVEMENT | No | S |
| Admin editor (hidden) | No | Yes | INTENTIONAL_V2_IMPROVEMENT | No | M |

---

## Missing required sections (detail)

### Access and notices
- **v1:** Session gate (`Important Notice` + Accept) hides main content until click; proprietary tier copy.
- **v2:** No gate; preview banner and JSON mode alert visible immediately.
- **Impact:** Legal/UX regression for public site.

### Strategy and investor content
- **Strategy Overview:** Long-form BTC/ETH options narrative + methodology checklist tables.
- **Trading Universe & Risk Profile:** Exchanges, products, margin, fees, risk controls with tooltips.
- **Investor Information:** Terms & Fees rows, Account Stats with **proprietary vs client** columns, tranche narrative.

### Risk / drawdown
- **Maximum Drawdown Profile:** Table comparing TCP vs SPXTR (inception); uses yfinance benchmark data at v1 startup.
- **Drawdown chart:** `build_drawdown_figure()` exists in v1 source but is **not mounted** in public layout — confirm product need.

### Legal / footer
- Inline disclaimer paragraphs and bottom **Important Disclosure** panel.
- Footer contact line (NFA ID, address, phone, web).

---

## Existing matched / partial sections

| Section | Status |
| ------- | ------ |
| Product name “The Crypto Program” | MATCHES_V1 |
| Hughes & Company LLC header title | MATCHES_V1 (styling differs) |
| NAV investment footnote (primary) | MATCHES_V1 |
| Performance Summary heading + table | Present; v2 dynamic vs v1 static |
| Performance Metrics card | Present; methodology differs (sparse vs asfreq) |
| No public Daily Returns table | MATCHES_V1 (absent in both) |
| No percentage NAV axis | MATCHES_V1 (absent in both) |

---

## Behavior and callback map

| Section | v1 refresh | v1 data source | v2 refresh | v2 data source |
| ------- | ---------- | -------------- | ---------- | -------------- |
| Gate | Callback on click | Static copy | N/A | N/A |
| Header date | Static at startup | Workbook latest | Dynamic | Canonical NAV / JSON |
| NAV chart | Static at startup | Workbook C+L | Dynamic | Canonical NAV |
| Monthly table | Static at startup | Workbook-derived | Dynamic | `recompute_tcp_monthly_performance` |
| Daily metrics | Static at startup | `daily_returns` asfreq | Dynamic | Sparse ledger returns |
| Strategy cards | Static | Hard-coded HTML | Missing | N/A |
| Drawdown table | Static at startup | NAV + SPXTR downloads | Missing | Deferred |
| Account stats | Static | `ACCOUNT_STATS` | Missing | N/A |
| Disclosures | Static | Inline / module (WT) | Missing | N/A |
| Admin | N/A | N/A | Auth routes | JSON mutations |

**After Add/Delete:** v2 dynamic core already refreshes from canonical NAV; static v1-style cards would remain stale unless rebuilt or kept intentionally static.

---

## Kevin decisions

| Topic | Recommendation | Blocks cutover? |
| ----- | -------------- | --------------- |
| Sparse ledger dates vs v1 business-day fill | Accept v2 methodology | No |
| Public Daily Returns table | Keep absent | No |
| Percentage NAV axis | Keep absent | No |
| Drawdown table dynamic vs restart-static | **Needs decision** | Yes (if required) |
| Drawdown chart (unused in v1 layout) | **Needs decision** | No unless required |
| Benchmark presentation (SPXTR) | **Needs decision** | Yes (if required on page) |
| Accept gate on production v2 | Restore v1 behavior | Yes |
| Export feature | Deferred | No |
| `Last Updated` vs `Data current to` wording | **Needs decision** | No |

---

## Recommended implementation sequence

Do **not** implement in this step. Suggested slices:

| Step | Scope |
| ---- | ----- |
| **11B** | Full TCP public shell: header band, description, strategy overview, disclosures, footer; remove preview-only chrome for production path |
| **11C** | Trading Universe & Investor Information (terms/fees, proprietary/client account stats) |
| **11D** | Drawdown profile table (+ Kevin decision on dynamics and SPXTR dependency) |
| **11E** | Chart/table styling and two-column layout parity |
| **11F** | Mobile/responsive acceptance |
| **11G** | Visual acceptance screenshots + resume Step 11 cutover preflight |

---

## Paused Step 11 artifacts (not committed)

| Path | Label |
| ---- | ----- |
| `scripts/tcp_cutover_preflight.py` | CUTOVER WORK — PAUSED |
| `scripts/preflight_tcp_cutover.py` | CUTOVER WORK — PAUSED |
| `tests/test_tcp_cutover_preflight.py` | CUTOVER WORK — PAUSED |
| `docs/tcp_production_cutover_runbook.md` | CUTOVER WORK — PAUSED |
| `docs/tcp_production_rollback_runbook.md` | CUTOVER WORK — PAUSED |
| `docs/tcp_release_checklist.md` | CUTOVER WORK — PAUSED |
| `tcp_config.py` (bind-port helpers) | CUTOVER WORK — PAUSED |
| `tcp_ts_v2.py` (bind-port only) | CUTOVER WORK — PAUSED |
| `.gitignore` (Step 11 entries) | CUTOVER WORK — PAUSED |

---

## Audit tooling

```bash
.\.venv310\Scripts\python.exe scripts\audit_tcp_public_ui.py
.\.venv310\Scripts\python.exe -m pytest tests/test_tcp_public_ui_parity.py -q
```

---

## Production-readiness verdict

**Public cutover remains blocked.** Backend and admin layers are production-grade; the public tearsheet is not yet a visual or functional replacement for TCP v1.
