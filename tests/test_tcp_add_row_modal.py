"""TCP v2 Add Row modal contract after date-default parity work.

TCP v2's live production Add Row model (Cash Balance / Cash Transfers /
# Tranches) is intentionally different from TKP's (Plus500/StoneX/Deposit) --
the TCP v2 Implementation Plan explicitly excludes StoneX/Plus500 fields. Only
the Date default is being aligned with TKP's method here; the field set is
untouched.
"""
from __future__ import annotations

from tearsheet_date_defaults import default_add_row_date_str


def test_tcp_add_row_date_default_matches_tkp():
    import tcp_admin
    import tkp_ts

    defaults = tcp_admin.default_add_row_values({"#": 1})
    assert defaults["date"] == default_add_row_date_str()
    assert defaults["date"] == tkp_ts._default_add_row_date_str()


def test_tcp_add_row_modal_still_shows_cash_balance_and_tranches():
    import tcp_admin

    modal_str = str(tcp_admin.build_add_row_modal())
    assert "Cash Balance" in modal_str
    assert "Cash Transfers" in modal_str
    assert "# Tranches" in modal_str


def test_tcp_add_row_modal_does_not_show_plus500_or_stonex():
    import tcp_admin

    modal_str = str(tcp_admin.build_add_row_modal())
    assert "Plus500" not in modal_str
    assert "StoneX" not in modal_str


def test_tcp_add_row_modal_does_not_show_incentive_fee_paid():
    import tcp_admin

    modal_str = str(tcp_admin.build_add_row_modal())
    assert "Incentive Fee Paid" not in modal_str


def test_tcp_default_add_row_values_only_changed_date_field():
    """Cash balance / transfers / tranche-count defaults are unchanged --
    only the date field gained a default (previously "")."""
    import tcp_admin

    defaults = tcp_admin.default_add_row_values({"#": 4})
    assert defaults["cash_balance"] == ""
    assert defaults["cash_transfers"] == 0
    assert defaults["tranche_count"] == 4
