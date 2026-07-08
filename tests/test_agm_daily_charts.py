"""AGM chart daily-resolution tests: client NAV / drawdown, admin NLV and
accrued fees must be built from the DAILY balances CSV + daily SPX benchmark,
not from monthly workbook snapshots."""
from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture(scope="module")
def mp():
    import mp_ts

    return mp_ts


@pytest.fixture(scope="module")
def daily_expected(mp) -> pd.DataFrame:
    """The daily rows the client chart must plot (CSV rows from live inception)."""
    df = mp.daily_balances_df
    return df[df["Date"] >= pd.Timestamp(mp.PROGRAM_INCEPTION)].reset_index(drop=True)


# ── Client-facing NAV chart ──────────────────────────────────────────────────

def test_client_nav_chart_is_daily_not_monthly(mp, daily_expected):
    fig = mp.build_nav_figure()
    bot = next(t for t in fig.data if t.name == mp.CLIENT_NAV_TRACE_NAME)
    assert len(bot.x) == len(daily_expected)


def test_client_nav_chart_plots_client_net_value(mp, daily_expected):
    fig = mp.build_nav_figure()
    bot = next(t for t in fig.data if t.name == mp.CLIENT_NAV_TRACE_NAME)
    inception_tbl = mp.daily_accounting.table[
        mp.daily_accounting.table["Date"] >= pd.Timestamp(mp.PROGRAM_INCEPTION)
    ]
    assert len(bot.x) == len(inception_tbl)
    assert [float(v) for v in bot.y] == pytest.approx(
        [float(v) for v in inception_tbl["client_net_value"]]
    )
    assert pd.Timestamp(bot.x[0]) == pd.Timestamp(mp.PROGRAM_INCEPTION)
    assert pd.Timestamp(bot.x[-1]) == inception_tbl["Date"].iloc[-1]


def test_client_nav_chart_has_daily_spx_benchmark(mp, daily_expected):
    fig = mp.build_nav_figure()
    spx = next(t for t in fig.data if t.name == "S&P 500 (rebased, daily)")
    assert len(spx.x) == len(daily_expected)
    # Rebased to the same $30,000 start.
    assert float(spx.y[0]) == pytest.approx(float(mp.STARTING_CAPITAL))


def test_client_nav_chart_has_daily_ndx_benchmark(mp, daily_expected):
    # NDX stays on the approved client display, converted to daily like SPX.
    fig = mp.build_nav_figure()
    ndx = next(t for t in fig.data if t.name == "Nasdaq-100 (rebased, daily)")
    assert len(ndx.x) == len(daily_expected)
    assert float(ndx.y[0]) == pytest.approx(float(mp.STARTING_CAPITAL))


def test_client_drawdown_chart_is_daily(mp, daily_expected):
    fig = mp.build_drawdown_figure()
    dd = fig.data[0]
    assert len(dd.x) == len(daily_expected)
    assert all(float(v) <= 0 for v in dd.y)


def test_client_layout_does_not_expose_raw_admin_table(mp):
    """The public layout must not carry the raw admin balances table columns or
    values — that content only renders via the server-side auth-gated callback."""
    layout_str = str(mp.serve_layout())
    assert "Buying Power/Margin Deficit" not in layout_str
    assert "45,675.81" not in layout_str  # latest raw NLV
    assert "agm-daily-nlv-graph" not in layout_str


# ── Admin NLV chart ──────────────────────────────────────────────────────────

def test_admin_nlv_chart_shows_every_csv_trading_day(mp):
    fig = mp.build_agm_daily_nlv_figure()
    assert len(fig.data[0].x) == len(mp.daily_balances_df)
    assert fig.layout.title.text == "Actual NLV / TradeStation Net Worth"


# ── Accrued fees chart ───────────────────────────────────────────────────────

def test_accrued_fees_chart_is_daily_from_agm_vs_spx(mp):
    fig = mp.build_agm_accrued_fees_figure()
    line = fig.data[0]
    inception_rows = mp.daily_accounting.table[
        mp.daily_accounting.table["Date"] >= pd.Timestamp(mp.PROGRAM_INCEPTION)
    ]
    assert len(line.x) == len(inception_rows)
    assert len(line.x) > 100
    assert "Accrued Unpaid Fees" in fig.layout.title.text


def test_accrued_fees_chart_not_monthly_spike_triads(mp):
    """The old monthly chart plotted (0, fee, 0) triads — 3 points per month.
    The daily chart has one point per trading day and does not zero out at
    every third point."""
    fig = mp.build_agm_accrued_fees_figure()
    y = [float(v) for v in fig.data[0].y]
    assert len(y) != 3 * len(mp._display_summary_df)
    assert any(v != 0 for v in y[2::3])


def test_accrued_fees_values_never_negative(mp):
    fig = mp.build_agm_accrued_fees_figure()
    assert all(float(v) >= 0 for v in fig.data[0].y)


def test_monthly_spike_functions_removed(mp):
    # The monthly-resolution builders must be gone entirely.
    assert not hasattr(mp, "_compute_agm_fee_series")
    assert not hasattr(mp, "build_agm_nlv_figure")


# ── Monthly workbook stays internal-only ─────────────────────────────────────

def test_monthly_workbook_still_loaded_as_internal_reference(mp):
    assert mp.EXCEL_PATH.is_file()
    assert not mp.summary_df.empty
    # It feeds payment-reconciliation evidence in the daily fee engine.
    assert any(p["method"] == "workbook-reconciliation"
               for p in mp.daily_fee_accrual.payments)


def test_no_monthly_chart_reachable_in_layout(mp):
    layout_str = str(mp.serve_layout())
    assert "agm-nlv-graph" not in layout_str  # old monthly NLV chart removed
    assert "monthly resolution" not in layout_str.lower()
