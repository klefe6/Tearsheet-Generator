"""Pure AGM daily accounting model tests (algominds_daily_accounting).

Deterministic: synthetic fixtures and committed local cache only — no live
yfinance calls.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import algominds_benchmark_daily as ab
import algominds_daily_accounting as ada
import algominds_daily_balances as adb
import algominds_daily_fees as adf

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "Momentum Pacer" / "data" / "daily_balances" / adb.DAILY_BALANCES_FILENAME


def _balances(rows) -> pd.DataFrame:
    return pd.DataFrame(
        {"Date": pd.to_datetime([d for d, _ in rows]),
         "Net Worth": [v for _, v in rows],
         "Cash Balance": [v for _, v in rows],
         "Unrealized P/L": [0.0] * len(rows),
         "Initial Margin Req.": [0.0] * len(rows),
         "Maint Margin Req.": [0.0] * len(rows),
         "Buying Power/Margin Deficit": [0.0] * len(rows)}
    )


def _bench(rows) -> pd.DataFrame:
    return pd.DataFrame(
        {"Date": pd.to_datetime([d for d, _ in rows]),
         "Close": [c for _, c in rows]}
    )


def _raising_fetcher(symbol, start, end):
    raise AssertionError("network fetch attempted during tests")


@pytest.fixture
def synthetic_payment_scenario():
    """Jan fee crystallizes; exact drop evidences payment on Feb 3."""
    bal = _balances([
        ("2026-01-05", 30_000.0),
        ("2026-01-30", 32_000.0),
        ("2026-02-02", 32_000.0),
        ("2026-02-03", 31_000.0),
        ("2026-02-27", 31_000.0),
    ])
    bench = _bench([(d, 100.0) for d in
                    ["2025-12-31", "2026-01-05", "2026-01-30",
                     "2026-02-02", "2026-02-03", "2026-02-27"]])
    return bal, bench


# ── Core invariant & series definitions ─────────────────────────────────────

def test_actual_nlv_equals_csv_net_worth(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    merged = res.table.merge(bal[["Date", "Net Worth"]], on="Date")
    assert (merged["actual_nlv"] - merged["Net Worth"]).abs().max() < 1e-9


def test_client_net_value_formula(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    t = res.table
    assert (t["client_net_value"] - (t["actual_nlv"] - t["accrued_unpaid_fees"])).abs().max() < 1e-9


def test_invariant_holds_all_dates(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    assert ada.verify_accounting_invariant(res.table)


def test_spx_close_aligns_to_agm_dates(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    expected = ab.align_to_dates(bench, bal["Date"])
    got = pd.Series(res.table["spx_close"].values, index=expected.index)
    assert (got.astype(float) - expected.astype(float)).abs().max(skipna=True) < 1e-9


def test_momentum_daily_pct_is_client_net_pct_change(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    expected = adb.daily_pct_change(res.table["client_net_value"])
    assert (res.table["momentum_daily_pct"] - expected).abs().max(skipna=True) < 1e-9


def test_spx_daily_pct_is_spx_close_pct_change(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    expected = adb.daily_pct_change(res.table["spx_close"])
    assert (res.table["spx_daily_pct"] - expected).abs().max(skipna=True) < 1e-9


def test_spread_equals_momentum_minus_spx(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    spread = res.table["momentum_daily_pct"] - res.table["spx_daily_pct"]
    assert (res.table["momentum_vs_spx_daily_spread_pct"] - spread).abs().max(skipna=True) < 1e-9


# ── Payment / removal evidence ───────────────────────────────────────────────

def test_payment_reduces_accrued_only_when_evidenced(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    t = res.table.set_index("Date")
    # Jan fee crystallized at month-end; still accrued until payment.
    assert t.loc["2026-01-30", "accrued_unpaid_fees"] == pytest.approx(1000.0)
    assert t.loc["2026-02-02", "accrued_unpaid_fees"] == pytest.approx(1000.0)
    # Evidenced payment on Feb 3 clears accrued (no fabricated date).
    assert t.loc["2026-02-03", "accrued_unpaid_fees"] == pytest.approx(0.0)
    assert t.loc["2026-02-03", "fee_payment"] == pytest.approx(1000.0)


def test_no_payment_evidence_carries_accrued_forward():
    bal = _balances([
        ("2026-01-05", 30_000.0),
        ("2026-01-30", 32_000.0),
        ("2026-02-27", 32_500.0),
    ])
    bench = _bench([(d, 100.0) for d in ["2025-12-31", "2026-01-05", "2026-01-30", "2026-02-27"]])
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    assert res.payments == []
    assert res.table["accrued_unpaid_fees"].iloc[-1] > 1000.0
    assert res.table["fee_payment"].isna().all()


def test_no_double_subtract_fees_from_actual_nlv(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    # actual_nlv always tracks raw CSV Net Worth even when fees accrue.
    assert (res.table["actual_nlv"] - bal["Net Worth"]).abs().max() < 1e-9


# ── Daily table columns ──────────────────────────────────────────────────────

def test_daily_table_has_required_columns(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    required = {
        "Date", "actual_nlv", "client_net_value", "accrued_unpaid_fees",
        "spx_close", "momentum_daily_pct", "spx_daily_pct",
        "momentum_vs_spx_daily_spread_pct", "Cash Balance", "Unrealized P/L",
        "Initial Margin Req.", "Maint Margin Req.", "Buying Power/Margin Deficit",
        "daily_dollar", "daily_pct", "since_inception_pct", "fee_payment",
    }
    assert required.issubset(set(res.table.columns))


def test_output_series_match_table_columns(synthetic_payment_scenario):
    bal, bench = synthetic_payment_scenario
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2026-01-05"))
    t = res.table
    pairs = [
        ("actual_nlv", res.actual_nlv_series),
        ("client_net_value", res.client_net_value_series),
        ("accrued_unpaid_fees", res.accrued_unpaid_fees_series),
        ("spx_close", res.spx_close_series),
        ("momentum_daily_pct", res.momentum_daily_pct_series),
        ("spx_daily_pct", res.spx_daily_pct_series),
        ("momentum_vs_spx_daily_spread_pct", res.momentum_vs_spx_daily_spread_pct_series),
    ]
    for col, series in pairs:
        assert np.allclose(series.values.astype(float), t[col].values.astype(float), equal_nan=True)


def test_pre_inception_dates_have_zero_accrued_fees():
    bal = _balances([
        ("2025-10-20", 30_000.0),
        ("2025-11-12", 30_500.0),
        ("2025-11-13", 30_600.0),
    ])
    bench = _bench([("2025-10-20", 100.0), ("2025-11-12", 101.0), ("2025-11-13", 102.0)])
    res = ada.compute_agm_daily_accounting(bal, bench, inception=pd.Timestamp("2025-11-13"))
    pre = res.table[res.table["Date"] < "2025-11-13"]
    assert (pre["accrued_unpaid_fees"] == 0.0).all()
    assert (pre["client_net_value"] - pre["actual_nlv"]).abs().max() < 1e-9


# ── Real data (committed cache, no network) ───────────────────────────────────

@pytest.fixture(scope="module")
def real_accounting() -> ada.AgmDailyAccounting:
    bal = adb.load_daily_balances(CSV_PATH)
    spx = ab.load_daily_benchmark(
        ab.SPX_TICKER, bal["Date"].min() - pd.Timedelta(days=45),
        bal["Date"].max(), fetcher=_raising_fetcher,
    )
    return ada.compute_agm_daily_accounting(bal, spx)


def test_real_data_invariant(real_accounting):
    assert ada.verify_accounting_invariant(real_accounting.table)


def test_real_data_actual_nlv_matches_csv(real_accounting):
    bal = adb.load_daily_balances(CSV_PATH)
    merged = real_accounting.table.merge(bal[["Date", "Net Worth"]], on="Date")
    assert (merged["actual_nlv"] - merged["Net Worth"]).abs().max() < 1e-6


def test_real_data_spx_fully_aligned(real_accounting):
    assert real_accounting.table["spx_close"].notna().all()


def test_real_data_build_helper_uses_cache_only(monkeypatch):
    monkeypatch.setenv(ab.CACHE_ONLY_ENV, "1")
    res = ada.build_agm_daily_accounting(balances_path=CSV_PATH)
    assert not res.table.empty
    assert ada.verify_accounting_invariant(res.table)


def test_real_data_fee_payment_column_has_both_evidenced_amounts(real_accounting):
    """The accounting table's fee_payment column must carry the two
    confirmed TradeStation cash-transaction incentive-fee withdrawals."""
    t = real_accounting.table.set_index("Date")
    assert t.loc["2026-05-14", "fee_payment"] == pytest.approx(2967.85, abs=0.01)
    assert t.loc["2026-06-23", "fee_payment"] == pytest.approx(1330.25, abs=0.01)
    assert ada.verify_accounting_invariant(real_accounting.table)
