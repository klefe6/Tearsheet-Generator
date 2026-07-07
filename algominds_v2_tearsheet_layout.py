"""
Algominds v2 tearsheet layout — pure HTML/SVG rendering of a TearsheetViewModel.

Visual frame mirrors the Algominds v1 Momentum Pacer tearsheet (mp_ts.py):
grey header band, centered firm/program titles, Last Updated block, intro
paragraphs, NAV chart, Performance Summary table, two-column report cards,
Investor Information, and Drawdown from Peak chart.

This module contains no fee math, no account registry access, and no state
I/O — it renders exactly what the view model provides.
"""
from __future__ import annotations

import html as html_escape_module
from decimal import Decimal
from typing import Optional, Sequence

from algominds_v2_tearsheet import (
    FEE_STRUCTURE_ASSUMPTION_NOTE,
    FeeSlabRow,
    LabelValueRow,
    SummaryRow,
    TearsheetSeries,
    TearsheetViewModel,
)
from tearsheet_gate_ui import (
    TEARSHEET_GATE_STATIC_CSS,
    render_static_gate_markup,
    static_gate_script,
)

# v1 brand palette (mp_ts.py)
WHITE_BG = "#ffffff"
GREY_BG = "#EBEBEB"
PRIMARY_COLOR = "#1B4F8A"
SECONDARY_COLOR = "#CCCCCC"
ACCENT_GREEN = "#28a745"
ACCENT_RED = "#dc3545"
POSITIVE_CELL_BG = "#d4edda"
NEGATIVE_CELL_BG = "#f8d7da"
NET_DOLLAR_BG = "#E8F4FD"
SPX_LINE_COLOR = "#E67E22"

_esc = html_escape_module.escape

TEARSHEET_CSS = """
  * { box-sizing: border-box; }
  body { font-family: Arial, Helvetica, sans-serif; margin: 0; background: #ffffff;
         color: #212529; }
  .page { max-width: 1400px; margin: 0 auto; padding: 24px 24px 48px; }
  .preview-banner { background: #eef6ff; border-bottom: 1px solid #cfe2ff;
                    padding: 10px 24px; font-size: 0.9rem; }
  .fixture-banner { background: #fff3cd; border: 1px solid #ffeeba; color: #664d03;
                    padding: 8px 16px; margin: 12px 0; font-size: 0.85rem;
                    border-radius: 4px; text-align: center; }
  .header-band { background: #EBEBEB; padding: 14px 16px; display: flex;
                 align-items: center; }
  .header-left { flex: 0 0 16%; min-height: 60px; }
  .header-center { flex: 1 1 68%; text-align: center; line-height: 1.2; }
  .header-center h1 { margin: 0; font-size: 2rem; font-weight: 500; }
  .header-center h2 { margin: 4px 0 0; font-size: 1.15rem; font-weight: 400;
                      color: #6c757d; }
  .header-center .account-label { margin: 4px 0 0; font-size: 0.95rem;
                                  color: #1B4F8A; font-weight: 600; }
  .header-right { flex: 0 0 16%; text-align: right; }
  .header-right .lu-label { color: #6c757d; font-size: 0.95rem; margin: 0; }
  .header-right .lu-value { color: #1B4F8A; font-size: 1.1rem; margin: 2px 0 0;
                            font-weight: 500; }
  hr { border: 0; border-top: 1px solid rgba(0,0,0,0.15); margin: 16px 0; }
  .intro { text-align: center; max-width: 980px; margin: 0 auto 32px; }
  .intro .lead { font-size: 1.15rem; font-weight: 300; margin: 8px 0; }
  .intro p { font-size: 0.95rem; margin: 8px 0; }
  .chart-block { margin: 8px 0 4px; }
  .chart-caption { text-align: center; font-size: 0.83rem; color: #6c757d;
                   font-style: italic; max-width: 920px; margin: 10px auto 34px;
                   line-height: 1.45; }
  .section-title { text-align: center; font-size: 1.15rem; font-weight: 500;
                   margin: 10px 0 10px; }
  table.ts { border-collapse: collapse; width: 100%; font-size: 0.8rem;
             margin-bottom: 8px; background: #fff; }
  table.ts th, table.ts td { border: 1px solid #dee2e6; padding: 4px 8px; }
  table.ts th { background: #EBEBEB; text-align: center; vertical-align: bottom;
                font-size: 0.75rem; white-space: pre-wrap; }
  table.ts td { text-align: right; white-space: nowrap; }
  table.ts td.label-cell { text-align: left; font-weight: 500; background: #fff; }
  tr.net-row td { font-weight: 700; border-top: 2px solid #333; }
  .table-wrap { overflow-x: auto; margin-bottom: 40px; }
  .card-row { display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
  .card { border: 1px solid rgba(0,0,0,0.18); border-radius: 4px; background: #fff;
          flex: 1 1 460px; min-width: 320px; display: flex; flex-direction: column; }
  .card-header { background: #f8f9fa; border-bottom: 1px solid rgba(0,0,0,0.18);
                 padding: 8px 14px; font-size: 0.95rem; font-weight: 600; }
  .card-body { padding: 14px; }
  .card-footer { background: #f8f9fa; border-top: 1px solid rgba(0,0,0,0.18);
                 padding: 8px 14px; font-size: 0.78rem; color: #6c757d;
                 font-style: italic; }
  table.kv { border-collapse: collapse; width: 100%; font-size: 0.85rem; }
  table.kv th, table.kv td { border: 1px solid #dee2e6; padding: 5px 10px;
                             text-align: left; }
  table.kv th { background: #f8f9fa; }
  .subhead th { background: #f8f9fa !important; font-weight: 600; }
  .muted-note { font-size: 0.78rem; color: #6c757d; font-style: italic; }
  .footer-disclaimer { text-align: center; font-size: 0.8rem; margin-top: 24px; }
  .footer-disclaimer .bold-line { font-weight: 700; }
  .footer-disclaimer .muted { color: #6c757d; font-style: italic; }
  .legend { text-align: center; font-size: 0.8rem; margin-top: 4px; }
  .legend span.swatch { display: inline-block; width: 26px; height: 0;
                        border-top-width: 3px; margin: 0 6px 3px 14px;
                        vertical-align: middle; }
  .check { color: #28a745; }
  .cross { color: #CCCCCC; }
  a { color: #1B4F8A; }
  @media (max-width: 760px) {
    .header-band { flex-wrap: wrap; }
    .header-left, .header-right { flex: 1 1 100%; text-align: center; }
    .header-center { flex: 1 1 100%; }
  }
"""


def _sign_bg(value: Optional[Decimal]) -> str:
    if value is None:
        return "background:#ffffff;"
    if value > 0:
        return f"background:{POSITIVE_CELL_BG};"
    if value < 0:
        return f"background:{NEGATIVE_CELL_BG};"
    return "background:#ffffff;"


def _fmt_idx(value: Optional[Decimal]) -> str:
    return f"{value:,.2f}" if value is not None else "—"


def _fmt_dollar(value: Optional[Decimal]) -> str:
    return f"${value:,.0f}" if value is not None else "—"


def _fmt_pct(value: Optional[Decimal]) -> str:
    return f"{value:.2f}%" if value is not None else "—"


# ──────────────────────────────────────────────────────────────────────────────
# SVG chart rendering (deterministic; mirrors v1 plotly ggplot2 styling)
# ──────────────────────────────────────────────────────────────────────────────

_CHART_WIDTH = 1120
_PLOT_LEFT = 110
_PLOT_RIGHT = 1010
_SERIES_STYLES = (
    {"color": PRIMARY_COLOR, "width": 2.5, "dash": "", "markers": True},
    {"color": SPX_LINE_COLOR, "width": 1.5, "dash": "8,5", "markers": False},
    {"color": "#8E44AD", "width": 1.5, "dash": "2,4", "markers": False},
)


def _nice_ticks(lo: float, hi: float, target: int = 6) -> list[float]:
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / target
    magnitude = 10 ** _floor_log10(raw)
    for mult in (1, 2, 2.5, 5, 10):
        step = mult * magnitude
        if step >= raw:
            break
    first = _ceil_div(lo, step) * step
    ticks = []
    t = first
    while t <= hi + 1e-9:
        ticks.append(round(t, 10))
        t += step
    return ticks


def _floor_log10(x: float) -> int:
    from math import floor, log10

    return floor(log10(abs(x))) if x != 0 else 0


def _ceil_div(a: float, b: float) -> float:
    from math import ceil

    return ceil(a / b)


def _x_positions(count: int) -> list[float]:
    if count == 1:
        return [(_PLOT_LEFT + _PLOT_RIGHT) / 2]
    span = _PLOT_RIGHT - _PLOT_LEFT
    return [_PLOT_LEFT + span * i / (count - 1) for i in range(count)]


def render_line_chart_svg(
    series: Sequence[TearsheetSeries],
    *,
    title: str,
    y_prefix: str = "$",
    y_suffix: str = "",
    height: int = 440,
    fill_first_series: bool = False,
    element_id: str = "chart",
) -> str:
    """Deterministic SVG line chart styled after the v1 plotly charts."""
    if not series or not series[0].points:
        return (
            f'<svg id="{_esc(element_id)}" viewBox="0 0 {_CHART_WIDTH} {height}" '
            f'role="img"><text x="{_CHART_WIDTH / 2}" y="{height / 2}" '
            f'text-anchor="middle">No data</text></svg>'
        )

    plot_top = 56
    plot_bottom = height - 96

    all_values = [float(p.value) for s in series for p in s.points]
    y_min, y_max = min(all_values), max(all_values)
    pad = max((y_max - y_min) * 0.05, abs(y_max) * 0.01, 0.5)
    y_lo, y_hi = y_min - pad, y_max + pad
    if fill_first_series:
        y_hi = max(y_hi, 0.5)

    def y_px(v: float) -> float:
        return plot_bottom - (v - y_lo) / (y_hi - y_lo) * (plot_bottom - plot_top)

    n_points = max(len(s.points) for s in series)
    xs = _x_positions(n_points)

    parts: list[str] = []
    parts.append(
        f'<svg id="{_esc(element_id)}" viewBox="0 0 {_CHART_WIDTH} {height}" '
        f'preserveAspectRatio="xMidYMid meet" role="img" '
        f'style="width:100%;height:auto;background:{WHITE_BG};">'
    )
    parts.append(
        f'<text x="{_CHART_WIDTH / 2}" y="30" text-anchor="middle" '
        f'font-size="17" text-decoration="underline">{_esc(title)}</text>'
    )
    # plot background (ggplot2-style grey)
    parts.append(
        f'<rect x="{_PLOT_LEFT}" y="{plot_top}" width="{_PLOT_RIGHT - _PLOT_LEFT}" '
        f'height="{plot_bottom - plot_top}" fill="{GREY_BG}" />'
    )
    # horizontal gridlines + y labels
    ticks = _nice_ticks(y_lo, y_hi)
    step = ticks[1] - ticks[0] if len(ticks) > 1 else 1.0
    decimals = 0 if step >= 1 else (1 if step >= 0.1 else 2)
    for tick in ticks:
        py = y_px(tick)
        if py < plot_top - 1 or py > plot_bottom + 1:
            continue
        parts.append(
            f'<line x1="{_PLOT_LEFT}" y1="{py:.1f}" x2="{_PLOT_RIGHT}" y2="{py:.1f}" '
            f'stroke="#ffffff" stroke-width="1.4" />'
        )
        label = f"{y_prefix}{tick:,.{decimals}f}{y_suffix}"
        parts.append(
            f'<text x="{_PLOT_LEFT - 8}" y="{py + 4:.1f}" text-anchor="end" '
            f'font-size="12" fill="#444">{_esc(label)}</text>'
        )
    # vertical gridlines + x labels from the first (longest) series dates
    ref_points = max(series, key=lambda s: len(s.points)).points
    for i, point in enumerate(ref_points):
        px = xs[i]
        parts.append(
            f'<line x1="{px:.1f}" y1="{plot_top}" x2="{px:.1f}" y2="{plot_bottom}" '
            f'stroke="#ffffff" stroke-width="1" />'
        )
        label = point.when.strftime("%b %Y")
        parts.append(
            f'<text x="{px:.1f}" y="{plot_bottom + 28}" text-anchor="end" '
            f'font-size="11" fill="#444" '
            f'transform="rotate(-30 {px:.1f} {plot_bottom + 28})">{_esc(label)}</text>'
        )
    # zero line for drawdown-style charts
    if fill_first_series and y_lo < 0 < y_hi:
        zy = y_px(0.0)
        parts.append(
            f'<line x1="{_PLOT_LEFT}" y1="{zy:.1f}" x2="{_PLOT_RIGHT}" y2="{zy:.1f}" '
            f'stroke="#999" stroke-width="1" />'
        )

    # series
    for s_idx, s in enumerate(series):
        style = _SERIES_STYLES[s_idx % len(_SERIES_STYLES)]
        pts = [
            (xs[i], y_px(float(p.value)))
            for i, p in enumerate(s.points)
        ]
        path = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        if fill_first_series and s_idx == 0:
            zy = y_px(min(0.0, y_hi))
            fill_path = (
                f"{pts[0][0]:.1f},{zy:.1f} " + path + f" {pts[-1][0]:.1f},{zy:.1f}"
            )
            parts.append(
                f'<polygon points="{fill_path}" fill="{ACCENT_RED}" opacity="0.25" />'
            )
            color = ACCENT_RED
        else:
            color = style["color"]
        dash = f' stroke-dasharray="{style["dash"]}"' if style["dash"] else ""
        parts.append(
            f'<polyline points="{path}" fill="none" stroke="{color}" '
            f'stroke-width="{style["width"]}"{dash} />'
        )
        if style["markers"] and not fill_first_series:
            for x, y in pts:
                parts.append(
                    f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}" />'
                )

    parts.append("</svg>")

    # legend below the plot (mirrors v1's below-chart horizontal legend)
    legend_items = []
    for s_idx, s in enumerate(series):
        style = _SERIES_STYLES[s_idx % len(_SERIES_STYLES)]
        color = ACCENT_RED if (fill_first_series and s_idx == 0) else style["color"]
        border_style = "dashed" if style["dash"] else "solid"
        legend_items.append(
            f'<span class="swatch" style="border-top-style:{border_style};'
            f'border-top-color:{color};"></span>{_esc(s.label)}'
        )
    parts.append(f'<div class="legend">{"".join(legend_items)}</div>')
    return "".join(parts)


# ──────────────────────────────────────────────────────────────────────────────
# Section renderers
# ──────────────────────────────────────────────────────────────────────────────


def render_header(vm: TearsheetViewModel) -> str:
    return f"""
  <div class="header-band" id="tearsheet-header">
    <div class="header-left"></div>
    <div class="header-center">
      <h1>{_esc(vm.firm_name)}</h1>
      <h2>{_esc(vm.program_name)}</h2>
      <p class="account-label">{_esc(vm.display_name)}</p>
    </div>
    <div class="header-right">
      <p class="lu-label">Last Updated</p>
      <p class="lu-value">{_esc(vm.last_updated_label)}</p>
    </div>
  </div>
"""


def render_intro(vm: TearsheetViewModel) -> str:
    paragraphs = "".join(
        f'<p class="{"lead" if i == 0 else ""}">{_esc(text)}</p>'
        for i, text in enumerate(vm.intro_paragraphs)
    )
    return f'<div class="intro" id="tearsheet-intro">{paragraphs}</div>'


def render_nav_chart_section(vm: TearsheetViewModel) -> str:
    svg = render_line_chart_svg(
        vm.nav_series,
        title="Compounded NAV Since Inception",
        y_prefix="$",
        element_id="nav-chart",
    )
    inception_str = vm.inception_date.strftime("%B %d, %Y")
    caption = (
        f"Growth of a ${vm.starting_balance:,.0f} investment from inception "
        f"({inception_str}). NAV reflects compounded performance, net of all fees. "
        "The strategy trades NQ / MNQ (Nasdaq-100 futures) exclusively. "
        "SPX is rebased to the same starting capital for benchmark comparison only."
    )
    return (
        f'<div class="chart-block" id="nav-chart-section">{svg}</div>'
        f'<p class="chart-caption">{_esc(caption)}</p>'
    )


def render_performance_summary(vm: TearsheetViewModel) -> str:
    headers = (
        "Month",
        "SPX Start",
        "SPX End",
        "Acct Start",
        "Acct End\nAfter Fees",
        "SPX\nReturns%",
        "Gross\nReturns%",
        "Fees%",
        "Net\nReturns%",
        "Cumul.\nNet%",
    )
    head_html = "".join(f"<th>{_esc(h)}</th>" for h in headers)
    body_rows = []
    for row in vm.summary_rows:
        cells = [
            f'<td class="label-cell">{_esc(row.month_label)}</td>',
            f"<td>{_esc(_fmt_idx(row.spx_start))}</td>",
            f"<td>{_esc(_fmt_idx(row.spx_end))}</td>",
            f"<td>{_esc(_fmt_dollar(row.account_start))}</td>",
            f"<td>{_esc(_fmt_dollar(row.account_end_after_fees))}</td>",
            f'<td style="{_sign_bg(row.spx_return_pct)}">{_esc(_fmt_pct(row.spx_return_pct))}</td>',
            f'<td style="{_sign_bg(row.gross_return_pct)}">{_esc(_fmt_pct(row.gross_return_pct))}</td>',
            f"<td>{_esc(_fmt_pct(row.fees_pct))}</td>",
            f'<td style="{_sign_bg(row.net_return_pct)}">{_esc(_fmt_pct(row.net_return_pct))}</td>',
            f'<td style="{_sign_bg(row.cumulative_net_pct)}">{_esc(_fmt_pct(row.cumulative_net_pct))}</td>',
        ]
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    if vm.summary_totals:
        totals_cells = "".join(
            f'<td colspan="2" style="background:{NET_DOLLAR_BG};">'
            f"<strong>{_esc(row.label)}</strong> {_esc(row.value)}</td>"
            for row in vm.summary_totals
        )
        pad = len(headers) - 2 * len(vm.summary_totals)
        pad_cell = f'<td colspan="{pad}" style="background:{GREY_BG};"></td>' if pad > 0 else ""
        body_rows.append(f'<tr class="net-row">{pad_cell}{totals_cells}</tr>')
    return f"""
  <h3 class="section-title" id="performance-summary-title">Performance Summary</h3>
  <div class="table-wrap" id="performance-summary">
    <table class="ts">
      <thead><tr>{head_html}</tr></thead>
      <tbody>{''.join(body_rows)}</tbody>
    </table>
  </div>
"""


def _kv_table(rows: Sequence[LabelValueRow], head: tuple[str, str] | None = None) -> str:
    head_html = (
        f"<thead><tr><th>{_esc(head[0])}</th><th>{_esc(head[1])}</th></tr></thead>"
        if head
        else ""
    )
    body = "".join(
        f"<tr><td>{_esc(row.label)}</td><td>{_esc(row.value)}</td></tr>" for row in rows
    )
    return f'<table class="kv">{head_html}<tbody>{body}</tbody></table>'


def render_strategy_overview_card(vm: TearsheetViewModel) -> str:
    inception_str = vm.inception_date.strftime("%B %d, %Y")
    return f"""
    <div class="card" id="strategy-overview">
      <div class="card-header">Strategy Overview</div>
      <div class="card-body">
        <table class="kv">
          <thead><tr><th colspan="3">Strategy Description</th></tr></thead>
          <tbody>
            <tr><td colspan="3" style="font-style:italic;white-space:normal;">
              The Momentum Pacer Program is a systematic trend-following strategy
              trading exclusively in Nasdaq-100 futures (NQ / MNQ). Quantitative
              momentum signals identify and capture directional moves in the
              Nasdaq-100. The S&amp;P 500 (SPX) is shown as a benchmark for
              comparison only; the contractual incentive fee uses the S&amp;P 500
              return (the Benchmark in the Disclosure Document) solely as a
              reference for fee calculation. Risk is managed through adaptive
              position sizing and stop-loss orders.
            </td></tr>
            <tr class="subhead"><th colspan="3">Methodology</th></tr>
            <tr><td>Trading Style</td>
                <td><span class="check">&#10003; Momentum / Trend</span></td>
                <td><span class="cross">&#10007; Mean Reversion</span></td></tr>
            <tr><td>Decision Making</td>
                <td><span class="check">&#10003; Systematic</span></td>
                <td><span class="cross">&#10007; Discretionary</span></td></tr>
            <tr><td>Execution</td>
                <td><span class="check">&#10003; Fully automated</span></td>
                <td><span class="cross">&#10007; Manual</span></td></tr>
            <tr><td>Instruments</td>
                <td colspan="2">NQ / MNQ (Nasdaq-100 E-mini &amp; Micro)</td></tr>
            <tr><td>Exchanges</td><td colspan="2">CME Group</td></tr>
            <tr><td>Account Start Date</td><td colspan="2">{_esc(inception_str)}</td></tr>
            <tr><td>Initial Capital</td>
                <td colspan="2">${vm.starting_balance:,.0f}</td></tr>
            <tr><td>Trading Units</td><td colspan="2">{vm.number_of_units}</td></tr>
            <tr class="subhead"><th colspan="3">Risk Controls</th></tr>
            <tr><td><span class="check">&#10003; Stop Losses</span></td>
                <td><span class="check">&#10003; Position Sizing</span></td>
                <td><span class="check">&#10003; High-Water Mark</span></td></tr>
          </tbody>
        </table>
      </div>
    </div>
"""


def render_fee_structure_card(vm: TearsheetViewModel) -> str:
    slab_rows = "".join(
        f'<tr><td style="font-weight:600;white-space:nowrap;">{_esc(row.slab)}</td>'
        f"<td style=\"white-space:normal;\">{_esc(row.band)}</td>"
        f'<td style="white-space:nowrap;">{_esc(row.rate)}</td></tr>'
        for row in vm.fee_structure_rows
    )
    terms_rows = "".join(
        f'<tr><td>{_esc(row.label)}</td><td style="white-space:normal;">{_esc(row.value)}</td></tr>'
        for row in vm.fee_terms
    )
    return f"""
    <div class="card" id="fee-structure">
      <div class="card-header">Fee Structure</div>
      <div class="card-body">
        <table class="kv">
          <thead><tr><th colspan="2">Terms &amp; Fees</th></tr></thead>
          <tbody>{terms_rows}
            <tr class="subhead"><th colspan="2">Fee Slab Structure</th></tr>
          </tbody>
        </table>
        <table class="kv" style="margin-top:6px;">
          <thead><tr><th>Slab</th>
            <th>Net new profits slice (vs Benchmark dollar return)</th>
            <th>Incentive fee</th></tr></thead>
          <tbody>{slab_rows}</tbody>
        </table>
        <p class="muted-note">{_esc(FEE_STRUCTURE_ASSUMPTION_NOTE)}</p>
      </div>
    </div>
"""


def render_metrics_cards(vm: TearsheetViewModel) -> str:
    stats_title = (
        "Monthly Performance Statistics"
        if vm.is_preview_fixture
        else "Snapshot Performance Statistics"
    )
    footer = (
        "Statistics calculated from deterministic preview fixture months."
        if vm.is_preview_fixture
        else "Statistics calculated from the latest saved snapshot."
    )
    return f"""
    <div class="card-row">
      <div class="card" id="performance-metrics">
        <div class="card-header">Performance Metrics</div>
        <div class="card-body">
          {_kv_table(vm.performance_metrics, ("Metric", "Momentum Pacer (Inception)"))}
        </div>
      </div>
      <div class="card" id="performance-stats">
        <div class="card-header">{_esc(stats_title)}</div>
        <div class="card-body">
          {_kv_table(vm.performance_stats, ("Metric", "Momentum Pacer (Inception)"))}
        </div>
        <div class="card-footer">{_esc(footer)}</div>
      </div>
    </div>
"""


def render_investor_information_card(vm: TearsheetViewModel) -> str:
    return f"""
    <div class="card-row">
      <div class="card" id="investor-information" style="flex-basis:100%;">
        <div class="card-header">Investor Information</div>
        <div class="card-body">
          <div class="card-row" style="margin-bottom:0;">
            <div style="flex:1 1 420px;">
              {_kv_table(vm.investor_terms, ("Terms & Fees", "Details"))}
            </div>
            <div style="flex:1 1 420px;">
              {_kv_table(vm.account_stats, ("Account Stats", "Current"))}
            </div>
          </div>
        </div>
      </div>
    </div>
"""


def render_drawdown_section(vm: TearsheetViewModel) -> str:
    svg = render_line_chart_svg(
        (vm.drawdown_series,),
        title="Drawdown from Peak",
        y_prefix="",
        y_suffix="%",
        height=380,
        fill_first_series=True,
        element_id="drawdown-chart",
    )
    return f'<div class="chart-block" id="drawdown-section">{svg}</div>'


def render_footer_disclaimers(vm: TearsheetViewModel) -> str:
    return f"""
  <hr />
  <div class="footer-disclaimer" id="tearsheet-footer">
    <p class="bold-line">THE MOMENTUM PACER PROGRAM IS A PROPRIETARY TRADING STRATEGY.
      THIS PERFORMANCE DATA IS FOR INFORMATIONAL PURPOSES ONLY AND IS NOT A
      SOLICITATION TO INVEST. PAST PERFORMANCE IS NOT INDICATIVE OF FUTURE RESULTS.</p>
    <p class="muted">Past performance is not necessarily indicative of future results.
      The risk of loss in commodity trading can be substantial. This information is
      for informational purposes only and does not constitute investment advice or a
      solicitation to invest.</p>
    <p class="muted">For more information, contact {_esc(vm.firm_name)}</p>
  </div>
"""


def render_tearsheet_body(vm: TearsheetViewModel) -> str:
    """Full v1-style tearsheet body for one account view model."""
    fixture_banner = (
        f'<div class="fixture-banner" id="preview-fixture-banner">{_esc(vm.data_notice)}</div>'
        if vm.data_notice
        else ""
    )
    return "".join(
        [
            render_header(vm),
            fixture_banner,
            "<hr />",
            render_intro(vm),
            render_nav_chart_section(vm),
            render_performance_summary(vm),
            '<div class="card-row">',
            render_strategy_overview_card(vm),
            render_fee_structure_card(vm),
            "</div>",
            render_metrics_cards(vm),
            render_investor_information_card(vm),
            render_drawdown_section(vm),
            render_footer_disclaimers(vm),
        ]
    )


def render_tearsheet_page(vm: TearsheetViewModel) -> str:
    """Complete HTML document for one account tearsheet (read-only preview)."""
    gate = render_static_gate_markup("Momentum Pacer")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(vm.firm_name)} — {_esc(vm.display_name)}</title>
  <style>{TEARSHEET_CSS}{TEARSHEET_GATE_STATIC_CSS}</style>
</head>
<body>
  {gate}
  <div id="main-app" class="tearsheet-gate-hidden">
  <div class="page">
    {render_tearsheet_body(vm)}
  </div>
  </div>
  {static_gate_script()}
</body>
</html>"""
