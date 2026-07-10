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
| TKP | `<repo>/daily_returns_secret_state.json` (`Date`/`StoneX`/`Plus500`/`Deposit`, $-strings) | stonex_nlv, plus500_nlv, cash_transfer | 837 rows, 2023-04-10 → 2026-07-09 |
| TCP | LIVE state file from `TCP_V2_STATE_PATH` in `<repo>/.tcp_production.env` (`records[].NLV` / `Cash Transfers`) — the repo-root file of the same name is a **stale seed**, never used by default | stonex_nlv, cash_transfer | 121 rows, 2026-01-20 → 2026-07-07 |
| AGM | newest `<repo>/Momentum Pacer/data/daily_balances/balances_210TGG51_*.csv` (`Net Worth` = raw actual_nlv, **not** the client-net value the tearsheet shows) | tradestation_nlv, cash_transfer (evidenced fee withdrawals only) | 184 rows, 2025-10-20 → 2026-07-06 |
| Y&Q | `yq.csv` is **monthly** (2011-04 →), at real-fund ~$89M scale, while the tearsheet renders a $100k-normalized ROR curve | **no daily source — always skipped** | — |

### Data-correctness rules baked into the extractor

* **TKP unrecorded Plus500 funding**: on 2025-03-11 Plus500 went blank → $100,000
  with a blank `Deposit` cell. Without correction that day would chart as a fake
  +82.6% return. On a 0→V (or V→0) Plus500 transition with no recorded deposit,
  the extractor synthesizes the cash transfer and **warns loudly**. Recorded
  deposits are never altered.
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
2. **Sandbox-only** — `POST /api/backfill/import` and `DELETE /api/backfill`
   return 403 in production **by construction**; no flag can enable them.
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

```bash
# On the ops machine, from uploader/backend — audit only, writes nothing:
python scripts/extract_tearsheet_history.py --dry-run

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
