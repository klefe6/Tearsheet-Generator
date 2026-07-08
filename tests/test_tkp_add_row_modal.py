"""TKP Add Row modal field contract: Plus500 + StoneX balances, Deposit /
Withdrawal (renamed from the old bare "Deposit"/"StoneX Deposit" label), and
NO Incentive Fee Paid field (TKP fees are collected daily, not paid manually)."""
from __future__ import annotations


def _add_modal_str():
    import tkp_ts

    layout = tkp_ts.app.layout() if callable(tkp_ts.app.layout) else tkp_ts.app.layout
    return str(layout)


def test_tkp_add_row_shows_plus500_balance():
    assert "Plus500 Balance" in _add_modal_str()


def test_tkp_add_row_shows_stonex_balance():
    assert "StoneX Balance" in _add_modal_str()


def test_tkp_add_row_shows_deposit_withdrawal_label():
    layout = _add_modal_str()
    assert "Deposit / Withdrawal" in layout
    assert "negative number = withdrawal" in layout


def test_tkp_add_row_does_not_show_incentive_fee_paid():
    assert "Incentive Fee Paid" not in _add_modal_str()


def test_tkp_add_row_save_still_wires_deposit_into_pl_formula():
    """The label changed but the underlying field id / formula did not --
    _compute_new_row still treats the deposit input as a P&L adjustment."""
    import tkp_ts

    prev_row = {"StoneX": "$100,000.00", "NAV": "$100,000.00", "HWM": "$100,000.00"}
    computed = tkp_ts._compute_new_row(prev_row, new_balance=105_000.0, deposit=5_000.0)
    # A $5k deposit fully explains the $5k balance increase -> zero trading P&L.
    assert computed["$PL"] == "$0.00"
    assert computed["Deposit"] == "$5,000"
