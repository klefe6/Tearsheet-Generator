# TCP v2 Implementation Plan

## TKP Architecture + TCP Data, Calculations, UI, and Wording

## Final architectural decision

Build a new **`tcp_ts_v2.py`** using TKP’s proven dynamic architecture, but preserve TCP’s existing product identity and explicitly implement TCP-specific calculations.

Run TCP v2 beside the current TCP application until financial, functional, and visual parity is verified.

```text
Current production TCP
tcp_ts.py
Port 8302
        │
        │ remains unchanged during development
        │
        ├───────────────┐
        │               │
        ▼               ▼
TCP v1 production   TCP v2 preview
port 8302           port 8312
                    tcp_ts_v2.py
```

Cutover will use the repository’s existing batch-file and fixed-port deployment model:

1. Preserve TCP v1 as `tcp_ts_v1.py`.
2. Make the accepted v2 implementation the production `tcp_ts.py`.
3. Continue serving production on port 8302.
4. Keep TCP v1 available for immediate rollback.

Do not create a new environment-based version-switching system unless later justified.

---

# 1. Project objectives

TCP v2 must provide the useful operating behavior currently available in TKP:

* Full daily ledger
* Website-based Add Row workflow
* TCP-specific automatic calculations
* Durable JSON persistence
* Delete Last Row
* Excel export
* Immediate NAV-chart refresh
* Immediate monthly-performance refresh
* Immediate daily-performance refresh
* Immediate “data current through” refresh
* No daily Excel editing
* No process restart after a website entry

It must also preserve TCP-specific behavior and presentation:

* TCP strategy wording
* BTC/ETH-related copy
* TCP proprietary and client account-stat columns
* TCP disclosures and access-gate wording
* TCP placeholder behavior where still required
* TCP stacked layout unless intentionally redesigned
* Existing TCP public-facing statistics and labels

---

# 2. Scope boundaries

## Included in the initial release

* Separate TCP v2 application
* TCP configuration module
* TCP full-ledger Excel adapter
* Versioned TCP JSON state
* Atomic writes and backup recovery
* TCP row calculator
* Golden-row tests
* Dynamic monthly table
* Dynamic daily performance table
* Dynamic NAV chart
* Dynamic current-date labels
* Admin ledger
* Add Row
* Delete Last Row
* Calculation preview
* Excel export
* Server-side admin authorization before production
* Preview deployment on port 8312
* Reversible production cutover on port 8302

## Not included initially

* Refactoring TKP into shared modules
* Changing TKP behavior
* Automatically writing website changes back into the source Excel workbook
* Rebuilding every benchmark and drawdown output dynamically
* Changing Cloudflare configuration during preview
* Adding TCP v2 to Manager before the local preview is stable
* Dependence on stale runtime artifacts such as:

  * `tcp_ts_runtime_launch.py`
  * `_runtime/tcp_ts_launch.py`
  * `_runtime/tcp_alex_runtime.xlsx`

## Initial live-refresh scope

Match what TKP actually updates today:

* Monthly performance container
* Daily performance container
* NAV graph
* Desktop current-date label
* Mobile current-date label

Drawdown tables, benchmark comparisons, and other startup-derived statistics must be audited separately. They may remain static until restart in the initial release, provided this is clearly documented.

---

# 3. Proposed file structure

Use paths under the existing application directory:

```text
Tearsheet Generator/
├── tcp_ts.py
├── tcp_ts_v1.py                  # created at cutover
├── tcp_ts_v2.py
├── tkp_ts.py
├── tcp_config.py
├── tcp_calculations.py
├── tcp_state.py
├── tearsheet_disclosure.py
├── tcp_daily_returns_secret_state.json
├── tcp_daily_returns_secret_state.backup.json
│
├── docs/
│   ├── tcp_v2_implementation_plan.md
│   ├── tcp_daily_ledger_contract.md
│   ├── tcp_ui_preservation_checklist.md
│   ├── tcp_parity_report.md
│   └── tcp_cutover_runbook.md
│
├── scripts/
│   └── seed_tcp_state.py
│
└── tests/
    ├── test_tcp_excel_adapter.py
    ├── test_tcp_calculations.py
    ├── test_tcp_state.py
    └── test_tcp_dashboard_recompute.py
```

Do not move or rename the existing production files during early development.

---

# 4. Internal record-shape decision

For the first implementation, use **TCP’s existing display-column names internally**.

Examples:

```text
Cash Transfers
Trading Days
Date
Cash Balance
NLV
$PL
Inc. Fee
cumm fee
Day PnL
nav-x1
Loss Carry
%Net
S net cummulative %
HWM
```

This is intentionally less abstract than a snake-case canonical model, but it minimizes changes across the TKP-derived callbacks and DataTable code.

A canonical internal translation layer may be introduced during a later shared-engine refactor.

---

# 5. Phase 0 — Establish the TCP business contract

## Objective

Determine the correct financial and data behavior before implementing the row calculator.

## Required investigation

Inspect:

* `tcp_ts.py`
* `tkp_ts.py`
* `tcp_alex.xlsx`
* TCP’s `NAV` worksheet
* Existing formulas in historical rows
* Existing TCP production calculations
* Existing TKP row-calculation implementation

## Decisions that must be documented

### 5.1 Primary daily input

Determine whether the administrator enters:

* NLV only
* Cash Balance only
* NLV and Cash Balance

Likely candidate:

```text
Primary balance input: NLV
External capital input: Cash Transfers
```

This must be proven against historical rows rather than assumed.

### 5.2 Cash-transfer semantics

Define:

* Whether deposits are positive
* Whether withdrawals are negative
* Whether transfers affect `$PL`
* Whether transfers affect NAV independently
* Whether `AUTO_DETECT_CASH_TRANSFERS` remains necessary

Preferred target:

```text
Cash Transfers is an explicit ledger input.
Automatic transfer inference is removed from the new daily-entry path.
```

Automatic detection may remain temporarily for historical compatibility only if evidence requires it.

### 5.3 Gross P&L

Candidate formula:

```text
Gross P&L =
Current NLV
- Previous NLV
- Current Cash Transfer
```

Confirm this against historical rows.

### 5.4 Fee behavior

Document:

* Fee percentage
* Fee-trigger condition
* High-water-mark behavior
* Loss-carry behavior
* Fee rounding
* Whether `Inc. Fee` means current-day fee or something else
* How `cumm fee` is calculated
* Whether fees are accrued or deducted immediately

### 5.5 NAV and net-return behavior

Document exact formulas for:

* `Day PnL`
* `nav-x1`
* `Loss Carry`
* `%Net`
* `S net cummulative %`
* `HWM`

### 5.6 Baseline discrepancy

Resolve:

```text
BASELINE_AMOUNT = $150,000
versus
displayed TCP account amount = $50,000
```

Document separate concepts if both are intentional:

* Nominal assets traded
* Initial NAV
* Return denominator
* Chart baseline
* Public account-stat copy

Do not silently make every value $50,000 or $150,000.

### 5.7 Monthly overrides

Audit:

```text
2025-04 → 4.58%
2025-10 → 0.58%
```

TCP’s inception wording reportedly begins in January 2026, making these overrides suspicious.

Each override must be:

* Removed
* Corrected
* Or explicitly documented with evidence

### 5.8 Actual-last-date behavior

Preserve or replace the behavior that identifies the final row containing a real NAV value rather than merely the final dated Excel row.

Document:

* Which columns determine a completed row
* How partially prepared Excel rows are ignored
* How the JSON ledger determines its current date

### 5.9 Public daily-returns table

Decide whether TCP v2 should include TKP’s collapsible public Daily Returns table.

Recommended initial decision:

```text
Do not add it automatically.
Preserve current TCP public UI unless specifically approved.
```

## Deliverable

Create:

```text
Tearsheet Generator/docs/tcp_daily_ledger_contract.md
```

The document must distinguish:

* Confirmed behavior
* Evidence
* Recommended behavior
* Unresolved decision
* Production compatibility concern

## Exit gate

At least seven representative historical rows can be explained from the workbook formulas and prior-row values without unexplained material differences.

---

# 6. Phase 0.5 — Establish test infrastructure

## Objective

Create a minimal pytest harness before financial implementation.

## Tasks

* Add `Tearsheet Generator/tests/`
* Confirm how tests are run from the repository
* Create fixtures for historical TCP rows
* Add smoke tests for importing calculation and state modules
* Avoid importing and launching the Dash server during unit tests

## Initial command

```text
python -m pytest "Tearsheet Generator/tests" -q
```

Adjust to the repository’s real Python environment where necessary.

## Exit gate

The empty/scaffolded test suite runs successfully and can import isolated TCP modules without starting the application.

---

# 7. Phase 1 — Create an isolated TCP v2 foundation

## Objective

Create a safe preview foundation without affecting TCP or TKP production.

## Files

Create:

```text
Tearsheet Generator/tcp_ts_v2.py
Tearsheet Generator/tcp_config.py
reboot_tcp_ts_v2.bat
```

## Required configuration

`tcp_config.py` must contain:

* Absolute TCP workbook path
* `sheet_name = "NAV"`
* TCP JSON state path
* TCP backup-state path
* TCP export filename
* Preview port 8312
* Production port 8302
* `debug = False`
* TCP-specific labels and titles
* Read-only preview flag during the foundation phase

## Safety requirements

Before the preview is started:

* Replace all TKP workbook references
* Replace all TKP JSON references
* Replace all TKP export filenames
* Replace all TKP app names
* Disable Add Row
* Disable Delete Last Row
* Disable all JSON writes
* Do not write to Excel
* Do not change `reboot_tcp_ts.bat`
* Do not change Cloudflare
* Do not change port 8302
* Do not change Manager or HomePage debug configuration
* Do not change `tkp_ts.py`

## Preview behavior

The first preview may use the current TCP Date/NAV read path if necessary.

It does not yet need the full editor or correct TCP calculator.

It must be clearly marked:

```text
TCP v2 Preview — Read Only
```

## Exit gate

* TCP v1 still works unchanged on port 8302.
* TCP v2 starts locally on port 8312.
* TCP v2 runs with `debug=False`.
* No TKP workbook or state path is reachable from TCP v2.
* No data mutation is possible.
* Existing TCP and TKP files remain unchanged.

---

# 8. Phase 2 — Implement the full TCP Excel adapter

## Objective

Load the complete TCP ledger rather than only Date and NAV.

## Tasks

* Read the `NAV` worksheet.
* Load all required ledger columns.
* Implement TCP-specific last-row detection.
* Handle date-only and partially complete rows.
* Preserve source precision before display formatting.
* Sort and validate records.
* Preserve TCP display column names.
* Generate DataTable records and column definitions.
* Rebuild canonical Date/NAV records from the full ledger.

## Path behavior

Keep the actual absolute Windows workbook path in configuration.

Do not introduce an incorrect relative-path assumption.

## Excel safety

The application must read the workbook only.

It must not save, modify, lock, or reformat the workbook.

## Tests

Verify:

* Imported row count
* First date
* Last completed date
* Initial NLV
* Final NLV
* Initial NAV
* Final NAV
* Handling of blank trailing rows
* Handling of date-only rows
* Handling of currency-formatted cells
* Handling of percentage cells

## Exit gate

The normalized ledger matches the source workbook row-for-row for all required columns.

---

# 9. Phase 3 — Implement TCP JSON state

## Objective

Make JSON the authoritative working ledger after initial migration.

## State format

TCP v2 should use a versioned envelope even though TKP currently uses a plain array:

```json
{
  "schema_version": 1,
  "app": "tcp",
  "revision": 1,
  "updated_at": "2026-07-02T12:00:00-04:00",
  "source": "excel_bootstrap",
  "records": []
}
```

## Source precedence

```text
Valid TCP JSON
    ↓
Use JSON

No valid TCP JSON
    ↓
Read TCP Excel
```

Do not merge Excel and JSON automatically.

## Write behavior

Use:

* Full-state validation
* Temporary file
* Flush and fsync where supported
* Atomic replacement
* Last-known-good backup
* Process/file lock
* Revision check
* Structured logging

## Recovery

If the active JSON is invalid:

1. Preserve the invalid file.
2. Log the validation failure.
3. Try the backup.
4. Use Excel only when no valid JSON or backup exists.
5. Show an admin warning.

## Tests

* JSON round-trip
* Invalid schema rejection
* Atomic write
* Backup creation
* Backup recovery
* State revision increment
* Stale-revision rejection
* TCP/TKP state isolation

## Exit gate

A seeded TCP state survives browser refresh and service restart without relying on a changed Excel workbook.

---

# 10. Phase 4 — Implement the TCP row calculator

## Objective

Calculate TCP rows using verified TCP formulas rather than renamed TKP formulas.

## Module boundary

Create:

```python
compute_tcp_row(previous_row, entry, rules)
```

in:

```text
Tearsheet Generator/tcp_calculations.py
```

The function must not depend on Dash state or UI components.

## Candidate entry fields

* Date
* NLV
* Cash Transfers
* Cash Balance only if required
* Optional administrative note only if the ledger supports it

Do not include StoneX or Plus500 fields.

## Golden scenarios

Test at least:

1. Profitable day without transfer
2. Losing day without transfer
3. Deposit
4. Withdrawal
5. New high-water mark
6. Existing loss carry
7. Loss carry recovery
8. Fee-trigger day
9. No-fee day below high-water mark
10. Rounding boundary

## Full-ledger replay

Starting from the accepted seed row:

1. Feed each historical row’s actual input fields into `compute_tcp_row`.
2. Reconstruct the remaining calculated fields.
3. Compare against Excel.
4. Produce a discrepancy report.

## Acceptance tolerance

* Currency: normally exact to $0.01
* Percentages: accepted workbook precision
* Dates and trading-day count: exact
* No unexplained compounding drift

## Exit gate

All golden cases pass and full-ledger replay has no unexplained material difference.

This is the project’s hardest financial-correctness gate.

---

# 11. Phase 5 — Implement dynamic dashboard propagation

## Objective

Port the proven TKP state-propagation pattern while limiting initial scope to outputs TKP genuinely updates.

## Data flow

```text
TCP secret-data-store
        ↓
canonical-nav-store
        ↓
TCP dashboard recomputation
        ↓
monthly table
daily performance table
NAV chart
current-date labels
```

## Initial dynamic outputs

* `monthly-calendar-container`
* `daily-perf-container`
* `NAV-graph`
* `data-current-label-desktop`
* `data-current-label-mobile`

## Static-output audit

Create a matrix for:

* Max drawdown table
* Drawdown graph
* Benchmark columns
* Account statistics
* Placeholder values
* Public daily-returns output
* Other startup-built components

Classify each as:

```text
A — Updates immediately in v2
B — Updates after restart in v2 initial release
C — External data with separate refresh rules
D — Hard-coded product copy
```

Do not claim an output updates dynamically unless tested.

## Exit gate

Appending a valid in-memory test row updates all five required dynamic outputs from one canonical state snapshot.

---

# 12. Phase 6 — Adapt the admin editor

## Objective

Provide the TCP daily operating workflow.

## Required functionality

* Enter admin mode
* View full TCP ledger
* Add Row
* Preview calculations
* Confirm Save
* Delete Last Row
* Confirm deletion
* Select visible columns
* Paginate ledger
* Export Excel
* Show state source
* Show state revision
* Show last successful write
* Return to public mode

## Add Row workflow

1. Open modal.
2. Enter TCP inputs.
3. Validate inputs.
4. Calculate proposed row server-side.
5. Display every calculated field.
6. Confirm.
7. Acquire state lock.
8. Verify expected state revision.
9. Append row.
10. Write state atomically.
11. Increment revision.
12. Update canonical NAV.
13. Refresh required dashboard outputs.
14. Display saved date, NAV, and revision.

## Delete workflow

Initially permit deletion of the final row only.

Before deletion:

* Show the full final row.
* Require confirmation.
* Create a backup.
* Record the action.
* Verify state revision.

## Authorization

During early localhost preview, the hidden TKP-style trigger may be retained for convenience.

Before production cutover, require a server-side shared tearsheet admin token or equivalent authenticated session.

The hidden character must not be treated as production authorization.

## Exit gate

A nontechnical administrator can complete the daily workflow without Excel or a restart.

---

# 13. Phase 7 — Preserve TCP UI and apply TCP wording

## Objective

Prevent a functional TKP clone from unintentionally replacing TCP’s identity.

## Preservation checklist

Verify:

* Stacked TCP layout
* Proprietary and client account-stat columns
* BTC/ETH strategy copy
* TCP inception copy
* TCP chart titles
* TCP placeholders
* TCP disclosures
* Proprietary disclosure tier
* Existing access-gate copy
* Existing mobile layout
* Existing public table visibility
* Existing statistic labels

## Repository search

Search for accidental remnants:

```text
TKP
tkp
StoneX
Plus500
tkp_alex_old1
daily_returns_secret_state.json
Sheet1
FORCE_LAST_EXCEL_ROW
```

Every remaining result in TCP v2 must be justified.

Also inspect shared:

```text
tearsheet_disclosure.py
```

to confirm TCP still receives the intended proprietary disclosure behavior.

## Exit gate

No unintended TKP-specific data field, workbook, account name, calculation term, or public wording remains.

---

# 14. Phase 8 — Seed the TCP state

## Script

Create:

```text
Tearsheet Generator/scripts/seed_tcp_state.py
```

## Required modes

```text
--dry-run
--output
--replace-existing
--expected-row-count
```

## Migration behavior

* Read the configured TCP workbook.
* Normalize the full ledger.
* Validate chronology.
* Validate required fields.
* Validate final completed row.
* Build the versioned state envelope.
* Report summary and checksum.
* Refuse to overwrite existing state without an explicit flag.
* Back up existing state before replacement.

## Exit gate

The seeded state exactly represents the accepted TCP workbook ledger.

---

# 15. Phase 9 — Three-way parity validation

TCP parity is not a simple v1-versus-v2 comparison.

Compare three sources:

| Source                  | Purpose                                                |
| ----------------------- | ------------------------------------------------------ |
| TCP Excel ledger        | Financial row source of truth                          |
| Existing TCP production | Current visible behavior, including possible overrides |
| TCP v2 preview          | New intended behavior                                  |

## Required comparisons

### Ledger

* Row count
* Dates
* Transfers
* NLV
* Cash Balance
* Gross P&L
* Fee
* Cumulative fee
* Net P&L
* NAV
* Loss carry
* HWM
* Daily return
* Cumulative return

### Dashboard

* Final NAV
* Total return
* Monthly returns
* Sharpe ratio
* Win rate
* Best day
* Worst day
* Current date
* NAV chart points

### Known-difference log

Every difference between v1 and v2 must be classified as:

```text
Bug fixed
Intentional behavior change
Legacy override removed
Baseline correction
Formatting-only difference
Unresolved blocker
```

Create:

```text
Tearsheet Generator/docs/tcp_parity_report.md
```

## Exit gate

There are no unexplained differences.

---

# 16. Phase 10 — Preview and parallel operation

## Preview infrastructure

Use:

```text
tcp_ts_v2.py
port 8312
debug=False
reboot_tcp_ts_v2.bat
```

Keep preview local initially.

Only add Manager or Cloudflare preview configuration after the application is stable and only if remote review is necessary.

## Mutation canary

1. Back up state.
2. Add a controlled test row.
3. Verify all dynamic outputs.
4. Refresh the browser.
5. Restart TCP v2.
6. Verify persistence.
7. Open a second browser.
8. Verify the same row.
9. Export Excel.
10. Delete the row.
11. Confirm exact restoration.

## Parallel daily run

For at least one real update cycle:

* Update the existing accepted TCP process.
* Enter the equivalent input in TCP v2.
* Compare results.
* Record differences.

## Exit gate

TCP v2 survives a complete realistic daily cycle without affecting TCP v1.

---

# 17. Phase 11 — Production cutover

## Pre-cutover

* Freeze Excel updates.
* Back up the workbook.
* Back up TCP v1.
* Back up TCP v2 JSON.
* Seed final JSON from the accepted source.
* Verify row count.
* Verify final date.
* Verify final NAV.
* Verify admin authorization.
* Verify `debug=False`.
* Verify port 8302 is free after stopping v1.
* Document rollback commands.

## File strategy

Recommended:

```text
tcp_ts.py       → tcp_ts_v1.py
tcp_ts_v2.py    → tcp_ts.py
```

Alternatively, change only `reboot_tcp_ts.bat` to launch v2 while keeping filenames intact. Pick one method and document it consistently.

## Production binding

Keep:

```text
Port 8302
Existing Cloudflare route
Existing Manager expectations
Existing HomePage/debug expectations
```

Avoid unnecessary infrastructure changes during application cutover.

## Smoke tests

* Public page returns successfully.
* Public statistics render.
* NAV chart renders.
* Current date is correct.
* Admin authentication works.
* Ledger loads.
* No unexpected state write occurs.
* Restart restores the same state.

## Rollback

1. Stop TCP v2.
2. Restore the v1 batch-file target or original filename.
3. Restart TCP v1 on port 8302.
4. Preserve v2 state for reconciliation.
5. Document any row entered during the v2 production window.

## Exit gate

TCP v2 operates on production port 8302 and TCP v1 remains immediately recoverable.

---

# 18. Phase 12 — Stabilization and later refactor

## Stabilization

Add:

* Mutation audit log
* State health logging
* Backup retention
* Failed-write alerting
* Corrupt-state alerting
* Last-successful-update visibility
* State revision visibility
* Workbook bootstrap warning

## Later shared-engine extraction

Only after both applications are stable, consider:

```text
tearsheet_engine/
├── state.py
├── ledger.py
├── dashboard.py
├── validation.py
├── formatting.py
└── callback_factories.py
```

Keep strategy-specific modules:

```text
tkp_config.py
tkp_calculations.py
tcp_config.py
tcp_calculations.py
```

Do not begin this refactor during the TCP v2 migration.

---

# 19. Overall definition of done

The project is complete when:

## Financial correctness

* TCP formulas are documented.
* Golden-row tests pass.
* Full-ledger replay passes.
* Baseline behavior is explicit.
* Overrides are removed or justified.
* Cash-transfer treatment is explicit.

## State

* TCP JSON is authoritative.
* TCP and TKP state are fully isolated.
* Writes are atomic.
* Backups are created.
* Recovery is tested.
* Revision conflicts are rejected.

## Daily workflow

* Add Row works.
* Calculation preview works.
* Save works.
* Delete Last Row works.
* Export works.
* Refresh works.
* Restart persistence works.
* No Excel edit is required.
* No restart is required after entry.

## Dashboard

* Monthly performance updates.
* Daily performance updates.
* NAV chart updates.
* Current-date labels update.
* Static sections are honestly documented.

## Product integrity

* TCP layout is preserved.
* TCP branding is preserved.
* TCP disclosures are correct.
* No unintended TKP references remain.

## Deployment

* Preview ran separately on port 8312.
* Production remains on port 8302.
* Debug mode is disabled.
* Cutover is reversible.
* TCP v1 remains available for rollback.

---

# 20. Recommended milestone sequence

```text
Milestone 1
Business contract + pytest + isolated read-only preview

Milestone 2
Full Excel adapter + TCP state layer

Milestone 3
TCP calculator + historical replay

Milestone 4
Dynamic dashboard propagation

Milestone 5
Admin editor + authorization

Milestone 6
Branding/UI preservation + state seed

Milestone 7
Three-way parity + parallel run

Milestone 8
Production cutover + stabilization
```

The row calculator and historical replay remain the central acceptance gate. UI completion must never be mistaken for financial correctness.
