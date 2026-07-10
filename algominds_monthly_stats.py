"""
Algominds / Momentum Pacer — monthly return statistics (AGM-only).

Derives the Monthly Performance Statistics card from a chronological series of
complete-month net returns (decimal fractions, e.g. 0.10 = +10%).

Rules:
  - Positive month: return > 0
  - Negative month: return < 0
  - Zero-return months are excluded from positive/negative counts and from the
    percentage denominator; they break win/loss streaks.
  - Streaks follow calendar month order in the input series.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Union

import pandas as pd

SeriesLike = Union[pd.Series, pd.DataFrame]


@dataclass(frozen=True)
class MonthlyReturnStatistics:
    positive_count: int
    positive_pct: float
    negative_count: int
    negative_pct: float
    average_winning_month_pct: float
    average_losing_month_pct: float
    best_single_month_pct: float
    worst_single_month_pct: float
    longest_winning_streak_months: int
    longest_losing_streak_months: int


def _extract_returns(monthly_returns: SeriesLike) -> pd.Series:
    if isinstance(monthly_returns, pd.DataFrame):
        if "bot_net_ret" not in monthly_returns.columns:
            raise ValueError("monthly_returns DataFrame must include bot_net_ret")
        return monthly_returns["bot_net_ret"].astype(float).reset_index(drop=True)
    return pd.Series(monthly_returns).astype(float).reset_index(drop=True)


def _longest_streaks(returns: pd.Series) -> tuple[int, int]:
    longest_win = longest_loss = 0
    cur_win = cur_loss = 0
    for value in returns:
        if value > 0:
            cur_win += 1
            if cur_loss:
                longest_loss = max(longest_loss, cur_loss)
                cur_loss = 0
        elif value < 0:
            cur_loss += 1
            if cur_win:
                longest_win = max(longest_win, cur_win)
                cur_win = 0
        else:
            if cur_win:
                longest_win = max(longest_win, cur_win)
                cur_win = 0
            if cur_loss:
                longest_loss = max(longest_loss, cur_loss)
                cur_loss = 0
    if cur_win:
        longest_win = max(longest_win, cur_win)
    if cur_loss:
        longest_loss = max(longest_loss, cur_loss)
    return longest_win, longest_loss


def compute_monthly_return_statistics(monthly_returns: SeriesLike) -> MonthlyReturnStatistics:
    """Compute monthly return statistics from decimal monthly net returns."""
    rets = _extract_returns(monthly_returns)
    if rets.empty:
        return MonthlyReturnStatistics(
            positive_count=0,
            positive_pct=0.0,
            negative_count=0,
            negative_pct=0.0,
            average_winning_month_pct=0.0,
            average_losing_month_pct=0.0,
            best_single_month_pct=0.0,
            worst_single_month_pct=0.0,
            longest_winning_streak_months=0,
            longest_losing_streak_months=0,
        )

    positive = rets[rets > 0]
    negative = rets[rets < 0]
    nonzero = rets[rets != 0]
    denom = len(nonzero)

    positive_pct = (len(positive) / denom * 100.0) if denom else 0.0
    negative_pct = (len(negative) / denom * 100.0) if denom else 0.0
    avg_win = float(positive.mean() * 100.0) if len(positive) else 0.0
    avg_loss = float(negative.mean() * 100.0) if len(negative) else 0.0
    best = float(rets.max() * 100.0)
    worst = float(rets.min() * 100.0)
    longest_win, longest_loss = _longest_streaks(rets)

    return MonthlyReturnStatistics(
        positive_count=int(len(positive)),
        positive_pct=positive_pct,
        negative_count=int(len(negative)),
        negative_pct=negative_pct,
        average_winning_month_pct=avg_win,
        average_losing_month_pct=avg_loss,
        best_single_month_pct=best,
        worst_single_month_pct=worst,
        longest_winning_streak_months=longest_win,
        longest_losing_streak_months=longest_loss,
    )


def format_monthly_return_statistics(stats: MonthlyReturnStatistics) -> Mapping[str, str]:
    """Render statistics for the AGM Monthly Performance Statistics card."""
    if stats.positive_count == 0 and stats.negative_count == 0:
        empty = "—"
        return {
            "Number of Positive Months": empty,
            "Number of Negative Months": empty,
            "Average Winning Month %": empty,
            "Average Losing Month %": empty,
            "Best Single Month %": empty,
            "Worst Single Month %": empty,
            "Longest Winning Streak": empty,
            "Longest Losing Streak": empty,
        }

    return {
        "Number of Positive Months": (
            f"{stats.positive_count} ({stats.positive_pct:.1f}%)"
        ),
        "Number of Negative Months": (
            f"{stats.negative_count} ({stats.negative_pct:.1f}%)"
        ),
        "Average Winning Month %": (
            f"{stats.average_winning_month_pct:.2f}%"
            if stats.positive_count
            else "—"
        ),
        "Average Losing Month %": (
            f"{stats.average_losing_month_pct:.2f}%"
            if stats.negative_count
            else "—"
        ),
        "Best Single Month %": f"{stats.best_single_month_pct:.2f}%",
        "Worst Single Month %": f"{stats.worst_single_month_pct:.2f}%",
        "Longest Winning Streak": f"{stats.longest_winning_streak_months} months",
        "Longest Losing Streak": f"{stats.longest_losing_streak_months} months",
    }
