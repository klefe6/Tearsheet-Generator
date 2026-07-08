"""Hand-confirmed TradeStation cash-transaction fee-payment evidence
(algominds_fee_payment_evidence) — separate from the fee formula itself."""
from __future__ import annotations

import pandas as pd
import pytest

import algominds_fee_payment_evidence as agm_fee_evidence


def test_evidence_includes_confirmed_april_and_may_payments():
    by_date = {
        pd.Timestamp(ev.date).normalize(): ev
        for ev in agm_fee_evidence.EVIDENCED_FEE_PAYMENTS
    }
    april = by_date[pd.Timestamp("2026-05-14")]
    assert april.amount == pytest.approx(2967.85)
    assert "April 2026 Incentive Fee" in april.description

    may = by_date[pd.Timestamp("2026-06-23")]
    assert may.amount == pytest.approx(1330.25)
    assert "May 2026 Incentive Fee" in may.description


def test_evidence_amounts_are_positive_payment_dollars():
    """TradeStation's Debit/Credit column shows these as NEGATIVE cash flow
    (-2,967.85 / -1,330.25); this module stores the equivalent POSITIVE
    payment amount, matching every other payment amount in the codebase."""
    for ev in agm_fee_evidence.EVIDENCED_FEE_PAYMENTS:
        assert ev.amount > 0


def test_no_unrelated_payment_dates_fabricated():
    """Only the two hand-confirmed cash transactions belong in this list."""
    dates = {pd.Timestamp(ev.date).normalize() for ev in agm_fee_evidence.EVIDENCED_FEE_PAYMENTS}
    assert dates == {pd.Timestamp("2026-05-14"), pd.Timestamp("2026-06-23")}
    assert len(agm_fee_evidence.EVIDENCED_FEE_PAYMENTS) == 2


def test_evidenced_payments_by_date_groups_correctly():
    by_date = agm_fee_evidence.evidenced_payments_by_date()
    assert set(by_date.keys()) == {pd.Timestamp("2026-05-14"), pd.Timestamp("2026-06-23")}
    assert len(by_date[pd.Timestamp("2026-05-14")]) == 1
    assert by_date[pd.Timestamp("2026-05-14")][0].amount == pytest.approx(2967.85)
