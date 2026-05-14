# Momentum Pacer — Tearsheet

**CTA:** Algominds Financial LLC  
**Strategy:** Momentum Pacer  
**Engine:** `calc_engine.py` (reusable, config-driven)  
**App file:** `mp_ts.py`  
**Port:** 8079  

---

## How to Run

```bash
cd "c:\Coding Projects\Tearsheet Generator\Momentum Pacer"
python mp_ts.py
```

Then open your browser to:

```
http://localhost:8079
```

---

## How to Change Frequency or Compounding

Open `mp_ts.py` and find the **STRATEGY CONFIGURATION** block near the top (clearly marked with arrows). Change the two key fields:

| Field | Options | Effect |
|---|---|---|
| `result_frequency` | `"monthly"` or `"weekly"` | Controls row grouping and period labels |
| `return_mode` | `"compounded"` or `"non_compounded"` | Controls how cumulative returns are calculated |

### Compounded vs Non-Compounded

| Mode | Formula | When to use |
|---|---|---|
| `compounded` | `(1+r1)(1+r2)…(1+rN) - 1` | Recommended for real accounts where profits are reinvested |
| `non_compounded` | `r1 + r2 + … + rN` | Used for notional/non-reinvested reporting |

> **Note:** On the same data these will produce different cumulative numbers — that difference is intentional and expected. The website always shows a banner stating which mode is active.

### Weekly vs Monthly

| Mode | Row label format | Example |
|---|---|---|
| `monthly` | `Jan 2026` | Standard tearsheet rows |
| `weekly` | `Wk ending May 02, 2026` | Higher-frequency data |

Yearly summary rows work in both modes.

---

## CSV Data File

The app reads from `sample_data.csv` by default.  
To use live data, change `CSV_PATH` in `mp_ts.py`:

```python
CSV_PATH = BASE_DIR / "momentum_pacer_live.csv"
```

### Required CSV columns

| Column | Required | Description |
|---|---|---|
| `date` | **Yes** | Period end date (any standard date format) |
| `net_return_pct` | **Yes** | Net return for the period as a percentage (e.g. `2.15` for 2.15%) |
| `gross_return_pct` | No | Gross return before fees (hidden if missing) |
| `fees_pct` | No | Fee charged that period (hidden if missing) |
| `nav` | No | Explicit NAV value (derived from returns if missing) |

> Rename columns in `mp_ts.py` → `cfg` block if your CSV uses different headers.

---

## Folder Structure

```
Momentum Pacer/
├── mp_ts.py           # Main Dash app
├── calc_engine.py     # Reusable calculation engine (no UI code)
├── sample_data.csv    # 28-month sample data for testing
├── README.md          # This file
└── algominds_logo.png # (optional) Drop your logo here
```

---

## Reusing This Template for Other Strategies

1. Copy this entire folder.
2. Rename `mp_ts.py` to your strategy's name.
3. Edit only the `StrategyConfig` block at the top of the app file.
4. Point `CSV_PATH` to your data.
5. Run with a new port number.

The `calc_engine.py` is shared and requires no changes between strategies.

---

## Validation Errors

The engine will print clear errors for:

- Missing `date_column`
- Missing `net_return_column`
- Invalid `result_frequency` (not `weekly` or `monthly`)
- Invalid `return_mode` (not `compounded` or `non_compounded`)
- Unparseable date values
- Negative `starting_capital`

All errors display as a red banner on the website and are also printed to the console.

---

## Dependencies

```
dash
dash-bootstrap-components
pandas
numpy
plotly
yfinance
```

Install with:

```bash
pip install dash dash-bootstrap-components pandas numpy plotly yfinance
```
