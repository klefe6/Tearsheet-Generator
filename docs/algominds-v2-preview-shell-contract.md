# Algominds v2 Preview Shell Contract

Read-only Dash preview shell for Algominds v2 on port **8311**. First visual
preview lane — admin overview and per-account placeholder pages only.

Repository: `klefe6/Tearsheet-Generator`  
Module: `algominds_v2_preview_app.py`

---

## Routes

| Route | Purpose |
| ----- | ------- |
| `/` | Landing with links to `/admin` and default account (`prop`) |
| `/admin` | Admin overview table at top of page |
| `/{account_slug}` | Per-account read-only detail page |

Examples: `/prop`, `/acct-60k`

Unknown `account_slug` values render a clean 404 page (no crash).

---

## Admin overview table

Rendered from `list_account_profiles()` — not hard-coded rows.

| Column | Source |
| ------ | ------ |
| Account | `display_name` linked to `/{account_slug}` |
| Starting date | `AccountProfile.inception_date` |
| Benchmark base | `AccountProfile.benchmark_base` |
| Units | `AccountProfile.number_of_units` |
| After-fee NLV | `compute_latest_snapshot_result` → `after_fee_nlv`, or "No snapshot yet" |
| Week % | Placeholder `—` (no history lane yet) |
| Month % | Placeholder `—` |
| Since inception % | `(after_fee_nlv - starting_balance) / starting_balance` when computable |
| Exchange fee tier | `AccountProfile.exchange_fee_tier` (metadata only) |
| Last updated | preview state `last_updated_utc` or `—` |

---

## Per-account page

Shows profile metadata, resolved per-account state path, and latest snapshot
summary when present. Empty state when no snapshot saved.

Uses:

- `get_account_profile(account_slug)`
- `resolve_preview_state_path(account_slug)`
- `load_latest_snapshot_for_account(account_slug)`

---

## Isolation

- Port **8311** (configurable via `ALGOMINDS_V2_PREVIEW_PORT`)
- Does not use ports 8301, 8302, or 8304
- No TKP / TCP / Momentum Pacer imports
- No workbook reads
- No data mutation (no forms, saves, uploads)
- No deposits/withdrawals
- No exchange-fee cost math

Importing the module does **not** start the server. Server starts only under
`if __name__ == "__main__"`.

---

## State paths

Per-account JSON files via `algominds_v2_account_state_paths`:

```text
<state_root>/prop.json
<state_root>/acct-60k.json
```

Override root with `ALGOMINDS_V2_ACCOUNT_STATE_ROOT`.

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Initial read-only preview shell |
