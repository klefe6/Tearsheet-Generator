"""Unit tests for AGM Account Stats helper (public tearsheet table)."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

import algominds_account_stats as stats


def _sample_summary_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2025-11-01"),
                "bot_start": 30_000.0,
                "bot_end_after_fees": 34_338.0,
                "bot_net_ret": 0.1446,
                "bot_fees_pct": 0.0,
            },
            {
                "date": pd.Timestamp("2026-06-01"),
                "bot_start": 45_000.0,
                "bot_end_after_fees": 48_049.07,
                "bot_net_ret": 0.1016,
                "bot_fees_pct": 0.0314,
            },
        ]
    )


def _sample_net_totals() -> dict:
    return {
        "bot_net_dollar": 18_049.07,
        "bot_fees_dollar": 8_392.91,
    }


INCEPTION = datetime(2025, 11, 13)


def test_nav_chart_title_has_no_compounded():
    assert "Compounded" not in stats.NAV_SINCE_INCEPTION_CHART_TITLE
    assert "NAV Since Inception" in stats.NAV_SINCE_INCEPTION_CHART_TITLE


def test_compute_agm_account_stats_from_summary():
    result = stats.compute_agm_account_stats(
        _sample_summary_df(), _sample_net_totals(), INCEPTION
    )
    assert result is not None
    assert result.starting_capital == pytest.approx(30_000.0)
    assert result.current_nav_after_fees == pytest.approx(48_049.07)
    assert result.total_net_gain == pytest.approx(18_049.07)
    assert result.total_fees_paid == pytest.approx(8_392.91)
    assert result.inception_date == INCEPTION
    assert result.latest_report_date == pd.Timestamp("2026-06-01").to_pydatetime()


def test_total_net_gain_matches_nav_delta_without_cashflows():
    """No deposits/withdrawals: net gain = latest NAV - starting capital."""
    result = stats.compute_agm_account_stats(
        _sample_summary_df(), _sample_net_totals(), INCEPTION
    )
    assert result is not None
    naive = result.current_nav_after_fees - result.starting_capital
    assert result.total_net_gain == pytest.approx(naive)


def test_months_trading_uses_latest_report_date_not_today():
    months = stats.months_trading_elapsed_approx(
        INCEPTION, datetime(2026, 6, 1)
    )
    # Nov 13, 2025 → Jun 1, 2026 ≈ 6.6 months (matches live tearsheet convention).
    assert months == pytest.approx(6.6, abs=0.1)


def test_months_trading_updates_with_later_data():
    early = stats.months_trading_elapsed_approx(
        INCEPTION, datetime(2026, 3, 1)
    )
    later = stats.months_trading_elapsed_approx(
        INCEPTION, datetime(2026, 6, 1)
    )
    assert later > early


def test_format_agm_account_stats():
    result = stats.compute_agm_account_stats(
        _sample_summary_df(), _sample_net_totals(), INCEPTION
    )
    assert result is not None
    formatted = stats.format_agm_account_stats(result)
    assert formatted["starting_capital"] == "$30,000"
    assert formatted["current_nav_after_fees"] == "$48,049.07"
    assert formatted["total_net_gain"] == "$18,049.07"
    assert formatted["total_fees_paid"] == "$8,392.91"
    assert formatted["inception_date"] == "November 13, 2025"
    assert formatted["months_trading_approx"] == f"{result.months_trading_approx:.1f}"


def test_compute_returns_none_when_empty():
    assert stats.compute_agm_account_stats(pd.DataFrame(), {}, INCEPTION) is None


def test_mp_ts_nav_figure_title():
    """Integration: live mp_ts chart must not expose 'Compounded' in the title."""
    import sys
    from pathlib import Path

    mp_dir = Path(__file__).resolve().parent.parent / "Momentum Pacer"
    if str(mp_dir) not in sys.path:
        sys.path.insert(0, str(mp_dir))
    import mp_ts

    fig = mp_ts.build_nav_figure()
    title_text = fig.layout.title.text or ""
    assert "Compounded" not in title_text
    assert "NAV Since Inception" in title_text


def test_mp_ts_account_stats_not_hardcoded_literals():
    """Program Account Stats in layout must match the helper, not inline literals."""
    import sys
    from pathlib import Path

    mp_dir = Path(__file__).resolve().parent.parent / "Momentum Pacer"
    if str(mp_dir) not in sys.path:
        sys.path.insert(0, str(mp_dir))
    import mp_ts

    program_stats = stats.compute_agm_program_account_stats()
    rows = stats.format_agm_program_account_stats(program_stats)
    by_label = {label: (total, client, prop) for label, total, client, prop in rows}

    layout = mp_ts.serve_layout()
    layout_str = str(layout)
    assert by_label["Total Accounts/Tranches Opened"] == ("12", "7", "5")
    assert by_label["Nominal Assets Being Traded in the Program"] == (
        "360k",
        "210k",
        "150k",
    )
    for total, client, prop in by_label.values():
        assert total in layout_str
        assert client in layout_str
        assert prop in layout_str
    assert "Current NAV (after fees)" not in layout_str
    assert "Compounded NAV Since Inception" not in layout_str


def test_compute_agm_program_account_stats_known_buckets():
    """Client-facing Proprietary | Client table uses program-level bucket config."""
    result = stats.compute_agm_program_account_stats()
    assert result.proprietary.total_opened == 5
    assert result.proprietary.currently_open == 5
    assert result.proprietary.closed_profitably == 0
    assert result.proprietary.closed_unprofitably == 0
    assert result.proprietary.closed_return_range is None
    assert result.proprietary.nominal_assets == pytest.approx(150_000.0)

    assert result.client.total_opened == 7
    assert result.client.currently_open == 6
    assert result.client.closed_profitably == 1
    assert result.client.closed_unprofitably == 0
    assert result.client.closed_return_range == "0–1%"
    assert result.client.nominal_assets == pytest.approx(210_000.0)


def test_format_agm_program_account_stats_no_na_for_closed_counts():
    result = stats.compute_agm_program_account_stats()
    rows = stats.format_agm_program_account_stats(result)
    by_label = {label: (total, client, prop) for label, total, client, prop in rows}
    assert by_label["Accounts/Tranches Closed Profitably"] == ("1", "1", "0")
    assert by_label["Accounts/Tranches Closed Unprofitably"] == ("0", "0", "0")
    assert by_label["Range of Net Returns of Accounts/Tranches Closed"] == (
        "0–1%",
        "0–1%",
        "N/A",
    )
    assert by_label["Nominal Assets Being Traded in the Program"] == (
        "360k",
        "210k",
        "150k",
    )
    assert by_label["Total Accounts/Tranches Opened"] == ("12", "7", "5")
    assert by_label["Accounts/Tranches Currently Open"] == ("11", "6", "5")
