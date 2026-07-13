"""NYSE trading-session calendar for Glenn Daily Uploader date display.

All trading-date truth is computed server-side in America/New_York using the
NYSE exchange calendar (holidays + official early closes). Never infer trading
dates from the browser clock or UTC date truncation.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

NY_TZ = ZoneInfo("America/New_York")
EXCHANGE = "NYSE"

# Injectable in tests to simulate calendar load failures.
_calendar_loader: Optional[Callable[[], Any]] = None


def _default_calendar_loader():
    import pandas_market_calendars as mcal

    return mcal.get_calendar(EXCHANGE)


def _get_calendar():
    loader = _calendar_loader or _default_calendar_loader
    return loader()


def _iso(d: date) -> str:
    return d.isoformat()


def _as_ny_datetime(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now.replace(tzinfo=ZoneInfo("UTC")).astimezone(NY_TZ)
    return now.astimezone(NY_TZ)


def _prior_trading_day(cal: Any, on_date: date) -> date:
    """Most recent completed session strictly before ``on_date``."""
    start = pd.Timestamp(on_date) - pd.Timedelta(days=21)
    end = pd.Timestamp(on_date) - pd.Timedelta(days=1)
    valid = cal.valid_days(start_date=start, end_date=end)
    if len(valid) == 0:
        raise ValueError(f"No prior trading session before {on_date}")
    return valid[-1].date()


def _session_row(cal: Any, session_date: date) -> Optional[pd.Series]:
    sched = cal.schedule(start_date=session_date, end_date=session_date)
    if sched.empty:
        return None
    return sched.iloc[0]


def _market_status(now_ny: datetime, market_open: datetime, market_close: datetime) -> str:
    if now_ny < market_open:
        return "pre_market"
    if now_ny < market_close:
        return "open"
    return "closed"


def get_trading_date_status(now: Optional[datetime] = None) -> dict[str, Any]:
    """
    Return authoritative NY-market date context for the uploader UI.

    ``last_trading_date`` is the most recent *completed* applicable NYSE cash
    session — never today's calendar date before the official session close.
    """
    now_ny = _as_ny_datetime(now or datetime.now(NY_TZ))
    today_ny = now_ny.date()
    calculated_at = now_ny.isoformat()

    try:
        cal = _get_calendar()
    except Exception as exc:  # noqa: BLE001 — surface explicit unavailable state
        return {
            "today": _iso(today_ny),
            "last_trading_date": None,
            "timezone": "America/New_York",
            "market_status": "unavailable",
            "calculated_at": calculated_at,
            "error": str(exc),
        }

    try:
        session = _session_row(cal, today_ny)
        if session is None:
            last_td = _prior_trading_day(cal, today_ny)
            return {
                "today": _iso(today_ny),
                "last_trading_date": _iso(last_td),
                "timezone": "America/New_York",
                "market_status": "closed",
                "calculated_at": calculated_at,
                "is_trading_day": False,
                "session_close": None,
            }

        market_open = session["market_open"].tz_convert(NY_TZ)
        market_close = session["market_close"].tz_convert(NY_TZ)
        is_early_close = market_close.time() < time(16, 0)

        if now_ny >= market_close:
            last_td = today_ny
        else:
            last_td = _prior_trading_day(cal, today_ny)

        return {
            "today": _iso(today_ny),
            "last_trading_date": _iso(last_td),
            "timezone": "America/New_York",
            "market_status": _market_status(now_ny, market_open, market_close),
            "calculated_at": calculated_at,
            "is_trading_day": True,
            "session_close": market_close.isoformat(),
            "is_early_close": is_early_close,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "today": _iso(today_ny),
            "last_trading_date": None,
            "timezone": "America/New_York",
            "market_status": "unavailable",
            "calculated_at": calculated_at,
            "error": str(exc),
        }


def reset_calendar_loader() -> None:
    """Restore default calendar loader (for tests)."""
    global _calendar_loader
    _calendar_loader = None


def set_calendar_loader(loader: Optional[Callable[[], Any]]) -> None:
    """Inject calendar loader (for tests)."""
    global _calendar_loader
    _calendar_loader = loader
