# Cursor Patch – Auto-calculate all columns on Add Row

## Summary
Add a `_compute_new_row()` helper and wire it into the existing `add_row` callback.
Two changes only: **1 new function**, **1 modified callback**.

---

## Column formula reference (from Excel)

| Display col | Excel col | Formula (row n, prev = n-1) |
|---|---|---|
| $PL | I | `G_n - G_{n-1} - deposit_n` |
| Fee (20%) | J | `max(0, ($PL - LossCarry_prev) * 0.2)` if $PL > LossCarry_prev else 0 |
| Cumm Fee | K | `Fee + CummFee_prev` |
| Net P&L | L | `$PL - Fee` |
| Net P&L/Unit | M | `Net_PL / tranches` (tranches = 1 normally) |
| NAV | N | `NAV_prev + Net_PL` |
| Loss Carry | O | `max(0, HWM_prev - NAV_new)` |
| Perc. Net | P | `Net_PL / 150000` |
| Cumm % | Q | `Perc + CummPerc_prev` |
| HWM | R | `max(HWM_prev, NAV_new)` |

Baseline = N$2 = **150 000** (first NAV value, never changes).

---

## Change 1 — Add helper function

Place this anywhere before the `add_row` callback (e.g. right after the `delete_row` function).

```python
def _parse_money(s):
    """'$1,234.56' → 1234.56; '' or None → 0.0"""
    try:
        return float(str(s).replace("$", "").replace(",", "").strip())
    except (ValueError, TypeError):
        return 0.0

def _parse_pct(s):
    """'1.2345%' → 0.012345; '' or None → 0.0"""
    try:
        return float(str(s).replace("%", "").strip()) / 100
    except (ValueError, TypeError):
        return 0.0

def _compute_new_row(prev_row: dict, new_balance: float, deposit: float) -> dict:
    """
    Given the previous row's display dict and the two user-supplied inputs,
    return a dict of all computed display values for the new row.
    """
    BASELINE = 150_000.0   # N$2 – first NAV; matches BASELINE_AMOUNT constant

    prev_balance  = _parse_money(prev_row.get("Balance (StoneX)"))
    prev_nav      = _parse_money(prev_row.get("NAV"))
    prev_hwm_str  = str(prev_row.get("HWM", "")).replace(" *", "")
    prev_hwm      = _parse_money(prev_hwm_str) if prev_hwm_str else prev_nav
    prev_loss_carry = _parse_money(prev_row.get("Loss Carry"))
    prev_cumm_fee   = _parse_money(prev_row.get("Cumm Fee"))
    prev_cumm_pct   = _parse_pct(prev_row.get("Cumm Perc. Net"))

    # Core P&L chain
    pl           = new_balance - prev_balance - deposit
    fee          = max(0.0, (pl - prev_loss_carry) * 0.2) if pl > prev_loss_carry else 0.0
    cumm_fee     = prev_cumm_fee + fee
    net_pl       = pl - fee
    nav          = prev_nav + net_pl
    loss_carry   = max(0.0, prev_hwm - nav)
    pct_net      = net_pl / BASELINE
    cumm_pct     = prev_cumm_pct + pct_net
    hwm          = max(prev_hwm, nav)
    hwm_new_high = hwm > (prev_hwm + 0.01)   # tiny epsilon for float safety

    hwm_str = f"${hwm:,.2f}" + (" *" if hwm_new_high else "")

    return {
        "Balance (StoneX)": f"${new_balance:,.2f}",
        "$PL":              f"${pl:,.2f}",
        "Fee (20%)":        f"${fee:,.2f}",
        "Cumm Fee":         f"${cumm_fee:,.2f}",
        "Net P&L":          f"${net_pl:,.2f}",
        "Net P&L / Unit":   f"${net_pl:,.2f}",   # assumes 1 tranche
        "NAV":              f"${nav:,.2f}",
        "Loss Carry":       f"${loss_carry:,.2f}",
        "Perc. Net":        f"{pct_net * 100:.4f}%",
        "Cumm Perc. Net":   f"{cumm_pct * 100:.4f}%",
        "HWM":              hwm_str,
        "Deposit":          f"${deposit:,.0f}" if deposit != 0 else "",
    }
```

---

## Change 2 — Replace the `add_row` callback body

Find the existing `add_row` function and **replace only its body** (keep the decorator unchanged).

### BEFORE (existing body):
```python
def add_row(n_clicks, date_val, balance_val, deposit_val, current_data):
    if not n_clicks:
        return dash.no_update
    rows = list(current_data) if current_data else []
    max_id = max((r.get("_row_id", 0) for r in rows), default=-1) + 1
    def _safe_int(v):
        try:
            return int(v)
        except (ValueError, TypeError):
            return 0
    max_day = max((_safe_int(r.get("#Day")) for r in rows), default=0) + 1
    new_row = {c: "" for c in secret_all_columns}
    new_row["_row_id"] = max_id
    new_row["Date"] = date_val or ""
    new_row["#Day"] = str(max_day)
    new_row["Balance (StoneX)"] = f"${float(balance_val):,.2f}" if balance_val else ""
    dep = float(deposit_val) if deposit_val else 0
    new_row["Deposit"] = f"${dep:,.0f}" if dep != 0 else ""
    new_row["Edit"] = "\u270f"
    new_row["Del"] = "\u2716"
    rows.append(new_row)
    return rows
```

### AFTER (replacement body):
```python
def add_row(n_clicks, date_val, balance_val, deposit_val, current_data):
    if not n_clicks or not balance_val:
        return dash.no_update
    rows = list(current_data) if current_data else []
    max_id  = max((r.get("_row_id", 0) for r in rows), default=-1) + 1
    max_day = max((int(r["#Day"]) for r in rows if str(r.get("#Day","")).isdigit()), default=0) + 1

    new_balance = float(balance_val)
    deposit     = float(deposit_val) if deposit_val else 0.0

    # Find most-recent row sorted by #Day to use as prev
    sorted_rows = sorted(rows, key=lambda r: int(r["#Day"]) if str(r.get("#Day","")).isdigit() else 0)
    prev_row    = sorted_rows[-1] if sorted_rows else {}

    computed = _compute_new_row(prev_row, new_balance, deposit)

    new_row = {c: "" for c in secret_all_columns}
    new_row.update(computed)
    new_row["_row_id"] = max_id
    new_row["#Day"]    = str(max_day)
    new_row["Date"]    = date_val or ""
    new_row["# Trades"] = ""
    new_row["Edit"]    = "\u270f"
    new_row["Del"]     = "\u2716"
    rows.append(new_row)
    return rows
```

---

## Notes for Cursor

- No new imports needed.
- `_parse_money` / `_parse_pct` handle all the `"$1,234.56"` → `float` conversions
  that appear throughout `secret_table_records`.
- `BASELINE = 150_000` matches `BASELINE_AMOUNT` already defined at the top of the file —
  you can replace the literal with `BASELINE_AMOUNT` if you prefer.
- The `# Trades` field is left blank; it should be filled manually (or add it to the modal).
- `Net P&L / Unit` assumes 1 tranche. If the `H` column is ever > 1 in a row, divide by that value.
