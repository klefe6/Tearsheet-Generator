"""Tests for tcp_dashboard pure propagation layer."""
from __future__ import annotations

import ast
import math
from copy import deepcopy
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objs as go
import pytest

from tcp_config import load_config
from tcp_dashboard import (
    LABEL_HEADER,
    LABEL_UNAVAILABLE,
    METRIC_LABELS,
    STRATEGY_NAME,
    build_tcp_current_data_labels,
    build_tcp_nav_figure,
    calculate_period_metrics,
    canonical_nav_records_from_ledger,
    canonical_records_to_series,
    propagate_tcp_dashboard,
    recompute_tcp_daily_metrics,
    recompute_tcp_monthly_performance,
    DuplicateCanonicalDate,
    InvalidCanonicalNAV,
    NonChronologicalCanonicalDate,
)
from tcp_benchmarks import (
    BENCHMARK_STATUS_READY,
    BENCHMARK_STATUS_UNAVAILABLE,
    BTC_SYMBOL,
    ETH_SYMBOL,
    BenchmarkResult,
)
from tcp_drawdown import (
    BTC_INCEPTION_COLUMN,
    ETH_INCEPTION_COLUMN,
    SPXTR_INCEPTION_COLUMN,
    STRATEGY_INCEPTION_COLUMN,
    format_drawdown_table_for_display,
)
from tcp_ledger import load_ledger

REPO_ROOT = Path(__file__).resolve().parent.parent
_SESSION_LEDGER = None


def _get_session_ledger():
    global _SESSION_LEDGER
    if _SESSION_LEDGER is None:
        cfg = load_config()
        wb = Path(cfg.workbook_path)
        if not wb.is_file():
            pytest.skip("TCP workbook not available")
        _SESSION_LEDGER = load_ledger(cfg.workbook_path, cfg.sheet_name)
    return _SESSION_LEDGER


@pytest.fixture(scope="session")
def ledger():
    return _get_session_ledger()


@pytest.fixture(scope="session")
def canonical(ledger):
    return canonical_nav_records_from_ledger(ledger.completed_records)


@pytest.fixture(scope="session")
def propagation(canonical):
    return propagate_tcp_dashboard(canonical)


def _sample_records():
    return [
        {"Date": "2026-01-20", "NAV": 50000.0},
        {"Date": "2026-01-21", "NAV": 50013.472},
        {"Date": "2026-01-23", "NAV": 50031.504},
    ]


def test_canonical_conversion_from_ledger(ledger, canonical):
    assert len(canonical) == 112
    assert canonical[0]["Date"] == "2026-01-20"
    assert canonical[-1]["Date"] == "2026-06-24"
    assert math.isclose(canonical[-1]["NAV"], 44871.384, abs_tol=0.001)


def test_canonical_dates_ordered(canonical):
    dates = [row["Date"] for row in canonical]
    assert dates == sorted(dates)


def test_duplicate_date_rejected():
    records = [
        {"Date": "2026-01-20", "nav-x1": 50000.0},
        {"Date": "2026-01-20", "nav-x1": 50010.0},
    ]
    with pytest.raises(DuplicateCanonicalDate):
        canonical_nav_records_from_ledger(records)


def test_non_finite_nav_rejected():
    with pytest.raises(InvalidCanonicalNAV):
        canonical_nav_records_from_ledger([{"Date": "2026-01-20", "nav-x1": float("nan")}])


def test_non_chronological_rejected():
    records = [
        {"Date": "2026-01-21", "nav-x1": 50010.0},
        {"Date": "2026-01-20", "nav-x1": 50000.0},
    ]
    with pytest.raises(NonChronologicalCanonicalDate):
        canonical_nav_records_from_ledger(records)


def test_input_immutability(ledger):
    records = [dict(r.fields) for r in ledger.completed_records[:5]]
    original = deepcopy(records)
    canonical_nav_records_from_ledger(records)
    assert records == original


def test_empty_ledger_outputs():
    propagation = propagate_tcp_dashboard([])
    assert propagation.nav_point_count == 0
    assert propagation.monthly_calendar.empty
    assert propagation.drawdown_profile.empty
    assert propagation.desktop_label.header == LABEL_UNAVAILABLE
    assert isinstance(propagation.nav_figure, go.Figure)


def test_one_row_ledger_outputs():
    records = [{"Date": "2026-01-20", "NAV": 50000.0}]
    propagation = propagate_tcp_dashboard(records)
    assert propagation.nav_point_count == 1
    assert propagation.latest_nav == 50000.0
    days = propagation.daily_performance.loc[
        propagation.daily_performance["Metric"] == "Number of Trading Days",
        f"{STRATEGY_NAME} (Inception)",
    ].iloc[0]
    assert days == "0"


def test_deterministic_propagation(canonical):
    first = propagate_tcp_dashboard(canonical)
    second = propagate_tcp_dashboard(canonical)
    assert first.latest_nav == second.latest_nav
    assert first.monthly_calendar.equals(second.monthly_calendar)
    assert first.daily_performance.equals(second.daily_performance)
    assert first.drawdown_profile.equals(second.drawdown_profile)


def test_first_month_calculation(canonical):
    monthly = recompute_tcp_monthly_performance(canonical)
    assert "2026" in monthly["Year"].tolist()
    assert monthly.loc[0, "Jan"] != ""


def test_normal_month_to_month(canonical):
    monthly = recompute_tcp_monthly_performance(canonical)
    assert monthly.loc[0, "Feb"] != ""


def test_multi_year_ordering(canonical):
    monthly = recompute_tcp_monthly_performance(canonical)
    years = [int(y) for y in monthly["Year"]]
    assert years == sorted(years)


def test_partial_latest_month(canonical):
    monthly = recompute_tcp_monthly_performance(canonical)
    assert monthly.loc[monthly["Year"] == "2026", "Jun"].iloc[0] != ""


def test_no_legacy_overrides_in_module():
    source = (REPO_ROOT / "tcp_dashboard.py").read_text(encoding="utf-8")
    assert "override_months" not in source
    assert "2025-04" not in source
    assert "2025-10" not in source


def test_no_150000_baseline():
    source = (REPO_ROOT / "tcp_dashboard.py").read_text(encoding="utf-8")
    assert "150000" not in source
    propagation = propagate_tcp_dashboard(_sample_records())
    assert propagation.baseline_nav == 50000.0


def test_monthly_formatting_precision(canonical):
    monthly = recompute_tcp_monthly_performance(canonical)
    sample = next(v for v in monthly.iloc[0, 1:] if v)
    assert sample.endswith("%")
    assert len(sample.split(".")[-1].replace("%", "")) == 4


def test_trading_day_count_matches_returns(canonical):
    daily = recompute_tcp_daily_metrics(canonical)
    inception_days = daily.loc[
        daily["Metric"] == "Number of Trading Days", f"{STRATEGY_NAME} (Inception)"
    ].iloc[0]
    assert int(inception_days) == len(canonical) - 1


def test_seed_row_excluded_from_returns():
    records = _sample_records()
    series = canonical_records_to_series(records)
    baseline = float(series.iloc[0])
    returns = series.diff().div(baseline).dropna()
    assert len(returns) == len(records) - 1


def test_average_daily_return_present(canonical):
    daily = recompute_tcp_daily_metrics(canonical)
    value = daily.loc[daily["Metric"] == "Avg Daily Return", f"{STRATEGY_NAME} (Inception)"].iloc[0]
    assert value.endswith("%")


def test_sharpe_not_computed():
    assert "Sharpe" not in METRIC_LABELS


def test_win_rate_zero_return_neutral():
    returns = pd.Series([0.01, 0.0, -0.01], index=pd.to_datetime(["2026-01-21", "2026-01-22", "2026-01-23"]))
    metrics = calculate_period_metrics(returns, returns.index.min())
    assert "1 (33.3%)" in metrics["% Winning Days"]
    assert "1 (33.3%)" in metrics["% Losing Days"]


def test_best_and_worst_days():
    returns = pd.Series([0.02, -0.01, 0.03], index=pd.to_datetime(["2026-01-21", "2026-01-22", "2026-01-23"]))
    metrics = calculate_period_metrics(returns, returns.index.min())
    assert "3.00%" in metrics["Best 3 Days"]
    assert "-1.00%" in metrics["Worst 3 Days"]


def test_constant_nav_short_metrics():
    records = [
        {"Date": "2026-01-20", "NAV": 50000.0},
        {"Date": "2026-01-21", "NAV": 50000.0},
        {"Date": "2026-01-22", "NAV": 50000.0},
    ]
    daily = recompute_tcp_daily_metrics(records)
    row = daily.set_index("Metric")[f"{STRATEGY_NAME} (Inception)"]
    assert row["Cumulative Return"] == "0.0%"
    assert row["% Winning Days"].startswith("0 ")


def test_no_nan_in_metrics(canonical):
    daily = recompute_tcp_daily_metrics(canonical)
    for value in daily.values.flatten():
        assert "nan" not in str(value).lower()
        assert "inf" not in str(value).lower()


def test_latest_nav_and_date(propagation):
    assert propagation.latest_date == date(2026, 6, 24)
    assert math.isclose(propagation.latest_nav or 0, 44871.384, abs_tol=0.001)


def test_nav_chart_point_count(propagation, canonical):
    assert propagation.nav_point_count == len(canonical) == 112


def test_nav_chart_chronological(propagation):
    x_values = propagation.nav_figure.data[0].x
    assert list(x_values) == sorted(x_values)


def test_nav_chart_hover_template(propagation):
    assert "NAV=" in propagation.nav_figure.data[0].hovertemplate


def test_nav_chart_yaxis_title_is_nav(propagation):
    assert propagation.nav_figure.layout.yaxis.title.text == "NAV"


def test_empty_nav_figure():
    fig = build_tcp_nav_figure([])
    assert isinstance(fig, go.Figure)
    assert fig.layout.yaxis.title.text == "NAV"
    assert fig.layout.annotations


def test_no_percentage_axis():
    with pytest.raises(ValueError):
        build_tcp_nav_figure(_sample_records(), show_percentage_axis=True)


def test_nav_figure_input_immutability(canonical):
    copy = deepcopy(canonical)
    build_tcp_nav_figure(copy)
    assert copy == canonical


def test_desktop_and_mobile_labels_share_date(canonical):
    labels = build_tcp_current_data_labels(canonical)
    assert labels.header == LABEL_HEADER
    assert "June 24, 2026" in labels.date_line
    assert labels.date_line.endswith("close")


def test_empty_label_unavailable():
    labels = build_tcp_current_data_labels([])
    assert labels.header == LABEL_UNAVAILABLE


def test_workbook_parity_latest(propagation):
    assert propagation.latest_date.isoformat() == "2026-06-24"
    assert math.isclose(propagation.latest_nav or 0, 44871.384, abs_tol=0.001)


def test_no_tkp_imports():
    source = (REPO_ROOT / "tcp_dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    assert "tkp_ts" not in modules


def _returns_series(values, start="2026-01-20"):
    dates = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=dates, dtype=float)


def test_drawdown_includes_spxtr_btc_eth_when_benchmarks_ready(canonical):
    returns = _returns_series([0.01] * 120)
    propagation = propagate_tcp_dashboard(
        canonical,
        benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_READY,
            symbol="^SP500TR",
            display_name="SPXTR",
            as_of="2026-06-24",
            fetched_at="2026-06-24T00:00:00+00:00",
            returns=returns,
            warning=None,
        ),
        btc_benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_READY,
            symbol=BTC_SYMBOL,
            display_name="BTC",
            as_of="2026-06-24",
            fetched_at="2026-06-24T00:00:00+00:00",
            returns=returns,
            warning=None,
        ),
        eth_benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_READY,
            symbol=ETH_SYMBOL,
            display_name="ETH",
            as_of="2026-06-24",
            fetched_at="2026-06-24T00:00:00+00:00",
            returns=returns,
            warning=None,
        ),
    )
    columns = list(propagation.drawdown_profile.columns)
    assert SPXTR_INCEPTION_COLUMN in columns
    assert BTC_INCEPTION_COLUMN in columns
    assert ETH_INCEPTION_COLUMN in columns
    assert columns.index(SPXTR_INCEPTION_COLUMN) < columns.index(BTC_INCEPTION_COLUMN)
    assert columns.index(BTC_INCEPTION_COLUMN) < columns.index(ETH_INCEPTION_COLUMN)


def test_drawdown_display_renames_shorten_headers():
    df = pd.DataFrame(
        {
            "Metric": ["Depth"],
            STRATEGY_INCEPTION_COLUMN: ["-1.0%"],
            SPXTR_INCEPTION_COLUMN: ["-2.0%"],
            BTC_INCEPTION_COLUMN: ["-3.0%"],
            ETH_INCEPTION_COLUMN: ["-4.0%"],
        }
    )
    display = format_drawdown_table_for_display(df)
    assert list(display.columns) == ["Metric", "TCP", "SPXTR", "BTC", "ETH"]


def test_drawdown_omits_btc_eth_when_unavailable(canonical):
    propagation = propagate_tcp_dashboard(
        canonical,
        btc_benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=BTC_SYMBOL,
            display_name="BTC",
            as_of=None,
            fetched_at=None,
            returns=None,
            warning="unavailable",
        ),
        eth_benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=ETH_SYMBOL,
            display_name="ETH",
            as_of=None,
            fetched_at=None,
            returns=None,
            warning="unavailable",
        ),
    )
    assert BTC_INCEPTION_COLUMN not in propagation.drawdown_profile.columns
    assert ETH_INCEPTION_COLUMN not in propagation.drawdown_profile.columns
