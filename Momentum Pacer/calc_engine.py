"""
calc_engine.py  –  Reusable calculation engine for tearsheet templates
=======================================================================
Handles:
  - Period labelling  (weekly  / monthly)
  - Return aggregation (sum for non-compounded, product for compounded)
  - Cumulative-return series generation
  - Benchmark return alignment
  - Summary statistics (annualised return, win-rate, streaks, drawdown …)

Usage
-----
    from calc_engine import TearsheetEngine

    engine = TearsheetEngine(cfg)          # cfg is a StrategyConfig dict
    results = engine.process(raw_df)       # returns a ProcessedData object

Configuration keys
------------------
See StrategyConfig below for every accepted key and its meaning.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf

# ---------------------------------------------------------------------------
# 1.  STRATEGY CONFIGURATION
# ---------------------------------------------------------------------------

@dataclass
class StrategyConfig:
    """
    All strategy-level settings in one place.
    Change ONLY this block when setting up a new strategy –
    the rest of the engine reads from here.
    """

    # ── Identity ──────────────────────────────────────────────────────────
    strategy_name: str = "My Strategy"
    cta_name: str      = "My CTA"

    # ── Data columns in the CSV ───────────────────────────────────────────
    date_column:         str           = "date"
    net_return_column:   str           = "net_return_pct"
    gross_return_column: Optional[str] = None     # set to column name or leave None
    fees_column:         Optional[str] = None     # set to column name or leave None
    nav_column:          Optional[str] = None     # set to column name or leave None
    capital_column:      Optional[str] = None     # set to column name or leave None

    # ── Frequency ─────────────────────────────────────────────────────────
    # "weekly"  → one row per week, label = week-ending date
    # "monthly" → one row per month, label = "Jan 2026"
    result_frequency: str = "monthly"

    # ── Return mode ───────────────────────────────────────────────────────
    # "compounded"     → cumulative = (∏ (1+r_i)) - 1
    # "non_compounded" → cumulative = Σ r_i
    return_mode: str = "compounded"

    # ── Capital ───────────────────────────────────────────────────────────
    starting_capital: float = 100_000.0

    # ── Benchmarks ────────────────────────────────────────────────────────
    # List of (display_name, yfinance_symbol) tuples
    benchmark_symbols: List[Tuple[str, str]] = field(
        default_factory=lambda: [("SPX TR", "^SP500TR"), ("NDX", "^NDX")]
    )
    display_benchmarks: bool = True

    # ── Fees ──────────────────────────────────────────────────────────────
    fees_included: bool = True   # purely informational for the UI label

    # ── Date format hint (optional, pandas will infer if left as None) ────
    date_format: Optional[str] = None


# ---------------------------------------------------------------------------
# 2.  VALIDATION
# ---------------------------------------------------------------------------

class ConfigError(ValueError):
    """Raised when the configuration or input data fails validation."""


def validate_config(cfg: StrategyConfig) -> None:
    """Raise ConfigError for any invalid configuration value."""

    if cfg.result_frequency not in ("weekly", "monthly"):
        raise ConfigError(
            f"result_frequency must be 'weekly' or 'monthly', "
            f"got '{cfg.result_frequency}'"
        )

    if cfg.return_mode not in ("compounded", "non_compounded"):
        raise ConfigError(
            f"return_mode must be 'compounded' or 'non_compounded', "
            f"got '{cfg.return_mode}'"
        )

    if cfg.starting_capital <= 0:
        raise ConfigError("starting_capital must be positive.")


def validate_dataframe(df: pd.DataFrame, cfg: StrategyConfig) -> None:
    """Raise ConfigError if the required columns are missing or dates cannot be parsed."""

    if cfg.date_column not in df.columns:
        raise ConfigError(
            f"date_column '{cfg.date_column}' not found in CSV. "
            f"Available columns: {list(df.columns)}"
        )

    if cfg.net_return_column not in df.columns:
        raise ConfigError(
            f"net_return_column '{cfg.net_return_column}' not found in CSV. "
            f"Available columns: {list(df.columns)}"
        )

    # Try parsing dates
    try:
        pd.to_datetime(df[cfg.date_column], format=cfg.date_format, dayfirst=False)
    except Exception as exc:
        raise ConfigError(
            f"Could not parse '{cfg.date_column}' as dates "
            f"(frequency={cfg.result_frequency}): {exc}"
        ) from exc


# ---------------------------------------------------------------------------
# 3.  RETURN CALCULATIONS
# ---------------------------------------------------------------------------

def cumulative_return(returns_decimal: pd.Series, mode: str) -> pd.Series:
    """
    Compute a running cumulative-return series.

    Parameters
    ----------
    returns_decimal : pd.Series
        Period returns expressed as decimals (e.g. 0.03 for 3 %).
    mode : str
        'compounded'     → (1+r1)(1+r2)… - 1
        'non_compounded' → r1 + r2 + …

    Returns
    -------
    pd.Series
        Cumulative return as a decimal (multiply by 100 for %).
    """
    if mode == "compounded":
        return (1 + returns_decimal).cumprod() - 1
    else:  # non_compounded
        return returns_decimal.cumsum()


def nav_series(returns_decimal: pd.Series, starting_capital: float, mode: str) -> pd.Series:
    """
    Build a NAV/equity-curve series starting from *starting_capital*.

    For 'compounded':   NAV[t] = starting_capital × (1+r1)(1+r2)…(1+rt)
    For 'non_compounded': NAV[t] = starting_capital × (1 + Σr_i) up to t
    """
    cum = cumulative_return(returns_decimal, mode)
    return starting_capital * (1 + cum)


def annualised_return(cum_return_decimal: float, n_periods: int, freq: str) -> float:
    """
    Convert a total cumulative return to an annualised figure.

    Parameters
    ----------
    cum_return_decimal : float  (e.g. 0.50 for 50 %)
    n_periods : int             number of periods in the history
    freq : str                  'weekly' → 52 periods/year  |  'monthly' → 12
    """
    periods_per_year = 52 if freq == "weekly" else 12
    years = n_periods / periods_per_year
    if years <= 0:
        return 0.0
    return (1 + cum_return_decimal) ** (1 / years) - 1


def period_stats(returns_decimal: pd.Series, freq: str, mode: str) -> dict:
    """
    Compute a standard set of performance statistics for a return series.

    Returns a dict with string-formatted values ready for table display.
    """
    periods_per_year = 52 if freq == "weekly" else 12
    n = len(returns_decimal)
    if n < 2:
        return {k: "—" for k in [
            "Cumulative Return", "Annualized Return", "Avg Period Return",
            "Number of Periods", "% Winning Periods", "% Losing Periods",
            "Best 3 Periods", "Worst 3 Periods",
            "Max Drawdown", "Sharpe Ratio (approx)"
        ]}

    cum = cumulative_return(returns_decimal, mode).iloc[-1]
    ann = annualised_return(cum, n, freq)
    avg = returns_decimal.mean()
    wins = (returns_decimal > 0).sum()
    losses = (returns_decimal < 0).sum()

    # Sharpe (risk-free = 0, annualised)
    std = returns_decimal.std(ddof=1)
    sharpe = (avg / std * np.sqrt(periods_per_year)) if std > 0 else 0.0

    # Max drawdown on NAV
    nav = (1 + returns_decimal).cumprod()
    dd = (nav / nav.cummax() - 1)
    max_dd = dd.min()

    # Formatted % values (input already decimal)
    top3 = returns_decimal.nlargest(3) * 100
    bot3 = returns_decimal.nsmallest(3) * 100

    label = "Weeks" if freq == "weekly" else "Months"

    return {
        "Cumulative Return":     f"{cum*100:.2f}%",
        "Annualized Return":     f"{ann*100:.2f}%",
        f"Avg Period Return":    f"{avg*100:.3f}%",
        f"Number of {label}":   str(n),
        "% Winning Periods":     f"{wins} ({wins/n*100:.1f}%)",
        "% Losing Periods":      f"{losses} ({losses/n*100:.1f}%)",
        "Best 3 Periods":        ", ".join(f"{v:.2f}%" for v in top3),
        "Worst 3 Periods":       ", ".join(f"{v:.2f}%" for v in bot3),
        "Max Drawdown":          f"{max_dd*100:.2f}%",
        "Sharpe Ratio (approx)": f"{sharpe:.2f}",
    }


# ---------------------------------------------------------------------------
# 4.  PERIOD LABELLING
# ---------------------------------------------------------------------------

def period_label(date: pd.Timestamp, freq: str) -> str:
    """
    Return a human-readable label for a row date.

    weekly  → "Wk ending May 02, 2026"
    monthly → "Jan 2026"
    """
    if freq == "weekly":
        return f"Wk ending {date.strftime('%b %d, %Y')}"
    else:
        return date.strftime("%b %Y")


# ---------------------------------------------------------------------------
# 5.  BENCHMARK HELPERS
# ---------------------------------------------------------------------------

def download_benchmark_monthly(symbol: str, start: str, end: str) -> pd.Series:
    """
    Download price data for *symbol* and return monthly % returns (decimal).
    Falls back to an empty Series on failure.
    """
    try:
        data = yf.download(symbol, start=start, end=end,
                           auto_adjust=True, progress=False)
        if data.empty:
            warnings.warn(f"No data returned for {symbol}")
            return pd.Series(dtype=float)

        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        monthly = close.resample("ME").last()
        returns = monthly.pct_change().dropna()
        return returns
    except Exception as exc:
        warnings.warn(f"Failed to download {symbol}: {exc}")
        return pd.Series(dtype=float)


def download_benchmark_weekly(symbol: str, start: str, end: str) -> pd.Series:
    """
    Download price data and return weekly % returns (decimal).
    Week-end date = Friday close (resample 'W-FRI').
    """
    try:
        data = yf.download(symbol, start=start, end=end,
                           auto_adjust=True, progress=False)
        if data.empty:
            warnings.warn(f"No data returned for {symbol}")
            return pd.Series(dtype=float)

        close = data["Close"]
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]

        weekly = close.resample("W-FRI").last()
        returns = weekly.pct_change().dropna()
        return returns
    except Exception as exc:
        warnings.warn(f"Failed to download {symbol}: {exc}")
        return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# 6.  MAIN ENGINE
# ---------------------------------------------------------------------------

@dataclass
class ProcessedData:
    """
    Container for everything the UI needs.
    All DataFrames are ready for direct rendering – no further calculations
    should be needed in the Dash layer.
    """
    cfg: StrategyConfig

    # Core per-period table (the main "spreadsheet" table)
    period_table: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Yearly summary rows appended at the bottom of period_table
    # (also a DataFrame with the same columns for easy concat if desired)
    yearly_summary: pd.DataFrame = field(default_factory=pd.DataFrame)

    # Aggregate stats card data
    stats_inception: dict = field(default_factory=dict)
    stats_one_year:  dict = field(default_factory=dict)

    # NAV equity curve indexed by date
    nav_curve: pd.Series = field(default_factory=pd.Series)

    # Benchmark NAV curves keyed by display_name
    bench_nav: Dict[str, pd.Series] = field(default_factory=dict)

    # Benchmark per-period returns keyed by display_name
    bench_returns: Dict[str, pd.Series] = field(default_factory=dict)

    # Human-readable description of calculation mode (shown in UI banner)
    mode_description: str = ""


class TearsheetEngine:
    """
    Orchestrates all calculations given a StrategyConfig.

    Typical usage
    -------------
        cfg = StrategyConfig(
            strategy_name   = "Momentum Pacer",
            cta_name        = "Algominds Financial LLC",
            result_frequency= "monthly",
            return_mode     = "compounded",
            …
        )
        engine  = TearsheetEngine(cfg)
        raw_df  = pd.read_csv("data.csv")
        data    = engine.process(raw_df)
    """

    def __init__(self, cfg: StrategyConfig):
        validate_config(cfg)
        self.cfg = cfg

    # ------------------------------------------------------------------
    def process(self, raw_df: pd.DataFrame) -> ProcessedData:
        """
        Main entry point.  Validates, cleans, and computes everything.
        Returns a fully-populated ProcessedData object.
        """
        cfg = self.cfg
        validate_dataframe(raw_df, cfg)

        # 1. Parse dates and sort
        df = raw_df.copy()
        df[cfg.date_column] = pd.to_datetime(
            df[cfg.date_column], format=cfg.date_format, dayfirst=False
        )
        df = df.sort_values(cfg.date_column).reset_index(drop=True)
        df = df.drop_duplicates(subset=[cfg.date_column], keep="last")

        # 2. Extract net returns (stored as percentages in CSV → convert to decimal)
        net_pct = df[cfg.net_return_column].astype(float)
        net_dec = net_pct / 100.0

        dates = df[cfg.date_column]

        # 3. Optional columns
        gross_pct = (
            df[cfg.gross_return_column].astype(float)
            if cfg.gross_return_column and cfg.gross_return_column in df.columns
            else None
        )
        fees_pct = (
            df[cfg.fees_column].astype(float)
            if cfg.fees_column and cfg.fees_column in df.columns
            else None
        )
        nav_col = (
            df[cfg.nav_column].astype(float)
            if cfg.nav_column and cfg.nav_column in df.columns
            else None
        )
        capital_col = (
            df[cfg.capital_column].astype(float)
            if cfg.capital_column and cfg.capital_column in df.columns
            else None
        )

        # 4. Compute NAV curve
        nav = nav_series(net_dec, cfg.starting_capital, cfg.return_mode)
        nav_indexed = pd.Series(nav.values, index=dates)

        # 5. Cumulative return per period
        cum_series = cumulative_return(net_dec, cfg.return_mode)

        # 6. Build period table
        period_table = self._build_period_table(
            dates, net_pct, gross_pct, fees_pct,
            nav_indexed, capital_col, cum_series
        )

        # 7. Yearly summary
        yearly_summary = self._build_yearly_summary(
            dates, net_dec, cfg.return_mode
        )

        # 8. Stats
        stats_inception = period_stats(net_dec, cfg.result_frequency, cfg.return_mode)
        one_year_cutoff = dates.max() - pd.DateOffset(
            weeks=51 if cfg.result_frequency == "weekly" else 0,
            months=0 if cfg.result_frequency == "weekly" else 11,
        )
        mask_1y = dates >= one_year_cutoff
        stats_1y = period_stats(
            net_dec[mask_1y].reset_index(drop=True),
            cfg.result_frequency, cfg.return_mode
        )

        # 9. Benchmarks (only if enabled)
        bench_nav     : Dict[str, pd.Series] = {}
        bench_returns : Dict[str, pd.Series] = {}

        if cfg.display_benchmarks:
            dl_fn = (download_benchmark_weekly
                     if cfg.result_frequency == "weekly"
                     else download_benchmark_monthly)
            start_str = dates.min().strftime("%Y-%m-%d")
            end_str   = (dates.max() + pd.DateOffset(months=2)).strftime("%Y-%m-%d")

            for display_name, symbol in cfg.benchmark_symbols:
                b_ret = dl_fn(symbol, start_str, end_str)
                if b_ret.empty:
                    continue
                bench_returns[display_name] = b_ret
                b_nav = nav_series(b_ret, cfg.starting_capital, cfg.return_mode)
                bench_nav[display_name] = b_nav

        # 10. Mode description banner
        freq_label = "Weekly" if cfg.result_frequency == "weekly" else "Monthly"
        mode_label = "Compounded" if cfg.return_mode == "compounded" else "Non-Compounded"
        mode_desc  = f"Frequency: {freq_label}   |   Return Calculation: {mode_label}"

        print(f"[TearsheetEngine] {mode_desc}")
        print(f"[TearsheetEngine] Periods processed: {len(df)}")
        print(f"[TearsheetEngine] Cumulative Net Return (inception): "
              f"{cum_series.iloc[-1]*100:.2f}%")

        return ProcessedData(
            cfg             = cfg,
            period_table    = period_table,
            yearly_summary  = yearly_summary,
            stats_inception = stats_inception,
            stats_one_year  = stats_1y,
            nav_curve       = nav_indexed,
            bench_nav       = bench_nav,
            bench_returns   = bench_returns,
            mode_description= mode_desc,
        )

    # ------------------------------------------------------------------
    def _build_period_table(
        self,
        dates,
        net_pct,
        gross_pct,
        fees_pct,
        nav_indexed,
        capital_col,
        cum_series,
    ) -> pd.DataFrame:
        """
        Build the main per-period DataFrame.
        Columns are only included when data is available.
        """
        cfg = self.cfg
        rows = []
        nav_vals = nav_indexed.values

        for i in range(len(dates)):
            row: dict = {}

            row["Period"] = period_label(dates.iloc[i], cfg.result_frequency)

            # Start / End capital (prefer explicit column, fallback to derived NAV)
            if capital_col is not None:
                row["Start Capital"] = f"${capital_col.iloc[i]:,.0f}"
            else:
                start_nav = nav_vals[i - 1] if i > 0 else cfg.starting_capital
                row["Start Capital"] = f"${start_nav:,.0f}"

            row["End Capital"] = f"${nav_vals[i]:,.0f}"

            if gross_pct is not None:
                row["Gross Return %"] = f"{gross_pct.iloc[i]:.2f}%"

            if fees_pct is not None:
                row["Fees %"] = f"{fees_pct.iloc[i]:.2f}%"

            row["Net Return %"] = f"{net_pct.iloc[i]:.2f}%"

            row["Cumulative Net %"] = f"{cum_series.iloc[i]*100:.2f}%"

            rows.append(row)

        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    def _build_yearly_summary(
        self,
        dates,
        net_dec: pd.Series,
        mode: str,
    ) -> pd.DataFrame:
        """
        Aggregate returns by calendar year.
        Uses compounding or summation depending on *mode*.
        """
        years = sorted(dates.dt.year.unique())
        rows = []
        for yr in years:
            mask = dates.dt.year == yr
            yr_ret = net_dec[mask]
            if mode == "compounded":
                total = (1 + yr_ret).prod() - 1
            else:
                total = yr_ret.sum()

            rows.append({"Year": str(yr), "Annual Net Return": f"{total*100:.2f}%"})

        return pd.DataFrame(rows)
