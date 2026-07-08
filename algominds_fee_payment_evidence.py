"""
Algominds / Momentum Pacer — evidenced incentive-fee CASH TRANSACTIONS (AGM-only).

Separate from the fee FORMULA (algominds_daily_fees.py never changes because of
this file). This is a small, deterministic, hand-maintained list of incentive-fee
withdrawals confirmed directly from TradeStation's cash-transaction history —
stronger evidence than the accrual engine's own NET-WORTH-DELTA inference
methods (exact-daily-match / workbook-reconciliation), which can miss a real
payment on a day when ordinary trading P/L happens to land on the same date and
masks the isolated withdrawal amount in the day's aggregate Net Worth change.

Update this list whenever a new TradeStation cash-transaction export confirms
another incentive-fee withdrawal. Each entry:
  - date        : the cash-transaction date (withdrawal settlement date).
  - description : the transaction description, verbatim from the export.
  - amount      : the fee PAID, as a POSITIVE dollar amount. TradeStation's own
                  Debit/Credit column shows this as a NEGATIVE cash flow (money
                  leaving the account); this module stores the equivalent
                  positive PAYMENT amount, matching how every other payment
                  amount in this codebase (DailyFeeAccrual.payments[].amount,
                  the accounting table's fee_payment column, chart markers) is
                  represented.

Confirmed transactions (as of 2026-07-08):
  2026-05-14  "April 2026 Incentive Fee - April 2026 Incentive Fee"   -$2,967.85
  2026-06-23  "May 2026 Incentive Fee - May 2026 Incentive Fee"       -$1,330.25

No payment is fabricated: only entries explicitly confirmed by a real
TradeStation cash-transaction export belong in this list.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import pandas as pd


@dataclass(frozen=True)
class FeePaymentEvidence:
    date: pd.Timestamp
    description: str
    amount: float  # positive dollars paid


EVIDENCED_FEE_PAYMENTS: Tuple[FeePaymentEvidence, ...] = (
    FeePaymentEvidence(
        date=pd.Timestamp("2026-05-14"),
        description="April 2026 Incentive Fee - April 2026 Incentive Fee",
        amount=2967.85,
    ),
    FeePaymentEvidence(
        date=pd.Timestamp("2026-06-23"),
        description="May 2026 Incentive Fee - May 2026 Incentive Fee",
        amount=1330.25,
    ),
)


def evidenced_payments_by_date() -> dict:
    """{normalized Timestamp: [FeePaymentEvidence, ...]} — grouped in case a
    future export ever confirms more than one withdrawal on the same date."""
    by_date: dict = {}
    for ev in EVIDENCED_FEE_PAYMENTS:
        by_date.setdefault(pd.Timestamp(ev.date).normalize(), []).append(ev)
    return by_date
