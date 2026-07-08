"""Add Row date-default parity across TKP / TCP / AGM.

TKP's Add Row modal has always defaulted its Date field to the previous
business day (Mon -> Fri, skipping weekends) relative to today. TCP (no
default at all) and AGM ("next calendar day after the latest known row")
used different methods. All three now share tearsheet_date_defaults.py so
they agree on the exact same computation for the same "today".
"""
from __future__ import annotations

from datetime import date

from tearsheet_date_defaults import default_add_row_date_str


def test_previous_business_day_skips_saturday_and_sunday():
    # Monday 2026-07-13 -> previous business day is Friday 2026-07-10.
    assert default_add_row_date_str(date(2026, 7, 13)) == "2026-07-10"


def test_previous_business_day_from_sunday():
    # Sunday 2026-07-12 -> previous business day is still Friday 2026-07-10.
    assert default_add_row_date_str(date(2026, 7, 12)) == "2026-07-10"


def test_previous_business_day_from_midweek():
    # Wednesday 2026-07-08 -> previous business day is Tuesday 2026-07-07.
    assert default_add_row_date_str(date(2026, 7, 8)) == "2026-07-07"


def test_tkp_add_row_date_default_documented_by_test():
    """TKP's own Add Row date-default method is the shared helper (item 1)."""
    import tkp_ts

    assert tkp_ts._default_add_row_date_str() == default_add_row_date_str()


def test_tcp_add_row_date_default_matches_tkp_method():
    """TCP v2's Add Row modal now defaults its Date the same way TKP does
    (previously it had no default at all: default_add_row_values()["date"]
    used to be "")."""
    import tcp_admin

    latest_record = {"#": 3}
    defaults = tcp_admin.default_add_row_values(latest_record)
    assert defaults["date"] == default_add_row_date_str()

    import tkp_ts

    assert defaults["date"] == tkp_ts._default_add_row_date_str()


def test_agm_add_row_date_default_matches_tkp_method(monkeypatch):
    """AGM's Add Row modal now defaults its Date the same way TKP does
    (previously it computed "next calendar day after the latest known daily
    row" -- a fundamentally different method tied to the account's own data,
    not to today)."""
    import mp_ts
    import tkp_ts

    assert mp_ts._default_admin_add_row_date() == default_add_row_date_str()
    assert mp_ts._default_admin_add_row_date() == tkp_ts._default_add_row_date_str()


def test_agm_add_row_date_default_is_independent_of_latest_known_row(monkeypatch):
    """Regression guard: the old AGM method derived its default from the
    latest daily-balances/manual row date ("next calendar day after..."), so
    a far-future manual row would have shifted the default. The TKP method
    never looks at the account's data at all, so it must be unaffected."""
    import mp_ts

    before = mp_ts._default_admin_add_row_date()

    monkeypatch.setattr(
        mp_ts, "_load_agm_manual_daily_rows",
        lambda: [{"date": "2099-01-01", "actual_nlv": 999999.0}],
    )
    after = mp_ts._default_admin_add_row_date()
    assert before == after
