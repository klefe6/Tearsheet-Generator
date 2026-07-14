"""Shared program Account Stats helper (Total | Client | Proprietary)."""
from __future__ import annotations

import pytest

import program_account_stats as pas


def _bucket(
    *,
    nominal: float,
    opened: int,
    open_now: int,
    closed_p: int = 0,
    closed_u: int = 0,
    range_str: str | None = None,
) -> pas.ProgramBucketStats:
    return pas.ProgramBucketStats(
        nominal_assets=nominal,
        total_opened=opened,
        currently_open=open_now,
        closed_profitably=closed_p,
        closed_unprofitably=closed_u,
        closed_return_range=range_str,
    )


def test_agm_totals_derived_from_buckets():
    stats = pas.ProgramAccountStats(
        proprietary=_bucket(nominal=150_000, opened=5, open_now=5),
        client=_bucket(
            nominal=210_000,
            opened=7,
            open_now=6,
            closed_p=1,
            range_str="+0.57%",
        ),
    )
    total = stats.total
    assert total.nominal_assets == pytest.approx(360_000.0)
    assert total.total_opened == 12
    assert total.currently_open == 11
    assert total.closed_profitably == 1
    assert total.closed_unprofitably == 0
    assert total.closed_return_range == "+0.57%"


def test_format_agm_rows_include_total_column():
    stats = pas.ProgramAccountStats(
        proprietary=_bucket(nominal=150_000, opened=5, open_now=5),
        client=_bucket(
            nominal=210_000,
            opened=7,
            open_now=6,
            closed_p=1,
            range_str="+0.57%",
        ),
    )
    rows = pas.format_program_account_stats_rows(stats, include_total=True)
    by_label = {label: (total, client, prop) for label, total, client, prop in rows}
    assert by_label["Nominal Assets Being Traded in the Program"] == (
        "360k",
        "210k",
        "150k",
    )
    assert by_label["Total Accounts/Tranches Opened"] == ("12", "7", "5")
    assert by_label["Range of Net Returns of Accounts/Tranches Closed"] == (
        "+0.57%",
        "+0.57%",
        "N/A",
    )


def test_merge_ranges_across_both_buckets():
    merged = pas.merge_closed_return_ranges("0.36% to 4.2%", "0–1%")
    assert merged == "0% to 4.2%"


def test_tkp_should_not_show_total_column():
    stats = pas.ProgramAccountStats(
        proprietary=_bucket(nominal=300_000, opened=4, open_now=2, closed_p=2, range_str="0.36% to 4.2%"),
        client=_bucket(nominal=0, opened=0, open_now=0),
    )
    assert pas.should_show_total_column(stats) is False
    assert stats.total.total_opened == stats.proprietary.total_opened


def test_tcp_should_not_show_total_column():
    stats = pas.ProgramAccountStats(
        proprietary=_bucket(nominal=50_000, opened=2, open_now=2),
        client=_bucket(nominal=0, opened=0, open_now=0),
    )
    assert pas.should_show_total_column(stats) is False
