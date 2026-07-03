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

**Public cutover remains blocked** on Trading Universe, Investor Information / Terms & Fees (Step 11C), drawdown profile, and final mobile polish — but the **Step 11B shell** (gate, header, strategy, account stats, disclaimers, footer) is now restored in `feature/tcp-v2-public-shell`.

---

## Step 11B — Public shell restoration (2026-07-02)

**Branch:** `feature/tcp-v2-public-shell`  
**Base commit:** `b5fce4b`  
**Module:** `tcp_public_sections.py` (committed v1 copy; no workbook/JSON I/O)

### Reclassified sections

| Section | After Step 11B | Notes |
| ------- | -------------- | ----- |
| Accept gate / Important Notice | **MATCHES_V1** | Presentation-only session reveal; not admin auth |
| Header grey band + styling | **PRESENT_BUT_VISUALLY_DIFFERENT** | Grey `header-row` restored; preview banner remains above |
| Firm description / principals | **MATCHES_V1** | Committed v1 copy |
| NAV footnotes (2 paragraphs) | **MATCHES_V1** | Primary + percentage/entry-timing footnote |
| Strategy Overview (BTC/ETH) | **PRESENT_BUT_VISUALLY_DIFFERENT** | Description + core methodology rows; full v1 nested tables simplified |
| Account Stats (proprietary/client) | **MATCHES_V1** | Static `ACCOUNT_STATISTICS`; standalone card (not full Investor Information) |
| H&C / general disclaimer paragraphs | **MATCHES_V1** | Committed v1 wording |
| Important Disclosure panel | **MATCHES_V1** | Committed v1 inline copy (not untracked `tearsheet_disclosure.py`) |
| Footer contact | **MATCHES_V1** | Committed v1 `footer_contact` |
| Desktop two-column shell | **PRESENT_BUT_VISUALLY_DIFFERENT** | Strategy \| deferred column; metrics \| account stats |
| Trading Universe & Risk Profile | **MISSING_REQUIRED** | Deferred to Step 11C |
| Investor Information card | **MISSING_REQUIRED** | Deferred to Step 11C (Terms & Fees, tranche narrative) |
| Terms & Fees table | **MISSING_REQUIRED** | Deferred to Step 11C |
| Maximum Drawdown Profile | **MISSING_REQUIRED** | Deferred |
| Final mobile parity | **MISSING_REQUIRED** | Deferred to Step 11F |

### Revised completion estimates (post-11B)

| Area | Before 11B | After 11B |
| ---- | ---------: | --------: |
| Public content parity | 30% | **72%** |
| Visual parity | 25% | **58%** |
| Mobile parity | 40% | **48%** |
| **Entire project** | ~58% | **~68%** |

### Disclosure source

- **Used:** `git show b5fce4b:tcp_ts.py` (committed v1 wording via `tcp_public_sections.py`)
- **Not used:** untracked `tearsheet_disclosure.py` in dirty main checkout — defer newer wording for legal/operator review
- **Working-tree v1 delta:** main checkout `tcp_ts.py` modified locally; not used as Step 11B source

### Dynamic core (unchanged)

Monthly table, daily metrics, NAV chart, and current-date labels remain dynamic via `canonical-nav-store` / `propagate_tcp_dashboard`.

---

## Step 11C — Trading Universe and investor terms (2026-07-03)

**Branch:** `feature/tcp-v2-public-shell`  
**Prior commit:** `f975474`  
**Module extensions:** `tcp_public_sections.py` — `build_trading_universe()`, `build_investor_information()`, `TERMS_AND_FEES`

### Reclassified sections

| Section | After Step 11C | Notes |
| ------- | -------------- | ----- |
| Trading Universe & Risk Profile | **PRESENT_BUT_VISUALLY_DIFFERENT** | Committed v1 exchanges, products, risk, transaction fees; tooltips preserved |
| Investor Information card | **MATCHES_V1** | Terms & Fees + Account Stats + Other Notes in one card |
| Terms & Fees table | **MATCHES_V1** | Static `TERMS_AND_FEES` including Execution FCM |
| Account Stats (within investor card) | **MATCHES_V1** | Proprietary/client columns unchanged from v1 |
| Other Notes / tranche narrative | **MATCHES_V1** | $150k tranche / $300k nominal copy |
| Transaction fee footnote | **MATCHES_V1** | Committed StoneX give-up footnote in trading universe card |

### Review items (operator/legal)

| Item | Status |
| ---- | ------ |
| `$150,000` tranche / `$300,000` nominal in Other Notes vs `$50,000` account-stats display | **NEEDS_KEVIN_DECISION** — committed v1 has both; preserved for parity |
| StoneX in Terms & Fees and transaction footnote | Committed v1 — not from `tearsheet_disclosure.py` |
| Untracked `tearsheet_disclosure.py` | Still not used |

### Revised completion estimates (post-11C)

| Area | Before 11C | After 11C |
| ---- | ---------: | --------: |
| Public content parity | 72% | **88%** |
| Visual parity | 58% | **72%** |
| Mobile parity | 48% | **55%** |
| **Entire project** | ~68% | **~76%** |

### Still deferred (post-11C, pre-11D)

- Benchmark comparison
- Final chart/table styling (Step 11E)
- Final mobile acceptance (Step 11F)
- Production cutover (Step 11G)

---

## Step 11D — Dynamic Maximum Drawdown Profile (2026-07-03)

**Branch:** `feature/tcp-v2-public-shell`  
**Prior commit:** `e823032`  
**New module:** `tcp_drawdown.py` — pure baseline-relative worst-episode analysis

### Reclassified sections

| Section | After Step 11D | Notes |
| ------- | -------------- | ----- |
| Maximum Drawdown Profile card | **MATCHES_V1** | Heading, metric rows, TCP (Inception) column, footnote |
| Drawdown summary table | **MATCHES_V1** | Depth through End Date; display precision 0.1% |
| Drawdown dynamic refresh | **MATCHES_V1** | Via `canonical-nav-store` → `propagate_tcp_dashboard` |
| Drawdown chart | **N/A — not in committed v1 layout** | `build_drawdown_figure()` exists in v1 source but is not mounted publicly |

### Accepted methodology

| Item | Policy |
| ---- | ------ |
| Depth formula | `(nav - running_max) / baseline * 100` (baseline = first NAV) |
| Episode selection | Single worst drawdown only (committed v1) |
| NAV input for drawdown | US business-day `asfreq` + forward-fill on canonical ledger dates |
| Public NAV chart | Unchanged sparse ledger observations (no synthetic fill) |
| Durations | Calendar `.days` between business-day-filled index timestamps |
| Unrecovered end | `"TBD"`; recovery text `"Ongoing for N days"` |
| SPXTR column | Deferred to benchmark step (Step 11E+) |

### Workbook baseline (SHA-256 `1164a8cc…`, 112 rows)

| Metric | TCP (Inception) |
| ------ | --------------- |
| Depth | -10.4% |
| Decline Period | 148 days |
| Recovery Period | Ongoing for 0 days |
| Total Duration | Ongoing for 148 days |
| Start Date | 2026-01-27 |
| Valley Date | 2026-06-24 |
| End Date | TBD |

Add/Delete persistence updates drawdown through the same canonical NAV snapshot as monthly/daily/NAV outputs.

### Drawdown-chart decision

**A — Not required for v1 parity.** Committed v1 defines `build_drawdown_figure()` but does not mount it in the public layout. Table restoration is sufficient for this slice.

### Revised completion estimates (post-11D)

| Area | Before 11D | After 11D |
| ---- | ---------: | --------: |
| Public content parity | 88% | **94%** |
| Visual parity | 72% | **78%** |
| Mobile parity | 55% | **60%** |
| **Entire project** | ~76% | **~82%** |

### Still deferred

- Benchmark / SPXTR comparison column
- Drawdown chart (optional; not v1-public)
- Final chart/table styling polish (Step 11E)
- Final mobile acceptance (Step 11F)
- Production cutover (Step 11G)
