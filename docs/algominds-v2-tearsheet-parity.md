# Algominds v2 — Investor Tearsheet Visual Parity

Branch: `feature/algominds-v2-tearsheet-parity`
Preview port: `8311` (Algominds v2 preview only; 8301/8302/8304 untouched)

## What changed

The read-only v2 preview account pages (`/{account_slug}`, e.g. `/algominds`,
`/vikram-suman`) now render a full v1-style investor tearsheet (mirroring
`Momentum Pacer/mp_ts.py` on 8304) instead of the plain debug bullet-list shell:

1. "Important Notice" accept gate (shared sibling gate via `tearsheet_gate_ui.py`).
2. Grey header band — centered "Algominds Financial LLC" / "Momentum Pacer
   Program", account label, right-side Last Updated.
3. Centered intro/disclosure paragraphs (instruments, objective, benchmark/fee
   context).
4. "Compounded NAV Since Inception" chart — net-of-fees line plus SPX rebased
   benchmark line, grey plot area, legend below, caption underneath.
5. Performance Summary table — v1 spreadsheet style with green/red return
   shading and Net %/Net $ footer.
6. Strategy Overview and Fee Structure cards (two-column row).
7. Performance Metrics and Monthly Performance Statistics cards.
8. Investor Information card (Terms & Fees | Account Stats).
9. "Drawdown from Peak" filled area chart.
10. v1 footer disclaimers.

Account numbers (`AccountProfile.account_number`) appear on the `/admin`
overview only — never on the public tearsheet pages.

## Architecture

| Layer | Module | Responsibility |
| ----- | ------ | -------------- |
| Account config | `algominds_v2_account_registry.py` | investor profiles (registry only) |
| Fee/calculation | `algominds_v2/fee_engine.py`, `algominds_v2_snapshots.py` | unchanged, layout-free |
| View model | `algominds_v2_tearsheet.py` | normalized `TearsheetViewModel`: profile fields, last-updated label, chart series, summary rows, metrics, fee-structure rows, investor rows, drawdown series |
| Layout | `algominds_v2_tearsheet_layout.py` | pure HTML/SVG rendering of the view model; no fee math, registry, or state I/O |
| Gate | `tearsheet_gate_ui.py` (+ `tearsheet_disclosure.py`) | shared sibling Important Notice gate, presentation only |
| Routing | `algominds_v2_preview_app.py` | `/` account selector, `/admin` overview, `/{account_slug}` tearsheet, 404 fallback |

Charts are deterministic server-rendered inline SVG (no plotly/pandas in the
preview app, per the shell's import bans).

## Data behavior

- If a real per-account snapshot exists in preview state, the tearsheet uses it
  (single-point NAV series from inception to snapshot date) and shows no
  fixture banner.
- With no snapshot, the page renders complete deterministic preview fixture
  months (fixed return cycles through the real v2 fee engine), with a visible
  banner: "Preview fixture data — deterministic demo values for layout preview
  only." Fixture data is generated in memory only and never written to state.

## Isolated assumptions (not final business rules)

- `FEE_STRUCTURE_ASSUMPTION_NOTE` in `algominds_v2_tearsheet.py`: slab band
  wording restates the v1 tearsheet's Disclosure Document text; rates come from
  `algominds_v2.fee_engine.SLAB_RATES` / `NEGATIVE_BDR_RATE`. Final wording
  pending Disclosure Document confirmation.
- Snapshot mode plots only inception → snapshot-date NAV until a persisted
  daily/monthly history series exists in v2 state (future lane).
- Fixture month count is fixed at 8 (`FIXTURE_MONTH_COUNT`).

## Out of scope (unchanged)

- Admin Add/Delete mutations.
- Final production persistence and cutover.
- TKP (8301), TCP (8302), Algominds v1 (8304).
