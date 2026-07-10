# Historical backfill — tearsheet history → uploader graph (sandbox-only)

The top performance chart originally plotted **uploader `daily_rows` only**,
so a fresh sandbox looked sparse. This feature imports each program's
existing tearsheet history into a **separate `historical_rows` table** that
the chart merges in — without touching Glenn's entries, the export path, or
any tearsheet app.

## Why a separate table (design decision)

Considered options:

| Option | Verdict |
| ------ | ------- |
| A. Import straight into `daily_rows` | ❌ imported rows would be indistinguishable from Glenn's entries, would appear in his entry table, and would flow into the downstream export path |
| **B. Separate `historical_rows` table (chosen)** | ✅ clearly labeled, reversible in one call, invisible to export, merged only for the chart |
| C. Request-time overlay reading tearsheet files | ❌ the deployed sandbox (Fly.io) does not have the tearsheet state files on disk |
| D. Hide the graph until enough manual data | ❌ wastes 3+ years of real TKP history |

## Data flow

```
ops machine (has the tearsheet files)          sandbox backend (Fly.io / local)
──────────────────────────────────────         ─────────────────────────────────
scripts/extract_tearsheet_history.py  ──JSON──▶ POST /api/backfill/import
  reads (READ-ONLY):                            └─▶ historical_rows table
    TKP  daily_returns_secret_state.json            └─▶ merged into /api/performance
    TCP  live state via TCP_V2_STATE_PATH               (manual rows always win)
    AGM  newest balances_210TGG51_*.csv
    Y&Q  (skipped — no daily source)
```

## Sources per program (field-level audit, 2026-07-10)

| Program | Store | Maps to | Coverage |
| ------- | ----- | ------- | -------- |
| TKP | `<repo>/daily_returns_secret_state.json` — the **`NAV`** column (equity curve), NOT raw StoneX/Plus500 balances (see TKP decision below) | stonex_nlv = `NAV`, plus500_nlv = 0, cash_transfer = 0 | 837 rows, 2023-04-10 → 2026-07-09 |
| TCP | LIVE state file from `TCP_V2_STATE_PATH` in `<repo>/.tcp_production.env` — the repo-root file of the same name is a **stale seed**, never used by default. **Gated**: skipped unless `BACKFILL_TCP_NLV_FIELD=nav-x1` | stonex_nlv = `nav-x1`, cash_transfer = 0 (see TCP decision below) | 121 rows, 2026-01-20 → 2026-07-07 |
| AGM | newest `<repo>/Momentum Pacer/data/daily_balances/balances_210TGG51_*.csv` (`Net Worth` = raw actual_nlv, **not** the client-net value the tearsheet shows) | tradestation_nlv, cash_transfer (evidenced fee withdrawals only) | 184 rows, 2025-10-20 → 2026-07-06 |
| Y&Q | `yq.csv` is **monthly** (2011-04 →), at real-fund ~$89M scale, while the tearsheet renders a $100k-normalized ROR curve | **no daily source — always skipped** | — |

### TKP decision: the `NAV` equity curve, never raw balances (traced 2026-07-10)

The TKP tearsheet graphs the workbook's NAV column (renamed `nav-x1` in
`tkp_ts.py`), and the app explicitly neutralizes transfers on it —
`_apply_cash_transfer_adjustment` adds withdrawals back / removes deposits
from the transfer date onward (`AUTO_DETECT_CASH_TRANSFERS = True`). The
state JSON's own `NAV` column embodies exactly that concept:

```
NAV(t) = 150,000 × (1 + "Cumm Perc. Net"(t))     # verified to the cent, all 837 rows
```

— cumulative NET performance, seeded $150k, smooth through every
deposit/withdrawal date (e.g. 2025-10-29's −$100k day: NAV +0.009%).

Raw `StoneX + Plus500` balances are **rejected** because the state's
`Deposit` ledger is provably incomplete: on **2026-03-05 both accounts
dropped ~$25k each (−$49,915.58 combined) while `Deposit` recorded only
−$25,000**, and the 2025-03-11 Plus500 $100k funding had a blank `Deposit`
cell entirely. No neutralization built on that ledger can be trusted, so the
first backfill (raw balances + recorded/synthesized transfers) showed fake
drops on withdrawal days. Backfilled TKP rows carry `stonex_nlv = NAV`,
`plus500_nlv = 0`, `cash_transfer = 0` (NAV is already neutral); the
uploader's $100k line telescopes to `100000 × NAV(t)/NAV(first)` — a
faithful rescaling of TKP's own equity curve.

### TCP decision: `nav-x1`, never raw `NLV` (traced 2026-07-10)

The TCP tearsheet's public chart ("Non-Compounded NAV Since Inception") plots
exactly the state records' **`nav-x1`** field
(`tcp_dashboard.py::canonical_nav_records_from_ledger` line 149 →
`build_tcp_nav_figure`; `tcp_config.py` names it `nav_column`). Its formula
(`tcp_calculations.py::compute_tcp_row`):

```
pl      = cash_balance − prior_cash − cash_transfers   # transfer subtracted OUT
nav_x1  = prior_nav + (pl − fee) / tranche_count       # cash-transfer-neutral, fee-net, seeded $50,000
nlv     = prior_nlv + pl + cash_transfers              # raw NLV adds transfers BACK IN
```

So raw `NLV` charts deposits/withdrawals as performance and is **rejected** by
the extractor; `nav-x1` is the graph-equivalent calculated value. Backfilled
TCP rows carry `cash_transfer = 0` because `nav-x1` is already neutral — also
emitting the recorded transfers would double-adjust. Since the uploader
compounds returns with zero transfers, its $100k line telescopes to exactly
`100000 × nav-x1(t) / nav-x1(first)` — a faithful rescaling of TCP's own NAV
curve. TCP is included only when `BACKFILL_TCP_NLV_FIELD=nav-x1` is set
explicitly (no other value is accepted).

### Data-correctness rules baked into the extractor

* **AGM evidenced fee withdrawals**: the two hand-confirmed TradeStation
  incentive-fee withdrawals (2026-05-14 $2,967.85, 2026-06-23 $1,330.25) are
  applied as negative cash transfers, parsed **textually** from
  `algominds_fee_payment_evidence.py` (never imported — it pulls in pandas).
  Without them each withdrawal day would chart as a fake loss.
* **AGM `fee` is deliberately NOT backfilled** — whether fee is already netted
  out of `tradestation_nlv` is a documented open question
  (`programs.program_nlv` excludes it from performance), so backfill stays
  consistent with that placeholder rather than guessing.

## Safety guarantees (all tested in `tests/test_backfill.py`)

1. **Read-only toward tearsheets** — the extractor only ever opens source files
   for read (test hashes every file before/after); it never imports a tearsheet
   module; it never touches TCP's `.lock`/`.backup`. TKP's non-atomic writer is
   handled by retrying on `JSONDecodeError`; TCP's atomic `os.replace` writes
   make lock-free reads safe.
2. **Sandbox-only AND opt-in** — every `/api/backfill/*` endpoint returns 403
   unless `APP_ENV=sandbox` **and** `BACKFILL_ENABLED=true`. Production
   refuses regardless of the flag, by construction. The deployed sandbox has
   no live backfill surface until an operator sets the flag.
3. **Idempotent** — re-importing the same payload reports every row
   `unchanged` and rewrites nothing. Dry-run classifies through the *same*
   code path as the real import, so previews always match.
4. **Labeled** — every stored row carries a machine source label
   (`tkp_state_json` / `tcp_state_json` / `agm_daily_balances_csv`);
   `"manual"` is reserved and rejected. Backfilled rows never appear in
   Glenn's `/api/rows/{program}` entry table.
5. **Manual precedence (explicit design)** — a manual `daily_rows` entry always
   supersedes a historical row on the same (program, date); collisions are
   stored but reported as `overridden_by_manual` at import time.
6. **Export isolation** — export reads only `daily_rows`; backfilled rows can
   never be exported downstream, and importing never flips/resets any
   `exported` flag.
7. **Reversible** — `DELETE /api/backfill` (optionally `?program=`) clears
   only `historical_rows`; the chart label reverts to "uploader entries only".
8. **Audited** — every import/dry-run writes a `backfill_batches` record and a
   `backfill_dry_run`/`backfill_import` audit event with per-program counts;
   `GET /api/backfill/status` shows what is currently backfilled per program.
9. **Non-destructive migration** — the new tables are added via
   `CREATE TABLE IF NOT EXISTS` at startup; existing DBs (including the
   deployed sandbox volume) upgrade in place with no data loss.

## Runbook (sandbox)

Backfill endpoints require `BACKFILL_ENABLED=true` on the target backend
(sandbox only — e.g. `fly secrets set BACKFILL_ENABLED=true -a
glenn-uploader-sandbox`, and unset it again after importing). To include TCP,
also set `BACKFILL_TCP_NLV_FIELD=nav-x1` where the extractor/preview runs.

```bash
# On the ops machine, from uploader/backend — audit only, writes nothing:
python scripts/extract_tearsheet_history.py --dry-run
# include TCP via its approved calculated field:
python scripts/extract_tearsheet_history.py --dry-run --tcp-nlv-field nav-x1

# Produce the payload file:
python scripts/extract_tearsheet_history.py --out backfill_payload.json

# Preview against the sandbox (server-side dry-run — default):
python scripts/extract_tearsheet_history.py --push https://uploader-sandbox.hcresearch.ltd/api/backfill/import

# Import for real (sandbox only; production refuses):
python scripts/extract_tearsheet_history.py --push https://uploader-sandbox.hcresearch.ltd/api/backfill/import --commit

# Verify / revert:
curl https://uploader-sandbox.hcresearch.ltd/api/backfill/status
curl -X DELETE https://uploader-sandbox.hcresearch.ltd/api/backfill
```

## Graph copy

With backfill present the chart's provenance note reads
**“Strategy lines include historical tearsheet data plus uploader entries.”**
(and program-mode subtitles say “first recorded entry”); with none it keeps
**“Strategy lines reflect uploader entries only (no historical tearsheet data).”**
Driven by `program_data_source` — see `PERFORMANCE_PROVENANCE.md`.
