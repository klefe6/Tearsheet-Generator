"""Post-ingest full recalculation for TCP / AGM / TKP + ingest response signals."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from tearsheet_uploader_ingest import (
    ENABLED_ENV,
    TOKEN_ENV,
    IngestConfig,
    IngestOutcome,
    handle_ingest_request,
)


TOKEN = "recalc-test-token"


def _headers():
    return {"Authorization": f"Bearer {TOKEN}"}


# ── Framework response completeness ─────────────────────────────────────────


def test_framework_reports_recalculated_and_display_refreshed(monkeypatch):
    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(TOKEN_ENV, TOKEN)

    def apply(payload, dry_run):
        return IngestOutcome(
            action="created",
            before=None,
            after=dict(payload),
            persisted=True,
        )

    def on_persisted(outcome, payload):
        outcome.recalculated = True
        outcome.display_refreshed = True
        outcome.source_revision = 7
        outcome.display_revision = 7
        outcome.latest_display_date = payload["date"]
        outcome.recalculated_fields = ["nav_chart", "daily_returns"]

    cfg = IngestConfig(
        program="TKP",
        required_fields=("stonex_nlv",),
        optional_fields=("plus500_nlv", "cash_transfer"),
        apply=apply,
        on_persisted=on_persisted,
    )
    body = {
        "program": "TKP",
        "date": "2026-07-18",
        "stonex_nlv": 1000,
        "dry_run": False,
    }
    response, status = handle_ingest_request(cfg, _headers(), body, "t")
    assert status == 200
    assert response["persisted"] is True
    assert response["recalculated"] is True
    assert response["display_refreshed"] is True
    assert response["latest_display_date"] == "2026-07-18"
    assert response["source_revision"] == 7
    assert "nav_chart" in response["recalculated_fields"]


def test_framework_keeps_row_when_recalculation_fails(monkeypatch):
    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(TOKEN_ENV, TOKEN)

    def apply(payload, dry_run):
        return IngestOutcome(action="created", after=dict(payload), persisted=True)

    def on_persisted(outcome, payload):
        raise RuntimeError("boom")

    cfg = IngestConfig(
        program="TKP",
        required_fields=("stonex_nlv",),
        optional_fields=("plus500_nlv", "cash_transfer"),
        apply=apply,
        on_persisted=on_persisted,
    )
    body = {
        "program": "TKP",
        "date": "2026-07-18",
        "stonex_nlv": 1000,
        "dry_run": False,
    }
    response, status = handle_ingest_request(cfg, _headers(), body, "t")
    assert status == 200
    assert response["persisted"] is True
    assert response["recalculated"] is False
    assert response["display_refreshed"] is False
    assert "boom" in response["recalculation_error"]


# ── TCP ─────────────────────────────────────────────────────────────────────


def _tcp_record(date, cash_balance, nav_x1, trading_days, transfers=0.0):
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


@pytest.fixture
def tcp_env(tmp_path, monkeypatch):
    from tcp_config import load_config, resolve_state_paths
    from tcp_state import StatePaths, validate_state

    records = [
        _tcp_record("2026-01-20", 25000.0, 50000.0, 1.0),
        _tcp_record("2026-01-21", 25100.0, 50100.0, 2.0),
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
    active = tmp_path / "state.json"
    active.write_text(json.dumps(state), encoding="utf-8")
    monkeypatch.setenv("TCP_V2_STATE_MODE", "json_active")
    monkeypatch.setenv("TCP_V2_STATE_PATH", str(active))
    monkeypatch.setenv("TCP_V2_STATE_BACKUP_PATH", str(tmp_path / "state.backup.json"))
    monkeypatch.setenv("TCP_V2_STATE_LOCK_PATH", str(tmp_path / "state.lock"))
    monkeypatch.setenv("TCP_V2_SKIP_BENCHMARK_FETCH", "1")
    cfg = load_config()
    a, b, lock = resolve_state_paths(cfg, tmp_path)
    paths = StatePaths(active_path=a, backup_path=b, lock_path=lock)
    return cfg, paths, active


def test_tcp_ingest_updates_canonical_nav_and_response_flags(tcp_env, monkeypatch):
    from tcp_runtime_state import load_runtime_snapshot
    from tcp_ts_v2 import apply_tcp_recalculation
    from tcp_uploader_ingest import build_tcp_ingest_config

    cfg, paths, _active = tcp_env
    runtime = {"snapshot": load_runtime_snapshot(cfg, paths)}
    before_nav = runtime["snapshot"].canonical_nav[-1]["NAV"]

    def on_persisted(outcome, payload):
        status = apply_tcp_recalculation(
            cfg, paths, runtime, authoritative_date=payload["date"]
        )
        outcome.source_revision = status["source_revision"]
        outcome.display_revision = status["display_revision"]
        outcome.latest_display_date = status["latest_display_date"]
        outcome.recalculated_fields = status["recalculated_fields"]
        outcome.recalculated = True
        outcome.display_refreshed = True

    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    config = build_tcp_ingest_config(cfg, paths, on_persisted=on_persisted)
    body = {
        "program": "TCP",
        "date": "2026-01-22",
        "stonex_nlv": 24000.0,  # lower performance day
        "cash_transfer": 0.0,
        "dry_run": False,
    }
    response, status = handle_ingest_request(config, _headers(), body, "t")
    assert status == 200
    assert response["persisted"] is True
    assert response["recalculated"] is True
    assert response["display_refreshed"] is True
    assert response["latest_display_date"] == "2026-01-22"

    snap = runtime["snapshot"]
    assert snap.canonical_nav[-1]["Date"] == "2026-01-22"
    assert snap.canonical_nav[-1]["NAV"] != before_nav
    prop = runtime["last_propagation"]
    assert prop.latest_date.isoformat() == "2026-01-22"
    assert prop.nav_point_count == len(snap.canonical_nav)
    assert not prop.monthly_calendar.empty
    assert not prop.daily_performance.empty
    assert not prop.drawdown_profile.empty


def test_tcp_recalculation_failure_leaves_persisted_row(tcp_env, monkeypatch):
    from tcp_state import load_state
    from tcp_uploader_ingest import build_tcp_ingest_config

    cfg, paths, _active = tcp_env

    def on_persisted(outcome, payload):
        raise RuntimeError("tcp recalc failed")

    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    config = build_tcp_ingest_config(cfg, paths, on_persisted=on_persisted)
    body = {
        "program": "TCP",
        "date": "2026-01-22",
        "stonex_nlv": 25200.0,
        "cash_transfer": 0.0,
        "dry_run": False,
    }
    response, status = handle_ingest_request(config, _headers(), body, "t")
    assert status == 200
    assert response["persisted"] is True
    assert response["recalculated"] is False
    assert response["display_refreshed"] is False
    assert load_state(paths).state["records"][-1]["Date"] == "2026-01-22"


# ── AGM ─────────────────────────────────────────────────────────────────────


def _load_mp_ts():
    import importlib.util

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "mp_ts_recalc",
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
    return mod, manual_path


def test_agm_manual_row_enters_accounting_before_derived_fields(mp_ts):
    mod, _path = mp_ts
    csv_latest = pd.Timestamp(mod.daily_balances_df["Date"].max()).normalize()
    new_date = (csv_latest + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    # Pick an NLV near the last CSV value so fee math stays in-range.
    last_nlv = float(mod.daily_balances_df.sort_values("Date").iloc[-1]["Net Worth"])
    ok, msg, table = mod.agm_add_manual_daily_row(new_date, last_nlv + 50.0, 0.0, 0.0)
    assert ok, msg
    assert table is not None
    latest = table.sort_values("Date").iloc[-1]
    assert pd.Timestamp(latest["Date"]) == pd.Timestamp(new_date)
    assert "client_net_value" in table.columns
    assert "accrued_unpaid_fees" in table.columns
    # Derived NAV frame must include the new date (not CSV-only).
    eq = mod._daily_equity_frame()
    assert pd.Timestamp(eq["Date"].max()) == pd.Timestamp(new_date)
    fig = mod.build_nav_figure()
    assert any(pd.Timestamp(new_date) == pd.Timestamp(x) for x in fig.data[0].x)
    status = mod.recalculate_agm_display_state_from_disk(authoritative_date=new_date)
    assert status["latest_display_date"] == new_date
    assert "nav_chart" in status["recalculated_fields"]


def test_agm_client_admin_charts_agree_after_recalc(mp_ts):
    mod, _path = mp_ts
    csv_latest = pd.Timestamp(mod.daily_balances_df["Date"].max()).normalize()
    new_date = (csv_latest + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    last_nlv = float(mod.daily_balances_df.sort_values("Date").iloc[-1]["Net Worth"])
    ok, msg, _ = mod.agm_add_manual_daily_row(new_date, last_nlv - 100.0, 0.0, 0.0)
    assert ok, msg
    client_nav = mod.build_nav_figure()
    dd = mod.build_drawdown_figure()
    assert len(client_nav.data[0].x) == len(dd.data[0].x)
    assert pd.Timestamp(client_nav.data[0].x[-1]) == pd.Timestamp(new_date)
    assert pd.Timestamp(dd.data[0].x[-1]) == pd.Timestamp(new_date)
    fee_fig = mod.build_agm_accrued_fees_figure()
    assert fee_fig.data  # rebuilt from live accounting, not startup CSV-only


# ── TKP ─────────────────────────────────────────────────────────────────────


def test_tkp_recalculation_uses_stonex_only(monkeypatch, tmp_path):
    import tkp_ts

    rows = [
        {
            "Date": "2026-07-14",
            "StoneX": "$82,000.00",
            "Plus500": "$10,000.00",
            "NAV": "$999,999.00",
            "Deposit": "",
            "#Day": "1",
            "_row_id": 1,
        },
        {
            "Date": "2026-07-15",
            "StoneX": "$81,000.00",
            "Plus500": "$99,999.00",
            "NAV": "$888,888.00",
            "Deposit": "",
            "#Day": "2",
            "_row_id": 2,
        },
    ]
    state_path = tmp_path / "daily_returns_secret_state.json"
    state_path.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(tkp_ts, "_secret_editor_state_path", lambda: str(state_path))

    status = tkp_ts.apply_tkp_recalculation(authoritative_date="2026-07-15")
    assert status["latest_display_date"] == "2026-07-15"
    canonical = tkp_ts._canonical_records_from_secret_rows(status["rows"])
    assert canonical[-1]["NAV"] == pytest.approx(81000.0)
    # Plus500 must not drive the performance series.
    assert canonical[-1]["NAV"] != 99999.0


def test_tkp_duplicate_ingest_idempotent(monkeypatch, tmp_path):
    import tkp_ts
    from tearsheet_uploader_ingest import IngestRejected

    rows = [
        {
            "Date": "2026-07-14",
            "StoneX": "$82,000.00",
            "Plus500": "",
            "NAV": "$82,000.00",
            "Deposit": "",
            "#Day": "1",
            "_row_id": 1,
            "HWM": "$82,000.00",
            "Loss Carry": "$0.00",
            "$PL": "$0.00",
            "Perc. Net": 0.0,
            "Cumm Perc. Net": 0.0,
            "Inc. Fee": "$0.00",
            "cumm fee": "$0.00",
        },
    ]
    # Need enough structure for _compute_new_row on append — use unchanged path.
    state_path = tmp_path / "daily_returns_secret_state.json"
    state_path.write_text(json.dumps(rows), encoding="utf-8")
    monkeypatch.setattr(tkp_ts, "_secret_editor_state_path", lambda: str(state_path))
    monkeypatch.setattr(tkp_ts, "secret_all_columns", list(rows[0].keys()))

    outcome1 = tkp_ts._uploader_ingest_apply(
        {"date": "2026-07-14", "stonex_nlv": 82000.0, "plus500_nlv": 0.0, "cash_transfer": 0.0},
        False,
    )
    assert outcome1.action == "unchanged"
    outcome2 = tkp_ts._uploader_ingest_apply(
        {"date": "2026-07-14", "stonex_nlv": 82000.0, "plus500_nlv": 0.0, "cash_transfer": 0.0},
        False,
    )
    assert outcome2.action == "unchanged"
    loaded = json.loads(state_path.read_text(encoding="utf-8"))
    assert len(loaded) == 1
