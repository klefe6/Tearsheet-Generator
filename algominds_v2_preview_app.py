"""
Algominds v2 preview shell — read-only Dash app for /admin and /{account_slug} routes.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

import dash
from dash import html as dhtml

from algominds_v2_account_registry import (
    AccountProfileNotFoundError,
    get_account_profile,
    get_default_account_profile,
    list_account_profiles,
)
from algominds_v2_account_state_paths import resolve_preview_state_path
from algominds_v2_config import DEFAULT_PREVIEW_PORT, load_algominds_v2_config
from algominds_v2_snapshot_state import compute_latest_snapshot_result
from algominds_v2_state import read_preview_state
from algominds_v2_tearsheet import build_tearsheet_view_model
from algominds_v2_tearsheet_layout import render_tearsheet_page
from tearsheet_gate_ui import (
    TEARSHEET_GATE_STATIC_CSS,
    render_static_gate_markup,
    static_gate_script,
)

PLACEHOLDER = "—"


@dataclass(frozen=True)
class AdminAccountRow:
    display_name: str
    account_number: str
    account_slug: str
    inception_date: date
    benchmark_base: Decimal
    number_of_units: int
    exchange_fee_tier: str
    after_fee_nlv: Optional[Decimal]
    week_pct: Optional[Decimal]
    month_pct: Optional[Decimal]
    inception_pct: Optional[Decimal]
    last_updated_utc: Optional[str]
    account_href: str


def format_money(value: Optional[Decimal]) -> str:
    if value is None:
        return PLACEHOLDER
    return f"${value:,.2f}"


def format_percent_or_placeholder(value: Optional[Decimal]) -> str:
    if value is None:
        return PLACEHOLDER
    return f"{value:.2f}%"


def format_date_or_placeholder(value: Optional[date]) -> str:
    if value is None:
        return PLACEHOLDER
    return value.isoformat()


def build_admin_account_rows(
    *,
    state_root: Path | str | None = None,
) -> tuple[AdminAccountRow, ...]:
    """Build admin overview rows from registry profiles and per-account state."""
    rows: list[AdminAccountRow] = []
    for profile in list_account_profiles():
        path = resolve_preview_state_path(profile.account_slug, state_root=state_root)
        preview = read_preview_state(path)
        result = compute_latest_snapshot_result(path)
        after_fee_nlv = result.after_fee_nlv if result is not None else None
        inception_pct: Optional[Decimal] = None
        if after_fee_nlv is not None and profile.starting_balance > 0:
            inception_pct = (
                (after_fee_nlv - profile.starting_balance) / profile.starting_balance
            ) * Decimal("100")
        rows.append(
            AdminAccountRow(
                display_name=profile.display_name,
                account_number=profile.account_number,
                account_slug=profile.account_slug,
                inception_date=profile.inception_date,
                benchmark_base=profile.benchmark_base,
                number_of_units=profile.number_of_units,
                exchange_fee_tier=profile.exchange_fee_tier,
                after_fee_nlv=after_fee_nlv,
                week_pct=None,
                month_pct=None,
                inception_pct=inception_pct,
                last_updated_utc=preview.last_updated_utc,
                account_href=f"/{profile.account_slug}",
            )
        )
    return tuple(rows)


def _page_shell(title: str, body: str, *, program_code: str = "Momentum Pacer") -> str:
    gate = render_static_gate_markup(program_code)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, Helvetica, sans-serif; margin: 0; background: #ffffff; color: #212529; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
    th {{ background: #EBEBEB; }}
    .muted {{ color: #6c757d; }}
    a {{ color: #0D3562; }}
    {TEARSHEET_GATE_STATIC_CSS}
  </style>
</head>
<body>
  {gate}
  <div id="main-app" class="tearsheet-gate-hidden">
    {body}
  </div>
  {static_gate_script()}
</body>
</html>"""


def render_landing_page() -> str:
    default = get_default_account_profile()
    account_items = []
    for profile in list_account_profiles():
        suffix = " (default)" if profile.is_default else ""
        account_items.append(
            f'<li style="margin:6px 0;"><a href="/{html.escape(profile.account_slug)}">'
            f"{html.escape(profile.display_name)}</a>{suffix}</li>"
        )
    body = f"""
  <div style="max-width:960px;margin:0 auto;padding:24px;">
  <h1>Algominds Financial LLC — Momentum Pacer Program</h1>
  <p class="muted">Select an account tearsheet:</p>
  <ul>
    {''.join(account_items)}
  </ul>
  <p><a href="/admin">Admin overview</a></p>
  </div>
"""
    return _page_shell("Algominds v2 Preview", body)


def render_admin_page(*, state_root: Path | str | None = None) -> str:
    rows = build_admin_account_rows(state_root=state_root)
    table_rows = []
    for row in rows:
        table_rows.append(
            "<tr>"
            f'<td><a href="{html.escape(row.account_href)}">{html.escape(row.display_name)}</a></td>'
            f"<td>{html.escape(row.account_number)}</td>"
            f"<td>{html.escape(format_date_or_placeholder(row.inception_date))}</td>"
            f"<td>{html.escape(format_money(row.benchmark_base))}</td>"
            f"<td>{row.number_of_units}</td>"
            f"<td>{html.escape(format_money(row.after_fee_nlv) if row.after_fee_nlv is not None else 'No snapshot yet')}</td>"
            f"<td>{html.escape(format_percent_or_placeholder(row.week_pct))}</td>"
            f"<td>{html.escape(format_percent_or_placeholder(row.month_pct))}</td>"
            f"<td>{html.escape(format_percent_or_placeholder(row.inception_pct))}</td>"
            f"<td>{html.escape(row.exchange_fee_tier)}</td>"
            f"<td>{html.escape(row.last_updated_utc or PLACEHOLDER)}</td>"
            "</tr>"
        )
    body = f"""
  <div style="max-width:1200px;margin:0 auto;padding:24px;">
  <h1>Admin Overview</h1>
  <table id="admin-account-overview">
    <thead>
      <tr>
        <th>Account</th>
        <th>Account number</th>
        <th>Starting date</th>
        <th>Benchmark base</th>
        <th>Units</th>
        <th>After-fee NLV</th>
        <th>Week %</th>
        <th>Month %</th>
        <th>Since inception %</th>
        <th>Exchange fee tier</th>
        <th>Last updated</th>
      </tr>
    </thead>
    <tbody>
      {''.join(table_rows)}
    </tbody>
  </table>
  <p class="muted"><a href="/">Home</a></p>
  </div>
"""
    return _page_shell("Algominds v2 Admin", body)


def render_not_found_page(account_slug: str) -> str:
    body = f"""
  <h1>Account not found</h1>
  <p>No account profile exists for <code>{html.escape(account_slug)}</code>.</p>
  <p><a href="/admin">Back to admin overview</a></p>
"""
    return _page_shell("Account not found", body)


def render_account_page(
    account_slug: str,
    *,
    state_root: Path | str | None = None,
) -> str:
    """Render the full v1-style investor tearsheet for one account."""
    profile = get_account_profile(account_slug)
    view_model = build_tearsheet_view_model(profile, state_root=state_root)
    return render_tearsheet_page(view_model)


def create_algominds_v2_preview_app(
    *,
    state_root: Path | str | None = None,
) -> dash.Dash:
    """Construct the read-only Algominds v2 preview Dash app without starting the server."""
    app = dash.Dash(
        __name__,
        suppress_callback_exceptions=True,
        title="Algominds v2 Preview",
    )

    @app.server.route("/")
    def landing() -> str:
        return render_landing_page()

    @app.server.route("/admin")
    def admin() -> str:
        return render_admin_page(state_root=state_root)

    @app.server.route("/<account_slug>")
    def account_detail(account_slug: str):
        try:
            return render_account_page(account_slug, state_root=state_root)
        except AccountProfileNotFoundError:
            return render_not_found_page(account_slug), 404

    app.layout = dhtml.Div(
        [
            dhtml.H2("Algominds v2 Preview"),
            dhtml.P("Use /admin or /{account_slug} routes."),
        ]
    )
    return app


def main() -> None:
    cfg = load_algominds_v2_config()
    app = create_algominds_v2_preview_app()
    app.run(host="127.0.0.1", port=cfg.preview_port, debug=False)


if __name__ == "__main__":
    main()
