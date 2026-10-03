"""AGM public client views include persisted manual / uploader rows."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest


def _load_mp_ts():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "mp_ts_client_manual",
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
    # Clear import-time live display state so tests use the temp manual file only.
    with mod._AGM_DISPLAY_LOCK:
        mod._AGM_LIVE_ACCOUNTING = None
        mod._AGM_LIVE_FEE_ACCRUAL = None
        mod._AGM_DISPLAY_REVISION = 0
    return mod, manual_path


def test_effective_client_table_merges_manual_row(mp_ts):
    mod, manual_path = mp_ts
    manual_path.write_text(
        json.dumps(
            [
                {
                    "date": "2026-07-14",
                    "actual_nlv": 44709.50,
                    "deposit_withdrawal": 0.0,
                    "incentive_fee_paid": 0.0,
                }
            ]
        ),
        encoding="utf-8",
    )
    table = mod._effective_client_accounting_table()
    assert not table.empty
    latest = table.sort_values("Date").iloc[-1]
    assert pd.Timestamp(latest["Date"]) == pd.Timestamp("2026-07-14")
    assert float(latest["actual_nlv"]) == pytest.approx(44709.50)
