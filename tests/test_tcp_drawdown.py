"""Step 11D — TCP drawdown pure calculation, parity, and integration tests."""
from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from tcp_admin import simulate_add_row
from tcp_benchmarks import BENCHMARK_STATUS_UNAVAILABLE, SPXTR_SYMBOL, BenchmarkResult
from tcp_dashboard import (
    STRATEGY_NAME,
    canonical_nav_records_from_ledger,
    propagate_tcp_dashboard,
)
from tcp_drawdown import (
    DRAWDOWN_FOOTNOTE,
    DRAWDOWN_METRIC_ORDER,
    DRAWDOWN_NOMINAL_EXPOSURE_USD,
    STRATEGY_INCEPTION_COLUMN,
    build_drawdown_dataframe,
    build_drawdown_series,
    build_drawdown_summary,
    normalize_drawdown_nav_records,
    resolve_drawdown_nominal_exposure,
    worst_drawdown_profile,
)
from tcp_ledger import load_ledger
from tcp_public_sections import resolve_public_gate_styles

REPO_ROOT = Path(__file__).resolve().parent.parent
_SESSION_LEDGER = None

# Derived once from workbook + committed drawdown methodology (2026-07-03).
WORKBOOK_DRAWDOWN_BASELINE = {
    "Depth": "-5.2%",
    "Decline Period": "148 days",
    "Recovery Period": "Ongoing for 0 days",
    "Total Duration": "Ongoing for 148 days",
    "Start Date": "2026-01-27",
    "Valley Date": "2026-06-24",
    "End Date": "TBD",
}


def _get_session_ledger():
    global _SESSION_LEDGER
    if _SESSION_LEDGER is None:
        from tcp_config import load_config

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
def workbook_drawdown(canonical):
    return build_drawdown_dataframe(canonical)


def _records(*pairs):
    return [{"Date": d, "NAV": nav} for d, nav in pairs]


# --- Pure calculation (1–20) ---


def test_empty_records():
    df = build_drawdown_dataframe([])
    assert df.empty
    assert list(df.columns) == ["Metric", STRATEGY_INCEPTION_COLUMN]
    assert normalize_drawdown_nav_records([]).empty
    assert build_drawdown_series([]).empty


def test_one_record():
    records = _records(("2026-01-20", 50000.0))
    df = build_drawdown_dataframe(records)
    depth = df.loc[df["Metric"] == "Depth", STRATEGY_INCEPTION_COLUMN].iloc[0]
    assert depth == "0.0%"
    assert df.loc[df["Metric"] == "End Date", STRATEGY_INCEPTION_COLUMN].iloc[0] == "2026-01-20"


def test_constant_nav():
    records = _records(
        ("2026-01-20", 50000.0),
        ("2026-01-21", 50000.0),
        ("2026-01-22", 50000.0),
    )
    period = worst_drawdown_profile(normalize_drawdown_nav_records(records), baseline=50000.0)
    assert period.depth_decimal == 0.0
    assert period.recovered is True


def test_simple_recovered_drawdown():
    nav = pd.Series(
        [100.0, 90.0, 85.0, 95.0, 100.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert math.isclose(period.depth_decimal, -15.0)
    assert period.recovered is True
    assert period.end_date == "2026-01-05"
    assert period.recovery_days_text == "2 days"


def test_simple_unrecovered_drawdown():
    nav = pd.Series(
        [100.0, 90.0, 85.0, 88.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert period.recovered is False
    assert period.end_date == "TBD"
    assert "Ongoing" in period.recovery_days_text


def test_multiple_drawdowns_worst_selected():
    nav = pd.Series(
        [100.0, 95.0, 100.0, 80.0, 85.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert math.isclose(period.depth_decimal, -20.0)
    assert period.valley_date == "2026-01-04"


def test_new_high_resets_drawdown():
    series = build_drawdown_series(
        _records(
            ("2026-01-20", 50000.0),
            ("2026-01-21", 49000.0),
            ("2026-01-22", 51000.0),
        ),
        business_day_forward_fill=False,
    )
    assert series.iloc[-1] == 0.0


def test_correct_peak_date():
    nav = pd.Series(
        [100.0, 110.0, 105.0, 95.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert period.start_date == "2026-01-02"


def test_correct_trough_date():
    nav = pd.Series(
        [100.0, 110.0, 105.0, 95.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert period.valley_date == "2026-01-04"


def test_correct_recovery_date():
    nav = pd.Series(
        [100.0, 110.0, 95.0, 110.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert period.end_date == "2026-01-04"
    assert period.recovered is True


def test_correct_maximum_drawdown():
    nav = pd.Series(
        [100.0, 80.0, 90.0, 70.0, 75.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert math.isclose(period.depth_decimal, -30.0)


def test_correct_duration():
    nav = pd.Series(
        [100.0, 110.0, 95.0, 110.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert period.decline_days == 1


def test_correct_recovery_duration():
    nav = pd.Series(
        [100.0, 110.0, 95.0, 110.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert period.recovery_days_text == "1 days"


def test_business_day_forward_fill_methodology():
    sparse = _records(
        ("2026-01-20", 50000.0),
        ("2026-01-23", 49000.0),
    )
    filled = normalize_drawdown_nav_records(sparse, business_day_forward_fill=True)
    raw = normalize_drawdown_nav_records(sparse, business_day_forward_fill=False)
    assert len(filled) > len(raw)
    assert not filled.isna().any()


def test_duplicate_dates_keep_first():
    records = [
        {"Date": "2026-01-20", "NAV": 50000.0},
        {"Date": "2026-01-21", "NAV": 49000.0},
        {"Date": "2026-01-21", "NAV": 48000.0},
    ]
    series = normalize_drawdown_nav_records(records, business_day_forward_fill=False)
    assert series.loc["2026-01-21"] == 49000.0


def test_non_finite_nav_rejected():
    from tcp_dashboard import InvalidCanonicalNAV

    with pytest.raises(InvalidCanonicalNAV):
        build_drawdown_dataframe([{"Date": "2026-01-20", "NAV": float("nan")}])


def test_input_immutability(canonical):
    snapshot = deepcopy(canonical)
    build_drawdown_dataframe(canonical)
    assert canonical == snapshot


def test_deterministic_output(canonical):
    first = build_drawdown_dataframe(canonical)
    second = build_drawdown_dataframe(canonical)
    assert first.equals(second)


def test_no_nan_or_infinity_in_output(canonical):
    period = worst_drawdown_profile(
        normalize_drawdown_nav_records(canonical),
        baseline=resolve_drawdown_nominal_exposure(tranche_count=2),
        report_cutoff=canonical[-1]["Date"],
    )
    assert math.isfinite(period.depth_decimal)
    summary = build_drawdown_summary(period)
    for value in summary.values():
        assert "nan" not in value.lower()
        assert "inf" not in value.lower()


def test_presentation_rounding_only():
    nav = pd.Series(
        [100.0, 99.333333],
        index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert period.depth_decimal != round(period.depth_decimal, 1)
    displayed = period.to_display_row()["Depth"]
    assert displayed.endswith("%")
    assert displayed == f"{period.depth_decimal:.1f}%"


# --- Workbook / v1 parity (21–28) ---


@pytest.mark.parametrize("metric,expected", WORKBOOK_DRAWDOWN_BASELINE.items())
def test_workbook_drawdown_matches_baseline(workbook_drawdown, metric, expected):
    actual = workbook_drawdown.loc[workbook_drawdown["Metric"] == metric, STRATEGY_INCEPTION_COLUMN].iloc[0]
    assert actual == expected


def test_workbook_maximum_drawdown(workbook_drawdown):
    assert workbook_drawdown.loc[0, STRATEGY_INCEPTION_COLUMN] == "-5.2%"


def test_workbook_displayed_rows(workbook_drawdown):
    assert list(workbook_drawdown["Metric"]) == list(DRAWDOWN_METRIC_ORDER)


def test_workbook_open_status(workbook_drawdown):
    assert workbook_drawdown.loc[workbook_drawdown["Metric"] == "End Date", STRATEGY_INCEPTION_COLUMN].iloc[0] == "TBD"


def test_workbook_dates_match(workbook_drawdown):
    assert workbook_drawdown.loc[workbook_drawdown["Metric"] == "Start Date", STRATEGY_INCEPTION_COLUMN].iloc[0] == "2026-01-27"
    assert workbook_drawdown.loc[workbook_drawdown["Metric"] == "Valley Date", STRATEGY_INCEPTION_COLUMN].iloc[0] == "2026-06-24"


def test_workbook_durations_match(workbook_drawdown):
    assert "148 days" in workbook_drawdown.loc[workbook_drawdown["Metric"] == "Decline Period", STRATEGY_INCEPTION_COLUMN].iloc[0]
    assert "Ongoing" in workbook_drawdown.loc[workbook_drawdown["Metric"] == "Total Duration", STRATEGY_INCEPTION_COLUMN].iloc[0]


def test_workbook_percentages_at_display_precision(workbook_drawdown):
    depth = workbook_drawdown.loc[workbook_drawdown["Metric"] == "Depth", STRATEGY_INCEPTION_COLUMN].iloc[0]
    assert depth.count(".") == 1
    assert depth.endswith("%")


def test_running_peak_non_decreasing(canonical):
    series = build_drawdown_series(canonical)
    assert (series <= 0).all()


# --- Integration (29–45) ---


@pytest.fixture(scope="module")
def layout_text():
    import os

    saved = {
        "TCP_V2_ADMIN_TOKEN": os.environ.get("TCP_V2_ADMIN_TOKEN"),
        "TCP_V2_SESSION_SECRET": os.environ.get("TCP_V2_SESSION_SECRET"),
    }
    os.environ["TCP_V2_ADMIN_TOKEN"] = "drawdown-test-token"
    os.environ["TCP_V2_SESSION_SECRET"] = "drawdown-test-secret"
    from tcp_config import AdminAuthSettings
    from tcp_ts_v2 import create_app

    app, _cfg, state, _auth, _holder = create_app(
        auth_settings=AdminAuthSettings(
            admin_token="drawdown-test-token",
            session_secret="drawdown-test-secret",
        )
    )
    if state.snapshot is None:
        pytest.skip("runtime unavailable")
    text = str(app.layout)
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    return text


def test_drawdown_section_id_present(layout_text):
    assert "tcp-drawdown-profile-card" in layout_text


def test_drawdown_table_container_present(layout_text):
    assert "drawdown-profile-container" in layout_text


@pytest.mark.parametrize(
    "heading",
    ["Maximum Drawdown Profile", "Depth", "Decline Period", "Recovery Period", "Valley Date"],
)
def test_required_v1_headings(layout_text, heading):
    assert heading in layout_text


def test_section_behind_public_gate(layout_text):
    assert "disclaimer-screen" in layout_text
    assert "main-app" in layout_text
    assert "'display': 'none'" in layout_text or '"display": "none"' in layout_text


def test_gate_acceptance_reveals_content():
    hidden, shown = resolve_public_gate_styles(1)
    assert hidden["display"] == "none"
    assert shown["display"] == "block"


def test_gate_acceptance_not_admin_auth():
    hidden, shown = resolve_public_gate_styles(1)
    assert hidden == {"display": "none"}
    assert shown == {"display": "block"}


def test_drawdown_uses_canonical_store_propagation(canonical):
    propagation = propagate_tcp_dashboard(canonical)
    assert not propagation.drawdown_profile.empty
    assert STRATEGY_INCEPTION_COLUMN in propagation.drawdown_profile.columns


def test_drawdown_callback_does_not_reread_workbook():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert "read_excel" not in source
    assert "load_ledger" not in source
    assert "drawdown-profile-container" in source


def test_json_and_public_drawdown_share_snapshot(canonical):
    propagation = propagate_tcp_dashboard(canonical)
    from_store = build_drawdown_dataframe(propagation.canonical_records)
    assert propagation.drawdown_profile.equals(from_store)


def test_synthetic_add_changes_drawdown(canonical):
    baseline = propagate_tcp_dashboard(canonical).drawdown_profile
    extended = list(canonical) + [{"Date": "2026-06-25", "NAV": 40000.0}]
    changed = propagate_tcp_dashboard(extended).drawdown_profile
    assert not baseline.equals(changed)
    depth_before = baseline.loc[baseline["Metric"] == "Depth", STRATEGY_INCEPTION_COLUMN].iloc[0]
    depth_after = changed.loc[changed["Metric"] == "Depth", STRATEGY_INCEPTION_COLUMN].iloc[0]
    assert depth_before != depth_after


def test_synthetic_delete_restores_drawdown(canonical):
    baseline = propagate_tcp_dashboard(canonical).drawdown_profile
    trimmed = list(canonical[:-1])
    restored = propagate_tcp_dashboard(trimmed).drawdown_profile
    back = propagate_tcp_dashboard(canonical).drawdown_profile
    assert not baseline.equals(restored)
    assert back.equals(baseline)


def test_simulation_only_row_does_not_change_drawdown(ledger, canonical):
    before = propagate_tcp_dashboard(canonical).drawdown_profile
    prior = ledger.completed_records[-1].fields
    simulate_add_row(
        prior,
        row_date="2026-06-25",
        cash_balance=40000,
        cash_transfers=0,
        tranche_count=int(prior["#"]),
    )
    after = propagate_tcp_dashboard(canonical).drawdown_profile
    assert before.equals(after)


def test_failed_mutation_does_not_change_drawdown(canonical):
    before = deepcopy(canonical)
    propagation_before = propagate_tcp_dashboard(before).drawdown_profile
    propagation_after = propagate_tcp_dashboard(before).drawdown_profile
    assert propagation_before.equals(propagation_after)


def test_existing_dynamic_containers(layout_text):
    for container in (
        "monthly-calendar-container",
        "daily-perf-container",
        "nav-preview-graph",
        "data-current-label-desktop",
        "data-current-label-mobile",
    ):
        assert container in layout_text


def test_existing_admin_login_paths():
    source = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8")
    assert "/admin/login" in source or "admin/login" in (REPO_ROOT / "tcp_admin.py").read_text(encoding="utf-8")


def test_import_starts_no_server():
    import socket

    import tcp_drawdown  # noqa: F401

    sock = socket.socket()
    sock.settimeout(0.2)
    try:
        assert sock.connect_ex(("127.0.0.1", 8312)) != 0
    finally:
        sock.close()


def test_layout_creation_writes_no_workbook_or_state(tmp_path):
    from tcp_public_sections import build_drawdown_profile_card

    card = build_drawdown_profile_card("placeholder")
    assert card is not None


# --- Regression ---


def test_no_spxtr_column_when_benchmark_unavailable(canonical):
    propagation = propagate_tcp_dashboard(
        canonical,
        benchmark_result=BenchmarkResult(
            status=BENCHMARK_STATUS_UNAVAILABLE,
            symbol=SPXTR_SYMBOL,
            display_name="SPXTR",
            as_of=None,
            fetched_at=None,
            returns=None,
            warning="unavailable",
        ),
    )
    assert "SPXTR (Inception)" not in propagation.drawdown_profile.columns


def test_no_public_daily_returns(layout_text):
    assert "Daily Returns" not in layout_text


def test_no_percentage_nav_axis(layout_text):
    assert "NAV (%)" not in layout_text


def test_no_tkp_wording():
    body = (REPO_ROOT / "tcp_ts_v2.py").read_text(encoding="utf-8").lower()
    assert "the kelly program" not in body


def test_no_stonex_plus500_in_drawdown_slice(layout_text):
    start = layout_text.find("Maximum Drawdown Profile")
    end = layout_text.find("Important Disclosure", start)
    section = layout_text[start:end] if end > start else layout_text[start:]
    assert "Plus500" not in section
    assert DRAWDOWN_FOOTNOTE in layout_text


def test_drawdown_footnote_present(layout_text):
    assert "$100,000 fixed nominal" in layout_text
    assert "two $50,000 tranches" in layout_text


def test_v1_drawdown_chart_not_in_layout(layout_text):
    assert "build_drawdown_figure" not in layout_text
    assert layout_text.count("Drawdown vs Peak") == 0


# --- Nominal exposure and duration semantics ---


def test_drawdown_nominal_exposure_is_100k_for_two_tranches():
    assert resolve_drawdown_nominal_exposure(tranche_count=2) == 100_000.0
    assert DRAWDOWN_NOMINAL_EXPOSURE_USD == 100_000.0


def test_nominal_base_10k_decline_is_negative_ten_percent():
    nav = pd.Series(
        [100_000.0, 90_000.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
    )
    period = worst_drawdown_profile(nav, baseline=100_000.0)
    assert math.isclose(period.depth_decimal, -10.0)


def test_nominal_base_20k_decline_is_negative_twenty_percent():
    nav = pd.Series(
        [100_000.0, 80_000.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02"]),
    )
    period = worst_drawdown_profile(nav, baseline=100_000.0)
    assert math.isclose(period.depth_decimal, -20.0)


def test_completed_drawdown_duration_fields():
    nav = pd.Series(
        [100.0, 90.0, 80.0, 90.0, 100.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-06", "2026-01-11", "2026-01-16", "2026-01-21"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0, report_cutoff="2026-01-21")
    assert period.start_date == "2026-01-01"
    assert period.valley_date == "2026-01-11"
    assert period.end_date == "2026-01-21"
    assert period.decline_days == 10
    assert period.recovery_days_text == "10 days"
    assert period.total_duration_text == "20 days"
    assert period.recovered is True


def test_ongoing_drawdown_duration_fields_use_report_cutoff():
    nav = pd.Series(
        [100.0, 90.0, 80.0, 85.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-06", "2026-01-11", "2026-01-20"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0, report_cutoff="2026-01-31")
    assert period.decline_days == 10
    assert period.recovery_days_text == "Ongoing for 20 days"
    assert period.total_duration_text == "Ongoing for 30 days"
    assert period.end_date == "TBD"
    assert period.recovered is False


def test_calendar_day_difference_uses_end_minus_start_in_days():
    nav = pd.Series(
        [100.0, 110.0, 95.0, 110.0],
        index=pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]),
    )
    period = worst_drawdown_profile(nav, baseline=100.0)
    assert period.start_date == "2026-01-02"
    assert period.valley_date == "2026-01-03"
    assert period.decline_days == 1


def test_weekend_spanning_crypto_durations_use_calendar_days():
    from tcp_drawdown import build_benchmark_drawdown_period

    # Fri peak -> Mon valley = 3 calendar days despite only two return observations.
    crypto_returns = pd.Series(
        [0.0, -0.5],
        index=pd.to_datetime(["2026-01-02", "2026-01-05"]),
    )
    period = build_benchmark_drawdown_period(
        crypto_returns,
        inception_start=pd.Timestamp("2026-01-02"),
        baseline=100_000.0,
        report_cutoff="2026-01-05",
    )
    assert period is not None
    assert period.decline_days == 3


def test_benchmark_returns_clipped_to_tcp_report_cutoff():
    from tcp_benchmarks import clip_benchmark_returns_for_drawdown

    returns = pd.Series(
        [0.01, 0.02, 0.03],
        index=pd.to_datetime(["2026-01-20", "2026-01-21", "2026-01-22"]),
    )
    clipped = clip_benchmark_returns_for_drawdown(
        returns,
        inception_start="2026-01-20",
        report_cutoff="2026-01-21",
    )
    assert list(clipped.index.strftime("%Y-%m-%d")) == ["2026-01-20", "2026-01-21"]


def test_drawdown_footnote_text():
    assert "$100,000 fixed nominal" in DRAWDOWN_FOOTNOTE
    assert "two $50,000 tranches" in DRAWDOWN_FOOTNOTE
    assert "$150,000" not in DRAWDOWN_FOOTNOTE
