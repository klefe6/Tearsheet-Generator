# TCP Daily Ledger Contract

**Document status:** Step 1 audit (investigation only)  
**Audit date:** 2026-07-01  
**Auditor:** Cursor agent (TCP v2 Step 1)  
**Workbook audited:** `tcp_alex.xlsx` → worksheet `NAV`  
**Workbook evidence:** Size 482,279 bytes; LastWriteTime 2026-07-01 13:42:14 (unchanged during audit)

---

## 1. Executive findings

### What TCP reads today — **CONFIRMED**

Production `tcp_ts.py` loads **only two columns** from the workbook:

- **Column C** — `Date`
- **Column L** — `nav-x1`

via `pd.read_excel(..., sheet_name="NAV", usecols="C,L")`. It does **not** load the full daily ledger (columns A–Q).

### What the workbook contains — **CONFIRMED**

The `NAV` sheet holds a **full daily ledger** (columns A–Q) with formulas linking Cash Balance, NLV, P&L, fees, NAV per unit, loss carry, cumulative return, and HWM. As of audit:

- Last data row (scan of C/L): **114**
- Pandas rows after dropping all-blank rows: **113**
- Rows with `nav-x1` populated: **112**
- Date-only rows (date present, `nav-x1` empty): **1** (Excel row 2, inception seed 2026-01-19)
- Date range with NAV: **2026-01-20** through **2026-06-24**

### What appears to drive daily calculations — **STRONG INFERENCE**

The administrator’s practical daily input is **`Cash Balance` (column E)**, not NLV directly.

Evidence:

- `$PL` is derived from day-over-day **Cash Balance** change minus the **previous row’s** `Cash Transfers` value.
- `NLV` is formula-driven: prior NLV + current `$PL` + current `Cash Transfers`.
- `nav-x1` is formula-driven from prior `nav-x1`, net day P&L, and the **`#` (unit/tranche count, column G)**.

NLV moves in lockstep with the reconstructed chain (0 mismatches across rows 4–114).

### Major discrepancies — **CONFIRMED**

| Topic | Finding |
| ----- | ------- |
| **Baseline constant** | `BASELINE_AMOUNT = 150000` is defined in `tcp_ts.py` but **never referenced**. All return math uses `baseline = NAV_df[NAV_col].iloc[0]` (~**$50,000**). |
| **Public copy vs code** | Marketing/account stats refer to **$50,000** per tranche; code constant 150000 is dead. |
| **Monthly overrides** | `override_months` for 2025-04 and 2025-10 are copied from TKP; **no TCP ledger months match** → overrides have **zero effect** on current TCP data. |
| **Auto transfer detection** | `AUTO_DETECT_CASH_TRANSFERS = True` scans for **≥$50k NAV jumps** in column L. Workbook uses explicit `Cash Transfers` column; **no NAV jump ≥$50k exists** → detection finds **0 transfers** and does not alter production NAV. |
| **TKP formula parity** | TKP `_compute_new_row()` uses StoneX balance, HWM-based loss carry, and `BASELINE_AMOUNT` for `%Net`. TCP workbook uses different column names, fee trigger (prior **Loss Carry** not HWM), unit divisor `#`, and **$50,000** anchor cell `L$3` / `U6`. |

### Unresolved — requires Kevin confirmation

- Whether daily entry should remain **Cash Balance** or switch to **NLV** for TCP v2 Add Row UX.
- Intended meaning and future use of **`#` (unit count)** when adding a second tranche (G: 1→2 on deposit row 16).
- Whether **`BASELINE_AMOUNT = 150000`** should be deleted, wired up, or was a TKP copy-paste artifact.
- Whether TCP v2 should include TKP-style **hidden admin gate** (TCP production currently has **no** admin editor).
- Full **HWM (column Q)** formula behavior on tranche changes (workbook formula is complex; partial validation only).

---

## 2. Source inventory

| Source | Path | Role | Mutated during audit? |
| ------ | ---- | ---- | --------------------- |
| TCP production app | `Tearsheet Generator/tcp_ts.py` | Loads C+L only; static dashboard at startup | No |
| TKP reference app | `Tearsheet Generator/tkp_ts.py` | Full ledger + JSON + callbacks (reference only) | No |
| Shared disclosures | `Tearsheet Generator/tearsheet_disclosure.py` | PROPRIETARY tier for TCP/TKP | No |
| TCP launch script | `Tearsheet Generator/reboot_tcp_ts.bat` | Runs `python tcp_ts.py` on port 8302 | No |
| Manager config | `Manager/service_config.py` | TCP Tearsheet → port 8302, `reboot_tcp_ts.bat` | No |
| Service dashboard | `HomePage/debug.py` | TCP URL, reboot bat, port 8302 | No |
| Cloudflare tunnel | `Manager/cloudflare_tunnel_config.yaml` | `tcp-ts.hcresearch.ltd` → localhost:8302 | No |
| TCP workbook | `...\1. Tearsheet Project\TCP\tcp_alex.xlsx` | Authoritative ledger source | No (read-only) |
| TKP JSON state | `Tearsheet Generator/daily_returns_secret_state.json` | TKP operating ledger (TKP only) | No |
| Runtime workaround copy | `Tearsheet Generator/tcp_ts_runtime_launch.py` | Patched-path launcher (not used by `reboot_tcp_ts.bat`) | No |
| Runtime workaround copy | `Tearsheet Generator/_runtime/tcp_ts_launch.py` | Patched-path launcher (not used by production bat) | No |
| Runtime workbook copy | `Tearsheet Generator/_runtime/tcp_alex_runtime.xlsx` | Snapshot when source locked (not used by production bat) | No |
| This document | `Tearsheet Generator/docs/tcp_daily_ledger_contract.md` | Step 1 artifact | **Created** |

---

## 3. Current TCP data flow

```text
tcp_alex.xlsx (NAV sheet)
    ↓ pd.read_excel: columns C (Date) + L (nav-x1) only
    ↓ Drop invalid dates; drop duplicate dates
    ↓ Keep rows where nav-x1 is non-empty (ACTUAL_LAST_DATE = last such row)
    ↓ asfreq(US business day calendar)
    ↓ forward-fill NAV gaps
    ↓ AUTO_DETECT_CASH_TRANSFERS on nav-x1 (≥$50k jumps) → currently finds none
    ↓ baseline = first nav-x1 value (~$50,000)
    ↓ daily_returns = nav.diff() / baseline
    ↓ monthly_simple = (month_end_nav - month_start_nav) / baseline
    ↓ override_months applied (2025-04, 2025-10) → no effect on 2026 ledger
    ↓ benchmarks via yfinance (at startup)
    ↓ drawdown / perf metrics computed at startup
    ↓ serve_layout() bakes tables + NAV chart into HTML
    ↓ dynamic_layout() re-calls serve_layout() but does NOT reload workbook or recompute
```

**CONFIRMED:** Refreshing the browser does **not** pick up workbook changes. Only process restart reloads data.

**CONFIRMED:** `reboot_tcp_ts.bat` invokes `tcp_ts.py` directly (not runtime launcher copies).

**CONFIRMED:** If workbook is open/locked in Excel, startup fails with permission error (no automatic fallback in production bat).

---

## 4. Column contract

Workbook header row mapping (row 1). Column **M** has no header in row 1 (gap between L and N).

| Column | Excel col | Input/calculated | Formula or evidence | Format | Confidence | Open question |
| ------ | --------- | ---------------- | ------------------- | ------ | ---------- | ------------- |
| Cash Transfers | A | Manual (transfer days) | Value on row 2 (+25000 inception) and row 16 (+25000 deposit). Positive = deposit. **No negative transfers in ledger.** | Currency | **CONFIRMED** | Withdrawal sign convention untested |
| Trading Days | B | Calculated | Sequential counter from 0 (row 2) then 1…130 | Integer | **CONFIRMED** | Behavior on row delete |
| Date | C | Manual | Row 2 = 2026-01-19 (seed); trading from 2026-01-20 | Date | **CONFIRMED** | — |
| — | D | — | Placeholder/em dash header | — | **CONFIRMED** | — |
| Cash Balance | E | **Manual daily input** | `$PL` uses ΔCash Balance | Currency | **STRONG INFERENCE** | Confirm with operator |
| NLV | F | Calculated | `=F{r-1}+H{r}+A{r}` (0 mismatches rows 4–114) | Currency | **CONFIRMED** | — |
| # | G | Calculated / event-driven | Values `{1, 2}`; **1→2 on row 16** (deposit). Scales `nav-x1` and `%Net` denominators | Integer | **CONFIRMED** | How to set on Add Row |
| $PL | H | Calculated | `=(E{r}-E{r-1})-A{r-1}` (2 edge rows at deposit; see §7) | Currency | **CONFIRMED** | — |
| Inc. Fee | I | Calculated | `=IF(H{r}>N{r-1},(H{r}-N{r-1})*U$10,0)`; **U10 = 0.2** | Currency | **CONFIRMED** | Fee base is prior Loss Carry, not HWM |
| cumm fee | J | Calculated | `=I{r}+J{r-1}` (row 3: `=I3`) | Currency | **CONFIRMED** | — |
| Day PnL | K | Calculated | Row 3: `0`; row 4+: `=(H{r}-I{r})` | Currency | **CONFIRMED** | — |
| nav-x1 | L | Calculated | Row 3: `=U6` (**U6=50000**); row 4+: `=L{r-1}+(H{r}-I{r})/G{r}` (0 mismatches) | Currency | **CONFIRMED** | — |
| (empty) | M | — | No header | — | **CONFIRMED** | — |
| Loss Carry | N | Calculated | `=MAX(0,Q{r-1}-L{r})` (validated rows 10, 16, 17) | Currency | **CONFIRMED** | — |
| %Net | O | Calculated | G=1: `=(H-I)/L$3`; G≥2: `=(H-I)/(L$3*G)` (validated) | Decimal % | **CONFIRMED** | Display vs decimal |
| S net cummulative % | P | Calculated | Row 3–4: `=O{r}`; row 5+: `=O{r}+P{r-1}` | Decimal % | **STRONG INFERENCE** | Exact row-3 edge |
| HWM | Q | Calculated | `=MAX(L$3:L{r})` early rows; later rows use tranche-blend formula when G changes | Currency | **STRONG INFERENCE** | Full tranche-change formula |

### Hidden parameter cells (workbook) — **CONFIRMED**

| Cell | Value | Role |
| ---- | ----- | ---- |
| `U6` | 50000 | Initial `nav-x1` anchor (row 3) |
| `U10` | 0.2 | Performance fee rate (20%) |
| `U5` | 25000 | Appears in row 5 computed context (nominal reference) |
| `U6` (row 6) | 50000 | Second nominal reference row |

### Formula read mode — **CONFIRMED**

- `tcp_ts.py` uses `pd.read_excel(..., engine="openpyxl")` without `data_only` — reads **cached calculated values**, not formula text.
- Audit used `openpyxl` with `data_only=False` to inspect formulas and `data_only=True` to validate computed chains.

---

## 5. Calculation-chain reconstruction

Apparent order for a new trading row **r** (r ≥ 4), based on validated formulas:

```text
1. Administrator enters: Date (C), Cash Balance (E), optional Cash Transfers (A)
2. Trading Days (B) increments
3. # (G) may increment on deposit (observed 1→2 when A=25000 on row 16)
4. $PL (H) = (Cash Balance[r] - Cash Balance[r-1]) - Cash Transfers[r-1]
5. Inc. Fee (I) = IF($PL[r] > Loss Carry[r-1], ($PL[r] - Loss Carry[r-1]) * 0.2, 0)
6. cumm fee (J) = Inc. Fee[r] + cumm fee[r-1]
7. Day PnL (K) = $PL[r] - Inc. Fee[r]
8. nav-x1 (L) = nav-x1[r-1] + Day PnL[r] / #[r]
9. Loss Carry (N) = MAX(0, HWM[r-1] - nav-x1[r])
10. %Net (O) = Day PnL[r] / (L$3 * #[r])   [equivalently (H-I)/(L$3*G)]
11. S net cummulative % (P) = %Net[r] + prior cumulative (pattern varies row 3–4)
12. HWM (Q) = f(nav-x1, #[r], prior HWM) — complex on tranche change
13. NLV (F) = NLV[r-1] + $PL[r] + Cash Transfers[r]
```

**Row 3 (first trading day)** is a special case: `Day PnL = 0`, `nav-x1` seeded from `U6` (=50000), fee=0.

**Row 2 (2026-01-19)** is inception seed: Cash Transfer +25000, no `nav-x1`; excluded from website NAV series.

**Confidence:** Steps 4–9 are **CONFIRMED** by zero mismatches on historical replay. Step 12 (HWM on tranche change) is **STRONG INFERENCE** / partially validated.

---

## 6. Baseline analysis

| Value | Where it appears | Used in production math? |
| ----- | ---------------- | ------------------------ |
| **~$50,000** | `U6`, first `nav-x1` (row 3), account stats, chart copy, drawdown footnote | **Yes** — `baseline = NAV_df[nav-x1].iloc[0]` drives daily returns, monthly returns, drawdown denominator |
| **$150,000** | `BASELINE_AMOUNT` constant in `tcp_ts.py` | **No** — defined line 62 only; never referenced |
| **$300,000** | `NOMINAL_ASSETS` constant | **No** — not referenced in calculations |
| **$50,000 / $100,000** | TCP marketing copy (tranche / IB minimum) | Display only |

**CONFIRMED:** Website percentage math is anchored to **first NAV (~$50k)**, not $150k.

**CONFIRMED:** Workbook `%Net` uses **`L$3` (= $50,000)** and divisor `#` (unit count), not `BASELINE_AMOUNT`.

**UNRESOLVED:** Whether `BASELINE_AMOUNT = 150000` should be removed or repurposed in TCP v2.

---

## 7. Cash-transfer analysis

### Explicit ledger transfers — **CONFIRMED**

| Excel row | Date | Cash Transfers | Effect |
| --------- | ---- | -------------- | ------ |
| 2 | 2026-01-19 | +25,000 | Inception funding; no `nav-x1` |
| 16 | 2026-02-06 | +25,000 | Second tranche; `#` 1→2; `nav-x1` denominator doubles |

**Sign convention (observed):** Positive = deposit. **No withdrawal rows exist.**

### How transfers interact with `$PL` — **CONFIRMED**

- `$PL` subtracts **previous row’s** transfer, not current row’s: `=(E{r}-E{r-1})-A{r-1}`.
- Current row’s transfer flows into **NLV** via `F{r}=F{r-1}+H{r}+A{r}`.
- On deposit row 16, same-day transfer is **not** subtracted from `$PL` (explains the 25,000 gap in naive check).

### `AUTO_DETECT_CASH_TRANSFERS` — **CONFIRMED**

- Scans consecutive `nav-x1` values for |Δ| ≥ **$50,000**.
- Current ledger: **0 qualifying jumps** (deposit is handled in column A; NAV changes gradually).
- Production effect today: **none** (logs “No cash transfers detected”).

**STRONG INFERENCE:** Auto-detection is TKP-era machinery and is **redundant** for the current TCP workbook model. It could become harmful if a legitimate >$50k NAV move occurred without a matching column-A transfer.

---

## 8. Monthly-override analysis

```python
override_months = {
    pd.Period('2025-04', freq='M'): 4.58,
    pd.Period('2025-10', freq='M'): 0.58,
}
```

| Question | Answer | Confidence |
| -------- | ------ | ---------- |
| Where applied? | After `monthly_simple` computed in `tcp_ts.py` | **CONFIRMED** |
| TCP ledger months | 2026-01 through 2026-06 only | **CONFIRMED** |
| Overrides match any TCP month? | **No** | **CONFIRMED** |
| Predate TCP inception (Jan 2026)? | **Yes** | **CONFIRMED** |
| Effect on current production | **Zero** | **CONFIRMED** |

**STRONG INFERENCE:** Copied from TKP template; safe to omit in TCP v2 unless future 2026 overrides are requested.

---

## 9. TCP versus TKP implementation differences

| Area | TCP (production) | TKP (production) | Copy impact |
| ---- | ---------------- | ---------------- | ----------- |
| Workbook | `tcp_alex.xlsx` / `NAV` | `tkp_alex_old1.xlsx` / `Sheet1` | Must re-map columns |
| Load scope | C + L only | A–S full ledger + C+N for NAV | Major |
| Operating state | None (Excel + restart) | `daily_returns_secret_state.json` (plain array) | TCP needs separate file |
| Admin UI | **None** | Hidden “e” + Daily Returns editor | TCP v2 must add |
| Callbacks | 1 (disclaimer) | ~18 | Major port |
| `propagate_dashboard` | **Absent** | Updates monthly table, daily perf, NAV chart, last-updated labels only | Partial live refresh |
| Dynamic drawdown/benchmarks | Static at startup | Static at startup | Same limitation |
| Add Row inputs | N/A | StoneX balance, Plus500, Deposit | TCP needs Cash Balance + Transfer |
| Row calculator | N/A | `_compute_new_row()` (StoneX/HWM/BASELINE 150k) | **Cannot copy verbatim** |
| Record shape | N/A | Display names (`StoneX`, `Perc. Net`, …) | Prefer TCP display names |
| Cash transfer handling | Auto NAV jump detection (inactive) | Similar code + explicit Deposit column in ledger | TCP ledger already has column A |
| Gate | Accept only | Accept + hidden admin trigger | Product decision |
| Layout | Stacked | Side-by-side toggle | UI preservation |
| Public daily table | **Absent** | Present (collapsible) | Product decision |
| `% axis on chart` | **Absent** | `SHOW_PERCENTAGE_AXIS = True` | Product decision |
| Account stats | Proprietary **and** Client columns | Proprietary only | Must preserve TCP |
| `BASELINE_AMOUNT` | Defined 150k, **unused** | 150k, **used** in TKP calculator | Do not assume parity |
| `override_months` | Present, inert | Present, may affect TKP history | TCP-specific cleanup |

---

## 10. TCP UI preservation inventory

Future TCP v2 should explicitly decide keep/change for each item.

| Behavior | TCP today | Notes |
| -------- | --------- | ----- |
| Layout | Stacked (`dbc.Row` / two-column cards) | No `USE_SIDE_BY_SIDE_LAYOUT` |
| Strategy title | “The Crypto Program” | TKP says “The Keymaker Program” |
| Inception copy | “January 2026” | Matches workbook |
| Products | Bitcoin & Ethereum Options | TCP-specific |
| Account stats | **Proprietary + Client** dual columns | Unique to TCP |
| Nominal copy | $50k tranche / $100k IB minimum | Matches workbook anchor |
| Chart subtitle | “$50,000 investment” | Aligns with L$3/U6 |
| `SHOW_PLACEHOLDERS` | Flag exists, default False | TKP has no equivalent |
| Public Daily Returns table | **Not present** | TKP has collapsible table |
| NAV chart `% axis` | **Not present** | TKP optional right axis |
| Admin / secret editor | **Not present** | TKP only |
| Access gate | `tearsheet_disclosure.proprietary_gate_children("TCP")` | PROPRIETARY tier |
| Gate trigger | “Accept & Continue” only | No hidden admin letter |
| `DEBUG_PROVENANCE` | Flag exists, default False | Optional debug table |
| Mobile header | Separate Last Updated layout | Present |
| Drawdown footnote | “$50,000 fixed nominal exposure” | Uses runtime baseline |
| Disclaimer blocks | `hcdisclaimer_text` + standard disclaimer | TCP-specific proprietary notice |

---

## 11. Golden-row candidates

For future `compute_tcp_row()` tests. Excel row numbers are 1-indexed (row 1 = header).

| # | Excel row | Date | Scenario | Prior row | Manual inputs (apparent) | Key outputs | Uncertainty |
| - | --------- | ---- | -------- | --------- | ------------------------ | ----------- | ----------- |
| 1 | 4 | 2026-01-21 | Profitable day, no transfer, fee charged | Row 3 | Cash Balance 25013.60 | $PL 16.84, Fee 3.37, NAV 50013.47 | Low |
| 2 | 7 | 2026-01-26 | Losing day, loss carry begins | Row 6 | Cash Balance drop | $PL -177.16, Loss Carry 177.16, NAV 49855.10 | Low |
| 3 | 16 | 2026-02-06 | **Deposit** (+25000), tranche `#` 1→2 | Row 15 | Cash Transfer 25000, Cash Balance 48442.72 | $PL 1542.76, NAV 47660.38, G=2 | Medium (HWM formula) |
| 4 | 17 | 2026-02-09 | Post-deposit normal day (prior transfer on row 16) | Row 16 | Cash Balance 48690.88 | $PL 248.16 after subtracting A15=25000 | Low |
| 5 | 8 | 2026-01-27 | Recovery toward HWM | Row 7 | Cash Balance 25244.09 | NAV 50056.79 = HWM | Low |
| 6 | 10 | 2026-01-29 | Under HWM, loss carry > 0 | Row 9 | Loss day | Loss Carry 576.17, NAV 49480.62 | Low |
| 7 | 4 | 2026-01-21 | Fee-trigger day | Row 3 | $PL > prior Loss Carry (0) | Fee = 20% × $PL | Low |
| 8 | 3 | 2026-01-20 | First trading day edge case | Row 2 | Cash Balance 24996.76 | Day PnL 0, NAV 50000 from U6 | Medium |
| 9 | 114 | 2026-06-24 | Latest production row | Row 113 | Cash Balance 43007.30 | NAV 44871.38 | Low |
| 10 | 6 | 2026-01-23 | Small P&L / rounding | Row 5 | Small balance change | Day PnL 0.752 | Low |

**Withdrawal scenario:** **Not available** — no negative `Cash Transfers` in ledger.

**Recovery from loss carry with fee:** Row 8+ when NAV approaches but formulas still use Loss Carry in fee gate — needs dedicated test during calculator implementation.

---

## 12. Decision register

| Decision | Current evidence | Status | Recommended direction | Must Kevin confirm? |
| -------- | ---------------- | ------ | --------------------- | ------------------- |
| Primary daily balance input | Cash Balance (E) drives $PL; NLV is derived | **STRONG INFERENCE** | Add Row enters **Cash Balance** + optional **Cash Transfers** | **Yes** |
| Whether Cash Balance must be entered | Always populated on trading rows | **CONFIRMED** | Required for calculator | No |
| Transfer sign convention | Positive = deposit only observed | **CONFIRMED** for deposits | Document + confirm withdrawal sign | **Yes** (withdrawals) |
| Fee formula | 20% × max(0, $PL − prior Loss Carry) when $PL > prior LC | **CONFIRMED** | Implement TCP-specific; do not copy TKP HWM fee gate | No |
| HWM behavior | Tracks peak NAV; complex on `#` change | **STRONG INFERENCE** | Replay workbook formulas row-by-row | **Yes** (tranche changes) |
| Loss carry | MAX(0, prior HWM − current NAV) | **CONFIRMED** | Implement as workbook | No |
| Baseline for website returns | First NAV ≈ $50k | **CONFIRMED** | Use $50k; remove or ignore 150k constant | **Yes** |
| Monthly overrides | Inert on 2026 data | **CONFIRMED** | Omit for TCP v2 unless requested | Optional |
| Automatic transfer detection | No effect today | **CONFIRMED** | **Disable** for TCP v2; rely on column A | Recommended |
| Public Daily Returns table | Absent in TCP | **CONFIRMED** | Decide whether v2 adds TKP feature | **Yes** |
| Initial live-refresh scope | TKP refreshes 4 outputs only | **CONFIRMED** | Match TKP scope first; drawdown static | No |
| Production admin authentication | Neither tearsheet has real auth | **CONFIRMED** | Plan auth before exposing v2 editor | **Yes** |
| Unit count `#` on deposit | Auto 1→2 on row 16 | **CONFIRMED** | Calculator must increment on tranche deposit | **Yes** (business rules) |

---

## 13. Risks and blockers

### Financial-correctness blockers

- TCP workbook formulas **≠** TKP `_compute_new_row()` — blind copy will produce wrong fees/NAV.
- **HWM on tranche change** not fully reverse-engineered.
- **No withdrawal history** to validate negative transfer behavior.
- Row 3 first-trading-day edge case must be handled explicitly.

### Data-migration risks

- Production reads **2 of 17** ledger columns — seeding JSON must use **full** ledger.
- `pandas` reads cached values; stale Excel cache if workbook not recalculated before save.
- Separate JSON path required so TKP state is not corrupted.

### UI-preservation risks

- Cloning TKP may drop **Client** account-stat column and stacked layout.
- TCP gate has **no** admin entry — adding TKP “secret e” is new surface area.

### Deployment risks

- Port 8302 wired in bat, Manager, debug.py, Cloudflare — v2 preview needs **separate port**.
- Runtime launcher copies in repo may confuse operators if not documented.

---

## 14. Recommended next step

**Step 2 only:** Create isolated `tcp_ts_v2.py` shell + `tcp_config.py` with correct absolute workbook path, **separate preview port**, and **no formula logic** — placeholder/read-only bootstrap. Do not implement row calculator or JSON persistence until Step 2 exit gate is met.

---

## Appendix A — Bugs documented (not fixed)

1. `BASELINE_AMOUNT = 150000` is **dead code** in `tcp_ts.py`.
2. `override_months` references **2025** months copied from TKP; **no effect** on TCP 2026 ledger.
3. `NOMINAL_ASSETS = 300000` appears unused in calculations.
4. `AUTO_DETECT_CASH_TRANSFERS` is **misleading** for TCP’s explicit transfer column model (inactive but enabled).

## Appendix B — Audit methodology

- Repository files read directly.
- Workbook inspected via read-only `openpyxl` (formula + cached value) and `pandas.read_excel`.
- Formula validation scripts run in memory; no saves to workbook.
- Temporary audit script created and **deleted** before completion.
