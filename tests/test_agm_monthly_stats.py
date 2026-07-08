"""Tests for AGM derived monthly return statistics."""
from __future__ import annotations

import pandas as pd
import pytest

import algominds_monthly_stats as ams


def test_synthetic_monthly_return_statistics():
    returns = pd.Series([0.10, -0.05, 0.20, 0.05, -0.02, -0.03])
    stats = ams.compute_monthly_return_statistics(returns)

    assert stats.positive_count == 3
    assert stats.negative_count == 3
    assert stats.positive_pct == pytest.approx(50.0)
    assert stats.negative_pct == pytest.approx(50.0)
    assert stats.average_winning_month_pct == pytest.approx(11.6666666667, rel=1e-6)
    assert stats.average_losing_month_pct == pytest.approx(-3.3333333333, rel=1e-6)
    assert stats.best_single_month_pct == pytest.approx(20.0)
    assert stats.worst_single_month_pct == pytest.approx(-5.0)
    assert stats.longest_winning_streak_months == 2
    assert stats.longest_losing_streak_months == 2


def test_zero_month_excluded_from_positive_negative_counts():
    returns = pd.Series([0.10, 0.0, -0.05, 0.20])
    stats = ams.compute_monthly_return_statistics(returns)

    assert stats.positive_count == 2
    assert stats.negative_count == 1
    assert stats.positive_pct == pytest.approx(66.6666667, rel=1e-6)
    assert stats.negative_pct == pytest.approx(33.3333333, rel=1e-6)


def test_zero_month_breaks_streaks():
    returns = pd.Series([0.10, 0.20, 0.0, 0.05, 0.08])
    stats = ams.compute_monthly_return_statistics(returns)
    assert stats.longest_winning_streak_months == 2


def test_real_agm_monthly_statistics_match_accepted_values():
    import mp_ts

    stats = ams.compute_monthly_return_statistics(mp_ts._display_summary_df)
    rendered = ams.format_monthly_return_statistics(stats)

    assert stats.positive_count == 5
    assert stats.negative_count == 3
    assert stats.positive_pct == pytest.approx(62.5)
    assert stats.negative_pct == pytest.approx(37.5)
    assert stats.average_winning_month_pct == pytest.approx(15.80, abs=0.01)
    assert stats.average_losing_month_pct == pytest.approx(-6.28, abs=0.01)
    assert stats.best_single_month_pct == pytest.approx(38.01, abs=0.01)
    assert stats.worst_single_month_pct == pytest.approx(-8.81, abs=0.01)
    assert stats.longest_winning_streak_months == 2
    assert stats.longest_losing_streak_months == 1

    assert rendered["Number of Positive Months"] == "5 (62.5%)"
    assert rendered["Number of Negative Months"] == "3 (37.5%)"
    assert rendered["Average Winning Month %"] == "15.80%"
    assert rendered["Average Losing Month %"] == "-6.28%"
    assert rendered["Best Single Month %"] == "38.01%"
    assert rendered["Worst Single Month %"] == "-8.81%"
    assert rendered["Longest Winning Streak"] == "2 months"
    assert rendered["Longest Losing Streak"] == "1 months"


def test_partial_july_2026_excluded_from_monthly_summary():
    import mp_ts

    dates = list(mp_ts._display_summary_df["date"])
    assert pd.Timestamp("2026-07-01") not in dates
    assert pd.Timestamp("2026-06-01") in dates
    assert len(mp_ts._display_summary_df) == 8


def test_mp_ts_monthly_stats_card_uses_helper_not_hardcoded_literals():
    import mp_ts

    assert mp_ts.monthly_stats == ams.format_monthly_return_statistics(
        ams.compute_monthly_return_statistics(mp_ts._display_summary_df)
    )
