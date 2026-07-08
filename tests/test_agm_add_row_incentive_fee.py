"""AGM Add Row: Deposit / Withdrawal + Incentive Fee Paid wiring.

Three layers, each proving a different part of "connects to the existing
evidenced fee-payment/accrual model, without double-subtracting from Client
Net Economic Value, and without changing the fee formula":

  1. Formula layer (algominds_daily_fees / algominds_daily_accounting):
     synthetic fixtures, no repo data — proves a cash_transaction_payments
     entry reduces accrued_unpaid_fees and the
     actual_nlv = client_net_value + accrued_unpaid_fees invariant still
     holds (i.e. no double-subtraction).
  2. Wiring layer (mp_ts._agm_manual_fee_payments): a manual row's
     incentive_fee_paid becomes an additional FeePaymentEvidence alongside
     the committed EVIDENCED_FEE_PAYMENTS list — the SAME mechanism, not a
     parallel one.
  3. Persistence layer (mp_ts.agm_add_manual_daily_row): Deposit/Withdrawal
     and Incentive Fee Paid round-trip through the manual-rows JSON file,
     with validation (Incentive Fee Paid must not be negative).
"""
from __future__ import annotations

import pandas as pd
import pytest

import algominds_daily_accounting as ada
import algominds_daily_fees as adf
import algominds_fee_payment_evidence as afe


def _balances(rows):
    return pd.DataFrame({
        "Date": pd.to_datetime([d for d, _ in rows]),
        "Net Worth": [v for _, v in rows],
    })


def _bench(rows):
    return pd.DataFrame({
        "Date": pd.to_datetime([d for d, _ in rows]),
        "Close": [c for _, c in rows],
    })


@pytest.fixture
def synthetic_with_outstanding_fee():
    """Jan crystallizes a $1,000 fee (flat SPX -> 50% of $2,000 profit) with
    NO payment evidence -> it rides outstanding into Feb, exactly like
    test_agm_daily_fees.py's `synthetic` fixture."""
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
        ("2026-01-30", 100.0),
        ("2026-02-02", 100.0),
        ("2026-02-27", 100.0),
    ])
    return bal, bench


# ── Layer 1: formula-level proof (no double-subtraction) ────────────────────

def test_cash_transaction_payment_reduces_outstanding_fee(synthetic_with_outstanding_fee):
    bal, bench = synthetic_with_outstanding_fee
    inception = pd.Timestamp("2026-01-05")

    unpaid = adf.compute_daily_fee_accrual(
        bal, bench, inception=inception, cash_transaction_payments=(),
    )
    assert unpaid.outstanding == [{"month": "2026-01", "fee": 1000.0}]
    unpaid_feb_row = unpaid.daily[unpaid.daily["Date"] == "2026-02-02"].iloc[0]
    assert unpaid_feb_row["outstanding_total"] == pytest.approx(1000.0)

    admin_payment = afe.FeePaymentEvidence(
        date=pd.Timestamp("2026-02-02"),
        description="Admin-entered incentive fee payment",
        amount=1000.0,
    )
    paid = adf.compute_daily_fee_accrual(
        bal, bench, inception=inception, cash_transaction_payments=(admin_payment,),
    )
    assert paid.outstanding == []
    paid_feb_row = paid.daily[paid.daily["Date"] == "2026-02-02"].iloc[0]
    assert paid_feb_row["outstanding_total"] == pytest.approx(0.0)
    assert any(p["method"] == "cash-transaction-evidence" for p in paid.payments)


def test_incentive_fee_paid_increases_client_net_value_without_double_subtracting(
    synthetic_with_outstanding_fee,
):
    """The defining accounting property: paying down a previously-accrued fee
    must raise client_net_value by EXACTLY however much accrued_unpaid_fees
    drops (same actual_nlv either way -- the payment is evidence, not a
    second hand-entered cash adjustment), and the core invariant continues to
    hold in both scenarios. This holds regardless of the exact dollar amount
    the (unmodified) fee formula ends up attributing to accrued vs. paid --
    e.g. here the in-progress Feb month also accrues more once measured
    against the now-lower outstanding balance, so accrued_unpaid_fees drops
    by less than the $1,000 paid; client_net_value still gains back exactly
    that smaller amount, never more and never less (no double-subtraction in
    either direction)."""
    bal, bench = synthetic_with_outstanding_fee
    inception = pd.Timestamp("2026-01-05")

    unpaid_acct = ada.compute_agm_daily_accounting(
        bal, bench, inception=inception, cash_transaction_payments=(),
    )
    admin_payment = afe.FeePaymentEvidence(
        date=pd.Timestamp("2026-02-02"), description="test", amount=1000.0,
    )
    paid_acct = ada.compute_agm_daily_accounting(
        bal, bench, inception=inception, cash_transaction_payments=(admin_payment,),
    )

    assert ada.verify_accounting_invariant(unpaid_acct.table)
    assert ada.verify_accounting_invariant(paid_acct.table)

    unpaid_row = unpaid_acct.table[unpaid_acct.table["Date"] == "2026-02-02"].iloc[0]
    paid_row = paid_acct.table[paid_acct.table["Date"] == "2026-02-02"].iloc[0]

    # Same TradeStation NLV either way -- the payment is evidence, not a
    # second hand-entered cash adjustment.
    assert unpaid_row["actual_nlv"] == pytest.approx(paid_row["actual_nlv"])

    delta_accrued = paid_row["accrued_unpaid_fees"] - unpaid_row["accrued_unpaid_fees"]
    delta_client_net = paid_row["client_net_value"] - unpaid_row["client_net_value"]
    assert delta_accrued < 0  # a real evidenced payment reduces the fee liability
    # No double-subtraction: whatever accrued_unpaid_fees gives up,
    # client_net_value gains back -- dollar for dollar, since actual_nlv
    # (the only other term in the invariant) is unchanged.
    assert delta_client_net == pytest.approx(-delta_accrued)


# ── Layer 2: mp_ts wiring from manual rows to fee-payment evidence ──────────

def test_agm_manual_fee_payments_extends_evidenced_list():
    import mp_ts

    manual = [
        {"date": "2026-08-01", "actual_nlv": 50_000.0, "incentive_fee_paid": 250.0},
        {"date": "2026-08-02", "actual_nlv": 50_100.0, "incentive_fee_paid": 0},
    ]
    merged = mp_ts._agm_manual_fee_payments(manual)
    assert merged is not None
    assert len(merged) == len(mp_ts.agm_fee_evidence.EVIDENCED_FEE_PAYMENTS) + 1
    new_entry = merged[-1]
    assert new_entry.amount == pytest.approx(250.0)
    assert new_entry.date == pd.Timestamp("2026-08-01")
    # The committed evidence list is untouched, just extended.
    for original in mp_ts.agm_fee_evidence.EVIDENCED_FEE_PAYMENTS:
        assert original in merged


def test_agm_manual_fee_payments_none_when_nothing_paid():
    import mp_ts

    manual = [{"date": "2026-08-01", "actual_nlv": 50_000.0, "incentive_fee_paid": 0}]
    assert mp_ts._agm_manual_fee_payments(manual) is None
    assert mp_ts._agm_manual_fee_payments([]) is None


# ── Layer 3: persistence + validation ───────────────────────────────────────

def test_agm_add_row_persists_deposit_and_fee_paid(tmp_path, monkeypatch):
    import mp_ts

    monkeypatch.setattr(
        mp_ts, "_agm_manual_daily_rows_path",
        lambda: str(tmp_path / "manual_rows.json"),
    )
    ok, msg, _table = mp_ts.agm_add_manual_daily_row(
        "2026-07-07", 45_500.0, deposit_val=1_000.0, fee_paid_val=200.0,
    )
    assert ok, msg
    saved = mp_ts._load_agm_manual_daily_rows()
    assert saved[-1]["deposit_withdrawal"] == pytest.approx(1_000.0)
    assert saved[-1]["incentive_fee_paid"] == pytest.approx(200.0)


def test_agm_add_row_defaults_deposit_and_fee_paid_to_zero(tmp_path, monkeypatch):
    import mp_ts

    monkeypatch.setattr(
        mp_ts, "_agm_manual_daily_rows_path",
        lambda: str(tmp_path / "manual_rows.json"),
    )
    ok, msg, _table = mp_ts.agm_add_manual_daily_row("2026-07-07", 45_500.0)
    assert ok, msg
    saved = mp_ts._load_agm_manual_daily_rows()
    assert saved[-1]["deposit_withdrawal"] == 0.0
    assert saved[-1]["incentive_fee_paid"] == 0.0


def test_agm_add_row_rejects_negative_incentive_fee_paid(tmp_path, monkeypatch):
    import mp_ts

    monkeypatch.setattr(
        mp_ts, "_agm_manual_daily_rows_path",
        lambda: str(tmp_path / "manual_rows.json"),
    )
    ok, msg, _table = mp_ts.agm_add_manual_daily_row(
        "2026-07-07", 45_500.0, fee_paid_val=-1.0,
    )
    assert not ok
    assert "not be negative" in msg
