"""AGM (Momentum Pacer / mp_ts.py) Important Notice gate auth tests — parity with TCP/TKP."""
from __future__ import annotations

import pandas as pd
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


def test_agm_disclosure_describes_cta_only_not_cpo(agm_app):
    """Algominds Financial LLC is a CTA only — never describe it as a CPO."""
    import mp_ts

    layout = str(mp_ts.serve_layout())
    assert "Algominds Financial LLC — CTA" in layout
    assert "CPO" not in layout


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
    """Public/client-facing render carries no admin daily-entry controls at all:
    the obsolete summary-row data-entry panel and the bottom admin daily table
    section are both gone entirely (hotfix 2026-07-08)."""
    import mp_ts

    layout = mp_ts.serve_layout()
    assert _find_by_id(layout, "agm-admin-data-entry-container") is None
    assert _find_by_id(layout, "agm-admin-daily-table-container") is None
    layout_str = str(layout)
    for removed in ("agm-admin-daily-table-content", "Add Row", "Delete Last Row",
                    "Show Calculations"):
        assert removed not in layout_str, f"admin control leaked publicly: {removed}"


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
    from algominds_portal_registry import AGM_PORTAL_COLUMNS

    with agm_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[AGM_SESSION_KEY] = True
        response = client.get("/admin")
        assert response.status_code == 200
        assert b"Momentum Pacer" in response.data
        assert b"portal-account-registry" in response.data
        for column in AGM_PORTAL_COLUMNS:
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
    assert _find_by_id(container, "agm-accrued-fees-graph") is not None
    # The old monthly-resolution NLV chart is gone (daily NLV lives in the
    # auth-gated daily container instead).
    assert _find_by_id(container, "agm-nlv-graph") is None


def test_fee_charts_toggle_wired_to_access_mode(agm_app):
    matching = [
        cb
        for cb in agm_app.callback_map.values()
        if any(inp.get("id") == "access-mode" for inp in cb.get("inputs", []))
        and "agm-admin-fee-charts-container" in str(cb.get("output"))
    ]
    assert matching, "fee-charts container is not toggled by the access-mode store"


def test_fee_dollars_reconcile_against_workbook_detail_sheets():
    """The DAILY fee engine's crystallized month-end fees must still match the
    workbook per-month detail sheets to the cent (Apr 2026 Net Fees$
    $2,967.85; Jan 2026 $31.56 — cross-checked by hand, not fabricated)."""
    import mp_ts

    fees = {c["month"]: c["fee"] for c in mp_ts.daily_fee_accrual.crystallized}
    assert fees["2026-04"] == pytest.approx(2967.846349, abs=0.01)
    assert fees["2026-01"] == pytest.approx(31.56190398, abs=0.01)
    assert fees["2025-11"] == pytest.approx(3344.66, abs=0.01)
    assert fees["2026-02"] == pytest.approx(718.59, abs=0.01)


def test_accrued_fees_reset_only_on_evidenced_payments():
    """The daily accrued series drops to the remaining balance exactly on
    evidenced payment days (e.g. Feb's $718.59 left the account on 2026-03-27)
    and never resets on a fabricated date."""
    import mp_ts

    acc = mp_ts.daily_fee_accrual.daily.set_index("Date")
    # Mar 27: exact Net-Worth match payment of the Feb fee -> accrued drops to 0
    # (Mar itself is under the HWM, so no new accrual).
    assert acc.loc["2026-03-27", "accrued_total"] == pytest.approx(0.0, abs=0.01)
    day_before = acc.loc["2026-03-26", "accrued_total"]
    assert day_before == pytest.approx(718.59, abs=0.01)
    # Apr/May fees have no payment evidence -> still carried at the end.
    assert acc["accrued_total"].iloc[-1] >= 2967.0


def test_accrued_fees_never_negative():
    import mp_ts

    assert (mp_ts.daily_fee_accrual.daily["accrued_total"] >= -1e-9).all()


def test_public_nav_chart_is_daily_client_net_value(agm_app):
    """The client-facing equity curve is client net value (actual NLV minus
    accrued unpaid fees) from the daily accounting model."""
    import mp_ts
    import pandas as pd

    nav_fig = mp_ts.build_nav_figure()
    bot_trace = next(t for t in nav_fig.data if t.name == mp_ts.CLIENT_NAV_TRACE_NAME)
    expected = mp_ts.daily_accounting.table[
        mp_ts.daily_accounting.table["Date"] >= pd.Timestamp(mp_ts.PROGRAM_INCEPTION)
    ]
    assert len(bot_trace.y) == len(expected)
    assert [float(v) for v in bot_trace.y] == pytest.approx(
        [float(v) for v in expected["client_net_value"]]
    )
    assert any(t.name == "S&P 500 (rebased, daily)" for t in nav_fig.data)


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

DAILY_LATEST_NW = "45,335.28"  # latest daily Net Worth from the CSV (2026-07-06)


def test_daily_container_present_but_content_not_shipped_publicly(agm_app):
    """The daily container exists and is hidden by default; the sensitive raw-NLV
    content is NOT baked into the initial layout (it renders server-side only when
    authenticated), so a public browser never receives it. The bottom admin daily
    table container was removed entirely (hotfix 2026-07-08)."""
    import mp_ts

    layout = mp_ts.serve_layout()
    container = _find_by_id(layout, "agm-admin-daily-container")
    assert container is not None
    assert container.style == {"display": "none"}
    assert _find_by_id(layout, "agm-admin-daily-content") is not None
    assert _find_by_id(layout, "agm-admin-daily-table-container") is None
    assert _find_by_id(layout, "agm-admin-daily-table-content") is None
    layout_str = str(layout)
    assert DAILY_LATEST_NW not in layout_str
    assert "agm-daily-nlv-graph" not in layout_str


def test_client_view_has_no_raw_daily_nlv(agm_app):
    """Client-facing (public/standard) render must not expose raw TradeStation NLV."""
    import mp_ts

    with mp_ts.app.server.test_request_context("/"):
        assert mp_ts._render_admin_daily_content("standard") == []
        assert mp_ts._render_admin_daily_content("secret") == []


def test_admin_tearsheet_renders_raw_nlv_chart(agm_app):
    """In authenticated admin TearSheet mode, the NLV graph renders up top.
    The bottom daily accounting table section was removed (hotfix 2026-07-08)."""
    import mp_ts

    with mp_ts.app.server.test_request_context("/"):
        from flask import session as fsession
        fsession[AGM_SESSION_KEY] = True
        content = mp_ts._render_admin_daily_content("secret")
        assert content, "authenticated admin should get daily chart content"
        content_str = str(content)
        assert "agm-daily-nlv-graph" in content_str
        assert "Daily Balances" not in content_str
        assert "TradeStation Net Worth" in content_str
    assert not hasattr(mp_ts, "_render_admin_daily_table")


def test_daily_table_newest_date_at_top(agm_app):
    """The client Daily Returns table (the only remaining daily table) shows
    the latest date first."""
    import mp_ts

    rows = mp_ts.build_client_daily_table_rows(newest_first=True)
    assert rows, "client daily table rows should not be empty"
    assert rows[0]["Date"] == "2026-07-06"


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
    """Trimmed to live inception onward so it starts on the same date as
    the other 2 admin-verification charts -- values still come straight
    from the raw CSV Net Worth column, just not the pre-inception days."""
    import mp_ts

    fig = mp_ts.build_agm_daily_nlv_figure()
    inception_rows = mp_ts.daily_balances_df[
        mp_ts.daily_balances_df["Date"] >= pd.Timestamp(mp_ts.PROGRAM_INCEPTION)
    ]
    assert len(fig.data) == 1
    assert len(fig.data[0].x) == len(inception_rows)
    assert pd.Timestamp(fig.data[0].x[0]) == pd.Timestamp(mp_ts.PROGRAM_INCEPTION)
    assert float(fig.data[0].y[-1]) == pytest.approx(45335.28, abs=0.01)


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


def test_monthly_workbook_is_internal_backend_source_only(agm_app):
    """The monthly workbook stays alive as a BACKEND source (fee/accrual math,
    client performance figures) but is not a navigable website experience."""
    import mp_ts

    # Workbook file intact and still loaded internally.
    assert mp_ts.EXCEL_PATH.is_file()
    assert not mp_ts._display_summary_df.empty
    # It still feeds internal logic: the performance summary table and the
    # daily fee engine's payment-reconciliation evidence.
    assert any(p["method"] == "workbook-reconciliation"
               for p in mp_ts.daily_fee_accrual.payments)
    # The client performance view (investor NAV chart) is still served.
    layout = mp_ts.serve_layout()
    assert _find_by_id(layout, "mp-nav-graph") is not None


def test_monthly_route_not_exposed(agm_app):
    """/monthly is not a visible backup website — it returns a plain 404."""
    with agm_app.server.test_client() as client:
        response = client.get("/monthly", follow_redirects=False)
        assert response.status_code == 404


def test_no_monthly_backup_navigation_labels(agm_app):
    """No client- or admin-facing 'Monthly backup' tab/link/button exists."""
    import mp_ts

    layout_str = str(mp_ts.serve_layout())
    assert "Monthly backup" not in layout_str
    assert "/monthly" not in layout_str


def test_portal_is_account_registry_with_tearsheet_action(agm_app):
    """Portal = account/user registry (not a monthly view); the CSV-backed live
    account links to the current daily admin tearsheet."""
    from algominds_portal_registry import AGM_PORTAL_COLUMNS
    from tearsheet_portal import TEARSHEET_NOT_WIRED_TEXT

    with agm_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[AGM_SESSION_KEY] = True
        response = client.get("/admin")
        assert response.status_code == 200
        assert b"portal-account-registry" in response.data
        assert b"Tearsheet" in response.data
        assert b"Open tearsheet" in response.data
        assert TEARSHEET_NOT_WIRED_TEXT.encode("utf-8") in response.data
        # Portal carries no monthly-backup navigation.
        assert b"Monthly backup" not in response.data
        assert b"/monthly" not in response.data
        assert "Tearsheet" in AGM_PORTAL_COLUMNS
        assert "Status" not in AGM_PORTAL_COLUMNS


def test_portal_registry_lists_all_investors_with_account_numbers(agm_app):
    import algominds_portal_registry as agm_registry

    with agm_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[AGM_SESSION_KEY] = True
        response = client.get("/admin")
        html = response.data.decode("utf-8")
        assert response.status_code == 200
        for entry in agm_registry.INVESTOR_REGISTRY:
            # Names with "&" are HTML-escaped in the rendered table.
            assert entry["account"].replace("&", "&amp;") in html
            assert entry["account_number"] in html
        assert html.count("Open tearsheet") == 1
        assert "210TGG51" in html
        assert "Algominds" in html


def test_portal_registry_units_and_exchange_fee_tiers(agm_app):
    import algominds_portal_registry as agm_registry

    with agm_app.server.test_client() as client:
        with client.session_transaction() as sess:
            sess[AGM_SESSION_KEY] = True
        response = client.get("/admin")
        html = response.data.decode("utf-8")
        assert "Vishal Khemka" in html
        assert "210WHA83" in html
        # Fernando/Kal have 2 units.
        fernando_pos = html.index("Dr. Rajeev Fernando")
        kal_pos = html.index("Kaladhar Palaniappan")
        fernando_row = html[fernando_pos : fernando_pos + 400]
        kal_row = html[kal_pos : kal_pos + 400]
        assert ">2<" in fernando_row.split("Tearsheet")[0]
        assert ">2<" in kal_row.split("Tearsheet")[0]
        # Hughes is the sole Member exchange-fee row.
        assert html.count(">Member<") == 1
        assert html.count(">Non-Member<") == 12
        assert "Status" not in html


# ── Admin reconciliation panel (date-based spot-check) ──────────────────────

def test_three_admin_graphs_share_xaxis_configuration(agm_app):
    """Client Net Economic Value, Actual NLV, and Accrued Unpaid Fees charts
    must share the same visible date range and tick configuration so values
    on the same calendar date are easy to compare across the stacked charts."""
    import mp_ts

    client_fig = mp_ts.build_nav_figure()
    nlv_fig = mp_ts.build_agm_daily_nlv_figure()
    fees_fig = mp_ts.build_agm_accrued_fees_figure()

    ranges = {
        tuple(client_fig.layout.xaxis.range),
        tuple(nlv_fig.layout.xaxis.range),
        tuple(fees_fig.layout.xaxis.range),
    }
    assert len(ranges) == 1, f"x-axis ranges differ across the 3 admin graphs: {ranges}"

    dticks = {client_fig.layout.xaxis.dtick, nlv_fig.layout.xaxis.dtick, fees_fig.layout.xaxis.dtick}
    assert len(dticks) == 1
    formats = {
        client_fig.layout.xaxis.tickformat,
        nlv_fig.layout.xaxis.tickformat,
        fees_fig.layout.xaxis.tickformat,
    }
    assert len(formats) == 1

    # Same left/right margins so the plot areas line up vertically.
    for fig in (client_fig, nlv_fig, fees_fig):
        assert fig.layout.margin.l == mp_ts.ADMIN_XAXIS_MARGIN_LR["l"]
        assert fig.layout.margin.r == mp_ts.ADMIN_XAXIS_MARGIN_LR["r"]


def test_admin_nlv_chart_trimmed_to_inception_for_perfect_alignment(agm_app):
    """All 3 admin-verification charts now start on live inception (the NLV
    chart is trimmed from the full CSV, which also holds pre-inception
    flat-$30K days), so the shared x-axis range needs no left-side padding
    for a series that starts earlier -- true alignment, not just an
    overlapping window."""
    import mp_ts

    client_fig = mp_ts.build_nav_figure()
    nlv_fig = mp_ts.build_agm_daily_nlv_figure()
    fees_fig = mp_ts.build_agm_accrued_fees_figure()

    assert pd.Timestamp(client_fig.data[0].x[0]) == pd.Timestamp(mp_ts.PROGRAM_INCEPTION)
    assert pd.Timestamp(nlv_fig.data[0].x[0]) == pd.Timestamp(mp_ts.PROGRAM_INCEPTION)
    assert pd.Timestamp(fees_fig.data[0].x[0]) == pd.Timestamp(mp_ts.PROGRAM_INCEPTION)

    x_left, x_right = nlv_fig.layout.xaxis.range
    assert pd.Timestamp(x_left) <= pd.Timestamp(mp_ts.PROGRAM_INCEPTION)
    assert pd.Timestamp(x_right) >= pd.Timestamp(mp_ts.daily_balances_df["Date"].max())


def test_daily_balances_data_still_holds_pre_inception_days(agm_app):
    """Trimming the NLV CHART to inception must not trim the underlying daily
    balances data -- the full CSV history stays loaded."""
    import mp_ts

    assert pd.Timestamp("2025-10-20") in set(
        mp_ts.daily_balances_df["Date"]
    )  # first CSV row, pre-inception


def test_reconciliation_widget_present_in_admin_layout(agm_app):
    """The date picker and its output container exist in the admin
    fee-charts section, under the 3 graphs."""
    import mp_ts

    layout = mp_ts.serve_layout()
    container = _find_by_id(layout, "agm-admin-fee-charts-container")
    assert container is not None
    picker = _find_by_id(container, mp_ts.AGM_RECON_DATE_PICKER_ID)
    assert picker is not None
    assert _find_by_id(container, mp_ts.AGM_RECON_OUTPUT_ID) is not None


def test_reconciliation_widget_defaults_to_latest_available_date(agm_app):
    import mp_ts

    layout = mp_ts.serve_layout()
    picker = _find_by_id(layout, mp_ts.AGM_RECON_DATE_PICKER_ID)
    latest = mp_ts.daily_accounting.table["Date"].max()
    assert str(picker.date) == latest.strftime("%Y-%m-%d")
    assert str(picker.max_date_allowed) == latest.strftime("%Y-%m-%d")


def test_reconciliation_panel_displays_required_fields():
    import mp_ts

    panel_str = str(mp_ts.build_agm_reconciliation_panel(None))
    assert "TradeStation NLV / Actual NLV" in panel_str
    assert "Client Net Economic Value" in panel_str
    assert "Accrued Unpaid Incentive Fee" in panel_str
    assert "Date" in panel_str
    # Reconciliation status is present (checkmark or warning glyph).
    assert "✓" in panel_str or "⚠" in panel_str


def test_reconciliation_formula_matches_exact_math():
    """Exact math string, e.g. 'TradeStation NLV ($45,675.81) = Client Net
    Economic Value ($42,327.59) + Accrued Unpaid Incentive Fee ($3,348.22) ✓'."""
    import mp_ts

    result = mp_ts._agm_reconciliation_lookup("2026-07-01")
    panel_str = str(mp_ts.build_agm_reconciliation_panel("2026-07-01"))
    expected_fragment = (
        f"TradeStation NLV (${result['actual_nlv']:,.2f}) = "
        f"Client Net Economic Value (${result['client_net_value']:,.2f}) + "
        f"Accrued Unpaid Incentive Fee (${result['accrued_unpaid_fees']:,.2f})"
    )
    assert expected_fragment in panel_str
    assert "45,675.81" in panel_str


def test_reconciliation_verifies_formula_within_tolerance():
    """TradeStation NLV = Client Net Economic Value + Accrued Unpaid
    Incentive Fee within RECONCILIATION_TOLERANCE, for every date in the
    accepted daily accounting table."""
    import mp_ts

    for _, row in mp_ts.daily_accounting.table.iterrows():
        residual = float(row["actual_nlv"]) - (
            float(row["client_net_value"]) + float(row["accrued_unpaid_fees"])
        )
        assert abs(residual) <= mp_ts.RECONCILIATION_TOLERANCE

    result = mp_ts._agm_reconciliation_lookup(None)
    assert result["within_tolerance"] is True
    assert result["residual"] == pytest.approx(0.0, abs=mp_ts.RECONCILIATION_TOLERANCE)


def test_reconciliation_selected_date_values_come_from_accounting_table():
    import mp_ts

    result = mp_ts._agm_reconciliation_lookup("2026-04-30")
    row = mp_ts.daily_accounting.table.set_index("Date").loc[pd.Timestamp("2026-04-30")]
    assert result["actual_nlv"] == pytest.approx(float(row["actual_nlv"]))
    assert result["client_net_value"] == pytest.approx(float(row["client_net_value"]))
    assert result["accrued_unpaid_fees"] == pytest.approx(float(row["accrued_unpaid_fees"]))


def test_reconciliation_handles_unavailable_date_gracefully():
    """A non-trading date (e.g. weekend) falls back to the nearest prior
    trading day rather than crashing or fabricating a row."""
    import mp_ts

    result = mp_ts._agm_reconciliation_lookup("2026-06-28")  # a Sunday
    assert result["available"] is True
    assert result["exact_match"] is False
    assert result["row_date"] < pd.Timestamp("2026-06-28")

    before_history = mp_ts._agm_reconciliation_lookup("2020-01-01")
    assert before_history["available"] is False
    assert "reason" in before_history

    invalid = mp_ts._agm_reconciliation_lookup("not-a-real-date")
    assert invalid["available"] is False


def test_reconciliation_panel_admin_only_via_callback(agm_app):
    import mp_ts

    # access-mode alone is not enough -- spoofed 'secret' with no real session
    # yields nothing (checked outside a request context, matching how
    # is_authenticated() would see no session at all).
    with mp_ts.app.server.test_request_context("/"):
        assert mp_ts._render_agm_reconciliation_panel("2026-07-01", "standard") == []
        assert mp_ts._render_agm_reconciliation_panel("2026-07-01", None) == []
        assert mp_ts._render_agm_reconciliation_panel("2026-07-01", "secret") == []

        from flask import session as fsession
        fsession[AGM_SESSION_KEY] = True
        content = mp_ts._render_agm_reconciliation_panel("2026-07-06", "secret")
        assert content, "authenticated admin should get reconciliation content"
        assert DAILY_LATEST_NW in str(content)  # latest CSV date
        assert "TradeStation NLV / Actual NLV" in str(content)


def test_public_layout_does_not_expose_reconciliation_values(agm_app):
    """The reconciliation output container exists (Dash needs it registered)
    but is empty in the initial public layout -- values only ever render via
    the auth-gated callback. The static instructional copy in the panel's
    label/caption text is fine to ship publicly; only the computed dollar
    figures for a specific date must never leak."""
    import mp_ts

    layout = mp_ts.serve_layout()
    output_div = _find_by_id(layout, mp_ts.AGM_RECON_OUTPUT_ID)
    assert output_div is not None
    assert not getattr(output_div, "children", None)
    layout_str = str(layout)
    result = mp_ts._agm_reconciliation_lookup(None)
    assert f"{result['actual_nlv']:,.2f}" not in layout_str
    assert f"{result['client_net_value']:,.2f}" not in layout_str
    assert f"{result['accrued_unpaid_fees']:,.2f}" not in layout_str


def test_reconciliation_isolated_from_tkp_and_tcp():
    import tkp_ts
    import tcp_ts_v2

    assert not hasattr(tkp_ts, "build_agm_reconciliation_panel")
    assert not hasattr(tcp_ts_v2, "build_agm_reconciliation_panel")


# ── Client-facing daily table (collapsed by default) ─────────────────────────

CLIENT_TABLE_REQUIRED_COLUMNS = [
    "Date",
    "Client Net Economic Value",
    "TradeStation NLV / Statement Value",
    "Accrued Unpaid Incentive Fee",
    "Daily $",
    "Daily %",
    "Since inception %",
    "SPX Close",
    "SPX daily %",
    "Momentum daily %",
    "Momentum vs SPX daily spread %",
    "Fee payment",
]


def test_client_daily_table_section_exists_in_public_layout(agm_app):
    import mp_ts

    layout = mp_ts.serve_layout()
    collapse = _find_by_id(layout, mp_ts.CLIENT_DAILY_COLLAPSE_ID)
    assert collapse is not None
    assert _find_by_id(layout, mp_ts.CLIENT_DAILY_TABLE_ID) is not None
    assert _find_by_id(layout, mp_ts.CLIENT_DAILY_TOGGLE_ID) is not None
    assert "Daily Returns" in str(layout)


def test_client_daily_table_collapsed_by_default(agm_app):
    import mp_ts

    layout = mp_ts.serve_layout()
    collapse = _find_by_id(layout, mp_ts.CLIENT_DAILY_COLLAPSE_ID)
    assert collapse.is_open is False
    toggle_btn = _find_by_id(layout, mp_ts.CLIENT_DAILY_TOGGLE_ID)
    assert "Show" in str(toggle_btn.children)


def test_client_daily_table_toggle_shows_and_hides(agm_app):
    import mp_ts

    is_open, label = mp_ts._toggle_client_daily_table(1, False)
    assert is_open is True
    assert "Hide" in label
    is_open2, label2 = mp_ts._toggle_client_daily_table(2, True)
    assert is_open2 is False
    assert "Show" in label2


def test_client_daily_table_has_required_columns(agm_app):
    import mp_ts

    layout_str = str(mp_ts.serve_layout())
    for label in CLIENT_TABLE_REQUIRED_COLUMNS:
        assert label in layout_str, f"missing client daily table column: {label}"

    col_ids = {c["id"] for c in mp_ts._build_client_daily_table_columns()}
    assert col_ids == {
        "Date", "client_net_value", "actual_nlv", "accrued_unpaid_fees",
        "daily_dollar", "daily_pct", "since_inception_pct", "spx_close",
        "spx_daily_pct", "momentum_daily_pct", "momentum_vs_spx_daily_spread_pct",
        "fee_payment",
    }


def test_client_daily_table_rows_from_accepted_accounting_model(agm_app):
    import mp_ts

    rows = mp_ts.build_client_daily_table_rows(newest_first=True)
    inception_tbl = mp_ts.daily_accounting.table[
        mp_ts.daily_accounting.table["Date"] >= pd.Timestamp(mp_ts.PROGRAM_INCEPTION)
    ]
    assert len(rows) == len(inception_tbl)
    assert rows[0]["Date"] == inception_tbl["Date"].max().strftime("%Y-%m-%d")
    latest_row = inception_tbl.sort_values("Date").iloc[-1]
    assert rows[0]["client_net_value"] == pytest.approx(float(latest_row["client_net_value"]))
    assert rows[0]["actual_nlv"] == pytest.approx(float(latest_row["actual_nlv"]))
    assert rows[0]["accrued_unpaid_fees"] == pytest.approx(float(latest_row["accrued_unpaid_fees"]))


def test_client_daily_table_invariant_holds_on_rendered_rows(agm_app):
    """actual_nlv = client_net_value + accrued_unpaid_fees on every row shown
    in the client-facing table."""
    import mp_ts

    for row in mp_ts.build_client_daily_table_rows():
        residual = row["actual_nlv"] - (row["client_net_value"] + row["accrued_unpaid_fees"])
        assert abs(residual) <= mp_ts.RECONCILIATION_TOLERANCE


def test_client_daily_table_does_not_expose_admin_only_content(agm_app):
    """The client table must not carry admin-only operational columns or the
    admin-only component ids/callback content."""
    import mp_ts

    layout_str = str(mp_ts.serve_layout())
    col_ids = {c["id"] for c in mp_ts._build_client_daily_table_columns()}
    for admin_only in ("Cash Balance", "Initial Margin Req.", "Maint Margin Req.",
                       "Buying Power/Margin Deficit"):
        assert admin_only not in col_ids
    # Admin-only components are distinct ids, never reused by the client table.
    assert mp_ts.CLIENT_DAILY_TABLE_ID != "agm-admin-daily-table-content"
    assert "agm-admin-daily-table-content" not in str(
        _find_by_id(mp_ts.serve_layout(), mp_ts.CLIENT_DAILY_TABLE_ID)
    )


def test_client_daily_table_isolated_from_tkp_and_tcp():
    import tkp_ts
    import tcp_ts_v2

    assert not hasattr(tkp_ts, "build_client_daily_table_section")
    assert not hasattr(tcp_ts_v2, "build_client_daily_table_section")


def test_agm_accounting_invariant_unaffected_by_ui_changes():
    """Sanity check: this session's UI-only changes never touch the
    accepted accounting model / fee formula."""
    import mp_ts
    import algominds_daily_accounting as ada

    assert ada.verify_accounting_invariant(mp_ts.daily_accounting.table)


# ── Obsolete summary-row entry form fully removed ────────────────────────────

def test_obsolete_summary_row_form_removed_everywhere(agm_app):
    """'Add a new Summary row' and its SPX/NDX/BOT inputs are gone from the
    layout entirely."""
    import mp_ts

    layout_str = str(mp_ts.serve_layout())
    for banned in ("Add a new Summary row", "No manually-entered rows yet"):
        assert banned not in layout_str
    for obsolete_id in (
        "agm-add-date", "agm-add-spx-start", "agm-add-spx-end",
        "agm-add-ndx-start", "agm-add-ndx-end", "agm-add-bot-start",
        "agm-add-bot-end", "agm-add-row-save-btn", "agm-pending-rows-table",
        "agm-admin-data-entry-container",
    ):
        assert obsolete_id not in layout_str, f"obsolete component still shipped: {obsolete_id}"


def test_obsolete_summary_row_callbacks_gone(agm_app):
    for key, cb in agm_app.callback_map.items():
        blob = key + str(cb.get("inputs", [])) + str(cb.get("state", []))
        assert "agm-add-row-save-btn" not in blob
        assert "agm-pending-rows-table" not in blob
        assert "agm-add-spx-start" not in blob


# ── Hotfix 2026-07-08: bottom admin daily table section removed entirely ─────

def test_admin_bottom_daily_table_section_removed(agm_app):
    """Everything below and including the bottom admin daily accounting /
    Daily Returns section is gone: the admin page now ends at the Important
    Disclosure panel."""
    import mp_ts

    layout = mp_ts.serve_layout()
    assert _find_by_id(layout, "agm-admin-daily-table-container") is None
    assert _find_by_id(layout, "agm-admin-daily-table-content") is None
    assert _find_by_id(layout, "agm-admin-data-entry-container") is None
    # The Important Disclosure panel is the LAST element of the main app.
    main_app = _find_by_id(layout, "main-app")
    last_child = main_app.children[-1]
    assert _find_by_id(last_child, "important-disclosure") is not None
    # No layout or callback references to the removed section remain.
    layout_str = str(layout)
    assert "daily accounting detail" not in layout_str
    for key, cb in agm_app.callback_map.items():
        blob = key + str(cb.get("output", "")) + str(cb.get("inputs", []))
        assert "agm-admin-daily-table-container" not in blob
        assert "agm-admin-daily-table-content" not in blob
    # The removed feature's code is gone from the module too.
    for name in (
        "build_agm_admin_daily_returns_section",
        "build_agm_admin_daily_table_rows",
        "build_agm_show_calculations_body",
        "agm_add_manual_daily_row",
        "agm_delete_last_manual_daily_row",
        "_render_admin_daily_table",
        "ADMIN_DAILY_CONTROL_IDS",
    ):
        assert not hasattr(mp_ts, name), f"removed feature still present: {name}"


def test_upper_admin_sections_survive_hotfix(agm_app):
    """The hotfix must not touch anything above the removed section: NLV
    chart/KPIs, fee-accrual chart, and the reconciliation panel all remain."""
    import mp_ts

    layout = mp_ts.serve_layout()
    assert _find_by_id(layout, "agm-admin-daily-container") is not None
    assert _find_by_id(layout, "agm-admin-fee-charts-container") is not None
    assert _find_by_id(layout, mp_ts.AGM_RECON_DATE_PICKER_ID) is not None
    assert _find_by_id(layout, mp_ts.CLIENT_DAILY_TABLE_ID) is not None
    with mp_ts.app.server.test_request_context("/"):
        from flask import session as fsession
        fsession[AGM_SESSION_KEY] = True
        assert mp_ts._render_admin_daily_content("secret")
        recon = mp_ts._render_agm_reconciliation_panel("2026-07-06", "secret")
        assert recon and DAILY_LATEST_NW in str(recon)
