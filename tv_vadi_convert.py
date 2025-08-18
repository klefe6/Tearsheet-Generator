import os
import pandas as pd
import numpy as np

# ───────────────────────────────────────────────────────────────────────────────
# 1) CONFIGURATION
# ───────────────────────────────────────────────────────────────────────────────

# Input files
TRADES_XLSX = r"C:\Program Files\Coding Projects\Tearsheet Generator\CHoCH_+_Dual_EMA_Bias_(Full_Signal_Control)_+_Zones_+_EMA_Shifts_COMEX_MINI_MGC1!_2025-06-13.xlsx"
HIST_TXT    = r"C:\Program Files\Coding Projects\StrategyOptimizer\25Futures_hist_data\daily\GC_daily.txt"

# Output file
OUTPUT_XLSX = r"C:\Program Files\Coding Projects\Tearsheet Generator\VADI.xlsx"

# Strategy parameters
MULTIPLIER     = 10       # $10 per point per contract (micro-gold)
INITIAL_EQUITY = 1_000.0  # starting equity for VADI

# ───────────────────────────────────────────────────────────────────────────────
# 2) SANITY-CHECK INPUT PATHS
# ───────────────────────────────────────────────────────────────────────────────
for path, label in [(TRADES_XLSX, "Trades XLSX"), (HIST_TXT, "Historical TXT")]:
    print(f"[CHECK] {label}: {path}")
    print("   exists?   ", os.path.exists(path))
    print("   is file?  ", os.path.isfile(path))
    print("   readable? ", os.access(path, os.R_OK))
print()

# ───────────────────────────────────────────────────────────────────────────────
# 3) LOAD & CLEAN TRADES
# ───────────────────────────────────────────────────────────────────────────────
print("[LOAD] Reading trades…")
tr = pd.read_excel(
    TRADES_XLSX,
    sheet_name="List of trades",
    converters={
        "Price USD": lambda x: float(str(x).replace(",", "")),
        "P&L USD"  : lambda x: float(str(x).replace(",", ""))
    }
)

# Ensure numeric
tr["Quantity"]  = pd.to_numeric(tr["Quantity"], errors="coerce", downcast="integer")
tr["Date/Time"] = pd.to_datetime(tr["Date/Time"])

# Split entry vs exit
entries = tr[tr["Type"].str.startswith("Entry")].set_index("Trade #")
exits   = tr[tr["Type"].str.startswith("Exit")].set_index("Trade #")
print(f"  loaded {len(entries)} entries, {len(exits)} exits\n")

# Build a trade-level DataFrame
df = pd.DataFrame({
    "entry_date" : entries["Date/Time"].dt.floor("D"),
    "exit_date"  : exits  ["Date/Time"].dt.floor("D"),
    "sign"       : np.where(entries["Type"]=="Entry long",  1, -1),
    "quantity"   : entries["Quantity"],
    "pnl_usd"    : exits["P&L USD"]
}).sort_values("entry_date")

print("[TRADES] sample:")
print(df.head(), "\n")

# ───────────────────────────────────────────────────────────────────────────────
# 4) LOAD DAILY HISTORICAL CLOSES
# ───────────────────────────────────────────────────────────────────────────────
print("[LOAD] Reading daily GC closes…")
hist = (
    pd.read_csv(
        HIST_TXT,
        header=None,
        names=["Date","Open","High","Low","Close","Volume"],
        parse_dates=["Date"]
    )
    .set_index("Date")
    .sort_index()
)
print(f"  loaded {len(hist)} daily rows\n")

# ───────────────────────────────────────────────────────────────────────────────
# 5) COMPUTE DAILY PnL & POSITION
# ───────────────────────────────────────────────────────────────────────────────
start = df["entry_date"].min()
end   = df["exit_date"].max()
print(f"[BUILD] Daily PnL from {start.date()} to {end.date()}\n")

prev_close = None
records    = []

for today in hist.loc[start:end].index:
    close_t = hist.at[today, "Close"]

    # 1) realized PnL = sum of P&L USD for trades exiting today
    realized = df.loc[df["exit_date"] == today, "pnl_usd"].sum()

    # 2) net open contracts = sum(sign * quantity) for trades still open
    open_trades   = df[(df["entry_date"] <= today) & (df["exit_date"] > today)]
    net_contracts = (open_trades["sign"] * open_trades["quantity"]).sum()

    # 3) mark-to-market PnL on open position(s)
    if prev_close is None or net_contracts == 0:
        mtm = 0.0
    else:
        mtm = (close_t - prev_close) * MULTIPLIER * net_contracts

    daily_pnl = realized + mtm

    # debug first few days
    if len(records) < 5:
        print(f"{today.date()} | Close={close_t:.2f} | "
              f"Realized={realized:.2f} | MTM={mtm:.2f} | "
              f"DailyPnL={daily_pnl:.2f} | OpenContracts={net_contracts}")

    records.append({
        "Date"            : today,
        "VADI"            : np.nan,            # leave empty
        "Nb_open_trades"  : int(net_contracts),
        "Daily_PnL_USD"   : daily_pnl
    })

    prev_close = close_t

daily_df = pd.DataFrame(records).set_index("Date")
print("\n[RESULT] daily_df info:")
print(daily_df.info(), "\n")

# ───────────────────────────────────────────────────────────────────────────────
# 6) FILL VADI AS CUMULATIVE EQUITY
# ───────────────────────────────────────────────────────────────────────────────
daily_df["VADI"] = INITIAL_EQUITY + daily_df["Daily_PnL_USD"].cumsum()

# Reorder columns: Date | VADI | Nb_open_trades | Daily_PnL_USD
daily_df = daily_df[["VADI","Nb_open_trades","Daily_PnL_USD"]]

# ───────────────────────────────────────────────────────────────────────────────
# 7) SAVE TO EXCEL
# ───────────────────────────────────────────────────────────────────────────────
print(f"[SAVE] Writing to {OUTPUT_XLSX}")
try:
    if os.path.exists(OUTPUT_XLSX):
        os.remove(OUTPUT_XLSX)
    daily_df.to_excel(OUTPUT_XLSX)
    print("🎉 Wrote VADI.xlsx successfully")
except PermissionError:
    fallback = OUTPUT_XLSX.replace(".xlsx","_new.xlsx")
    daily_df.to_excel(fallback)
    print("⚠️ Permission denied; wrote to", fallback)
