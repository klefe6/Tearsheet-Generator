"""Deterministic tests for NYSE trading-date status (injectable ``now``)."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.trading_calendar import (
    get_trading_date_status,
    reset_calendar_loader,
    set_calendar_loader,
)

NY = ZoneInfo("America/New_York")


def _ny(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=NY)


@pytest.fixture(autouse=True)
def _restore_calendar_loader():
    yield
    reset_calendar_loader()


def test_monday_before_normal_close_last_session_is_prior_friday():
    # Monday 2026-07-13 10:00 ET — market still open; last completed = Friday 2026-07-10.
    status = get_trading_date_status(_ny(2026, 7, 13, 10, 0))
    assert status["today"] == "2026-07-13"
    assert status["last_trading_date"] == "2026-07-10"
    assert status["market_status"] == "open"
    assert status["timezone"] == "America/New_York"


def test_monday_after_normal_close_last_session_is_monday():
    status = get_trading_date_status(_ny(2026, 7, 13, 16, 5))
    assert status["today"] == "2026-07-13"
    assert status["last_trading_date"] == "2026-07-13"
    assert status["market_status"] == "closed"


def test_saturday_last_session_is_prior_friday():
    status = get_trading_date_status(_ny(2026, 7, 11, 12, 0))
    assert status["today"] == "2026-07-11"
    assert status["last_trading_date"] == "2026-07-10"
    assert status["is_trading_day"] is False


def test_exchange_holiday_last_session_is_prior_valid_day():
    # Independence Day 2026 is Saturday; NYSE observes Friday 2026-07-03 as closed.
    status = get_trading_date_status(_ny(2026, 7, 3, 11, 0))
    assert status["today"] == "2026-07-03"
    assert status["last_trading_date"] == "2026-07-02"
    assert status["is_trading_day"] is False


def test_early_close_before_close_last_session_is_prior_day():
    # Day after Thanksgiving 2025 — NYSE early close 1:00 PM ET.
    status = get_trading_date_status(_ny(2025, 11, 28, 12, 30))
    assert status["today"] == "2025-11-28"
    assert status["last_trading_date"] == "2025-11-26"
    assert status["is_early_close"] is True
    assert status["market_status"] == "open"


def test_early_close_after_close_last_session_is_current_day():
    status = get_trading_date_status(_ny(2025, 11, 28, 13, 15))
    assert status["today"] == "2025-11-28"
    assert status["last_trading_date"] == "2025-11-28"
    assert status["is_early_close"] is True
    assert status["market_status"] == "closed"


def test_utc_date_differs_from_new_york_still_uses_ny():
    # 2026-07-13 02:00 UTC = 2026-07-12 22:00 ET (Sunday evening).
    status = get_trading_date_status(datetime(2026, 7, 13, 2, 0, tzinfo=ZoneInfo("UTC")))
    assert status["today"] == "2026-07-12"
    assert status["last_trading_date"] == "2026-07-10"


def test_calendar_failure_does_not_label_today_as_last_trading_date():
    def _boom():
        raise RuntimeError("calendar offline")

    set_calendar_loader(_boom)
    status = get_trading_date_status(_ny(2026, 7, 13, 10, 0))
    assert status["today"] == "2026-07-13"
    assert status["last_trading_date"] is None
    assert status["market_status"] == "unavailable"
    assert status["error"]
