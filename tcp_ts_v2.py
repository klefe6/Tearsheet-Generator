"""
TCP v2 preview shell (port 8312).

Does not import tcp_ts.py or tkp_ts.py. Does not write Excel.
Server starts only under if __name__ == "__main__".
"""
from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import dash
import dash_bootstrap_components as dbc
import pandas as pd
from dash import Input, Output, State, dcc, html, no_update
from flask import jsonify, redirect, render_template_string, request, session

from tcp_admin import (
    DELETE_CONFIRM_MESSAGE,
    DELETE_PERSIST_MESSAGE,
    LOGIN_FORM_HTML,
    AdminAuthManager,
    build_admin_editor_layout,
    configure_flask_session_secret,
    datatable_column_defs,
    default_add_row_values,
    delete_preview_content,
    ledger_records_to_rows,
    ledger_table_style_conditional,
    proposed_row_table,
    simulate_add_row,
    simulate_delete_last_row,
)
from tcp_config import AdminAuthSettings, TCPConfig, load_admin_auth_settings, load_config, resolve_state_paths, validate_config
from tcp_benchmarks import (
    BENCHMARK_STATUS_STALE,
    BENCHMARK_STATUS_UNAVAILABLE,
    BenchmarkResult,
    DEFAULT_CACHE_FILENAME,
    benchmark_status_message,
    load_spxtr_benchmark,
)
from tcp_dashboard import (
    GREY_BG,
    propagate_tcp_dashboard,
)
from tcp_ledger import TCPLedgerError
from tcp_runtime_state import (
    RuntimeSnapshot,
    health_fields_from_snapshot,
    load_runtime_snapshot,
    persist_add_row,
    persist_delete_last_row,
    state_record_to_fields,
)
from tcp_public_sections import (
    build_firm_intro,
    build_inline_performance_disclaimers,
    build_drawdown_profile_card,
    build_investor_information,
    build_nav_footnotes,
    build_public_disclosure_panel,
    build_public_footer,
    build_public_gate_wrapper,
    build_strategy_overview,
    build_tcp_header,
    build_trading_universe,
    build_two_column_shell_row,
    resolve_public_gate_styles,
)
from tcp_state import StatePaths

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tcp_ts_v2")

WHITE_BG = "#ffffff"
REPO_ROOT = Path(__file__).resolve().parent

LOGO_PATH = (
    r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents"
    r"\2_Hughes & Company Marketing\Branded Logo\Trianle-Only-Logo.png"
)


@dataclass
class PreviewState:
    snapshot: Optional[RuntimeSnapshot] = None
    error: Optional[str] = None
    error_type: Optional[str] = None


def _configured_state_paths(cfg: TCPConfig) -> StatePaths:
    active, backup, lock = resolve_state_paths(cfg, REPO_ROOT)
    return StatePaths(active_path=active, backup_path=backup, lock_path=lock)


def _logo_src() -> str:
    import base64

    try:
        with open(LOGO_PATH, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except OSError:
        return ""


def load_preview_state(cfg: TCPConfig) -> PreviewState:
    paths = _configured_state_paths(cfg)
    try:
        snapshot = load_runtime_snapshot(cfg, paths)
        meta = snapshot.ledger.metadata
        logger.info(
            "TCP v2 loaded %s rows from %s; latest %s; revision %s",
            meta.completed_row_count,
            snapshot.data_source,
            meta.latest_completed_date,
            snapshot.state_revision,
        )
        return PreviewState(snapshot=snapshot)
    except (TCPLedgerError, Exception) as exc:
        logger.error("TCP v2 runtime load failed: %s", exc)
        return PreviewState(error=str(exc), error_type=type(exc).__name__)


def _monthly_table_component(monthly_df: pd.DataFrame) -> html.Div:
    if monthly_df.empty:
        return html.P("No monthly performance data available.", className="text-muted text-center")
    return dbc.Table(
        [
            html.Thead(
                html.Tr(
                    [html.Th(col, style={"backgroundColor": GREY_BG, "color": "#000"}) for col in monthly_df.columns]
                )
            ),
            html.Tbody(
                [html.Tr([html.Td(monthly_df.iloc[i][col]) for col in monthly_df.columns]) for i in range(len(monthly_df))]
            ),
        ],
        bordered=True,
        hover=True,
        size="sm",
        className="table-responsive mb-5",
        style={"width": "95%", "margin": "0 auto", "pageBreakInside": "avoid"},
    )


def _daily_perf_table_component(daily_df: pd.DataFrame) -> html.Div:
    if daily_df.empty:
        return html.P("No daily performance metrics available.", className="text-muted")
    return dbc.Table.from_dataframe(daily_df, striped=False, bordered=True, hover=True, size="sm", className="fixed-cols")


def _drawdown_table_component(drawdown_df: pd.DataFrame) -> html.Div:
    if drawdown_df.empty:
        return html.P("No drawdown profile data available.", className="text-muted")
    return dbc.Table.from_dataframe(
        drawdown_df,
        striped=False,
        bordered=True,
        hover=True,
        size="sm",
        className="fixed-cols",
    )


def _desktop_label_children(header: str, date_line: str) -> List[Any]:
    return [
        html.H6(header, className="text-end text-secondary mb-1", id="data-current-label-desktop-header"),
        html.H5(date_line, className="text-end text-primary", id="data-current-label-desktop-date"),
    ]


def _mobile_label_children(header: str, date_line: str) -> List[Any]:
    return [
        html.Small(header, className="d-block text-end text-primary mb-1", id="data-current-label-mobile-header"),
        html.Small(date_line, className="d-block text-end text-primary", id="data-current-label-mobile-date"),
    ]


def build_error_layout(cfg: TCPConfig, state: PreviewState) -> html.Div:
    message = state.error or "Unknown runtime error"
    return html.Div(
        [
            dbc.Alert(cfg.preview_label, color="warning", className="text-center fw-bold"),
            dbc.Container(
                fluid=True,
                className="py-4",
                children=[
                    dbc.Alert(
                        [
                            html.H4("Preview error", className="alert-heading"),
                            html.P(message, className="mb-0"),
                            html.P(f"Status: {state.error_type or 'error'}", className="small text-muted mt-2"),
                        ],
                        color="danger",
                    )
                ],
            ),
        ]
    )


def _benchmark_cache_path() -> Path:
    return REPO_ROOT / "_runtime" / DEFAULT_CACHE_FILENAME


def _unavailable_benchmark_result() -> BenchmarkResult:
    return BenchmarkResult(
        status=BENCHMARK_STATUS_UNAVAILABLE,
        symbol="^SP500TR",
        display_name="SPXTR",
        as_of=None,
        fetched_at=None,
        returns=None,
        warning="SPXTR benchmark data is temporarily unavailable.",
    )


def _resolve_benchmark_result(runtime_holder: Dict[str, Any]) -> BenchmarkResult:
    existing = runtime_holder.get("benchmark")
    if isinstance(existing, BenchmarkResult):
        return existing
    if os.environ.get("TCP_V2_SKIP_BENCHMARK_FETCH") == "1":
        result = _unavailable_benchmark_result()
    else:
        result = load_spxtr_benchmark(cache_path=_benchmark_cache_path())
    runtime_holder["benchmark"] = result
    return result


def _benchmark_notice_component(result: BenchmarkResult) -> html.Div:
    message = benchmark_status_message(result)
    if not message:
        return html.Div()
    color = "info"
    if result.status == BENCHMARK_STATUS_UNAVAILABLE:
        color = "warning"
    elif result.status == BENCHMARK_STATUS_STALE:
        color = "secondary"
    return dbc.Alert(message, color=color, className="py-2 mb-2 small")


def build_preview_layout(cfg: TCPConfig, state: PreviewState, benchmark_result: BenchmarkResult) -> html.Div:
    snapshot = state.snapshot
    assert snapshot is not None
    meta = snapshot.ledger.metadata
    first_completed = meta.first_completed_date.strftime("%B %d, %Y") if meta.first_completed_date else "—"
    propagation = propagate_tcp_dashboard(snapshot.canonical_nav, benchmark_result=benchmark_result)
    mode_alert = (
        "JSON state is authoritative. Authenticated Add/Delete persist to preview JSON."
        if cfg.persistence_enabled and snapshot.data_source == "json"
        else "Workbook is authoritative. JSON persistence is disabled in this mode."
    )
    if snapshot.warning:
        mode_alert = snapshot.warning

    performance_metrics_card = dbc.Card(
        [
            dbc.CardHeader(html.H6("Performance Metrics", className="mb-0")),
            dbc.CardBody(html.Div(_daily_perf_table_component(propagation.daily_performance), id="daily-perf-container")),
        ],
        outline=True,
        className="mb-4",
        id="tcp-performance-metrics-card",
    )

    main_children = [
        dcc.Store(id="canonical-nav-store", storage_type="memory", data=snapshot.canonical_nav),
        dcc.Store(id="benchmark-store", storage_type="memory", data=benchmark_result.to_store_dict()),
        dcc.Location(id="url", refresh=False),
        dbc.Container(
            fluid=True,
            className="py-4",
            id="page-container",
            children=[
                dbc.Alert(cfg.preview_label, color="warning", className="text-center fw-bold"),
                *build_tcp_header(
                    _logo_src(),
                    _desktop_label_children(
                        propagation.desktop_label.header,
                        propagation.desktop_label.date_line,
                    ),
                    _mobile_label_children(
                        propagation.mobile_label.header,
                        propagation.mobile_label.date_line,
                    ),
                ),
                build_firm_intro(),
                dbc.Alert(mode_alert, color="info"),
                dcc.Graph(
                    id="nav-preview-graph",
                    figure=propagation.nav_figure,
                    config={"displayModeBar": False, "responsive": True},
                    style={"width": "100%", "maxWidth": "100%", "maxHeight": "400px", "pageBreakInside": "avoid"},
                ),
                *build_nav_footnotes(),
                html.H5("Performance Summary", className="text-center mb-2"),
                html.Div(_monthly_table_component(propagation.monthly_calendar), id="monthly-calendar-container"),
                build_two_column_shell_row(
                    build_strategy_overview(),
                    build_trading_universe(),
                    row_id="tcp-strategy-row",
                ),
                build_two_column_shell_row(
                    html.Div(
                        [
                            performance_metrics_card,
                            build_drawdown_profile_card(
                                _drawdown_table_component(propagation.drawdown_profile),
                                benchmark_notice=_benchmark_notice_component(benchmark_result),
                            ),
                        ],
                        id="tcp-performance-drawdown-column",
                    ),
                    build_investor_information(),
                    row_id="tcp-performance-account-row",
                ),
                *build_inline_performance_disclaimers(),
                build_public_disclosure_panel(),
                build_public_footer(),
                html.Div(id="admin-editor-container", style={"display": "none"}),
                dbc.Card(
                    [
                        dbc.CardHeader("Runtime diagnostics (preview only)"),
                        dbc.CardBody(
                            [
                                html.P([html.Strong("State mode: "), cfg.state_mode], className="mb-1"),
                                html.P([html.Strong("Data source: "), snapshot.data_source], className="mb-1"),
                                html.P([html.Strong("Recovery status: "), snapshot.recovery_status], className="mb-1"),
                                html.P([html.Strong("State revision: "), str(snapshot.state_revision or "—")], className="mb-1"),
                                html.P([html.Strong("Completed ledger rows: "), str(meta.completed_row_count)], className="mb-1"),
                                html.P([html.Strong("First completed date: "), first_completed], className="mb-1"),
                                html.P([html.Strong("Latest completed date: "), propagation.desktop_label.date_line], className="mb-1"),
                                html.P([html.Strong("Workbook: "), cfg.workbook_filename, " · Sheet: ", cfg.sheet_name], className="mb-1 small text-muted"),
                                html.P(html.A("Admin login", href="/admin/login", className="small"), className="mb-0"),
                            ]
                        ),
                    ],
                    className="mt-3",
                ),
            ],
        ),
    ]
    return build_public_gate_wrapper(main_children)


def _health_payload(cfg: TCPConfig, state: PreviewState, auth_manager: AdminAuthManager) -> dict:
    base: Dict[str, Any] = {
        "app": "tcp-v2",
        "mode": "read-only" if cfg.read_only else "json-active",
        "port": cfg.preview_port,
        "debug": cfg.debug,
        "workbook": cfg.workbook_filename,
        "sheet": cfg.sheet_name,
        "dashboard_propagation": "ready",
        "monthly_performance": "dynamic",
        "daily_metrics": "dynamic",
        "nav_chart": "dynamic",
        "current_date_labels": "dynamic",
        "admin_auth": auth_manager.auth_status_label(),
    }
    if state.snapshot is not None:
        snap = state.snapshot
        meta = snap.ledger.metadata
        base.update(health_fields_from_snapshot(snap, auth_configured=auth_manager.is_configured))
        base.update(
            {
                "adapter_status": "ok",
                "completed_rows": meta.completed_row_count,
                "latest_completed_date": meta.latest_completed_date.isoformat() if meta.latest_completed_date else None,
                "first_completed_date": meta.first_completed_date.isoformat() if meta.first_completed_date else None,
                "candidate_rows": meta.total_candidate_rows,
            }
        )
    else:
        base.update({"adapter_status": "error", "error_type": state.error_type, "message": state.error})
    return base


def _register_public_gate_callback(app: dash.Dash) -> None:
    @app.callback(
        Output("disclaimer-screen", "style"),
        Output("main-app", "style"),
        Input("accept-button", "n_clicks"),
    )
    def _reveal_public_layout(n_clicks):
        return resolve_public_gate_styles(n_clicks)


def _register_dashboard_callback(app: dash.Dash, runtime_holder: Dict[str, Any]) -> None:
    @app.callback(
        Output("nav-preview-graph", "figure"),
        Output("monthly-calendar-container", "children"),
        Output("daily-perf-container", "children"),
        Output("drawdown-profile-container", "children"),
        Output("tcp-benchmark-notice", "children"),
        Output("data-current-label-desktop", "children"),
        Output("data-current-label-mobile", "children"),
        Input("canonical-nav-store", "data"),
        Input("benchmark-store", "data"),
    )
    def _propagate_dashboard_outputs(canonical_data, benchmark_data):
        records = canonical_data or []
        benchmark_result = (
            BenchmarkResult.from_store_dict(benchmark_data)
            if benchmark_data
            else _resolve_benchmark_result(runtime_holder)
        )
        propagation = propagate_tcp_dashboard(records, benchmark_result=benchmark_result)
        return (
            propagation.nav_figure,
            _monthly_table_component(propagation.monthly_calendar),
            _daily_perf_table_component(propagation.daily_performance),
            _drawdown_table_component(propagation.drawdown_profile),
            _benchmark_notice_component(benchmark_result),
            _desktop_label_children(propagation.desktop_label.header, propagation.desktop_label.date_line),
            _mobile_label_children(propagation.mobile_label.header, propagation.mobile_label.date_line),
        )


def _register_admin_callbacks(
    app: dash.Dash,
    cfg: TCPConfig,
    paths: StatePaths,
    runtime_holder: Dict[str, Any],
    auth_manager: AdminAuthManager,
) -> None:
    def current_snapshot() -> RuntimeSnapshot:
        return runtime_holder["snapshot"]

    def set_snapshot(snapshot: RuntimeSnapshot) -> None:
        runtime_holder["snapshot"] = snapshot

    @app.callback(
        Output("admin-editor-container", "children"),
        Output("admin-editor-container", "style"),
        Input("url", "pathname"),
        Input("admin-state-revision-store", "data"),
    )
    def _render_admin_editor(_pathname, _revision):
        if not auth_manager.is_authenticated(session):
            return [], {"display": "none"}
        snap = current_snapshot()
        rows = ledger_records_to_rows(snap.records)
        latest_date = snap.ledger.metadata.latest_completed_date
        latest_iso = latest_date.isoformat() if latest_date else None
        editor = build_admin_editor_layout(
            rows=rows,
            completed_rows=len(rows),
            latest_date=latest_iso,
            data_source=snap.data_source,
            state_revision=snap.state_revision,
            persistence_enabled=cfg.persistence_enabled,
            writable=snap.writable,
            warning=snap.warning,
        )
        return editor, {"display": "block"}

    @app.callback(
        Output("admin-ledger-table", "data"),
        Output("admin-ledger-table", "style_data_conditional"),
        Input("admin-state-revision-store", "data"),
        prevent_initial_call=False,
    )
    def _refresh_ledger_table(_revision):
        if not auth_manager.is_authenticated(session):
            return no_update, no_update
        rows = ledger_records_to_rows(current_snapshot().records)
        display_rows = [{k: v for k, v in row.items() if k != "_highlight"} for row in rows]
        return display_rows, ledger_table_style_conditional(rows)

    @app.callback(
        Output("admin-ledger-table", "columns"),
        Input("admin-column-selector", "value"),
        prevent_initial_call=False,
    )
    def _update_visible_columns(visible_columns):
        if not auth_manager.is_authenticated(session):
            return no_update
        visible = visible_columns or []
        return datatable_column_defs(visible)

    @app.callback(
        Output("admin-add-modal", "is_open"),
        Output("admin-add-date", "value"),
        Output("admin-add-cash-balance", "value"),
        Output("admin-add-cash-transfers", "value"),
        Output("admin-add-tranche-count", "value"),
        Input("admin-open-add-modal", "n_clicks"),
        Input("admin-add-cancel-btn", "n_clicks"),
        State("admin-add-modal", "is_open"),
        prevent_initial_call=True,
    )
    def _toggle_add_modal(open_clicks, cancel_clicks, is_open):
        if not auth_manager.is_authenticated(session):
            return no_update, no_update, no_update, no_update, no_update
        triggered = dash.callback_context.triggered_id
        if triggered == "admin-add-cancel-btn":
            return False, no_update, no_update, no_update, no_update
        latest_record = state_record_to_fields(current_snapshot().records[-1].fields)
        defaults = default_add_row_values(latest_record)
        return True, defaults["date"], defaults["cash_balance"], defaults["cash_transfers"], defaults["tranche_count"]

    @app.callback(
        Output("admin-add-preview-modal", "is_open"),
        Output("admin-add-preview-table", "children"),
        Output("admin-add-general-error", "children"),
        Output("admin-add-general-error", "is_open"),
        Output("admin-add-date-error", "children"),
        Output("admin-add-cash-balance-error", "children"),
        Output("admin-add-transfer-error", "children"),
        Output("admin-add-tranche-error", "children"),
        Output("admin-proposed-row-store", "data"),
        Input("admin-add-preview-btn", "n_clicks"),
        State("admin-add-date", "value"),
        State("admin-add-cash-balance", "value"),
        State("admin-add-cash-transfers", "value"),
        State("admin-add-tranche-count", "value"),
        prevent_initial_call=True,
    )
    def _preview_add_row(_n_clicks, row_date, cash_balance, cash_transfers, tranche_count):
        if not auth_manager.is_authenticated(session):
            return (no_update,) * 9
        prior = state_record_to_fields(current_snapshot().records[-1].fields)
        result = simulate_add_row(
            prior,
            row_date=row_date,
            cash_balance=cash_balance,
            cash_transfers=cash_transfers,
            tranche_count=tranche_count,
        )
        if not result.success:
            return (
                False,
                no_update,
                result.error_message or "Unable to preview row.",
                bool(result.error_message),
                result.field_errors.get("date", ""),
                result.field_errors.get("cash_balance", ""),
                result.field_errors.get("cash_transfers", ""),
                result.field_errors.get("tranche", ""),
                None,
            )
        table = proposed_row_table(result.proposed_row or {}, result.prior_row)
        return True, table, "", False, "", "", "", "", {
            "row_date": row_date,
            "cash_balance": cash_balance,
            "cash_transfers": cash_transfers,
            "tranche_count": tranche_count,
        }

    @app.callback(
        Output("admin-add-preview-modal", "is_open", allow_duplicate=True),
        Input("admin-add-confirm-btn", "n_clicks"),
        Input("admin-add-preview-close-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _close_preview_modal(_confirm, _close):
        if not auth_manager.is_authenticated(session):
            return no_update
        return False

    @app.callback(
        Output("canonical-nav-store", "data"),
        Output("admin-state-revision-store", "data"),
        Output("admin-add-save-result", "children"),
        Output("admin-add-save-result", "is_open"),
        Output("admin-add-preview-modal", "is_open", allow_duplicate=True),
        Input("admin-add-save-btn", "n_clicks"),
        State("admin-proposed-row-store", "data"),
        State("admin-state-revision-store", "data"),
        prevent_initial_call=True,
    )
    def _save_add_row(_n_clicks, proposed_inputs, expected_revision):
        if not auth_manager.is_authenticated(session):
            return no_update, no_update, no_update, no_update, no_update
        if not proposed_inputs or expected_revision is None:
            return no_update, no_update, "Missing preview inputs or revision.", True, no_update
        result = persist_add_row(
            cfg,
            paths,
            expected_revision=int(expected_revision),
            row_date=proposed_inputs.get("row_date"),
            cash_balance=proposed_inputs.get("cash_balance"),
            cash_transfers=proposed_inputs.get("cash_transfers"),
            tranche_count=proposed_inputs.get("tranche_count"),
            authenticated=True,
        )
        if not result.success or result.snapshot is None:
            return no_update, no_update, result.error_message or "Save failed.", True, True
        set_snapshot(result.snapshot)
        message = f"Saved row {result.saved_date} · NAV {result.saved_nav:.3f} · revision {result.revision}"
        return result.snapshot.canonical_nav, result.revision, message, True, False

    @app.callback(
        Output("admin-delete-modal", "is_open"),
        Output("admin-delete-preview-content", "children"),
        Output("admin-delete-result", "is_open"),
        Output("admin-delete-result", "children"),
        Output("admin-delete-final-date-store", "data"),
        Output("canonical-nav-store", "data", allow_duplicate=True),
        Output("admin-state-revision-store", "data", allow_duplicate=True),
        Input("admin-open-delete-modal", "n_clicks"),
        Input("admin-delete-close-btn", "n_clicks"),
        Input("admin-delete-confirm-btn", "n_clicks"),
        State("admin-delete-modal", "is_open"),
        State("admin-state-revision-store", "data"),
        State("admin-delete-final-date-store", "data"),
        prevent_initial_call=True,
    )
    def _delete_row(open_clicks, close_clicks, confirm_clicks, is_open, expected_revision, final_date):
        if not auth_manager.is_authenticated(session):
            return (no_update,) * 7
        triggered = dash.callback_context.triggered_id
        snap = current_snapshot()
        if triggered == "admin-open-delete-modal":
            preview = simulate_delete_last_row(snap.records)
            deleted_date = None
            if preview.deleted_row:
                raw = preview.deleted_row.get("Date")
                deleted_date = raw.isoformat() if hasattr(raw, "isoformat") else str(raw)
            return True, delete_preview_content(preview), False, "", deleted_date, no_update, no_update
        if triggered == "admin-delete-close-btn":
            return False, no_update, False, "", no_update, no_update, no_update
        if triggered == "admin-delete-confirm-btn":
            if cfg.persistence_enabled and snap.writable and expected_revision is not None and final_date:
                result = persist_delete_last_row(
                    cfg,
                    paths,
                    expected_revision=int(expected_revision),
                    expected_final_date=str(final_date),
                    authenticated=True,
                )
                if result.success and result.snapshot is not None:
                    set_snapshot(result.snapshot)
                    msg = f"{DELETE_PERSIST_MESSAGE} · revision {result.revision}"
                    return (
                        True,
                        delete_preview_content(simulate_delete_last_row(result.snapshot.records)),
                        True,
                        msg,
                        result.saved_date,
                        result.snapshot.canonical_nav,
                        result.revision,
                    )
                return True, no_update, True, result.error_message or "Delete failed.", no_update, no_update, no_update
            preview = simulate_delete_last_row(snap.records)
            return True, delete_preview_content(preview), True, DELETE_CONFIRM_MESSAGE, no_update, no_update, no_update
        return False, no_update, False, "", no_update, no_update, no_update


def _register_auth_routes(app: dash.Dash, auth_manager: AdminAuthManager) -> None:
    @app.server.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            token = request.form.get("token", "")
            ok, error = auth_manager.login(session, token)
            if ok:
                return redirect("/")
            return render_template_string(LOGIN_FORM_HTML, error=error), 401
        return render_template_string(LOGIN_FORM_HTML, error=None)

    @app.server.route("/admin/logout", methods=["GET", "POST"])
    def admin_logout():
        auth_manager.logout(session)
        return redirect("/")


def create_app(
    cfg: Optional[TCPConfig] = None,
    auth_settings: Optional[AdminAuthSettings] = None,
    runtime_holder: Optional[Dict[str, Any]] = None,
) -> Tuple[dash.Dash, TCPConfig, PreviewState, AdminAuthManager, Dict[str, Any]]:
    """Construct Dash app and attach health/auth routes. Does not start the server."""
    cfg = cfg or load_config()
    ok, msg = validate_config(cfg)
    if not ok:
        raise ValueError(f"Invalid TCP v2 config: {msg}")

    auth_settings = auth_settings or load_admin_auth_settings()
    auth_manager = AdminAuthManager(auth_settings)
    state = load_preview_state(cfg)
    paths = _configured_state_paths(cfg)

    if runtime_holder is None:
        runtime_holder = {}
    if state.snapshot is not None:
        runtime_holder["snapshot"] = state.snapshot

    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True,
        title="H&C – TCP v2 Preview",
    )
    configure_flask_session_secret(app.server, auth_settings)
    _register_auth_routes(app, auth_manager)

    if state.snapshot is not None:
        benchmark_result = _resolve_benchmark_result(runtime_holder)
        app.layout = build_preview_layout(cfg, state, benchmark_result)
        _register_public_gate_callback(app)
        _register_dashboard_callback(app, runtime_holder)
        _register_admin_callbacks(app, cfg, paths, runtime_holder, auth_manager)
    else:
        app.layout = build_error_layout(cfg, state)

    @app.server.route("/healthz")
    def healthz():
        live_state = PreviewState(snapshot=runtime_holder.get("snapshot")) if runtime_holder.get("snapshot") else state
        payload = _health_payload(cfg, live_state if live_state.snapshot else state, auth_manager)
        status = 200 if (live_state.snapshot or state.snapshot) is not None else 503
        return jsonify(payload), status

    return app, cfg, state, auth_manager, runtime_holder


_RUNTIME_HOLDER: Dict[str, Any] = {}
app, _CONFIG, _PREVIEW_STATE, _AUTH_MANAGER, _RUNTIME_HOLDER = create_app(runtime_holder=_RUNTIME_HOLDER)


def main() -> None:
    cfg = _CONFIG
    ok, msg = validate_config(cfg)
    if not ok:
        logger.error("Config validation failed: %s", msg)
        sys.exit(1)
    logger.info("Starting %s on port %s (debug=%s)", cfg.preview_label, cfg.preview_port, cfg.debug)
    app.run(debug=cfg.debug, port=cfg.preview_port)


if __name__ == "__main__":
    main()
