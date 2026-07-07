"""AGM (Momentum Pacer / mp_ts.py) Important Notice gate auth tests — parity with TCP/TKP."""
from __future__ import annotations

import pytest

from tearsheet_gate_auth import (
    ADMIN_DAILY_ENTRY_PATH,
    ADMIN_PORTAL_PATH,
    AGM_SESSION_KEY,
    GATE_PASSWORD_INPUT_ID,
    GATE_PASSWORD_PORTAL_ID,
    GATE_PASSWORD_ROW_ID,
    GATE_PASSWORD_SUBMIT_ID,
    GATE_PASSWORD_TEARSHEET_LABEL,
    GATE_PASSWORD_PORTAL_LABEL,
    GATE_PASSWORD_VISIBLE_STORE_ID,
    INVALID_PASSWORD_MESSAGE,
    gate_password_row_style,
    load_agm_admin_auth_settings,
)
from tcp_admin import AdminAuthManager
from tearsheet_portal import PORTAL_COLUMNS

TEST_TOKEN = "test-runtime-admin-token"  # matches tests/conftest.py AGM_ADMIN_TOKEN


@pytest.fixture
def agm_app():
    import mp_ts

    return mp_ts.app


def test_admin_route_constants():
    assert ADMIN_DAILY_ENTRY_PATH == "/"
    assert ADMIN_PORTAL_PATH == "/admin"


def test_gate_renders_important_notice_and_hidden_trigger(agm_app):
    import mp_ts

    layout = str(mp_ts.serve_layout())
    assert "Important Notic" in layout
    assert layout.count("secret-notice-e") >= 1


def test_accept_and_continue_present(agm_app):
    import mp_ts

    layout = str(mp_ts.serve_layout())
    assert "Accept & Continue" in layout


def test_gate_renders_tearsheet_and_portal_buttons(agm_app):
    import mp_ts

    layout = str(mp_ts.serve_layout())
    assert GATE_PASSWORD_ROW_ID in layout
    assert GATE_PASSWORD_SUBMIT_ID in layout
    assert GATE_PASSWORD_PORTAL_ID in layout
    assert GATE_PASSWORD_TEARSHEET_LABEL in layout
    assert GATE_PASSWORD_PORTAL_LABEL in layout


def test_password_row_initially_hidden():
    hidden_style = str(gate_password_row_style(False))
    assert "'display': 'none'" in hidden_style or '"display": "none"' in hidden_style


def _find_by_id(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component
    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]
    for child in children:
        found = _find_by_id(child, target_id)
        if found is not None:
            return found
    return None


def test_client_mode_has_no_admin_controls_by_default(agm_app):
    """Public/client-facing render must not show the admin data-entry panel."""
    import mp_ts

    layout = mp_ts.serve_layout()
    # The container exists in the DOM (Dash needs it registered) but must be display:none by default,
    # since access-mode starts at None (public/client mode) until a TearSheet login succeeds.
    container = _find_by_id(layout, "agm-admin-data-entry-container")
    assert container is not None, "admin data-entry container not found in layout"
    assert container.style == {"display": "none"}


def test_e_click_reveals_row_without_authenticating(agm_app):
    auth = AdminAuthManager(load_agm_admin_auth_settings(), session_key=AGM_SESSION_KEY)
    assert not auth.is_authenticated({})
    assert any(
        GATE_PASSWORD_VISIBLE_STORE_ID in str(cb.get("output", ""))
        and any(inp.get("id") == "secret-notice-e" for inp in cb.get("inputs", []))
        for cb in agm_app.callback_map.values()
    )


def test_enter_key_wired_to_tearsheet_not_portal(agm_app):
    tearsheet_callbacks = [
        cb
        for cb in agm_app.callback_map.values()
        if any(inp.get("id") == GATE_PASSWORD_SUBMIT_ID for inp in cb.get("inputs", []))
    ]
    portal_callbacks = [
        cb
        for cb in agm_app.callback_map.values()
        if any(inp.get("id") == GATE_PASSWORD_PORTAL_ID for inp in cb.get("inputs", []))
    ]
    assert tearsheet_callbacks, "TearSheet submit callback not registered"
    assert portal_callbacks, "Portal callback not registered"
    assert any(
        inp.get("id") == GATE_PASSWORD_INPUT_ID and inp.get("property") == "n_submit"
        for cb in tearsheet_callbacks
        for inp in cb.get("inputs", [])
    ), "Enter key (n_submit) must trigger the TearSheet callback"
    assert not any(
        inp.get("id") == GATE_PASSWORD_INPUT_ID and inp.get("property") == "n_submit"
        for cb in portal_callbacks
        for inp in cb.get("inputs", [])
    ), "Enter key must not trigger the Portal callback"


def test_wrong_password_message_constant():
    auth = AdminAuthManager(load_agm_admin_auth_settings(), session_key=AGM_SESSION_KEY)
    ok, msg = auth.login({}, "definitely-wrong-password")
    assert not ok
    assert msg == INVALID_PASSWORD_MESSAGE


def test_empty_password_blocked():
    auth = AdminAuthManager(load_agm_admin_auth_settings(), session_key=AGM_SESSION_KEY)
    ok, _msg = auth.login({}, "")
    assert not ok


def test_correct_password_authenticates():
    auth = AdminAuthManager(load_agm_admin_auth_settings(), session_key=AGM_SESSION_KEY)
    session: dict = {}
    ok, _msg = auth.login(session, TEST_TOKEN)
    assert ok
    assert auth.is_authenticated(session)


def test_admin_portal_requires_auth(agm_app):
    with agm_app.server.test_client() as client:
        response = client.get("/admin", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")


def test_valid_tearsheet_auth_reaches_editable_mode(agm_app):
    """Valid TearSheet auth (simulated via server-side login) must be reflected in
    the auth manager the admin data-entry callback checks -- the actual reveal is
    driven client-side by the access-mode store once _gate_admin_tearsheet_login
    succeeds."""
    import mp_ts

    session: dict = {}
    ok, _msg = mp_ts.agm_admin_auth_manager.login(session, TEST_TOKEN)
    assert ok
    assert mp_ts.agm_admin_auth_manager.is_authenticated(session)


def test_admin_portal_returns_200_when_authenticated_with_participating_accounts(agm_app):
    with agm_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[AGM_SESSION_KEY] = True
        response = client.get("/admin")
        assert response.status_code == 200
        assert b"Momentum Pacer" in response.data
        assert b"portal-account-registry" in response.data
        for column in PORTAL_COLUMNS:
            assert column.encode("utf-8") in response.data
        # AGM has a real participating account -> not the Pending empty state.
        assert b"Pending" not in response.data


def test_admin_logout_clears_session(agm_app):
    with agm_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[AGM_SESSION_KEY] = True
        client.get("/admin/logout")
        response = client.get("/admin", follow_redirects=False)
        assert response.status_code == 302


def test_healthz_is_real_json(agm_app):
    with agm_app.server.test_client() as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload is not None
        assert payload["app"] == "algominds-momentum-pacer"


def test_runtime_token_not_in_layout(agm_app):
    import mp_ts

    layout = str(mp_ts.serve_layout())
    assert TEST_TOKEN not in layout


# ── Admin-only Accrued Fees / NLV charts (AGM only) ─────────────────────────

def test_fee_charts_container_present_but_hidden_by_default(agm_app):
    import mp_ts

    layout = mp_ts.serve_layout()
    container = _find_by_id(layout, "agm-admin-fee-charts-container")
    assert container is not None
    assert container.style == {"display": "none"}
    graph_ids = {"agm-accrued-fees-graph", "agm-nlv-graph"}
    found_ids = {
        getattr(g, "id", None)
        for g in [_find_by_id(container, gid) for gid in graph_ids]
        if g is not None
    }
    assert found_ids == graph_ids


def test_fee_charts_toggle_wired_to_access_mode(agm_app):
    matching = [
        cb
        for cb in agm_app.callback_map.values()
        if any(inp.get("id") == "access-mode" for inp in cb.get("inputs", []))
        and "agm-admin-fee-charts-container" in str(cb.get("output"))
    ]
    assert matching, "fee-charts container is not toggled by the access-mode store"


def test_fee_dollars_reconciles_against_workbook_detail_sheets():
    """Cross-checked by hand against the 'Apr 2026' and 'Jan 2026' per-month
    detail sheets in Momentum Fee Calculation.xlsx (Net Fees$ / BOT Closing
    before fees), not fabricated."""
    import mp_ts

    rows = mp_ts._compute_agm_fee_series(mp_ts._display_summary_df)
    by_month = {r["date"].strftime("%Y-%m"): r for r in rows}

    apr = by_month["2026-04"]
    assert apr["fee_dollars"] == pytest.approx(2967.846349, abs=0.01)
    assert apr["nlv_before_fees"] == pytest.approx(47451.27, abs=0.01)
    assert apr["nlv_after_fees"] == pytest.approx(44483.42, abs=0.01)

    jan = by_month["2026-01"]
    assert jan["fee_dollars"] == pytest.approx(31.56190398, abs=0.01)
    assert jan["nlv_before_fees"] == pytest.approx(34654.12, abs=0.05)


def test_accrued_fees_resets_to_zero_after_each_payment():
    """Accounting invariant: accrued_fees_after_payment == 0 for every month."""
    import mp_ts

    fig = mp_ts.build_agm_accrued_fees_figure()
    y = list(fig.data[0].y)
    # Every third point in the (start, month-end-peak, reset) triad must be 0.
    resets = y[2::3]
    assert all(v == 0 for v in resets)


def test_nlv_drops_by_exactly_the_paid_fee_amount():
    """Accounting invariant: actual_nlv_after_payment == actual_nlv_before_payment - fee_paid."""
    import mp_ts

    rows = mp_ts._compute_agm_fee_series(mp_ts._display_summary_df)
    for row in rows:
        drop = row["nlv_before_fees"] - row["nlv_after_fees"]
        assert drop == pytest.approx(row["fee_dollars"], abs=1e-6)


def test_public_nav_chart_unaffected_by_fee_charts(agm_app):
    """The client-facing equity curve must still be built only from
    bot_end_after_fees values (never pre-fee values) -- no extra
    fee-payment-only hit layered on top by this session's changes.

    Note: build_nav_figure() pre-existingly omits the second-to-last month's
    point when the latest month is in progress (cosmetic tick-spacing fix,
    unrelated to fees -- see its "avoids two points 1 day apart" comment), so
    this doesn't assert every month appears, only that nothing pre-fee does."""
    import mp_ts

    nav_fig = mp_ts.build_nav_figure()
    bot_trace = next(t for t in nav_fig.data if t.name == "Momentum Pacer (Net of Fees)")
    rows = mp_ts._compute_agm_fee_series(mp_ts._display_summary_df)
    starting_capital = mp_ts.STARTING_CAPITAL

    after_fees_values = {round(v, 2) for v in mp_ts._display_summary_df["bot_end_after_fees"]}
    before_fees_values = {round(r["nlv_before_fees"], 2) for r in rows if r["fee_dollars"] > 0}
    nav_values = {round(v, 2) for v in bot_trace.y if v is not None}

    # Every point actually plotted is either the starting capital or a genuine after-fee value.
    assert nav_values.issubset(after_fees_values | {starting_capital})
    # No pre-fee (before-payment) value ever leaks onto the public chart.
    assert nav_values.isdisjoint(before_fees_values)


def test_fee_charts_isolated_from_tkp_and_tcp():
    """AGM-only feature -- must not leak into TKP or TCP."""
    import tkp_ts
    import tcp_ts_v2

    assert not hasattr(tkp_ts, "build_agm_accrued_fees_figure")
    assert not hasattr(tcp_ts_v2, "build_agm_accrued_fees_figure")
    tkp_layout = str(tkp_ts.dynamic_layout())
    assert "agm-admin-fee-charts-container" not in tkp_layout
    assert "Accrued Fees" not in tkp_layout


# ── Admin-only DAILY TradeStation balances view (raw NLV, AGM only) ──────────

DAILY_LATEST_NW = "45,675.81"  # latest daily Net Worth from the CSV (2026-07-01)


def test_daily_container_present_but_content_not_shipped_publicly(agm_app):
    """The daily container exists and is hidden by default; the sensitive raw-NLV
    content is NOT baked into the initial layout (it renders server-side only when
    authenticated), so a public browser never receives it."""
    import mp_ts

    layout = mp_ts.serve_layout()
    container = _find_by_id(layout, "agm-admin-daily-container")
    assert container is not None
    assert container.style == {"display": "none"}
    # Placeholder present, but no raw NLV value and no daily graph in the shipped layout.
    assert _find_by_id(layout, "agm-admin-daily-content") is not None
    layout_str = str(layout)
    assert DAILY_LATEST_NW not in layout_str
    assert "agm-daily-nlv-graph" not in layout_str


def test_client_view_has_no_raw_daily_nlv(agm_app):
    """Client-facing (public/standard) render must not expose raw TradeStation NLV."""
    import mp_ts

    with mp_ts.app.server.test_request_context("/"):
        # No admin session -> public. Even a spoofed 'secret' store yields nothing.
        assert mp_ts._render_admin_daily_content("standard") == []
        assert mp_ts._render_admin_daily_content("secret") == []


def test_admin_tearsheet_renders_daily_table_and_raw_nlv(agm_app):
    """In authenticated admin TearSheet mode, the daily table + raw NLV graph render."""
    import mp_ts

    with mp_ts.app.server.test_request_context("/"):
        from flask import session as fsession
        fsession[AGM_SESSION_KEY] = True
        content = mp_ts._render_admin_daily_content("secret")
        assert content, "authenticated admin should get daily content"
        content_str = str(content)
        assert "agm-daily-nlv-graph" in content_str
        assert "Daily Balances" in content_str
        assert DAILY_LATEST_NW in content_str
        assert "TradeStation Net Worth" in content_str


def test_daily_table_columns_match_spec(agm_app):
    import mp_ts

    table = mp_ts.build_agm_daily_balances_table()
    table_str = str(table)
    for col in ["Date", "Net Worth", "Cash Balance", "Unrealized P/L",
                "Initial Margin Req.", "Maint Margin Req.",
                "Buying Power/Margin Deficit", "Daily $", "Daily %", "Since inception %"]:
        assert col in table_str, f"missing daily table column: {col}"


def test_daily_table_newest_date_at_top(agm_app):
    import mp_ts

    table = mp_ts.build_agm_daily_balances_table()
    # tbody first data row should be the latest date (2026-07-01).
    tbody = table.children[1]
    first_row = tbody.children[0]
    first_cell = first_row.children[0]
    assert first_cell.children == "2026-07-01"


def test_portal_uses_latest_daily_net_worth(agm_app):
    """Portal (admin-only) current value must come from the daily CSV, not the
    monthly workbook."""
    with agm_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[AGM_SESSION_KEY] = True
        response = client.get("/admin")
        assert response.status_code == 200
        assert DAILY_LATEST_NW.encode("utf-8") in response.data
        # The old monthly workbook after-fee value must no longer be the shown NLV.
        assert b"44,895.63" not in response.data


def test_daily_nlv_graph_uses_csv_net_worth(agm_app):
    import mp_ts

    fig = mp_ts.build_agm_daily_nlv_figure()
    assert len(fig.data) == 1
    assert len(fig.data[0].x) == len(mp_ts.daily_balances_df)
    assert float(fig.data[0].y[-1]) == pytest.approx(45675.81, abs=0.01)


def test_daily_logic_isolated_from_tkp_and_tcp():
    """AGM daily CSV logic must not be imported or rendered by TKP or TCP."""
    import tkp_ts
    import tcp_ts_v2

    assert not hasattr(tkp_ts, "daily_balances_df")
    assert not hasattr(tcp_ts_v2, "daily_balances_df")
    assert not hasattr(tkp_ts, "build_agm_daily_nlv_figure")
    assert not hasattr(tcp_ts_v2, "build_agm_daily_nlv_figure")
    tkp_layout = str(tkp_ts.dynamic_layout())
    assert "agm-admin-daily-container" not in tkp_layout
    assert "TradeStation Net Worth" not in tkp_layout


def test_monthly_backup_view_preserved(agm_app):
    """The monthly performance view (client-facing) and its NAV chart remain intact
    -- the monthly workbook stays as fee-calc source + backup."""
    import mp_ts

    layout = mp_ts.serve_layout()
    # The client performance NAV chart is still present.
    assert _find_by_id(layout, "mp-nav-graph") is not None
    # Monthly workbook is still the fee source (accrued-fees chart still monthly).
    assert not mp_ts._display_summary_df.empty


def test_monthly_backup_route_available(agm_app):
    """/monthly is a stable Monthly-backup entry point (currently redirects to the
    monthly client view at "/"), guaranteed to survive a later daily-first default."""
    with agm_app.server.test_client() as client:
        response = client.get("/monthly", follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/")
