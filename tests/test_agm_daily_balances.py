"""AGM daily TradeStation balances parser tests (algominds_daily_balances)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import algominds_daily_balances as adb

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "Momentum Pacer" / "data" / "daily_balances" / adb.DAILY_BALANCES_FILENAME


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    return adb.load_daily_balances(CSV_PATH)


def test_csv_exists_in_agm_data_dir():
    assert CSV_PATH.is_file(), f"expected daily balances CSV at {CSV_PATH}"


def test_finds_correct_header_row():
    idx = adb._find_header_row_index(CSV_PATH)
    # Metadata block precedes the real header, so it must not be row 0.
    assert idx > 0
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        lines = f.read().splitlines()
    assert lines[idx].startswith("Date,Net Worth")


def test_loads_daily_rows(df):
    assert not df.empty
    assert len(df) == 181


def test_money_columns_are_numeric(df):
    for col in adb.MONEY_COLUMNS:
        assert col in df.columns
        assert pd.api.types.is_numeric_dtype(df[col])


def test_negative_values_parsed_from_parentheses(df):
    # Accountant-format negatives like ($530.00) must become negative floats.
    assert (df["Unrealized P/L"] < 0).any()


def test_money_parser_handles_formats():
    assert adb._parse_money('"$45,675.81 "') == pytest.approx(45675.81)
    assert adb._parse_money("$0.00 ") == pytest.approx(0.0)
    assert adb._parse_money("($530.00)") == pytest.approx(-530.0)
    assert adb._parse_money('"($1,324.00)"') == pytest.approx(-1324.0)
    assert adb._parse_money("") is None
    assert adb._parse_money(None) is None


def test_date_range_parsed(df):
    assert df["Date"].min().date().isoformat() == "2025-10-20"
    assert df["Date"].max().date().isoformat() == "2026-07-01"
    assert pd.api.types.is_datetime64_any_dtype(df["Date"])


def test_latest_net_worth_available(df):
    assert adb.latest_net_worth(df) == pytest.approx(45675.81)
    row = adb.latest_row(df)
    assert row["Date"].date().isoformat() == "2026-07-01"


def test_derived_fields_compute(df):
    for col in ["daily_net_worth_change", "daily_net_worth_change_pct",
                "since_inception_pct", "mtd_pct", "wtd_pct"]:
        assert col in df.columns
    # First Net Worth is $30,000; since-inception at the latest row is (45675.81/30000 - 1).
    expected_since = (45675.81 / 30000.0 - 1.0) * 100.0
    assert df["since_inception_pct"].iloc[-1] == pytest.approx(expected_since, abs=0.01)
    # daily change reconciles with a raw diff of Net Worth.
    assert df["daily_net_worth_change"].iloc[-1] == pytest.approx(
        df["Net Worth"].iloc[-1] - df["Net Worth"].iloc[-2], abs=1e-6
    )


def test_missing_file_returns_empty_not_error(tmp_path):
    missing = tmp_path / "nope.csv"
    out = adb.load_daily_balances(missing)
    assert out.empty


def test_does_not_mutate_source_csv(df):
    # Loading must be read-only; the on-disk file size/content is unchanged.
    before = CSV_PATH.read_bytes()
    adb.load_daily_balances(CSV_PATH)
    after = CSV_PATH.read_bytes()
    assert before == after
