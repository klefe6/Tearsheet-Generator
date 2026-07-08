"""UI adapter tests for algominds_daily_accounting_ui (no network, no mp_ts)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import algominds_benchmark_daily as ab
import algominds_daily_accounting as ada
import algominds_daily_accounting_ui as adui
import algominds_daily_balances as adb

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "Momentum Pacer" / "data" / "daily_balances" / adb.DAILY_BALANCES_FILENAME


def _balances(rows) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": pd.to_datetime([d for d, _ in rows]),
            "Net Worth": [v for _, v in rows],
            "Cash Balance": [v for _, v in rows],
            "Unrealized P/L": [0.0] * len(rows),
            "Initial Margin Req.": [0.0] * len(rows),
            "Maint Margin Req.": [0.0] * len(rows),
            "Buying Power/Margin Deficit": [0.0] * len(rows),
        }
    )


def _bench(rows) -> pd.DataFrame:
    return pd.DataFrame(
        {"Date": pd.to_datetime([d for d, _ in rows]), "Close": [c for _, c in rows]}
    )


def _raising_fetcher(symbol, start, end):
    raise AssertionError("network fetch attempted during tests")


@pytest.fixture
def synthetic_payment_scenario():
    bal = _balances(
        [
            ("2026-01-05", 30_000.0),
            ("2026-01-30", 32_000.0),
            ("2026-02-02", 32_000.0),
            ("2026-02-03", 31_000.0),
            ("2026-02-27", 31_000.0),
        ]
    )
    spx = _bench(
        [
            ("2025-12-31", 100.0),
            ("2026-01-05", 100.0),
            ("2026-01-30", 100.0),
            ("2026-02-02", 100.0),
            ("2026-02-03", 100.0),
            ("2026-02-27", 100.0),
        ]
    )
    ndx = _bench(
        [
            ("2025-12-31", 200.0),
            ("2026-01-05", 200.0),
            ("2026-01-30", 210.0),
            ("2026-02-02", 210.0),
            ("2026-02-03", 205.0),
            ("2026-02-27", 205.0),
        ]
    )
    return bal, spx, ndx


def test_ui_table_includes_all_required_display_columns(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    accounting = ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05"))
    ui = adui.build_agm_daily_accounting_ui(accounting, ndx_df=ndx, inception=pd.Timestamp("2026-01-05"))
    labels = set(ui.display_table().columns)
    assert labels == set(adui.required_ui_table_labels())


def test_table_rows_use_display_keys_newest_first(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    accounting = ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05"))
    ui = adui.build_agm_daily_accounting_ui(accounting, ndx_df=ndx, inception=pd.Timestamp("2026-01-05"))
    rows = ui.table_rows(newest_first=True)
    assert rows[0]["Date"] == "2026-02-27"
    assert "Actual NLV / TradeStation Net Worth" in rows[0]
    assert "Client Net Value / Net of Accrued Fees" in rows[0]


def test_invariant_delegated_to_pure_model(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    accounting = ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05"))
    ui = adui.build_agm_daily_accounting_ui(accounting, ndx_df=ndx, inception=pd.Timestamp("2026-01-05"))
    assert ada.verify_accounting_invariant(ui.table)


def test_actual_nlv_equals_csv_net_worth(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    ui = adui.build_agm_daily_accounting_ui(
        ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05")),
        ndx_df=ndx,
        inception=pd.Timestamp("2026-01-05"),
    )
    merged = ui.table.merge(bal[["Date", "Net Worth"]], on="Date")
    assert (merged["actual_nlv"] - merged["Net Worth"]).abs().max() < 1e-9


def test_client_net_equals_actual_minus_accrued(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    ui = adui.build_agm_daily_accounting_ui(
        ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05")),
        ndx_df=ndx,
        inception=pd.Timestamp("2026-01-05"),
    )
    t = ui.table
    assert (t["client_net_value"] - (t["actual_nlv"] - t["accrued_unpaid_fees"])).abs().max() < 1e-9


def test_chart_series_match_accounting_table(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    inception = pd.Timestamp("2026-01-05")
    ui = adui.build_agm_daily_accounting_ui(
        ada.compute_agm_daily_accounting(bal, spx, inception=inception),
        ndx_df=ndx,
        inception=inception,
    )
    post = ui.table[ui.table["Date"] >= inception]
    c = ui.chart
    assert len(c.dates) == len(post)
    assert np.allclose(c.client_net_value.values, post["client_net_value"].values)
    assert np.allclose(c.actual_nlv.values, post["actual_nlv"].values)
    assert np.allclose(c.accrued_unpaid_fees.values, post["accrued_unpaid_fees"].values)
    assert np.allclose(c.spx_close.values, post["spx_close"].values, equal_nan=True)


def test_momentum_daily_pct_from_client_net(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    ui = adui.build_agm_daily_accounting_ui(
        ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05")),
        ndx_df=ndx,
        inception=pd.Timestamp("2026-01-05"),
    )
    expected = adb.daily_pct_change(ui.chart.client_net_value)
    assert np.allclose(
        ui.chart.momentum_daily_pct.values.astype(float),
        expected.values.astype(float),
        equal_nan=True,
    )


def test_spx_daily_pct_from_spx_close(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    ui = adui.build_agm_daily_accounting_ui(
        ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05")),
        ndx_df=ndx,
        inception=pd.Timestamp("2026-01-05"),
    )
    expected = adb.daily_pct_change(ui.chart.spx_close)
    assert np.allclose(
        ui.chart.spx_daily_pct.values.astype(float),
        expected.values.astype(float),
        equal_nan=True,
    )


def test_spread_equals_momentum_minus_spx(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    ui = adui.build_agm_daily_accounting_ui(
        ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05")),
        ndx_df=ndx,
        inception=pd.Timestamp("2026-01-05"),
    )
    spread = ui.chart.momentum_daily_pct - ui.chart.spx_daily_pct
    assert np.allclose(
        ui.chart.momentum_vs_spx_daily_spread_pct.values.astype(float),
        spread.values.astype(float),
        equal_nan=True,
    )


def test_ndx_rebased_starts_at_starting_capital(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    ui = adui.build_agm_daily_accounting_ui(
        ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05")),
        ndx_df=ndx,
        inception=pd.Timestamp("2026-01-05"),
        starting_capital=30_000.0,
    )
    assert ui.chart.ndx_rebased.iloc[0] == pytest.approx(30_000.0)
    assert ui.chart.spx_rebased.iloc[0] == pytest.approx(30_000.0)


def test_fee_payment_marker_only_when_evidenced(synthetic_payment_scenario):
    bal, spx, ndx = synthetic_payment_scenario
    ui = adui.build_agm_daily_accounting_ui(
        ada.compute_agm_daily_accounting(bal, spx, inception=pd.Timestamp("2026-01-05")),
        ndx_df=ndx,
        inception=pd.Timestamp("2026-01-05"),
    )
    rows = {r["Date"]: r for r in ui.table_rows(newest_first=False)}
    assert rows["2026-02-03"]["Fee payment"] == pytest.approx(1000.0)
    assert rows["2026-02-02"]["Fee payment"] is None
    assert all(r["Fee payment"] is None for d, r in rows.items() if d != "2026-02-03")


@pytest.fixture(scope="module")
def real_ui() -> adui.AgmDailyAccountingUI:
    return adui.load_agm_daily_accounting_ui(
        balances_path=CSV_PATH,
        fetcher=_raising_fetcher,
    )


def test_real_data_loader_cache_only(real_ui):
    assert ada.verify_accounting_invariant(real_ui.table)
    assert not real_ui.table.empty
    assert real_ui.chart.ndx_rebased.iloc[0] == pytest.approx(30_000.0)
