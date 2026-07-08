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
from algominds_v2_account_state_paths import (
    load_latest_snapshot_for_account,
    resolve_preview_state_path,
)
from algominds_v2_config import DEFAULT_PREVIEW_PORT, load_algominds_v2_config
from algominds_v2_snapshot_state import compute_latest_snapshot_result
from algominds_v2_state import read_preview_state

PLACEHOLDER = "—"


@dataclass(frozen=True)
class AdminAccountRow:
    display_name: str
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


def _page_shell(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 24px; }}
    th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
    th {{ background: #f5f5f5; }}
    .muted {{ color: #666; }}
    .banner {{ background: #eef6ff; padding: 12px; margin-bottom: 16px; }}
  </style>
</head>
<body>
  <div class="banner"><strong>Algominds v2 Preview</strong> — read-only shell</div>
  {body}
</body>
</html>"""


def render_landing_page() -> str:
    default = get_default_account_profile()
    body = f"""
  <h1>Algominds v2 Preview</h1>
  <p><a href="/admin">Admin overview</a></p>
  <p><a href="/{html.escape(default.account_slug)}">Default account ({html.escape(default.display_name)})</a></p>
"""
    return _page_shell("Algominds v2 Preview", body)


def render_admin_page(*, state_root: Path | str | None = None) -> str:
    rows = build_admin_account_rows(state_root=state_root)
    table_rows = []
    for row in rows:
        table_rows.append(
            "<tr>"
            f'<td><a href="{html.escape(row.account_href)}">{html.escape(row.display_name)}</a></td>'
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
  <h1>Admin Overview</h1>
  <table id="admin-account-overview">
    <thead>
      <tr>
        <th>Account</th>
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
    profile = get_account_profile(account_slug)
    path = resolve_preview_state_path(profile.account_slug, state_root=state_root)
    preview = read_preview_state(path)
    snapshot = load_latest_snapshot_for_account(profile.account_slug, state_root=state_root)
    result = compute_latest_snapshot_result(path) if snapshot is not None else None

    if snapshot is None:
        snapshot_block = "<p>No preview snapshot saved for this account yet.</p>"
    else:
        snapshot_block = f"""
  <h2>Latest snapshot</h2>
  <ul>
    <li>account_slug: {html.escape(snapshot.account_slug or PLACEHOLDER)}</li>
    <li>account_balance: {html.escape(format_money(snapshot.account_balance))}</li>
    <li>fee_removal: {html.escape(format_money(snapshot.fee_removal))}</li>
    <li>displayed_fee_owed: {html.escape(format_money(result.displayed_fee_owed if result else None))}</li>
    <li>after_fee_nlv: {html.escape(format_money(result.after_fee_nlv if result else None))}</li>
    <li>last_updated_utc: {html.escape(preview.last_updated_utc or PLACEHOLDER)}</li>
  </ul>
"""

    body = f"""
  <h1>{html.escape(profile.display_name)}</h1>
  <ul>
    <li>account_slug: {html.escape(profile.account_slug)}</li>
    <li>starting date: {html.escape(format_date_or_placeholder(profile.inception_date))}</li>
    <li>benchmark base: {html.escape(format_money(profile.benchmark_base))}</li>
    <li>units: {profile.number_of_units}</li>
    <li>exchange fee tier: {html.escape(profile.exchange_fee_tier)}</li>
    <li>state path: {html.escape(str(path))}</li>
  </ul>
  {snapshot_block}
  <p><a href="/admin">Admin overview</a></p>
"""
    return _page_shell(profile.display_name, body)


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
