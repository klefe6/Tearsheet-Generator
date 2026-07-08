"""
Shared Add Row date-default helper.

TKP's Add Row modal defaults its Date field to the previous business day
(skipping weekends) relative to today, computed once when the modal/layout is
built. AGM and TCP mirror this exact method so all three Add Row modals agree
on "today" -> default date, instead of each computing its own default
(AGM previously used "next calendar day after the latest known row"; TCP had
no default at all).

Safe to import: no server start, no network, no filesystem access.
"""
from __future__ import annotations

from datetime import date as _date
from datetime import datetime, timedelta
from typing import Optional


def default_add_row_date_str(today: Optional[_date] = None) -> str:
    """Previous business day (Mon -> Fri) as YYYY-MM-DD, relative to *today*
    (defaults to the real today when omitted)."""
    d = (today if today is not None else datetime.today().date()) - timedelta(days=1)
    while d.weekday() >= 5:  # Saturday=5, Sunday=6
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")
