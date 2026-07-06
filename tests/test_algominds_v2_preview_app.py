"""Tests for Algominds v2 preview shell."""
from __future__ import annotations

import ast
import socket
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_preview_app as preview_app
from algominds_v2_account_state_paths import save_latest_snapshot_for_account
from algominds_v2_snapshots import AlgomindsV2FeeSnapshot

D = Decimal
REPO_ROOT = Path(__file__).resolve().parent.parent


def _port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _prop_snapshot() -> AlgomindsV2FeeSnapshot:
    return AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        prior_high_water_mark=D("44483.423270"),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        benchmark_base=D("30000"),
        account_slug="prop",
    )


def test_import_does_not_start_preview_server() -> None:
    assert not _port_listening(8311), "Port 8311 already in use before import"
    import importlib

    importlib.reload(preview_app)
    assert not _port_listening(8311), "Importing preview app must not start the server"


def test_create_app_does_not_bind_port(tmp_path: Path) -> None:
    assert not _port_listening(8311)
    preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    assert not _port_listening(8311)


def test_admin_layout_includes_account_overview_table(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert 'id="admin-account-overview"' in html_text
    assert "Admin Overview" in html_text


def test_admin_table_includes_prop_and_acct_60k(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert "Proprietary Aggregate" in html_text
    assert "60k Benchmark Account" in html_text
    assert "prop" in html_text
    assert "acct-60k" in html_text


def test_admin_rows_link_to_account_routes(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert 'href="/prop"' in html_text
    assert 'href="/acct-60k"' in html_text


def test_admin_table_shows_profile_settings_columns(tmp_path: Path) -> None:
    rows = preview_app.build_admin_account_rows(state_root=tmp_path)
    by_slug = {row.account_slug: row for row in rows}
    assert by_slug["prop"].number_of_units == 1
    assert by_slug["prop"].exchange_fee_tier == "non-member"
    assert by_slug["prop"].benchmark_base == D("30000")
    assert by_slug["acct-60k"].number_of_units == 2
    assert by_slug["acct-60k"].exchange_fee_tier == "member"
    assert by_slug["acct-60k"].benchmark_base == D("60000")


def test_after_fee_nlv_placeholder_when_no_snapshot(tmp_path: Path) -> None:
    html_text = preview_app.render_admin_page(state_root=tmp_path)
    assert "No snapshot yet" in html_text


def test_after_fee_nlv_shown_when_snapshot_exists(tmp_path: Path) -> None:
    save_latest_snapshot_for_account("prop", _prop_snapshot(), state_root=tmp_path)
    rows = preview_app.build_admin_account_rows(state_root=tmp_path)
    prop_row = next(row for row in rows if row.account_slug == "prop")
    assert prop_row.after_fee_nlv is not None
    assert abs(prop_row.after_fee_nlv - D("48794.960939")) < D("0.01")


def test_prop_detail_page_renders(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    response = app.server.test_client().get("/prop")
    assert response.status_code == 200
    assert b"Proprietary Aggregate" in response.data
    assert b"account_slug" in response.data


def test_acct_60k_detail_page_renders(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    response = app.server.test_client().get("/acct-60k")
    assert response.status_code == 200
    assert b"60k Benchmark Account" in response.data


def test_unknown_account_slug_returns_404(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    response = app.server.test_client().get("/client-unknown")
    assert response.status_code == 404
    assert b"Account not found" in response.data


def test_admin_route_returns_200(tmp_path: Path) -> None:
    app = preview_app.create_algominds_v2_preview_app(state_root=tmp_path)
    response = app.server.test_client().get("/admin")
    assert response.status_code == 200
    assert b"admin-account-overview" in response.data


def test_account_page_empty_snapshot_state(tmp_path: Path) -> None:
    html_text = preview_app.render_account_page("prop", state_root=tmp_path)
    assert "No preview snapshot saved for this account yet." in html_text


def test_forbidden_import_scan() -> None:
    source_path = Path(preview_app.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "openpyxl",
        "pandas",
        "tkp_ts",
        "tcp_ts",
        "mp_ts",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert node.module.split(".")[0] not in forbidden_roots


def test_no_workbook_reader_strings_in_source() -> None:
    source = Path(preview_app.__file__).read_text(encoding="utf-8").lower()
    assert "read_excel" not in source
    assert "openpyxl" not in source
