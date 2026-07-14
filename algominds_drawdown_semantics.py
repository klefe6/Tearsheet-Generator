"""
Algominds / Momentum Pacer — drawdown semantics helper (AGM-only).

The Momentum Pacer strategy is traded as ONE trading-unit with $30,000 initial
strategy capital. Client-facing AGM drawdown percentages express peak-to-valley
dollar declines as a share of that initial capital — not as a share of the
recent NAV peak.

  * Strategy grows from $30k to $50k, then loses $5k to $45k.
  * AGM reports drawdown depth as $5k / $30k = 16.7% (% of initial capital).
  * Standard peak-relative drawdown would be $5k / $50k = 10%.

This module is the single source of truth for AGM drawdown labels, the daily
drawdown series, and worst-episode profile rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

# ── AGM strategy unit constants ─────────────────────────────────────────────
AGM_INITIAL_CAPITAL = 30_000.0

# ── Labels (shared by client + admin) ─────────────────────────────────────
STRATEGY_UNIT_DRAWDOWN_LABEL = "Drawdown (% of Initial Capital)"
STRATEGY_UNIT_DRAWDOWN_CHART_TITLE = (
    "<u>Strategy Unit Drawdown from Peak (% of Initial Capital)</u>"
)
NA_DISPLAY = "N/A"

DRAWDOWN_METRIC_ORDER: Tuple[str, ...] = (
    "Depth",
    "Decline Period",
    "Recovery Period",
    "Total Duration",
    "Start Date",
    "Valley Date",
    "End Date",
)

AGM_INCEPTION_COLUMN = "AGM (Inception)"
SPX_INCEPTION_COLUMN = "S&P 500 (Inception)"

AGM_DRAWDOWN_FOOTNOTE = (
    "Drawdown depth is peak-to-valley decline expressed as a percentage of the "
    "$30,000 initial strategy capital (not peak NAV)."
)


@dataclass(frozen=True)
class StrategyUnitDrawdown:
    """Strategy-UNIT drawdown from the strategy NAV curve.

    Percentages are in PERCENT units and are <= 0.0 (0.0 exactly at a fresh
    high, negative below the running peak). Denominator is initial capital.
    """

    strategy_unit_starting_capital: Optional[float]
    strategy_unit_initial_capital: Optional[float]
    strategy_unit_high_watermark: Optional[float]
    strategy_unit_current_nav: Optional[float]
    strategy_unit_current_drawdown_pct: Optional[float]
    strategy_unit_max_drawdown_pct: Optional[float]

    @property
    def available(self) -> bool:
        return self.strategy_unit_current_drawdown_pct is not None


@dataclass(frozen=True)
class DrawdownPeriod:
    depth_decimal: float
    decline_days: int
    recovery_days_text: str
    total_duration_text: str
    start_date: str
    valley_date: str
    end_date: str

    def to_display_row(self) -> Dict[str, str]:
        return {
            "Depth": f"{self.depth_decimal:.1f}%",
            "Decline Period": f"{self.decline_days} days",
            "Recovery Period": self.recovery_days_text,
            "Total Duration": self.total_duration_text,
            "Start Date": self.start_date,
            "Valley Date": self.valley_date,
            "End Date": self.end_date,
        }


def _resolve_initial_capital(
    equity_values: Sequence[float],
    initial_capital: Optional[float],
) -> Optional[float]:
    if initial_capital is not None:
        return float(initial_capital)
    vals = [float(v) for v in equity_values if v is not None]
    if not vals:
        return None
    return float(vals[0])


def drawdown_pct_of_initial_capital(
    nav: float,
    running_peak: float,
    initial_capital: float,
) -> float:
    """Peak-to-current dollar decline as % of initial capital (<= 0)."""
    if initial_capital <= 0:
        return 0.0
    return (float(nav) - float(running_peak)) / float(initial_capital) * 100.0


def compute_strategy_unit_drawdown(
    equity_values: Sequence[float],
    *,
    initial_capital: Optional[float] = None,
) -> StrategyUnitDrawdown:
    """Strategy-unit drawdown using initial capital as the percentage denominator."""
    vals = [float(v) for v in equity_values if v is not None]
    baseline = _resolve_initial_capital(vals, initial_capital)
    if not vals or baseline is None or baseline <= 0:
        return StrategyUnitDrawdown(None, baseline, None, None, None, None)

    peak = vals[0]
    max_dd = 0.0
    for v in vals:
        if v > peak:
            peak = v
        dd = drawdown_pct_of_initial_capital(v, peak, baseline)
        if dd < max_dd:
            max_dd = dd

    starting = vals[0]
    current = vals[-1]
    hwm = max(vals)
    current_dd = drawdown_pct_of_initial_capital(current, hwm, baseline)
    return StrategyUnitDrawdown(
        strategy_unit_starting_capital=starting,
        strategy_unit_initial_capital=baseline,
        strategy_unit_high_watermark=hwm,
        strategy_unit_current_nav=current,
        strategy_unit_current_drawdown_pct=current_dd,
        strategy_unit_max_drawdown_pct=max_dd,
    )


def drawdown_series_pct_of_initial_capital(
    equity_values: Sequence[float],
    *,
    initial_capital: Optional[float] = None,
) -> List[float]:
    """Daily drawdown series aligned to *equity_values* (% of initial capital)."""
    vals = [float(v) for v in equity_values if v is not None]
    baseline = _resolve_initial_capital(vals, initial_capital)
    if not vals or baseline is None or baseline <= 0:
        return []

    peak = vals[0]
    out: List[float] = []
    for v in vals:
        if v > peak:
            peak = v
        out.append(drawdown_pct_of_initial_capital(v, peak, baseline))
    return out


def worst_drawdown_profile(
    nav: pd.Series,
    *,
    initial_capital: float,
) -> Optional[DrawdownPeriod]:
    """Worst drawdown episode for a dated NAV series (% of initial capital)."""
    if nav is None or nav.empty:
        return None
    if len(nav) == 1:
        only = nav.index[0]
        only_date = only.strftime("%Y-%m-%d")
        return DrawdownPeriod(
            depth_decimal=0.0,
            decline_days=0,
            recovery_days_text="0 days",
            total_duration_text="0 days",
            start_date=only_date,
            valley_date=only_date,
            end_date=only_date,
        )

    baseline = float(initial_capital)
    if baseline <= 0:
        return None

    nav = nav.astype(float)
    running_max = nav.cummax()
    dd_series = (nav - running_max) / baseline * 100.0

    trough = dd_series.idxmin()
    peak = nav.loc[:trough].idxmax()

    peak_date = peak.strftime("%Y-%m-%d")
    valley_date = trough.strftime("%Y-%m-%d")
    decline_days = int((trough - peak).days)

    recovered_slice = nav.loc[trough:][nav.loc[trough:] >= nav.loc[peak]]
    rec_idx = recovered_slice.index[0] if not recovered_slice.empty else None

    if rec_idx is not None:
        end_date = rec_idx.strftime("%Y-%m-%d")
        recovery_days = int((rec_idx - trough).days)
        total_days = int((rec_idx - peak).days)
        recovery_text = f"{recovery_days} days"
        total_text = f"{total_days} days"
    else:
        last_date = nav.index.max()
        end_date = "TBD"
        recovery_days = int((last_date - trough).days)
        total_days = int((last_date - peak).days)
        recovery_text = f"Ongoing for {recovery_days} days"
        total_text = f"Ongoing for {total_days} days"

    depth = float(dd_series.min())
    return DrawdownPeriod(
        depth_decimal=depth,
        decline_days=decline_days,
        recovery_days_text=recovery_text,
        total_duration_text=total_text,
        start_date=peak_date,
        valley_date=valley_date,
        end_date=end_date,
    )


def build_drawdown_profile_dataframe(
    strategy_nav: pd.Series,
    *,
    initial_capital: float = AGM_INITIAL_CAPITAL,
    benchmark_nav: Optional[pd.Series] = None,
    benchmark_column: str = SPX_INCEPTION_COLUMN,
) -> pd.DataFrame:
    """Maximum Drawdown Profile table for AGM (optional benchmark column)."""
    columns: Dict[str, List[str]] = {"Metric": list(DRAWDOWN_METRIC_ORDER)}
    strategy_period = worst_drawdown_profile(strategy_nav, initial_capital=initial_capital)
    if strategy_period is None:
        columns[AGM_INCEPTION_COLUMN] = [NA_DISPLAY] * len(DRAWDOWN_METRIC_ORDER)
    else:
        row = strategy_period.to_display_row()
        columns[AGM_INCEPTION_COLUMN] = [row[m] for m in DRAWDOWN_METRIC_ORDER]

    if benchmark_nav is not None and not benchmark_nav.empty:
        benchmark_period = worst_drawdown_profile(benchmark_nav, initial_capital=initial_capital)
        if benchmark_period is None:
            columns[benchmark_column] = [NA_DISPLAY] * len(DRAWDOWN_METRIC_ORDER)
        else:
            bench_row = benchmark_period.to_display_row()
            columns[benchmark_column] = [bench_row[m] for m in DRAWDOWN_METRIC_ORDER]

    return pd.DataFrame(columns)


def format_drawdown_pct(pct: Optional[float]) -> str:
    """``'-10.0%'`` style; ``N/A`` when unavailable. Input is already in percent."""
    if pct is None:
        return NA_DISPLAY
    return f"{pct:.1f}%"
