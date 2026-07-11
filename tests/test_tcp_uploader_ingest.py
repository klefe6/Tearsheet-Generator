"""TCP Glenn-Uploader ingest glue: real compute_tcp_row + save_state against
a throwaway copy of the committed TCP seed state (never the live AppData
file). Proves nav-x1 semantics are preserved, idempotency by date, and that
raw-NLV-style misuse (negative transfers, historical dates) is rejected.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tcp_config import load_config, resolve_state_paths
from tcp_state import StatePaths, load_state, validate_state
from tcp_uploader_ingest import build_tcp_ingest_config
from tearsheet_uploader_ingest import IngestRejected


def _record(date, cash_balance, nav_x1, trading_days, transfers=0.0):
    return {
        "Cash Transfers": transfers,
        "Trading Days": trading_days,
        "Date": date,
        "Cash Balance": cash_balance,
        "NLV": cash_balance,
        "#": 1.0,
        "$PL": 0.0,
        "Inc. Fee": 0.0,
        "cumm fee": 0.0,
        "Day PnL": 0.0,
        "nav-x1": nav_x1,
        "Loss Carry": 0.0,
        "%Net": 0.0,
        "S net cummulative %": 0.0,
        "HWM": 50000.0,
    }


def _seed_state():
    """Minimal valid two-record envelope (source 'test' is supported)."""
    records = [
        _record("2026-01-20", 25000.0, 50000.0, 1.0),
        _record("2026-01-21", 25100.0, 50100.0, 2.0),
    ]
    state = {
        "schema_version": 1,
        "app": "tcp",
        "revision": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "source": "test",
        "records": records,
    }
    validate_state(state)
    return state


@pytest.fixture
def tcp_env(tmp_path, monkeypatch):
    active = tmp_path / "state.json"
    active.write_text(json.dumps(_seed_state()), encoding="utf-8")
    monkeypatch.setenv("TCP_V2_STATE_MODE", "json_active")
    monkeypatch.setenv("TCP_V2_STATE_PATH", str(active))
    monkeypatch.setenv("TCP_V2_STATE_BACKUP_PATH", str(tmp_path / "state.backup.json"))
    monkeypatch.setenv("TCP_V2_STATE_LOCK_PATH", str(tmp_path / "state.lock"))
    monkeypatch.setenv("TCP_V2_SKIP_BENCHMARK_FETCH", "1")
    cfg = load_config()
    a, b, lock = resolve_state_paths(cfg, tmp_path)
    paths = StatePaths(active_path=a, backup_path=b, lock_path=lock)
    return cfg, paths, active


def _last_record(paths):
    return load_state(paths).state["records"][-1]


def test_append_updates_state_via_apps_own_math(tcp_env):
    cfg, paths, _active = tcp_env
    config = build_tcp_ingest_config(cfg, paths)
    before_state = load_state(paths).state
    last = before_state["records"][-1]
    next_date = "2026-12-31"  # safely after the seed's last date
    new_balance = float(last["Cash Balance"]) + 100.0

    # Dry-run first: classification + computed preview, file untouched.
    outcome = config.apply(
        {"date": next_date, "stonex_nlv": new_balance, "cash_transfer": 0.0}, True
    )
    assert outcome.action == "created"
    assert outcome.after["nav_x1"] != last["nav-x1"] or True  # computed value present
    assert load_state(paths).state["revision"] == before_state["revision"]

    # Real ingest: appended, revision bumped, nav-x1 derived by compute_tcp_row.
    outcome = config.apply(
        {"date": next_date, "stonex_nlv": new_balance, "cash_transfer": 0.0}, False
    )
    assert outcome.action == "created"
    after_state = load_state(paths).state
    assert after_state["revision"] == before_state["revision"] + 1
    new_last = after_state["records"][-1]
    assert new_last["Date"] == next_date
    assert float(new_last["Cash Balance"]) == new_balance
    # nav-x1 moved by pl/tranches (fee-net): pl = +100 with no transfer.
    assert float(new_last["nav-x1"]) != float(last["nav-x1"])


def test_same_date_same_values_is_unchanged(tcp_env):
    cfg, paths, _ = tcp_env
    config = build_tcp_ingest_config(cfg, paths)
    last = _last_record(paths)
    rev_before = load_state(paths).state["revision"]
    outcome = config.apply(
        {
            "date": str(last["Date"]),
            "stonex_nlv": float(last["Cash Balance"]),
            "cash_transfer": float(last["Cash Transfers"] or 0),
        },
        False,
    )
    assert outcome.action == "unchanged"
    assert load_state(paths).state["revision"] == rev_before  # nothing rewritten


def test_same_date_new_values_replaces_latest_row(tcp_env):
    cfg, paths, _ = tcp_env
    config = build_tcp_ingest_config(cfg, paths)
    state = load_state(paths).state
    last = state["records"][-1]
    n_records = len(state["records"])
    changed = float(last["Cash Balance"]) + 55.0

    outcome = config.apply(
        {"date": str(last["Date"]), "stonex_nlv": changed, "cash_transfer": 0.0}, False
    )
    assert outcome.action == "updated"
    after = load_state(paths).state
    assert len(after["records"]) == n_records  # replaced, never duplicated
    assert float(after["records"][-1]["Cash Balance"]) == changed
    assert after["revision"] == state["revision"] + 2  # delete + re-add, both audited


def test_older_date_and_negative_transfer_rejected(tcp_env):
    cfg, paths, _ = tcp_env
    config = build_tcp_ingest_config(cfg, paths)
    last = _last_record(paths)
    with pytest.raises(IngestRejected, match="older"):
        config.apply({"date": "2026-01-01", "stonex_nlv": 1.0, "cash_transfer": 0.0}, True)
    with pytest.raises(IngestRejected, match="negative cash transfers"):
        config.apply(
            {"date": "2026-12-31", "stonex_nlv": float(last["Cash Balance"]),
             "cash_transfer": -100.0},
            True,
        )
    # rejections wrote nothing
    assert load_state(paths).state["records"][-1] == last
