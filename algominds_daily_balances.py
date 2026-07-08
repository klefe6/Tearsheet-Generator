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
DAILY_BALANCES_FILENAME = "balances_210TGG51_20OCT2025_07JUL2026.csv"

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
    elif s.startswith("-"):
        negative = True
        s = s[1:].strip()
    s = s.replace("$", "").replace(",", "").strip()
    if s == "":
        return None
    try:
        num = float(s)
    except ValueError:
        return None
    return -num if negative else num


def _parse_trade_station_date(series: pd.Series) -> pd.Series:
    """Parse TradeStation balance dates (M/D/YYYY or MM-DD-YYYY)."""
    raw = series.astype(str).str.strip()
    parsed = pd.to_datetime(raw, format="%m/%d/%Y", errors="coerce")
    missing = parsed.isna()
    if missing.any():
        parsed.loc[missing] = pd.to_datetime(raw[missing], format="%m-%d-%Y", errors="coerce")
    return parsed


def _format_money(value: float) -> str:
    """Serialize a float back to TradeStation-style money text for CSV export."""
    if value < 0:
        return f'"(${abs(value):,.2f})"'
    return f'"${value:,.2f} "'


def _format_trade_station_date(dt: pd.Timestamp) -> str:
    month = int(dt.month)
    day = int(dt.day)
    return f"{month}/{day}/{dt.year}"


def write_daily_balances_csv(df: pd.DataFrame, path: os.PathLike | str) -> Path:
    """
    Write a canonical TradeStation Historical Balances CSV from a cleaned frame.

    *df* must contain RAW_COLUMNS sorted oldest→newest with numeric money columns.
    """
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    work = df[RAW_COLUMNS].copy().sort_values("Date").reset_index(drop=True)
    min_date = work["Date"].min().strftime("%m/%d/%Y").lstrip("0").replace("/0", "/")
    max_date = work["Date"].max().strftime("%m/%d/%Y").lstrip("0").replace("/0", "/")

    lines = [
        "# -----------------------------------------------,,,,,,,",
        "TradeStation Historical Balances Report,,,,,,,",
        f"Dates: {min_date} - {max_date},,,,,,",
        "Account: 210TGG51,,,,,,,",
        "Type: Futures,,,,,,,",
        "Alias: AMF MNQRdr GG51,,,,,,,",
        "# -----------------------------------------------,,,,,,,",
        ",,,,,,,",
        ",,,,,,,",
        ",".join(RAW_COLUMNS),
    ]
    for _, row in work.iterrows():
        cells = [_format_trade_station_date(pd.Timestamp(row["Date"]))]
        for col in MONEY_COLUMNS:
            val = row[col]
            cells.append(_format_money(float(val)) if pd.notna(val) else '"$0.00 "')
        lines.append(",".join(cells))
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def merge_daily_balances_exports(
    canonical_path: os.PathLike | str,
    source_path: os.PathLike | str,
    output_path: Optional[os.PathLike | str] = None,
) -> dict:
    """
    Merge a newer TradeStation export into the canonical daily balances CSV.

    Overlapping dates take values from *source_path*; genuinely new dates append.
  Returns a summary dict suitable for changelog / PR notes.
    """
    canonical_path = Path(canonical_path)
    source_path = Path(source_path)
    output_path = Path(output_path) if output_path is not None else canonical_path

    before = load_daily_balances(canonical_path)
    incoming = load_daily_balances(source_path)
    if before.empty and incoming.empty:
        raise ValueError("both canonical and source balances are empty")

    appended: list[str] = []
    changed: list[dict] = []
    overlap_count = 0

    base = before if not before.empty else pd.DataFrame(columns=RAW_COLUMNS)
    if incoming.empty:
        merged = base[RAW_COLUMNS] if not base.empty else base
    else:
        base_idx = base.set_index("Date")
        incoming_idx = incoming.set_index("Date")
        overlap = base_idx.index.intersection(incoming_idx.index)
        overlap_count = int(len(overlap))
        for dt in overlap:
            old = float(base_idx.loc[dt, "Net Worth"])
            new = float(incoming_idx.loc[dt, "Net Worth"])
            if abs(old - new) > 1e-6:
                changed.append({"date": pd.Timestamp(dt).date().isoformat(), "old": old, "new": new})
        if overlap_count:
            base_idx.loc[overlap, RAW_COLUMNS[1:]] = incoming_idx.loc[overlap, RAW_COLUMNS[1:]]
        append_idx = incoming_idx.index.difference(base_idx.index)
        appended = [pd.Timestamp(d).date().isoformat() for d in sorted(append_idx)]
        if len(append_idx):
            base_idx = pd.concat([base_idx, incoming_idx.loc[append_idx]], axis=0)
        merged = base_idx.reset_index().sort_values("Date").reset_index(drop=True)[RAW_COLUMNS]

    write_daily_balances_csv(merged, output_path)
    after = load_daily_balances(output_path)
    return {
        "canonical_path": str(output_path),
        "source_path": str(source_path),
        "previous_max_date": None if before.empty else before["Date"].max().date().isoformat(),
        "new_max_date": None if after.empty else after["Date"].max().date().isoformat(),
        "overlapping_rows_updated": overlap_count,
        "new_rows_appended": len(appended),
        "appended_dates": appended,
        "overwritten_dates": changed,
        "latest_net_worth": None if after.empty else float(after["Net Worth"].iloc[-1]),
        "row_count": int(len(after)),
    }


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

    df["Date"] = _parse_trade_station_date(df["Date"])
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


def daily_pct_change(values: pd.Series) -> pd.Series:
    """Previous-row percent change in percent units (first row NaN)."""
    return values.astype(float).pct_change() * 100.0
