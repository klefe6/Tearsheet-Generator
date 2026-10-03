"""AGM downstream continuity regressions for intermediate historical daily rows.

These tests use a temporary manual JSON path and never touch the live
momentum_pacer_manual_daily_rows.json file.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


def _load_mp_ts():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "mp_ts_agm_continuity",
        root / "Momentum Pacer" / "mp_ts.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mp_ts(monkeypatch, tmp_path):
    mod = _load_mp_ts()
    manual_path = tmp_path / "manual_rows.json"
    manual_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(mod, "_agm_manual_daily_rows_path", lambda: str(manual_path))
    with mod._AGM_DISPLAY_LOCK:
        mod._AGM_LIVE_ACCOUNTING = None
        mod._AGM_LIVE_FEE_ACCRUAL = None
        mod._AGM_DISPLAY_REVISION = 0
    return mod, manual_path


def _row(date: str, nlv: float) -> dict:
    return {
        "date": date,
        "actual_nlv": float(nlv),
        "deposit_withdrawal": 0.0,
        "incentive_fee_paid": 0.0,
    }


def test_append_three_consecutive_trading_dates_preserves_all(mp_ts):
    mod, path = mp_ts
    seed = [
        _row("2026-07-20", 43716.0),
        _row("2026-07-21", 43716.0),
    ]
    path.write_text(json.dumps(seed), encoding="utf-8")

    for date, nlv in (
        ("2026-07-22", 43716.0),
        ("2026-07-23", 43496.6),
        ("2026-07-24", 43496.6),
    ):
        ok, message, _ = mod.agm_add_manual_daily_row(date, nlv, 0.0, 0.0)
        assert ok, message

    rows = json.loads(path.read_text(encoding="utf-8"))
    dates = [r["date"] for r in rows]
    assert dates == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
        "2026-07-24",
    ]
    assert len(dates) == len(set(dates))


def test_later_tip_preserves_earlier_intermediate_dates(mp_ts):
    mod, path = mp_ts
    path.write_text(
        json.dumps(
            [
                _row("2026-07-21", 43716.0),
                _row("2026-07-22", 43716.0),
                _row("2026-07-23", 43496.6),
                _row("2026-07-24", 43496.6),
            ]
        ),
        encoding="utf-8",
    )
    ok, message, _ = mod.agm_add_manual_daily_row("2026-07-27", 42613.75, 0.0, 0.0)
    assert ok, message
    rows = json.loads(path.read_text(encoding="utf-8"))
    dates = [r["date"] for r in rows]
    assert "2026-07-22" in dates
    assert "2026-07-23" in dates
    assert "2026-07-24" in dates
    assert dates[-1] == "2026-07-27"


def test_reexport_same_newest_values_is_idempotent(mp_ts, monkeypatch):
    mod, path = mp_ts
    path.write_text(json.dumps([_row("2026-07-22", 43716.0)]), encoding="utf-8")
    payload = {
        "date": "2026-07-22",
        "tradestation_nlv": 43716.0,
        "cash_transfer": 0.0,
        "fee": 0.0,
    }
    first = mod._uploader_ingest_apply_agm(payload, dry_run=False)
    second = mod._uploader_ingest_apply_agm(payload, dry_run=False)
    assert first.action in {"created", "unchanged", "updated"}
    assert second.action == "unchanged"
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert [r["date"] for r in rows].count("2026-07-22") == 1


def test_duplicate_interior_date_rejected(mp_ts):
    mod, path = mp_ts
    path.write_text(
        json.dumps(
            [
                _row("2026-07-22", 43716.0),
                _row("2026-07-23", 43496.6),
            ]
        ),
        encoding="utf-8",
    )
    ok, message, _ = mod.agm_add_manual_daily_row("2026-07-22", 43716.0, 0.0, 0.0)
    assert ok is False
    assert "after the latest existing daily row" in message


def test_chronologically_sorted_accounting_after_insert(mp_ts):
    mod, path = mp_ts
    path.write_text(
        json.dumps(
            [
                _row("2026-07-21", 43716.0),
                _row("2026-07-22", 43716.0),
                _row("2026-07-23", 43496.6),
                _row("2026-07-24", 43496.6),
                _row("2026-07-27", 42613.75),
                _row("2026-07-28", 42613.75),
                _row("2026-07-29", 42613.75),
            ]
        ),
        encoding="utf-8",
    )
    table = mod._effective_client_accounting_table().sort_values("Date")
    dates = [pd.Timestamp(d).strftime("%Y-%m-%d") for d in table["Date"]]
    assert dates == sorted(dates)
    jul29 = table[table["Date"] == pd.Timestamp("2026-07-29")].iloc[0]
    assert float(jul29["actual_nlv"]) == pytest.approx(42613.75)
    # Daily return continuity for inserted dates uses prior client_net_value.
    jul23 = table[table["Date"] == pd.Timestamp("2026-07-23")].iloc[0]
    jul22 = table[table["Date"] == pd.Timestamp("2026-07-22")].iloc[0]
    expected = float(jul23["client_net_value"]) / float(jul22["client_net_value"]) - 1.0
    assert float(jul23["momentum_daily_pct"]) == pytest.approx(expected * 100.0)


def test_weekends_not_required_between_fri_and_mon(mp_ts):
    mod, path = mp_ts
    path.write_text(
        json.dumps(
            [
                _row("2026-07-24", 43496.6),  # Friday
                _row("2026-07-27", 42613.75),  # Monday
            ]
        ),
        encoding="utf-8",
    )
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert "2026-07-25" not in [r["date"] for r in rows]
    assert "2026-07-26" not in [r["date"] for r in rows]


def test_zero_cash_movement_not_treated_as_performance(mp_ts):
    mod, path = mp_ts
    path.write_text(
        json.dumps(
            [
                _row("2026-07-22", 43716.0),
                _row("2026-07-23", 43496.6),
            ]
        ),
        encoding="utf-8",
    )
    table = mod._effective_client_accounting_table().sort_values("Date")
    jul23 = table[table["Date"] == pd.Timestamp("2026-07-23")].iloc[0]
    # deposit_withdrawal persisted as 0 and is not used as return numerator
    assert float(jul23["momentum_daily_pct"]) == pytest.approx(
        (43496.6 / 43716.0 - 1.0) * 100.0
    )


def test_save_manual_rows_is_atomic_enough_for_roundtrip(mp_ts, tmp_path):
    mod, path = mp_ts
    payload = [
        _row("2026-07-22", 43716.0),
        _row("2026-07-23", 43496.6),
        _row("2026-07-24", 43496.6),
    ]
    mod._save_agm_manual_daily_rows(payload)
    loaded = mod._load_agm_manual_daily_rows()
    assert loaded == payload
    assert path.exists()
