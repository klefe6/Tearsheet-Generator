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
| Drawdown table | Dynamic from canonical NAV | NAV + SPXTR via `tcp_benchmarks` | **MATCHES_V1** (Step 11D/11E) |
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
| Benchmark presentation (SPXTR) | **MATCHES_V1** (drawdown column) | No — degraded gracefully if provider unavailable |
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

- Final chart/table styling (Step 11F)
- Final mobile acceptance (Step 11G)
- Production cutover (Step 11H)

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
| SPXTR column | **MATCHES_V1** (Step 11E) | `SPXTR (Inception)` in drawdown table when provider ready/stale |

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

- Drawdown chart (optional; not v1-public)
- Final chart/table styling polish (Step 11F)
- Final mobile acceptance (Step 11G)
- Production cutover (Step 11H)

*(Benchmark comparison restored in Step 11E — see below.)*

---

## Step 11E — SPXTR benchmark comparison (2026-07-03)

**Branch:** `feature/tcp-v2-public-shell`  
**Prior commit:** `9281a7a`  
**New module:** `tcp_benchmarks.py`

### Reclassified sections

| Section | After Step 11E | Notes |
| ------- | -------------- | ----- |
| SPXTR drawdown column | **MATCHES_V1** | `SPXTR (Inception)` in Maximum Drawdown Profile table |
| Benchmark NAV chart traces | **N/A — not in committed v1 public layout** | AGG/GLD/BTC/ETH only in unmounted drawdown figure helper |
| Daily/monthly SPXTR columns | **N/A — not in committed v1** | v1 daily metrics are TCP-only |
| Benchmark failure handling | **INTENTIONAL_V2_IMPROVEMENT** | v1 crashes if `bench_ret["SPXTR"]` missing; v2 degrades gracefully |

### Accepted benchmark contract

| Item | Policy |
| ---- | ------ |
| Public benchmark | **SPXTR only** (`^SP500TR` via quantstats `utils.download_returns`) |
| Provider | quantstats / yfinance stack (committed v1) |
| Alignment | `reindex(nav_bd_index).ffill().bfill().dropna()` |
| SPXTR NAV | `(1 + returns).cumprod() * strategy_baseline` from inception |
| SPXTR drawdown | quantstats-style `(nav/running_max - 1) * 100` |
| TCP drawdown | unchanged baseline-relative (Step 11D) |
| NAV chart | TCP only — no benchmark trace added |

### Data strategy

**A — Live bounded fetch (10s) with last-known-good disk cache** at `_runtime/tcp_benchmark_cache.json`.

| Status | Behavior |
| ------ | -------- |
| `ready` | Fresh fetch succeeded; as-of date shown |
| `stale` | Fetch failed; cached returns shown with explicit stale label |
| `unavailable` | No fetch and no cache; TCP-only drawdown column; warning banner |

Rejected: frozen snapshot for cutover (live+cache matches v1 startup intent with safer failure); startup-only memory (no stale recovery).

### Provider normalization (live fix, 2026-07-03)

Committed v1 uses quantstats `utils.download_returns`, which can surface pandas `DataFrame` or MultiIndex payloads from yfinance. TCP v2 adds `normalize_provider_returns()` as the single boundary:

| Input | Behavior |
| ----- | -------- |
| `Series` | Accepted after `to_numeric`, inf/NaN drop, sort, dedupe |
| One-column `DataFrame` | Reduced to that column deterministically |
| yfinance MultiIndex | Selects `Adj Close`/`Close` for requested symbol when unambiguous |
| Ambiguous multi-column | `BenchmarkNormalizationError` → unavailable/stale fallback |
| Duplicate dates | **keep_first** |
| ±inf / NaN | Dropped; empty result → unavailable |

No scalar boolean checks on Series-valued cells; no raw provider tracebacks on the public page.

### External-data cutover note

Benchmark comparison is **not a hard cutover blocker** if stale cache or unavailable state is acceptable to operators; Kevin should confirm whether live SPXTR is required on day-one cutover vs stale-tolerant display.

### Revised completion estimates (post-11E)

| Area | Before 11E | After 11E |
| ---- | ---------: | --------: |
| Public content parity | 94% | **97%** |
| Visual parity | 78% | **82%** |
| Mobile parity | 60% | **63%** |
| Deployment readiness | 15% | **22%** |
| **Entire project** | ~82% | **~86%** |

### Still deferred (post-11E, pre-11F)

- Dedicated mobile/responsive acceptance (Step 11G)
- Production cutover (Step 11H)

### Remaining visual/mobile limitations (post-11E, pre-11F)

- Drawdown/benchmark table column widths and header wrapping are functional but not final-polished at 390px.
- Full-page mobile screenshots still require scroll-to-section validation; no dedicated responsive acceptance pass yet.
- Preview-only runtime diagnostics banner remains above the public shell.
- Do **not** mark final styling, mobile acceptance, or cutover complete from Step 11E alone.

---

## Step 11F — Desktop visual parity (2026-07-03)

**Branch:** `feature/tcp-v2-public-shell`  
**Prior commit:** `806bd1a`  
**Presentation modules:** `assets/styles.css`, `tcp_public_sections.py`, `tcp_ts_v2.py`, `tcp_dashboard.py` (axis label only)

### Desktop canary results

| Viewport | Result | Notes |
| -------- | ------ | ----- |
| **1440 px** | **PASS** | Gate/header hierarchy, two-column rows, monthly/daily/NAV/drawdown/benchmark/footer all visible; no page-level overflow |
| **1280 px** | **PASS** | Two-column balance retained; NAV chart container 900px centered; monthly table readable; no clipping |
| **1024 px** | **PASS** | Transitional layout usable; account-stats Proprietary/Client distinct; disclosures/footer present; no horizontal overflow |

Benchmark **ready** state observed live (`SPXTR source: quantstats. Data as of 2026-07-02.`). Unavailable/stale styling classes validated in unit tests (`tcp-benchmark-notice-*`).

### Reclassified desktop styling

| Area | After Step 11F | Classification |
| ---- | -------------- | -------------- |
| Page shell / `#page-container` | v1 stylesheet wired (`/assets/styles.css`); 90% width, max 90rem | **MATCHES_V1** |
| Header grey band | `header-row` + `bg-light` preserved | **MATCHES_V1** |
| Two-column cards | `tcp-two-column-row` with equal-height lg columns | **PRESENT_BUT_VISUALLY_DIFFERENT** (preview banner above) |
| Public cards | Shared `tcp-public-card` padding/shadow/header band | **MATCHES_V1** |
| Monthly performance table | Grey headers, 95% width, pos/neg cell classes | **MATCHES_V1** |
| Daily metrics card | `tcp-daily-metrics-table` + grey card header | **MATCHES_V1** |
| NAV chart | `chart-container` max 900px; y-axis **Value Added Daily Index** | **MATCHES_V1** |
| Drawdown profile | Grey card header, `tcp-drawdown-table`, footnote | **MATCHES_V1** |
| Benchmark notice | Distinct ready/stale/unavailable classes | **INTENTIONAL_V2_IMPROVEMENT** |
| Account statistics | Proprietary/Client columns unchanged | **MATCHES_V1** |
| Disclosures/footer | Panel + footer spacing preserved | **MATCHES_V1** |
| Preview diagnostics card | Subordinate opacity (`tcp-runtime-diagnostics-card`) | **INTENTIONAL_V2_IMPROVEMENT** |

### Validation evidence

| Suite | Result | Duration |
| ----- | ------ | --------: |
| `tests/test_tcp_desktop_visual_parity.py` | **22 passed** | 305.94s |
| Step 11F focused regression group | **286 passed, 1 skipped** | 675.25s |
| Full `pytest tests` | **Deferred** to final branch-integration gate (presentation-only slice) |

Structural contracts: `tests/test_tcp_desktop_visual_parity.py` (22 tests, no pixel screenshots).

### Remaining desktop gaps

- Preview-only banner still visible above public shell (intentional for 8312).
- Runtime diagnostics card remains at page bottom (preview only).
- Fine-grained v1 print/PDF styling not re-audited.

### Remaining mobile-specific issues (not Step 11F)

- No dedicated 390px acceptance pass (Step 11G).
- Drawdown/benchmark column wrapping at narrow widths not final-polished.
- Full-page mobile screenshots still require scroll-to-section validation.

### Revised completion estimates (post-11F)

| Area | Before 11F | After 11F |
| ---- | ---------: | --------: |
| Public content parity | 97% | **97%** |
| Desktop visual parity | 82% | **94%** |
| Mobile parity | 63% | **63%** |
| Deployment readiness | 22% | **28%** |
| **Entire project** | ~86% | **~89%** |

### Still deferred

- Dedicated mobile/responsive acceptance (Step 11G)
- Final complete integration suite + branch integration
- Production cutover (Step 11H)

---

## Step 11G-access — Access flow and shared Daily Values (`feature/tcp-v2-access-daily-values`)

**Date:** 2026-07-03  
**Base:** `f0005c9` (`feature/tcp-v2-public-shell`)

### TKP reference behavior (audited)

| Behavior | TKP |
| -------- | --- |
| Gate title | “Important Notic” + clickable **e** (`secret-notice-e`) |
| **e** click | Sets `access-mode: secret` and reveals a secret admin Daily Returns table |
| Accept | Reveals public site; public collapsed Daily Returns at page bottom |
| Public Daily Returns | Read-only columns: `#Day`, `Date`, `NAV`, `Perc. Net`, `$PL`, `HWM`, `Fee (20%)` |
| Admin logout | Not separately audited in TKP shell for this slice |

### TCP v2 behavior (intentional differences)

| Behavior | TCP v2 |
| -------- | ------ |
| Gate title | “Important Notice” — inline clickable **e** (`secret-notice-e`, baseline-aligned) |
| **e** click | Redirects to `/admin/login` — does **not** grant admin by itself |
| Accept | Reveals public site + shared Daily Values (read-only); stores acceptance in session `public-gate-accepted-store` |
| Admin login | Flask session (`tcp_v2_admin_authenticated`); reveals public page without second Accept |
| Daily Values | Single `tcp-daily-values-table` from canonical runtime snapshot |
| Admin toolbar | Add Row / Delete Last Row in `tcp-daily-values-admin-toolbar` (hidden unless authenticated) |
| Logout | Clears Flask admin session; if public accepted, remains in read-only public mode |

**Security not copied from TKP:** TCP does not expose a client-side “secret mode” table or URL tokens. Admin authorization is server-side only; public Accept is presentation-only.

### Daily Values contract

| Item | Detail |
| ---- | ------ |
| Position | Bottom of public content, before disclosure panel and footer |
| Canonical source | `RuntimeSnapshot.records` → `ledger_records_to_rows` → `project_public_daily_rows` |
| Public columns | `#`, `Date`, `NAV`, `%Net`, `$PL`, `HWM`, `Inc. Fee` |
| Public permissions | Read-only DataTable, pagination, native sort, row count + latest date summary |
| Admin controls | Same table + Add/Delete modals (existing server-side validation) |
| Synchronization | `admin-state-revision-store` refresh updates table; successful Add/Delete updates canonical NAV store and dashboard outputs |

### Mobile placement

Daily Values card uses `overflowX: auto` on the table. Gate **e** and Accept remain usable at ~390px; admin toolbar stacks with Bootstrap buttons.

### Validation evidence

Focused pytest group:

```text
tests/test_tcp_access_daily_values.py
tests/test_tcp_public_shell.py
tests/test_tcp_admin.py
tests/test_tcp_v2_shell.py
tests/test_tcp_runtime_state.py
```

Browser canary on port **8312** with disposable JSON state and admin token (production **8302** untouched).

---

## Step 11G — Mobile and responsive acceptance (`feature/tcp-v2-mobile-acceptance`)

**Date:** 2026-07-03  
**Base:** `7a377d9` (`feature/tcp-v2-access-daily-values`)

### Viewports tested

| Viewport | Use |
| -------- | --- |
| 375 × 812 | Small phone — gate, login, toolbar, modals |
| 390 × 844 | Primary phone — full scroll pass |
| 430 × 932 | Large phone |
| 768 × 1024 | Tablet portrait |
| 834 × 1112 | Tablet landscape |
| 844 × 390 | Phone landscape — gate, modals, charts |

### Responsive contract

| Area | Behavior |
| ---- | -------- |
| Page overflow | `overflow-x: hidden` on `html`, `body`, `.tcp-public-root`, `#page-container` |
| Table overflow | `.tcp-table-scroll` — internal horizontal scroll for monthly, daily metrics, drawdown, Daily Values, trading universe, strategy overview |
| Card stacking | Bootstrap `width=12 lg=6` two-column rows stack below `lg` |
| Charts | `autosize=True`, reduced margins, `automargin` axes; container `max-width: 900px` |
| Gate | Fixed overlay; 95vw panel; **e** touch target ≥ 44px (`.tcp-gate-secret-e`) |
| Admin toolbar | `.tcp-admin-toolbar` flex-wrap |
| Modals | `.tcp-admin-modal` — max-height viewport, internal body scroll |
| Login | Viewport meta + 16px inputs (no iOS zoom) |
| Footer | `.tcp-public-footer-wrap` word wrap |

### Section results (summary)

| Section | Mobile result |
| ------- | ------------- |
| Gate / Accept / **e** | MATCHES_ACCEPTED_BEHAVIOR |
| Header / shell | MATCHES_ACCEPTED_BEHAVIOR |
| Strategy / Trading / Investor | INTENTIONAL_HORIZONTAL_SCROLL where 3-col tables need it |
| Account stats / Terms | MATCHES_ACCEPTED_BEHAVIOR |
| Monthly performance | INTENTIONAL_HORIZONTAL_SCROLL |
| Daily metrics / Drawdown | INTENTIONAL_HORIZONTAL_SCROLL |
| NAV chart | MATCHES_ACCEPTED_BEHAVIOR |
| Benchmark ready/stale/unavailable | MATCHES_ACCEPTED_BEHAVIOR |
| Daily Values | MATCHES_ACCEPTED_BEHAVIOR |
| Admin toolbar / modals | MATCHES_ACCEPTED_BEHAVIOR |
| Disclosures / footer | MATCHES_ACCEPTED_BEHAVIOR |

### Modal test contract (corrected)

Admin modals (`tcp-admin-modal`) are **not** present in the initial public `app.layout`. They are built from `tcp_admin.py` and injected into `admin-editor-container` only after authenticated login. Tests validate:

- `className=ADMIN_MODAL_CLASS` on modal builders in `tcp_admin.py`
- Built modal components serialize with `tcp-admin-modal`
- CSS max-height / internal scroll rules in `assets/styles.css`

### Validation evidence

| Suite | Result | Duration |
| ----- | ------ | --------: |
| `tests/test_tcp_mobile_responsive.py` | **29 passed** | 382.13s |
| `tests/test_tcp_admin.py` + access + public_shell | **120 passed** | 316.06s |
| Focused Step 11G group | **324 passed** | 1082.73s |

Focused pytest files:

```text
tests/test_tcp_mobile_responsive.py
tests/test_tcp_access_daily_values.py
tests/test_tcp_desktop_visual_parity.py
tests/test_tcp_public_shell.py
tests/test_tcp_public_content.py
tests/test_tcp_benchmarks.py
tests/test_tcp_drawdown.py
tests/test_tcp_admin.py
```

Browser canary on port **8312** (disposable JSON only). Production **8302** untouched.

### Remaining responsive gaps

- Preview diagnostics card still visible at page bottom (preview only).
- Fine-grained print/PDF layout not re-audited.
- Pixel-perfect screenshot baselines not committed.

### Revised completion estimates (post-11G)

| Area | Before 11G | After 11G |
| ---- | ---------: | --------: |
| Public content parity | 97% | **97%** |
| Desktop visual parity | 94% | **94%** |
| Mobile parity | 63% | **88%** |
| Deployment readiness | 28% | **38%** |
| **Entire project** | ~89% | **~91%** |

### Still deferred

- Integration branch merge (public-shell + access + mobile)
- One complete full-suite gate
- Production cutover (Step 11H)

