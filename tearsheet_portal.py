"""
Shared admin Portal — account-registry board (TCP, TKP, Algominds).

Presentation only — no auth, server binding, or persistence. Callers pass in
whatever account rows they actually have; an empty/None list renders the
shared "Pending" empty state rather than a fabricated row.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import render_template_string
from markupsafe import Markup, escape

PORTAL_COLUMNS: List[str] = [
    "Account",
    "Account number",
    "Status",
    "Starting date",
    "Benchmark base",
    "Units",
    "After-fee NLV",
    "Week %",
    "Month %",
    "Since inception %",
    "Exchange fee tier",
    "Last updated",
    "Tearsheet",
]

# Placeholder for registry rows whose per-account tearsheet is not wired up yet.
TEARSHEET_NOT_WIRED_TEXT = "Coming soon"

# Keys read off each account dict, in column order. Missing/None values render as EMPTY_CELL.
PORTAL_ROW_FIELDS: List[str] = [
    "account",
    "account_number",
    "status",
    "starting_date",
    "benchmark_base",
    "units",
    "after_fee_nlv",
    "week_pct",
    "month_pct",
    "since_inception_pct",
    "fee_tier",
    "last_updated",
    "tearsheet",
]

EMPTY_CELL = "—"
PENDING_EMPTY_STATE_TEXT = "Pending — no participating accounts yet."

PORTAL_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ title }}</title>
  <style>
    body {
      font-family: Arial, Helvetica, sans-serif;
      margin: 0;
      background: #ffffff;
      color: #212529;
    }
    .wrap {
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px;
    }
    h1 {
      color: #0D3562;
      font-size: 1.75rem;
      margin-bottom: 0.5rem;
    }
    h2 {
      color: #0D3562;
      font-size: 1.1rem;
      margin-top: 2rem;
    }
    .muted {
      color: #6c757d;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 1.5rem 0;
    }
    th, td {
      border: 1px solid #ccc;
      padding: 8px;
      text-align: left;
      font-size: 0.9rem;
    }
    th {
      background: #EBEBEB;
    }
    a {
      color: #0D3562;
    }
    .actions a {
      margin-right: 0.75rem;
    }
    .portal-empty-state {
      text-align: center;
      color: #6c757d;
      font-style: italic;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>{{ program_name }} — Portal</h1>
    <p class="muted">Participating accounts.</p>
    <table id="portal-account-registry">
      <thead>
        <tr>
          {% for col in columns %}<th>{{ col }}</th>{% endfor %}
        </tr>
      </thead>
      <tbody>
        {% if rows %}
          {% for row in rows %}
          <tr>
            {% for cell in row %}<td>{{ cell }}</td>{% endfor %}
          </tr>
          {% endfor %}
        {% else %}
          <tr><td colspan="{{ columns|length }}" class="portal-empty-state">{{ empty_state_text }}</td></tr>
        {% endif %}
      </tbody>
    </table>
    {% if diagnostics %}
    <h2>Diagnostics</h2>
    {{ diagnostics|safe }}
    {% endif %}
    <p class="muted"><a href="{{ logout_href }}">Logout</a> · <a href="{{ back_href }}">Back to tearsheet</a></p>
  </div>
</body>
</html>
"""


def _format_cell(value: Any) -> str:
    if value is None or value == "":
        return EMPTY_CELL
    return str(value)


def _tearsheet_cell(account: Dict[str, Any]) -> Any:
    """Action cell: link to the account's tearsheet when wired, else placeholder.

    Accounts opt in by providing "tearsheet_href"; everything else shows the
    shared "Coming soon" placeholder (backend links do not all exist yet).
    """
    href = account.get("tearsheet_href")
    if href:
        return Markup(f'<a href="{escape(href)}">Open tearsheet</a>')
    return TEARSHEET_NOT_WIRED_TEXT


def render_portal_page(
    *,
    program_name: str,
    accounts: Optional[List[Dict[str, Any]]] = None,
    empty_state_text: str = PENDING_EMPTY_STATE_TEXT,
    diagnostics_html: Optional[str] = None,
    logout_href: str = "/admin/logout",
    back_href: str = "/",
) -> str:
    """Render the shared account-registry Portal page.

    accounts: list of dicts keyed by PORTAL_ROW_FIELDS. None/empty -> Pending empty state.
    diagnostics_html: optional pre-rendered HTML block shown below the registry
        (e.g. legacy program-status info), kept separate so it can't be mistaken
        for the account registry itself.
    """
    rows = [
        [
            _tearsheet_cell(account) if field == "tearsheet" else _format_cell(account.get(field))
            for field in PORTAL_ROW_FIELDS
        ]
        for account in (accounts or [])
    ]
    return render_template_string(
        PORTAL_HTML,
        title=f"{program_name} — Portal",
        program_name=program_name,
        columns=PORTAL_COLUMNS,
        rows=rows,
        empty_state_text=empty_state_text,
        diagnostics=diagnostics_html,
        logout_href=logout_href,
        back_href=back_href,
    )


LEGACY_DIAGNOSTICS_HTML = """
<table>
  <thead>
    <tr><th>Program</th><th>Latest completed date</th><th>Completed rows</th><th>Actions</th></tr>
  </thead>
  <tbody>
    <tr>
      <td>{{ program_name }}</td>
      <td>{{ latest_date }}</td>
      <td>{{ row_count }}</td>
      <td class="actions"><a href="{{ daily_entry_href }}">Daily entry</a></td>
    </tr>
  </tbody>
</table>
"""


def render_legacy_diagnostics_table(
    *,
    program_name: str,
    latest_date: str = EMPTY_CELL,
    row_count: str = EMPTY_CELL,
    daily_entry_href: str = "/",
) -> str:
    """Pre-rendered HTML for the old program-status board, shown as a Portal diagnostics section."""
    return render_template_string(
        LEGACY_DIAGNOSTICS_HTML,
        program_name=program_name,
        latest_date=latest_date,
        row_count=row_count,
        daily_entry_href=daily_entry_href,
    )
