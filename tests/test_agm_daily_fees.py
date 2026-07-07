"""Daily incentive-fee accrual engine tests (algominds_daily_fees).

Two layers:
  1. Pure-fixture tests (synthetic balances + synthetic benchmark) — fully
     deterministic, no repo data needed.
  2. Workbook-parity tests: engine run on the real daily CSV + committed SPX
     cache must reproduce every completed month's fee from
     "Momentum Fee Calculation.xlsx" to the cent (values cross-checked by hand
     against the workbook's per-month detail sheets, not fabricated).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import algominds_benchmark_daily as ab
import algominds_daily_balances as adb
import algominds_daily_fees as adf

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "Momentum Pacer" / "data" / "daily_balances" / adb.DAILY_BALANCES_FILENAME


# ── slab_fee: the approved workbook formula ──────────────────────────────────

def test_slab_fee_reproduces_workbook_apr_2026():
    # Apr 2026 detail sheet: P = 47,451.27 - 35,341.15 HWM = 12,110.12;
    # B = 10.4233425% x $30,000 = $3,127.00 -> Net Fees $2,967.846349.
    assert adf.slab_fee(12110.12, 3127.002751) == pytest.approx(2967.846349, abs=0.01)


def test_slab_fee_reproduces_workbook_nov_2025():
    # Nov 2025: P = 37,683.16 - 30,000 = 7,683.16; B = 1.656403201% x $30,000.
    b = 0.01656403201 * 30_000.0
    assert adf.slab_fee(7683.16, b) == pytest.approx(3344.66, abs=0.01)


def test_slab_fee_negative_benchmark_is_50_percent():
    # Feb 2026: SPX negative -> fee = 50% of net new profits (1,437.18 -> 718.59).
    assert adf.slab_fee(1437.18, -260.05) == pytest.approx(718.59, abs=0.01)
    assert adf.slab_fee(1000.0, 0.0) == pytest.approx(500.0)


def test_slab_fee_first_slab_only():
    # Jan 2026: P = 315.62 < B = 409.76 -> 10% of P.
    assert adf.slab_fee(315.62, 409.7582352) == pytest.approx(31.56, abs=0.01)


def test_slab_fee_never_negative_and_zero_under_hwm():
    assert adf.slab_fee(-500.0, 300.0) == 0.0
    assert adf.slab_fee(0.0, 300.0) == 0.0
    assert adf.slab_fee(-500.0, -300.0) == 0.0


# ── Synthetic fixtures: daily behavior ───────────────────────────────────────

def _balances(rows) -> pd.DataFrame:
    df = pd.DataFrame({"Date": pd.to_datetime([d for d, _ in rows]),
                       "Net Worth": [v for _, v in rows]})
    return df


def _bench(rows) -> pd.DataFrame:
    return pd.DataFrame({"Date": pd.to_datetime([d for d, _ in rows]),
                         "Close": [c for _, c in rows]})


@pytest.fixture
def synthetic():
    """Jan in-profit month (flat SPX -> 50% rate) + Feb start, no payment events."""
    bal = _balances([
        ("2026-01-05", 30_000.0),
        ("2026-01-15", 31_000.0),
        ("2026-01-30", 32_000.0),   # Jan month-end: P=2,000, B=0 -> fee 1,000
        ("2026-02-02", 32_500.0),
        ("2026-02-27", 32_500.0),
    ])
    bench = _bench([
        ("2025-12-31", 100.0),
        ("2026-01-05", 100.0),
        ("2026-01-15", 100.0),
        ("2026-01-30", 100.0),      # flat SPX all month -> B = 0
        ("2026-02-02", 100.0),
        ("2026-02-27", 100.0),
    ])
    return bal, bench


def test_daily_accrual_grows_intramonth_and_crystallizes(synthetic):
    bal, bench = synthetic
    res = adf.compute_daily_fee_accrual(bal, bench, inception=pd.Timestamp("2026-01-05"))
    d = res.daily
    # Accrues daily: 0 -> 500 (50% of 1,000) -> crystallized 1,000 at month-end.
    assert d["accrued_total"].iloc[0] == pytest.approx(0.0)
    assert d["accrued_total"].iloc[1] == pytest.approx(500.0)
    assert d["accrued_total"].iloc[2] == pytest.approx(1000.0)
    assert res.crystallized[0]["fee"] == pytest.approx(1000.0)
    assert res.crystallized[0]["month"] == "2026-01"


def test_hwm_updates_to_after_fee_close(synthetic):
    bal, bench = synthetic
    res = adf.compute_daily_fee_accrual(bal, bench, inception=pd.Timestamp("2026-01-05"))
    d = res.daily
    # After Jan crystallizes: HWM = 32,000 - 1,000 fee = 31,000 (after-fee close).
    assert d["hwm"].iloc[2] == pytest.approx(31_000.0)
    # Feb accrual measures equity NET of the still-owed Jan fee:
    # (32,500 - 1,000) - 31,000 = 500 -> 50% = 250.
    assert d["month_accrual"].iloc[3] == pytest.approx(250.0)


def test_no_fabricated_resets_without_payment_evidence(synthetic):
    bal, bench = synthetic
    res = adf.compute_daily_fee_accrual(bal, bench, inception=pd.Timestamp("2026-01-05"))
    # No matching Net-Worth drop and no workbook reference -> Jan fee stays
    # outstanding; nothing invents a payment date.
    assert res.payments == []
    assert [(o["month"], round(o["fee"])) for o in res.outstanding] == [("2026-01", 1000)]
    assert (res.daily["accrued_total"].iloc[-1]
            == pytest.approx(1000.0 + res.daily["month_accrual"].iloc[-1]))


def test_exact_net_worth_drop_detected_as_payment():
    bal = _balances([
        ("2026-01-05", 30_000.0),
        ("2026-01-30", 32_000.0),   # fee crystallizes: 1,000 (flat SPX)
        ("2026-02-02", 32_000.0),
        ("2026-02-03", 31_000.0),   # drops by exactly the outstanding fee
        ("2026-02-27", 31_000.0),
    ])
    bench = _bench([(d, 100.0) for d in
                    ["2025-12-31", "2026-01-05", "2026-01-30",
                     "2026-02-02", "2026-02-03", "2026-02-27"]])
    res = adf.compute_daily_fee_accrual(bal, bench, inception=pd.Timestamp("2026-01-05"))
    assert len(res.payments) == 1
    assert res.payments[0]["method"] == "exact-daily-match"
    assert res.payments[0]["date"] == pd.Timestamp("2026-02-03")
    assert res.payments[0]["amount"] == pytest.approx(1000.0)
    assert res.outstanding == []
    d = res.daily
    # Accrued series resets to $0 on the evidenced payment day.
    assert d.loc[d["Date"] == "2026-02-03", "accrued_total"].iloc[0] == pytest.approx(0.0)


def test_missing_benchmark_days_are_skipped_not_fabricated():
    bal = _balances([
        ("2026-01-05", 30_000.0),
        ("2026-01-20", 31_000.0),   # >5 days after the last SPX close -> skipped
        ("2026-01-30", 32_000.0),
    ])
    bench = _bench([("2025-12-31", 100.0), ("2026-01-05", 100.0), ("2026-01-30", 100.0)])
    res = adf.compute_daily_fee_accrual(bal, bench, inception=pd.Timestamp("2026-01-05"))
    assert [d.date().isoformat() for d in res.skipped_dates] == ["2026-01-20"]


def test_empty_inputs_return_empty_result():
    res = adf.compute_daily_fee_accrual(pd.DataFrame(), pd.DataFrame())
    assert res.daily.empty
    assert res.crystallized == [] and res.payments == [] and res.outstanding == []


# ── Workbook parity on the real data ─────────────────────────────────────────

@pytest.fixture(scope="module")
def real_result() -> adf.DailyFeeAccrual:
    import mp_ts  # noqa: F401 — reuse its import-time wiring (CSV + cache + workbook)

    return mp_ts.daily_fee_accrual


WORKBOOK_FEES = {
    # month -> Net Fees $ from Momentum Fee Calculation.xlsx (BOT Fees% x $30,000).
    "2025-11": 3344.66,
    "2025-12": 0.0,
    "2026-01": 31.56,
    "2026-02": 718.59,
    "2026-03": 0.0,
    "2026-04": 2967.85,
}


def test_engine_reproduces_every_completed_workbook_month(real_result):
    fees = {c["month"]: c["fee"] for c in real_result.crystallized}
    for month, expected in WORKBOOK_FEES.items():
        assert fees[month] == pytest.approx(expected, abs=0.01), month


def test_engine_extends_daily_fees_beyond_stale_workbook(real_result):
    # May/Jun 2026 have no reliable workbook rows (sheet frozen at the May 12
    # as-of); the engine still crystallizes them from actual daily data.
    months = [c["month"] for c in real_result.crystallized]
    assert "2026-05" in months and "2026-06" in months


def test_payment_events_only_where_evidenced(real_result):
    methods = {(p["date"].date().isoformat(), p["method"]) for p in real_result.payments}
    # Feb fee left the account on Mar 27 (Net Worth fell by exactly $718.59).
    assert ("2026-03-27", "exact-daily-match") in methods
    # Nov / Jan fees are only evidenced by month-end workbook reconciliation.
    assert ("2025-12-31", "workbook-reconciliation") in methods
    assert ("2026-02-27", "workbook-reconciliation") in methods
    assert len(real_result.payments) == 3  # nothing fabricated beyond these


def test_unpaid_fees_reported_honestly(real_result):
    # Apr 2026 ($2,967.85) and May 2026 fees show no payment evidence in the
    # CSV -> they must remain outstanding, not silently reset.
    out = {o["month"]: o["fee"] for o in real_result.outstanding}
    assert out["2026-04"] == pytest.approx(2967.85, abs=0.01)
    assert "2026-05" in out


def test_accrued_total_is_daily_and_never_negative(real_result):
    d = real_result.daily
    assert len(d) == len(d["Date"].unique())
    assert (d["accrued_total"] >= 0).all()
    # One row per AGM trading day since inception — genuinely daily resolution.
    assert len(d) > 100
    assert d["Date"].iloc[0] == pd.Timestamp("2025-11-13")
    assert d["Date"].iloc[-1] == pd.Timestamp("2026-07-01")
    # Invariant: plotted series = current-month accrual + outstanding ledger.
    assert (d["accrued_total"] - d["month_accrual"] - d["outstanding_total"]).abs().max() < 1e-9


def test_no_spx_days_skipped_on_real_data(real_result):
    assert real_result.skipped_dates == []
