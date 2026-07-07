"""
Algominds / Momentum Pacer — daily TradeStation balances loader (AGM-only).

Parses the "Historical Balances Report" CSV exported from TradeStation into a
tidy DataFrame with numeric money columns and a few derived performance fields.

ADMIN / OPERATIONAL DATA ONLY. The raw Net Worth (NLV) values in this file are
not shown on the client-facing AGM tearsheet — they surface only in AGM admin
TearSheet mode and (optionally) the admin Portal. See mp_ts.py for wiring.

Safe to import: no server start, no network, and it never mutates the source
CSV (opened read-only).
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import List, Optional

import pandas as pd

# Filename of the current export. Kept as a constant so callers don't hardcode it.
DAILY_BALANCES_FILENAME = "balances_210TGG51_20OCT2025_02JUL2026.csv"

# The real data header, exactly as it appears after the metadata block.
RAW_COLUMNS: List[str] = [
    "Date",
    "Net Worth",
    "Cash Balance",
    "Unrealized P/L",
    "Securities on Deposit",
    "Initial Margin Req.",
    "Maint Margin Req.",
    "Buying Power/Margin Deficit",
]

# Every column except Date holds a money string like `"$45,675.81 "` or `($530.00)`.
MONEY_COLUMNS: List[str] = RAW_COLUMNS[1:]


def default_csv_path() -> Path:
    """Canonical location the CSV was copied to inside the AGM data directory."""
    return (
        Path(__file__).resolve().parent
        / "Momentum Pacer"
        / "data"
        / "daily_balances"
        / DAILY_BALANCES_FILENAME
    )


def _parse_money(value: object) -> Optional[float]:
    """
    Convert a TradeStation money string to float.

    Handles: leading `$`, thousands `,`, trailing spaces, surrounding quotes,
    and accountant-style negatives in parentheses e.g. `($1,324.00)` -> -1324.0.
    Returns None for blank/unparseable cells (never raises).
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip().strip('"').strip()
    if s == "" or s == "-":
        return None
    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1].strip()
    s = s.replace("$", "").replace(",", "").strip()
    if s == "":
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    return -num if negative else num


def _find_header_row_index(path: Path) -> int:
    """
    Return the 0-based line index of the true `Date,Net Worth,...` header,
    skipping the TradeStation metadata block. Raises ValueError if absent.
    """
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if row and row[0].strip().lstrip("﻿") == "Date" and "Net Worth" in [c.strip() for c in row]:
                return i
    raise ValueError(f"Could not find 'Date,Net Worth,...' header row in {path.name}")


def load_daily_balances(path: Optional[os.PathLike | str] = None) -> pd.DataFrame:
    """
    Load and clean the daily balances CSV.

    Returns a DataFrame sorted oldest→newest with:
      - "Date" as datetime64
      - every money column as float (NaN where blank)
      - derived fields:
          daily_net_worth_change      (Net Worth diff, $)
          daily_net_worth_change_pct  (Net Worth pct change, %)
          since_inception_pct         (vs. first Net Worth, %)
          mtd_pct                     (month-to-date vs first Net Worth of that calendar month, %)
          wtd_pct                     (week-to-date vs first Net Worth of that ISO week, %)

    Returns an empty DataFrame (no exception) if the file is missing.
    """
    csv_path = Path(path) if path is not None else default_csv_path()
    if not csv_path.is_file():
        return pd.DataFrame(columns=RAW_COLUMNS)

    header_idx = _find_header_row_index(csv_path)
    df = pd.read_csv(csv_path, skiprows=header_idx, dtype=str, encoding="utf-8-sig")

    # Normalize column names (strip stray whitespace) and keep only known columns present.
    df.columns = [c.strip() for c in df.columns]

    # Drop fully blank rows and rows without a Date or Net Worth.
    df = df.dropna(how="all")
    if "Date" not in df.columns or "Net Worth" not in df.columns:
        return pd.DataFrame(columns=RAW_COLUMNS)

    df["Date"] = pd.to_datetime(df["Date"].astype(str).str.strip(), format="%m/%d/%Y", errors="coerce")
    df = df[df["Date"].notna()].copy()

    for col in MONEY_COLUMNS:
        if col in df.columns:
            df[col] = df[col].map(_parse_money)

    df = df[df["Net Worth"].notna()].copy()
    df = df.sort_values("Date").reset_index(drop=True)

    if df.empty:
        return df

    net = df["Net Worth"].astype(float)
    first_nw = float(net.iloc[0])

    df["daily_net_worth_change"] = net.diff()
    df["daily_net_worth_change_pct"] = net.pct_change() * 100.0
    df["since_inception_pct"] = (net / first_nw - 1.0) * 100.0 if first_nw else pd.NA

    # Month-to-date: vs the first Net Worth observed in the same calendar month.
    month_key = df["Date"].dt.to_period("M")
    month_first_nw = net.groupby(month_key).transform("first")
    df["mtd_pct"] = (net / month_first_nw - 1.0) * 100.0

    # Week-to-date: vs the first Net Worth observed in the same ISO year+week.
    iso = df["Date"].dt.isocalendar()
    week_key = iso["year"].astype(str) + "-W" + iso["week"].astype(str)
    week_first_nw = net.groupby(week_key).transform("first")
    df["wtd_pct"] = (net / week_first_nw - 1.0) * 100.0

    return df


def latest_row(df: pd.DataFrame) -> Optional[pd.Series]:
    """Most recent daily row (current account state), or None if empty."""
    if df is None or df.empty:
        return None
    return df.iloc[-1]


def latest_net_worth(df: pd.DataFrame) -> Optional[float]:
    """Latest daily Net Worth (current NLV), or None if empty."""
    row = latest_row(df)
    if row is None:
        return None
    return float(row["Net Worth"])
