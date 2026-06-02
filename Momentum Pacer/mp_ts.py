"""
mp_ts.py  –  Momentum Pacer Tearsheet
======================================
Strategy : Momentum Pacer
CTA       : Algominds Financial LLC

Visual frame matches the Y&Q tearsheet (yq_ts.py).
Data source: Momentum Fee Calculation.xlsx  (Summary + Sris Fee Calc Detail tabs)

HOW TO RUN
----------
    python mp_ts.py
Then open: http://127.0.0.1:8304

Production (Cloudflare / reboot_mp_ts.bat): set MP_TS_PRODUCTION=1 so the server runs
without Dash debug/reloader (avoids unstable behavior behind a reverse proxy).
"""

from __future__ import annotations

import base64
import math
import os
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objs as go
import openpyxl

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

# ==============================================================================
# PATHS
# ==============================================================================
BASE_DIR  = Path(__file__).parent
EXCEL_PATH = BASE_DIR / "Momentum Fee Calculation.xlsx"

# ==============================================================================
# BRAND / STYLE  (mirrors Y&Q tearsheet conventions)
# ==============================================================================
WHITE_BG         = "#ffffff"
GREY_BG          = "#EBEBEB"
PRIMARY_COLOR    = "#1B4F8A"      # Algominds blue
SECONDARY_COLOR  = "#CCCCCC"
ACCENT_GREEN     = "#28a745"
ACCENT_RED       = "#dc3545"
LEFT_TABLE_GAPS  = "20px"
RIGHT_TABLE_GAPS = "30px"
HEADER_ROW_CLASS = "bg-light"

# ==============================================================================
# LOGO
# ==============================================================================
logo_src = ""
for lp in [BASE_DIR / "algominds_logo.png", BASE_DIR / "logo.png"]:
    if lp.exists():
        with open(lp, "rb") as _f:
            logo_src = f"data:image/png;base64,{base64.b64encode(_f.read()).decode()}"
        break

# ==============================================================================
# DATA LOADING  –  reads directly from Excel
# ==============================================================================
LOAD_ERROR = None

def load_summary(path: Path) -> pd.DataFrame:
    """
    Parse the 'Summary' sheet.
    Columns: Month, SPX Start, SPX End, NDX Start, NDX End,
             BOT Start, BOT End After Fees,
             SPX Returns%, NDX Returns%,
             BOT Returns Before Fees%, BOT Fees%, BOT Returns After Fees%,
             Cumulative After Fees%
    Only rows where Month is a real date AND BOT Start is not None are kept.
    """
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Summary"]

    rows = list(ws.iter_rows(values_only=True))
    # Row 0 = headers, rows 1+ = data
    data = []
    for row in rows[1:]:
        # stop at Net% / Net$ footer rows or empty month
        if row[0] is None or not isinstance(row[0], datetime):
            continue
        # skip rows where BOT Start is empty (future months)
        if row[5] is None:
            continue
        data.append({
            "date":              row[0],
            "spx_start":         row[1],
            "spx_end":           row[2],
            "ndx_start":         row[3],
            "ndx_end":           row[4],
            "bot_start":         row[5],
            "bot_end_after_fees":row[6],
            "spx_ret":           row[7],   # decimal  e.g. 0.0166
            "ndx_ret":           row[8],
            "bot_gross_ret":     row[9],   # BOT returns before fees
            "bot_fees_pct":      row[10],
            "bot_net_ret":       row[11],  # BOT returns after fees
            "cumulative_net":    row[12],
        })

    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    return df


def load_net_totals(path: Path) -> dict:
    """Read the Net% and Net$ footer rows from Summary sheet."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Summary"]
    totals = {}
    for row in ws.iter_rows(values_only=True):
        if row[0] == "Net%":
            totals["spx_net_pct"]          = row[7]
            totals["ndx_net_pct"]          = row[8]
            totals["bot_gross_pct"]        = row[9]
            totals["bot_fees_pct"]         = row[10]
            totals["bot_net_pct"]          = row[11]
        if row[0] == "Net$":
            totals["spx_net_dollar"]       = row[7]
            totals["ndx_net_dollar"]       = row[8]
            totals["bot_gross_dollar"]     = row[9]
            totals["bot_fees_dollar"]      = row[10]
            totals["bot_net_dollar"]       = row[11]
    return totals


# Live trading began (TradeStation); monthly summary rows are month-stubs (e.g. Nov 1).
PROGRAM_INCEPTION = datetime(2025, 11, 13, 0, 0, 0)

# Charts and table filter use this date instead of machine clock (first of its month caps rows).
TEARSHEET_AS_OF = datetime(2026, 5, 12, 0, 0, 0)

# Extra point on NAV / drawdown only: month stub (e.g. May 1) stays; this x is added after it when later.
# Set NAV when known; None keeps the same dollar level as the prior point (placeholder).
TEARSHEET_CHART_EXTRA_DATE: datetime | None = datetime(2026, 5, 12, 0, 0, 0)
TEARSHEET_CHART_EXTRA_NAV_USD: float | None = None

# Incentive fee slabs — AlgoMinds Financial LLC Disclosure Document (e.g. effective March 1, 2026),
# "Advisor's Fees" / Incentive Fee. Benchmark = S&P 500 monthly return (WSJ official month-end closes);
# tiers are slices of net new profits measured vs multiples of the Benchmark's *dollar* return for the month.
FEE_SLAB_BANDS_DISPLAY = (
    (
        "Slab 1",
        "Net new profits from $0 up through 100% of the Benchmark's monthly dollar return (0–1×)",
        "10%",
    ),
    (
        "Slab 2",
        "Portion exceeding 100% but not more than 200% of that Benchmark dollar return (1×–2×)",
        "20%",
    ),
    (
        "Slab 3",
        "Portion exceeding 200% but not more than 300% (2×–3×)",
        "30%",
    ),
    (
        "Slab 4",
        "Portion exceeding 300% but not more than 400% (3×–4×)",
        "40%",
    ),
    (
        "Slab 5",
        "Portion exceeding 400% of the Benchmark's monthly dollar return (>4×)",
        "50%",
    ),
)

try:
    summary_df   = load_summary(EXCEL_PATH)
    net_totals   = load_net_totals(EXCEL_PATH)
    STARTING_CAPITAL = float(summary_df["bot_start"].iloc[0])
    LATEST_DATE      = summary_df["date"].max()
    print(f"[mp_ts] Loaded {len(summary_df)} months from {EXCEL_PATH.name}")
    print(
        f"[mp_ts] Program inception: {PROGRAM_INCEPTION.strftime('%m/%d/%Y')}  "
        f"Latest month: {LATEST_DATE.strftime('%b %Y')}"
    )
except Exception as _e:
    traceback.print_exc()
    summary_df   = pd.DataFrame()
    net_totals   = {}
    STARTING_CAPITAL = 30_000.0
    LATEST_DATE      = PROGRAM_INCEPTION
    LOAD_ERROR = str(_e)


def months_trading_elapsed_approx() -> str:
    """
    Elapsed time from live inception (Nov 13) to the *start* of the latest Summary
    month row (e.g. May 1), expressed as decimal months using 365.25/12 days/month.
    This is not the same as the count of monthly return rows in the sheet.
    """
    if summary_df.empty:
        return "—"
    disp = _summary_through_current_month(summary_df)
    if disp.empty:
        return "—"
    end = pd.Timestamp(disp["date"].max()).to_pydatetime()
    delta = end - PROGRAM_INCEPTION
    if delta.days <= 0:
        return "0.0"
    days_per_month = 365.25 / 12.0
    return f"{delta.days / days_per_month:.1f}"


# ==============================================================================
# CALCULATED METRICS  (mirroring Y&Q's calculate_period_metrics_monthly)
# ==============================================================================
def calc_performance_metrics(df: pd.DataFrame) -> dict:
    """
    Compute key performance stats from the summary dataframe.
    Returns a dict of display-ready strings.

    Cumulative net return matches the spreadsheet / Net% row: it is taken from
    actual month-end BOT balances (last ÷ first − 1), not from chaining the
    monthly "% after fees" cells — those can differ slightly from a pure MoM
    NAV ratio (HWM / fee mechanics / rounding), so ∏(1+r) would not match 49.65%.
    """
    if df.empty:
        return {}

    net_rets = df["bot_net_ret"].astype(float)  # decimal per month (displayed %)
    n        = len(net_rets)

    # Dollar-accurate cumulative (aligns with Summary "Cumul. Net%" / Net% row)
    start_eq = float(df["bot_start"].iloc[0])
    end_eq   = float(df["bot_end_after_fees"].iloc[-1])
    cum      = (end_eq / start_eq) - 1.0 if start_eq > 0 else 0.0

    # CAGR using calendar span inception → start of latest summary month in *df*
    latest_row = pd.Timestamp(df["date"].max()).to_pydatetime()
    span_days = (latest_row - PROGRAM_INCEPTION).days
    years_real = span_days / 365.25 if span_days > 0 else 0.0
    ann = ((1 + cum) ** (1 / years_real) - 1) if years_real > 0 else 0.0

    avg      = net_rets.mean()
    std      = net_rets.std(ddof=1)
    sharpe   = (avg / std * np.sqrt(12)) if std > 0 else 0.0

    wins   = (net_rets > 0).sum()
    losses = (net_rets < 0).sum()
    top3   = net_rets.nlargest(3) * 100
    bot3   = net_rets.nsmallest(3) * 100

    return {
        "Cumulative Net Return":   f"{cum*100:.2f}%",
        "Annualized Net Return":   f"{ann*100:.2f}%",
        "Avg Monthly Net Return":  f"{avg*100:.3f}%",
        "Sharpe Ratio (approx)":   f"{sharpe:.2f}",
        "Number of Months":        str(n),
        "% Winning Months":        f"{wins} ({wins/n*100:.1f}%)",
        "% Losing Months":         f"{losses} ({losses/n*100:.1f}%)",
        "Best 3 Months":           ", ".join(f"{v:.2f}%" for v in top3),
        "Worst 3 Months":          ", ".join(f"{v:.2f}%" for v in bot3),
    }


def calc_monthly_stats(df: pd.DataFrame) -> dict:
    """Monthly performance statistics card (mirrors Y&Q's calculate_monthly_stats)."""
    if df.empty:
        return {}
    net_rets = df["bot_net_ret"].astype(float)
    pos  = net_rets[net_rets > 0]
    neg  = net_rets[net_rets < 0]
    n    = len(net_rets)

    # Streak calculation
    signs = (net_rets > 0).astype(int)
    win_streaks, loss_streaks = [], []
    cur, cur_sign = 1, signs.iloc[0]
    for i in range(1, len(signs)):
        if signs.iloc[i] == cur_sign:
            cur += 1
        else:
            (win_streaks if cur_sign == 1 else loss_streaks).append(cur)
            cur, cur_sign = 1, signs.iloc[i]
    (win_streaks if cur_sign == 1 else loss_streaks).append(cur)

    return {
        "Number of Positive Months": f"{len(pos)} ({len(pos)/n*100:.1f}%)",
        "Number of Negative Months": f"{len(neg)} ({len(neg)/n*100:.1f}%)",
        "Average Winning Month %":   f"{pos.mean()*100:.2f}%" if len(pos) else "—",
        "Average Losing Month %":    f"{neg.mean()*100:.2f}%" if len(neg) else "—",
        "Best Single Month %":       f"{net_rets.max()*100:.2f}%",
        "Worst Single Month %":      f"{net_rets.min()*100:.2f}%",
        "Longest Winning Streak":    f"{max(win_streaks) if win_streaks else 0} months",
        "Longest Losing Streak":     f"{max(loss_streaks) if loss_streaks else 0} months",
    }


# ==============================================================================
# FIGURE BUILDERS
# ==============================================================================


def _chart_today() -> pd.Timestamp:
    """Calendar date for chart cutoffs (tearsheet as-of; not machine clock)."""
    return pd.Timestamp(TEARSHEET_AS_OF.date())


def _first_of_calendar_month(ts: pd.Timestamp) -> pd.Timestamp:
    """Midnight on the 1st of the same calendar month as *ts*."""
    t = pd.Timestamp(ts).normalize()
    return t.replace(day=1)


def _first_of_month_after(d: pd.Timestamp) -> pd.Timestamp:
    """First day of the month after *d* (for Summary rows dated 1st of M)."""
    d = pd.Timestamp(d).normalize()
    return (d + pd.DateOffset(months=1)).normalize()


def _last_calendar_day_of_month(d: pd.Timestamp) -> pd.Timestamp:
    """Row date *d* is the 1st of month M; return last calendar day of M."""
    d = pd.Timestamp(d).normalize()
    first_next = (d + pd.DateOffset(months=1)).replace(day=1)
    return (first_next - pd.Timedelta(days=1)).normalize()


def _summary_through_current_month(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rows on or before the 1st of the current calendar month.
    Excludes next-month rows from Excel so mid-May never looks like June data.
    """
    if df.empty:
        return df
    cur = _first_of_calendar_month(_chart_today())
    return df[df["date"] <= cur].reset_index(drop=True)


def _month_close_x_positions(dates: pd.Series | list) -> list[pd.Timestamp]:
    """
    Map each summary row date (1st of month M) to the x used for that month's close NAV.

    Completed months: x = 1st of following month (same tick convention as the sheet).
    Current calendar month (in progress): x = M (1st of month) on the May 2026 tick.

    If the prior month's default close (1st of next month) would share that same date
    as the in-progress row (e.g. April end and May row both on May 1), use the last
    day of the prior month instead so there is only one point on the current tick.
    """
    dates = [pd.Timestamp(d).normalize() for d in dates]
    if not dates:
        return []
    as_of = _chart_today()
    cur_start = _first_of_calendar_month(as_of)
    n = len(dates)
    out: list[pd.Timestamp] = []
    for i, d in enumerate(dates):
        if i == n - 1 and d == cur_start:
            out.append(d)
        else:
            nxt_first = _first_of_month_after(d)
            if (
                n >= 2
                and i == n - 2
                and dates[n - 1] == cur_start
                and nxt_first == dates[n - 1]
            ):
                out.append(_last_calendar_day_of_month(d))
            else:
                out.append(nxt_first)
    return out


def _append_tearsheet_chart_extra_date(xs: list, ys: list, y_extra: float | None = None) -> tuple[list, list]:
    """
    Append TEARSHEET_CHART_EXTRA_DATE after the last x when it is strictly later.
    Keeps the prior point (e.g. May 1); y_extra None duplicates the last y (placeholder NAV).
    """
    if TEARSHEET_CHART_EXTRA_DATE is None or not xs:
        return xs, ys
    tx = pd.Timestamp(TEARSHEET_CHART_EXTRA_DATE.date()).normalize()
    if tx <= pd.Timestamp(xs[-1]):
        return xs, ys
    tail_y = float(y_extra) if y_extra is not None else float(ys[-1])
    return list(xs) + [tx], list(ys) + [tail_y]


# Summary slice on this tearsheet (respects TEARSHEET_AS_OF); metrics + tables use this.
_display_summary_df = _summary_through_current_month(summary_df)
perf_metrics  = calc_performance_metrics(_display_summary_df)
monthly_stats = calc_monthly_stats(_display_summary_df)

perf_df = pd.DataFrame({
    "Metric": list(perf_metrics.keys()),
    f"Momentum Pacer (Inception)": list(perf_metrics.values()),
}) if perf_metrics else pd.DataFrame()

stats_df = pd.DataFrame({
    "Metric": list(monthly_stats.keys()),
    "Momentum Pacer (Inception)": list(monthly_stats.values()),
}) if monthly_stats else pd.DataFrame()


def _hover_customdata(y_vals: list[float], baseline: float) -> list[list]:
    """
    Returns a list of [delta_vs_prior_str, cum_pct_vs_baseline_str] per point.
    First point shows '—' for both fields.
    """
    out: list[list] = []
    for i, y in enumerate(y_vals):
        yf = float(y)
        # Δ vs prior
        if i == 0:
            delta = "—"
        else:
            prev = float(y_vals[i - 1])
            if abs(prev) < 1e-12:
                delta = "—"
            else:
                delta = f"{(yf / prev - 1.0) * 100.0:+.2f}%"
        # Cumulative % vs baseline
        if abs(baseline) < 1e-12 or i == 0:
            cum = "—"
        else:
            cum = f"{(yf / baseline - 1.0) * 100.0:+.2f}%"
        out.append([delta, cum])
    return out


# Keep old name as thin wrapper for any other callers
def _pct_change_vs_prior(y_vals: list[float]) -> list[str]:
    """One label per point: percent change from previous point (first point → '—')."""
    out: list[str] = []
    for i, y in enumerate(y_vals):
        if i == 0:
            out.append("—")
            continue
        prev = float(y_vals[i - 1])
        yf = float(y)
        if abs(prev) < 1e-12:
            out.append("—")
        else:
            pct = (yf / prev - 1.0) * 100.0
            out.append(f"{pct:+.2f}%")
    return out


_NAV_HOVER = (
    "<b>%{fullData.name}</b><br>"
    "%{x|%b %d, %Y}<br>"
    "$%{y:,.2f}<br>"
    "Δ vs prior: %{customdata[0]}<br>"
    "Cumulative % Chg: %{customdata[1]}<extra></extra>"
)


def build_nav_figure() -> go.Figure:
    """
    NAV chart: BOT (after fees) vs SPX & NDX (rebased to same start capital).

    Timeline logic:
      - summary_df row date = 1st of the month (BOT Start value)
      - Each row's bot_end_after_fees = end-of-month NAV
      - Inception = Nov 13: strategy was flat at $30K from Nov 1 → Nov 13
      - From Nov 13 → Nov 30: NAV rises to first bot_end_after_fees ($34,338)

    Points plotted per series:
      Nov 1  (row[0].date)       → $30K  (flat pre-inception)
      Nov 13 (PROGRAM_INCEPTION) → $30K  (inception, still $30K)
      Dec 1  (next month start)  → $34,338  (end-of-Nov NAV, on grid line)
      … completed months use the 1st of the following month on the x-axis.

    Mid-month: rows after the tearsheet as-of month are hidden. The month-stub point
    (e.g. May 1) stays on the x-axis; TEARSHEET_CHART_EXTRA_DATE may add one further
    point after it (see TEARSHEET_CHART_EXTRA_NAV_USD).
    """
    fig = go.Figure()
    if summary_df.empty:
        fig.add_annotation(text="No data", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    nav_df = _summary_through_current_month(summary_df)
    if nav_df.empty:
        fig.add_annotation(text="No data", xref="paper", yref="paper",
                           x=0.5, y=0.5, showarrow=False)
        return fig

    # When the last row is the current month, exclude the prior row (avoids two
    # points 1 day apart: April 30 + May 1 both near the May tick).
    cur_start = _first_of_calendar_month(_chart_today())
    if len(nav_df) >= 2 and pd.Timestamp(nav_df["date"].iloc[-1]) == cur_start:
        nav_df = pd.concat([nav_df.iloc[:-2], nav_df.iloc[[-1]]], ignore_index=True)

    month_close_dates = _month_close_x_positions(nav_df["date"])

    # ── BOT NAV ──────────────────────────────────────────────────────────────
    # Nov 1 → flat $30K → Nov 13 → month-close xs (… Apr 30 then May 1 when May is in-progress)
    bot_x = (
        [nav_df["date"].iloc[0]]
        + [pd.Timestamp(PROGRAM_INCEPTION)]
        + month_close_dates
    )
    bot_y = (
        [STARTING_CAPITAL, STARTING_CAPITAL]
        + list(nav_df["bot_end_after_fees"].astype(float))
    )

    # ── SPX rebased ───────────────────────────────────────────────────────────
    # Same shape: flat until inception, then cumulative from month-end to month-end
    spx_y = [STARTING_CAPITAL, STARTING_CAPITAL]
    spx_cum = 1.0
    for ret in nav_df["spx_ret"].astype(float):
        spx_cum *= (1 + ret)
        spx_y.append(STARTING_CAPITAL * spx_cum)

    # ── NDX rebased ───────────────────────────────────────────────────────────
    ndx_y = [STARTING_CAPITAL, STARTING_CAPITAL]
    ndx_cum = 1.0
    for ret in nav_df["ndx_ret"].astype(float):
        ndx_cum *= (1 + ret)
        ndx_y.append(STARTING_CAPITAL * ndx_cum)

    # Optional extra x (e.g. May 12) after the month stub (May 1); NAV placeholder until set.
    _nx_before_extra = len(bot_x)
    bot_x, bot_y = _append_tearsheet_chart_extra_date(bot_x, bot_y, TEARSHEET_CHART_EXTRA_NAV_USD)
    if len(bot_x) > _nx_before_extra:
        spx_y = list(spx_y) + [float(spx_y[-1])]
        ndx_y = list(ndx_y) + [float(ndx_y[-1])]

    bot_hover_data = _hover_customdata([float(v) for v in bot_y], STARTING_CAPITAL)

    fig.add_trace(go.Scatter(
        x=bot_x, y=bot_y,
        mode="lines+markers",
        line={"color": PRIMARY_COLOR, "width": 2.5},
        marker={"size": 5, "color": PRIMARY_COLOR},
        name="Momentum Pacer (Net of Fees)",
        customdata=np.asarray(bot_hover_data, dtype=object),
        hovertemplate=_NAV_HOVER,
        yaxis="y",
    ))

    spx_hover_data = _hover_customdata([float(v) for v in spx_y], STARTING_CAPITAL)
    fig.add_trace(go.Scatter(
        x=bot_x, y=spx_y,
        mode="lines", line={"color": "#E67E22", "dash": "dash", "width": 1.5},
        name="SPX TR (rebased)", opacity=0.8,
        customdata=np.asarray(spx_hover_data, dtype=object),
        hovertemplate=_NAV_HOVER,
        yaxis="y",
    ))

    ndx_hover_data = _hover_customdata([float(v) for v in ndx_y], STARTING_CAPITAL)
    fig.add_trace(go.Scatter(
        x=bot_x, y=ndx_y,
        mode="lines", line={"color": "#8E44AD", "dash": "dot", "width": 1.5},
        name="NDX (rebased)", opacity=0.8,
        customdata=np.asarray(ndx_hover_data, dtype=object),
        hovertemplate=_NAV_HOVER,
        yaxis="y",
    ))

    # ── Inception annotation ──────────────────────────────────────────────────
    fig.add_annotation(
        x=pd.Timestamp(PROGRAM_INCEPTION),
        y=STARTING_CAPITAL,
        text=f"Live Inception<br>{PROGRAM_INCEPTION.strftime('%b %d')}<br>${STARTING_CAPITAL:,.0f}",
        showarrow=True,
        arrowhead=2,
        arrowsize=1,
        arrowwidth=1.5,
        arrowcolor=PRIMARY_COLOR,
        # Straight vertical: label centered above the point (ax=0)
        ax=0,
        ay=-72,
        xanchor="center",
        yanchor="bottom",
        font={"size": 9, "color": PRIMARY_COLOR},
        bgcolor="rgba(255,255,255,0.9)",
        bordercolor=PRIMARY_COLOR,
        borderwidth=1.5,
    )

    # Legend below the plot (not y≈1) so it never collides with the title
    fig.update_layout(
        title={
            "text": "<u>Compounded NAV Since Inception</u>",
            "x": 0.5,
            "xanchor": "center",
            "y": 0.97,
            "yanchor": "top",
            "pad": {"t": 8, "b": 4},
        },
        template="ggplot2",
        plot_bgcolor=GREY_BG,
        paper_bgcolor=WHITE_BG,
        xaxis_title="Date",
        autosize=True,
        margin={"l": 110, "r": 140, "t": 72, "b": 128},
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.30,
            "xanchor": "center",
            "x": 0.5,
            "bgcolor": "rgba(255,255,255,0.92)",
            "bordercolor": "rgba(0,0,0,0.12)",
            "borderwidth": 1,
            "font": {"size": 11},
        },
    )
    x_right = max(pd.Timestamp(t) for t in bot_x) + pd.Timedelta(days=10)
    x_left = min(pd.Timestamp(t) for t in bot_x) - pd.Timedelta(days=7)
    fig.update_xaxes(
        showgrid=True,
        automargin=True,
        title_standoff=12,
        range=[x_left, x_right],
    )
    # ── Compute shared y range ────────────────────────────────────────────────
    # Both axes share the same numeric dollar range. yaxis2 is just a relabelled
    # mirror: its tick POSITIONS are dollar values, its tick LABELS are % vs baseline.
    all_y = [float(v) for v in bot_y + spx_y + ndx_y]
    y_min = min(all_y)
    y_max = max(all_y)
    pad = max((y_max - y_min) * 0.05, STARTING_CAPITAL * 0.01)
    y_lo = y_min - pad
    y_hi = y_max + pad

    # Choose a round dollar step that gives ~5-8 ticks across the visible range.
    raw_step = (y_hi - y_lo) / 6.0
    for step in [500, 1000, 2000, 2500, 5000, 10000, 20000]:
        if step >= raw_step:
            dollar_step = step
            break
    else:
        dollar_step = 10000

    first_tick = math.ceil(y_lo / dollar_step) * dollar_step
    tickvals: list[float] = []
    t = first_tick
    while t <= y_hi:
        tickvals.append(float(t))
        t += dollar_step

    # Plotly only renders yaxis2 when at least one trace is assigned to it.
    # This invisible trace spans the full dollar range and forces the axis to appear.
    fig.add_trace(go.Scatter(
        x=[bot_x[0], bot_x[-1]],
        y=[y_lo, y_hi],
        mode="lines",
        line={"color": "rgba(0,0,0,0)", "width": 0},
        showlegend=False,
        hoverinfo="skip",
        yaxis="y2",
    ))

    # Each tickval is a dollar amount; label it as % change from STARTING_CAPITAL.
    # Use "0%" for the baseline tick, "+N%" for positive, "−N%" for negative.
    def _pct_label(v: float) -> str:
        pct = (v / STARTING_CAPITAL - 1.0) * 100.0
        if abs(pct) < 0.5:
            return "0%"
        return f"+{pct:.0f}%" if pct > 0 else f"{pct:.0f}%"

    ticktext = [_pct_label(v) for v in tickvals]

    fig.update_layout(
        yaxis=dict(
            title=dict(
                text=f"NAV (${STARTING_CAPITAL:,.0f} baseline)",
                standoff=25,
            ),
            range=[y_lo, y_hi],
            showgrid=True,
            automargin=True,
            tickprefix="$",
            tickformat=",.0f",
            zeroline=False,
        ),
        yaxis2=dict(
            title=dict(
                text="Return (%)",
                standoff=15,
            ),
            overlaying="y",
            side="right",
            anchor="x",
            # Same dollar range as yaxis — ticks placed at dollar values,
            # labelled as % change vs STARTING_CAPITAL.
            range=[y_lo, y_hi],
            tickmode="array",
            tickvals=tickvals,
            ticktext=ticktext,
            showticklabels=True,
            visible=True,
            showgrid=False,
            zeroline=False,
            automargin=True,
        ),
    )
    return fig


def build_drawdown_figure() -> go.Figure:
    """Drawdown from peak. Mirrors Y&Q's build_drawdown_figure()."""
    fig = go.Figure()
    if summary_df.empty:
        return fig

    nav_df = _summary_through_current_month(summary_df)
    if nav_df.empty:
        return fig

    eq = nav_df["bot_end_after_fees"].astype(float)
    pk = eq.cummax()
    dd = ((eq / pk) - 1.0) * 100.0
    dd_x = _month_close_x_positions(nav_df["date"])
    dd_vals = [float(v) for v in dd.values]
    dd_x, dd_vals = _append_tearsheet_chart_extra_date(dd_x, dd_vals, None)

    fig.add_trace(go.Scatter(
        x=dd_x, y=dd_vals,
        mode="lines", fill="tozeroy",
        line={"color": ACCENT_RED, "width": 1.5},
        name="Momentum Pacer Drawdown",
        hovertemplate=(
            "<b>%{fullData.name}</b><br>"
            "%{x|%b %d, %Y}<br>"
            "%{y:.2f}%<extra></extra>"
        ),
    ))

    fig.update_layout(
        title={"text": "<u>Drawdown from Peak</u>",
               "x": 0.5, "xanchor": "center"},
        template="ggplot2",
        plot_bgcolor=GREY_BG, paper_bgcolor=WHITE_BG,
        xaxis_title="Date", yaxis_title="Drawdown (%)",
        autosize=True,
        # Extra bottom margin so "Date" + month ticks never collide with page footer
        margin={"l": 50, "r": 20, "t": 50, "b": 88},
    )
    x_right = max(pd.Timestamp(t) for t in dd_x) + pd.Timedelta(days=10)
    x_left = min(pd.Timestamp(t) for t in dd_x) - pd.Timedelta(days=7)
    fig.update_xaxes(
        showgrid=True,
        automargin=True,
        title_standoff=22,
        range=[x_left, x_right],
    )
    fig.update_yaxes(showgrid=True)
    return fig


# ==============================================================================
# PERFORMANCE SUMMARY TABLE  (spreadsheet style – mirrors screenshot + Y&Q style)
# ==============================================================================

def _cell_style(val_str: str, extra: dict | None = None) -> dict:
    """Green/red background for % values, white otherwise."""
    style = {"fontSize": "0.78rem", "padding": "4px 8px", "whiteSpace": "nowrap",
             "textAlign": "right"}
    try:
        v = float(str(val_str).replace("%", "").replace("$", "").replace(",", ""))
        if v > 0:
            style["backgroundColor"] = "#d4edda"
        elif v < 0:
            style["backgroundColor"] = "#f8d7da"
        else:
            style["backgroundColor"] = "white"
    except (ValueError, AttributeError):
        style["textAlign"] = "left"
    if extra:
        style.update(extra)
    return style


def build_performance_summary_table():
    """
    Spreadsheet-style monthly table matching the screenshot exactly:
    Month | SPX Start | SPX End | NDX Start | NDX End |
    BOT Start | BOT End After Fees |
    SPX Returns% | NDX Returns% |
    BOT Returns Before Fees% | BOT Fees% | BOT Returns After Fees% | Cumulative Net%
    Plus Net% and Net$ footer rows.
    """
    if _display_summary_df.empty:
        return html.P("No data available.", className="text-danger")

    # Header columns
    cols = [
        "Month",
        "SPX Start", "SPX End",
        "NDX Start", "NDX End",
        "BOT Start", "BOT End\nAfter Fees",
        "SPX\nReturns%", "NDX\nReturns%",
        "BOT Returns\nBefore Fees%", "BOT Fees%",
        "BOT Returns\nAfter Fees%", "Cumul.\nNet%",
    ]

    # Column groups: index | spx | ndx | bot$ | spx% ndx% | bot% fees% net% cumul%
    group_borders = {6: "3px solid #dee2e6", 7: "none", 9: "3px solid #dee2e6"}

    th_style_base = {
        "backgroundColor": GREY_BG, "color": "#000",
        "fontSize": "0.75rem", "padding": "4px 6px",
        "whiteSpace": "pre-wrap", "textAlign": "center",
        "verticalAlign": "bottom",
    }

    header_cells = []
    for i, col in enumerate(cols):
        sty = dict(th_style_base)
        if i in group_borders:
            sty["borderLeft"] = group_borders[i]
        header_cells.append(html.Th(col, style=sty))

    thead = html.Thead(html.Tr(header_cells))

    # Data rows
    body_rows = []
    for _, row in _display_summary_df.iterrows():
        month_label = row["date"].strftime("%b-%Y")

        def fmt_idx(v):
            try: return f"{float(v):,.2f}"
            except: return "—"

        def fmt_dollar(v):
            try: return f"${float(v):,.0f}"
            except: return "—"

        def fmt_pct(v):
            try: return f"{float(v)*100:.2f}%"
            except: return "—"

        vals = [
            month_label,
            fmt_idx(row["spx_start"]),  fmt_idx(row["spx_end"]),
            fmt_idx(row["ndx_start"]),  fmt_idx(row["ndx_end"]),
            fmt_dollar(row["bot_start"]), fmt_dollar(row["bot_end_after_fees"]),
            fmt_pct(row["spx_ret"]),    fmt_pct(row["ndx_ret"]),
            fmt_pct(row["bot_gross_ret"]), fmt_pct(row["bot_fees_pct"]),
            fmt_pct(row["bot_net_ret"]),   fmt_pct(row["cumulative_net"]),
        ]

        cells = []
        for i, v in enumerate(vals):
            sty = _cell_style(v)
            if i == 0:
                sty["textAlign"] = "left"
                sty["fontWeight"] = "500"
                sty["backgroundColor"] = "white"
            # dollar columns: white background, no sign colouring
            if i in (1, 2, 3, 4, 5, 6):
                sty["backgroundColor"] = "white"
                sty["textAlign"] = "right"
            if i in group_borders:
                sty["borderLeft"] = group_borders[i]
            cells.append(html.Td(v, style=sty))
        body_rows.append(html.Tr(cells))

    # Net% footer row
    if net_totals:
        def _nt(k): return f"{float(net_totals.get(k, 0))*100:.2f}%"

        def _sign_bg(val_str: str) -> str:
            """Return green/red/white based on numeric sign. Never raises."""
            try:
                v = float(str(val_str).replace("%", "").replace("$", "").replace(",", ""))
                if v > 0:   return "#d4edda"
                if v < 0:   return "#f8d7da"
                return "white"
            except (ValueError, AttributeError):
                return GREY_BG

        net_pct_vals = [
            "Net %", "", "", "", "", "", "",
            _nt("spx_net_pct"), _nt("ndx_net_pct"),
            _nt("bot_gross_pct"), _nt("bot_fees_pct"),
            _nt("bot_net_pct"), _nt("bot_net_pct"),
        ]
        net_pct_cells = []
        for i, v in enumerate(net_pct_vals):
            bg = GREY_BG if (i == 0 or v == "") else _sign_bg(v)
            sty = {
                "fontSize": "0.78rem", "padding": "4px 8px",
                "whiteSpace": "nowrap", "textAlign": "left" if i == 0 else "right",
                "fontWeight": "700", "backgroundColor": bg,
            }
            if i in group_borders:
                sty["borderLeft"] = group_borders[i]
            net_pct_cells.append(html.Td(v, style=sty))
        body_rows.append(html.Tr(net_pct_cells,
                                  style={"borderTop": "2px solid #333"}))

        # Net$ footer row
        def _nd(k):
            try: return f"${float(net_totals.get(k, 0)):,.2f}"
            except: return "—"
        net_dol_vals = [
            "Net $", "", "", "", "", "", "",
            _nd("spx_net_dollar"), _nd("ndx_net_dollar"),
            _nd("bot_gross_dollar"), _nd("bot_fees_dollar"),
            _nd("bot_net_dollar"), _nd("bot_net_dollar"),
        ]
        net_dol_cells = []
        for i, v in enumerate(net_dol_vals):
            sty = {"fontSize": "0.78rem", "padding": "4px 8px",
                   "whiteSpace": "nowrap", "textAlign": "right",
                   "fontWeight": "700", "backgroundColor": "#E8F4FD"}
            if i == 0:
                sty["textAlign"] = "left"
                sty["backgroundColor"] = GREY_BG
            if i in group_borders:
                sty["borderLeft"] = group_borders[i]
            net_dol_cells.append(html.Td(v, style=sty))
        body_rows.append(html.Tr(net_dol_cells))

    return dbc.Table(
        [thead, html.Tbody(body_rows)],
        bordered=True, hover=True, size="sm",
        className="table-responsive",
        style={"width": "100%", "margin": "0 auto",
               "pageBreakInside": "avoid"},
    )


def _fee_slab_structure_rows() -> list:
    """
    Brief summary, slab table, and a single footnote row pointing to the Disclosure Document.
    """
    explain = html.Tr([
        html.Td(
            html.Small(
                "Net new profits above the High-Water Mark are measured against a Benchmark dollar amount "
                "for the month: the S&P 500's monthly percentage return times the Program's nominal trading level. "
                "When that Benchmark return is positive, the incentive fee is graduated — each slab rate applies "
                "only to the profits falling in that slice (0–1× through >4× of the Benchmark dollar amount; see table). "
                "When the Benchmark return is zero or negative, the incentive fee is 50% of qualifying net new profits; "
                "these slabs do not apply.",
                className="text-muted fst-italic",
            ),
            colSpan=2,
        ),
    ])
    th_style = {"fontSize": "0.78rem", "verticalAlign": "bottom"}
    thead = html.Thead(html.Tr([
        html.Th("Slab", className=HEADER_ROW_CLASS, style=th_style),
        html.Th(
            "Net new profits slice (vs Benchmark dollar return for the month)",
            className=HEADER_ROW_CLASS,
            style=th_style,
        ),
        html.Th(
            "Incentive fee on profits in that slice",
            className=HEADER_ROW_CLASS,
            style=th_style,
        ),
    ]))
    tbody = html.Tbody([
        html.Tr([
            html.Td(slab, style={"fontWeight": "600", "whiteSpace": "nowrap"}),
            html.Td(band),
            html.Td(rate, style={"whiteSpace": "nowrap"}),
        ])
        for slab, band, rate in FEE_SLAB_BANDS_DISPLAY
    ])
    nested = dbc.Table(
        [thead, tbody],
        bordered=True,
        hover=True,
        size="sm",
        className="mb-0",
    )
    table_row = html.Tr([
        html.Td(
            nested,
            colSpan=2,
            style={"padding": "6px 0", "borderTop": "none"},
        ),
    ])
    doc_row = html.Tr([
        html.Td(
            html.Small(
                "Definitions, worked examples, and rounding: see the AlgoMinds Financial LLC Disclosure Document.",
                className="text-muted fst-italic",
            ),
            colSpan=2,
        ),
    ])
    return [explain, table_row, doc_row]


# ==============================================================================
# DASH APP  –  structure mirrors Y&Q serve_layout()
# ==============================================================================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, "/assets/styles.css"],
    suppress_callback_exceptions=True,
    title="Algominds – Momentum Pacer",
)


def serve_layout():
    today      = datetime.now()
    first_day  = today.replace(day=1)
    days_ahead = -first_day.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    first_monday = first_day + timedelta(days=days_ahead)
    if first_monday.day <= 2:
        first_monday += timedelta(days=7)
    last_updated = first_monday.strftime("%B %d, %Y")

    inception_str = PROGRAM_INCEPTION.strftime("%B %d, %Y")
    latest_str = (
        _display_summary_df["date"].max().strftime("%B %Y")
        if not _display_summary_df.empty
        else PROGRAM_INCEPTION.strftime("%B %Y")
    )

    return dbc.Container(
        id="page-container",
        fluid=True,
        className="py-4",
        style={"maxWidth": "1400px"},
        children=[

            # ── Disclaimer overlay ──────────────────────────────────────────────
            html.Div(
                id="disclaimer-screen",
                style={"padding": "4rem", "textAlign": "center"},
                children=html.Div(
                    [
                        html.H2("Important Notice", className="mb-4"),
                        html.Hr(),
                        html.P(
                            "THE MOMENTUM PACER PROGRAM IS A PROPRIETARY TRADING STRATEGY. "
                            "THIS PERFORMANCE DATA IS FOR INFORMATIONAL PURPOSES ONLY AND IS "
                            "NOT A SOLICITATION TO INVEST. PAST PERFORMANCE IS NOT INDICATIVE "
                            "OF FUTURE RESULTS.",
                            className="mb-2",
                            style={"fontWeight": "bold"},
                        ),
                        html.P(
                            "Past performance is not necessarily indicative of future results. "
                            "The risk of loss in commodity trading can be substantial. "
                            "This information does not constitute investment advice.",
                            className="text-muted mb-4",
                        ),
                        dbc.Button(
                            "Accept & Continue", id="accept-button",
                            color="success",
                            style={"backgroundColor": PRIMARY_COLOR,
                                   "borderColor": PRIMARY_COLOR},
                        ),
                    ],
                    style={
                        "backgroundColor": GREY_BG,
                        "padding": "4rem", "borderRadius": "1rem",
                        "width": "90vw", "maxWidth": "600px",
                        "margin": "10vh auto",
                        "boxShadow": "0 4px 12px rgba(0,0,0,0.15)",
                    },
                ),
            ),

            # ── Main content ────────────────────────────────────────────────────
            html.Div(
                id="main-app",
                style={"display": "none"},
                children=[

                    # ── Header  (identical structure to Y&Q) ──────────────────
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Img(
                                    src=logo_src,
                                    className="img-fluid",
                                    style={"maxHeight": "100px",
                                           "height": "auto", "width": "auto"},
                                    alt="Algominds Financial LLC Logo",
                                ) if logo_src else html.Div(style={"height": "80px"}),
                                width=2,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.H2("Algominds Financial LLC",
                                                className="text-center"),
                                        html.H5("Momentum Pacer Program",
                                                className="text-center text-muted"),
                                    ],
                                    style={"lineHeight": "1.2", "paddingTop": "20px"},
                                ),
                                width=8,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.H6("Last Updated",
                                                        className="text-end text-secondary mb-1"),
                                                html.H5(last_updated,
                                                        className="text-end",
                                                        style={"color": PRIMARY_COLOR}),
                                            ],
                                            className="d-none d-md-block",
                                            style={"paddingTop": "30px"},
                                        ),
                                        html.Div(
                                            [
                                                html.Small("Last Updated",
                                                           className="d-block text-end text-secondary mb-1"),
                                                html.Small(last_updated,
                                                           className="d-block text-end",
                                                           style={"color": PRIMARY_COLOR}),
                                            ],
                                            className="d-block d-md-none",
                                            style={"paddingTop": "20px"},
                                        ),
                                    ]
                                ),
                                width=2,
                            ),
                        ],
                        align="center",
                        style={"backgroundColor": GREY_BG, "padding": "10px 0",
                               "pageBreakInside": "avoid"},
                        className="header-row",
                    ),
                    html.Hr(),

                    # ── Description ───────────────────────────────────────────
                    html.Div(
                        [
                            html.P(
                                "Algominds Financial LLC — CTA & CPO. "
                                f"Momentum Pacer Trading Program (live inception {inception_str}).",
                                className="lead text-center",
                            ),
                            html.P(
                                "Instruments: Nasdaq-100 E-mini (NQ) / Micro Nasdaq-100 (MNQ). "
                                "Objective: Systematic momentum capture in the Nasdaq-100 futures "
                                "with adaptive position sizing and disciplined risk management. "
                                "SPX and NDX on this tearsheet are shown as benchmarks for context only. "
                                "Per the Disclosure Document, the monthly incentive (performance) fee is "
                                "determined against the S&P 500 (the Benchmark) as described in the Fee Slab "
                                "Structure, on net new trading profits and subject to a high-water mark.",
                                className="text-center mb-5",
                            ),
                        ],
                        className="description",
                    ),

                    # ── Error banner ───────────────────────────────────────────
                    dbc.Alert(f"Data error: {LOAD_ERROR}", color="danger",
                              className="mb-3") if LOAD_ERROR else html.Div(),

                    # ── NAV Chart (wrapper avoids caption / x-axis label overlap)
                    html.Div(
                        [
                            dcc.Graph(
                                id="mp-nav-graph",
                                figure=build_nav_figure(),
                                config={"displayModeBar": False, "responsive": True},
                                style={
                                    "width": "100%",
                                    "minHeight": "440px",
                                    "marginBottom": "0",
                                    "pageBreakInside": "avoid",
                                },
                            ),
                        ],
                        style={
                            "marginBottom": "0.25rem",
                            "paddingBottom": "0.5rem",
                            "overflow": "visible",
                        },
                    ),
                    html.P(
                        f"Growth of a ${STARTING_CAPITAL:,.0f} investment from inception ({inception_str}) "
                        f"to {latest_str}. NAV reflects compounded performance, net of all fees. "
                        "The strategy trades NQ / MNQ (Nasdaq-100 futures) exclusively. "
                        "SPX TR and NDX are rebased to the same starting capital for benchmark comparison only.",
                        className="text-center small text-muted fst-italic px-3",
                        style={
                            "marginTop": "1.5rem",
                            "marginBottom": "2.25rem",
                            "paddingTop": "0.75rem",
                            "lineHeight": "1.45",
                            "maxWidth": "920px",
                            "marginLeft": "auto",
                            "marginRight": "auto",
                        },
                    ),

                    # ── Performance Summary Table ──────────────────────────────
                    html.H5(
                        "Performance Summary",
                        className="text-center mb-2",
                        style={"marginTop": "0.5rem", "paddingTop": "0.25rem"},
                    ),
                    html.Div(
                        build_performance_summary_table(),
                        className="table-responsive mb-5",
                        style={"overflowX": "auto",
                               "pageBreakInside": "avoid"},
                    ),

                    # ── Strategy Overview  +  Risk & Controls  ─────────────────
                    # (same 2-column card layout as Y&Q)
                    dbc.Row(
                        [
                            # LEFT: Strategy Overview
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader(
                                            html.H6("Strategy Overview", className="mb-0"),
                                            className=HEADER_ROW_CLASS,
                                        ),
                                        dbc.CardBody(
                                            dbc.Table(
                                                [
                                                    html.Thead(
                                                        html.Tr([html.Th("Strategy Description",
                                                                          colSpan=3,
                                                                          className=HEADER_ROW_CLASS)]),
                                                        className="bg-light",
                                                    ),
                                                    html.Tbody([
                                                        html.Tr([
                                                            html.Td(
                                                                html.P(
                                                                    "The Momentum Pacer Program is a systematic "
                                                                    "trend-following strategy trading exclusively in "
                                                                    "Nasdaq-100 futures (NQ / MNQ). The program uses "
                                                                    "quantitative momentum signals to identify and "
                                                                    "capture directional moves in the Nasdaq-100. "
                                                                    "S&P 500 (SPX) and Nasdaq-100 (NDX) index levels "
                                                                    "are shown as benchmarks for comparison only — "
                                                                    "the strategy trades Nasdaq-100 futures only and does "
                                                                    "not trade the S&P 500 cash index or related products for alpha. "
                                                                    "The contractual incentive fee uses the S&P 500 monthly return "
                                                                    "(the Benchmark in the Disclosure Document) solely as a "
                                                                    "reference for fee calculation. "
                                                                    "Risk is managed through adaptive position sizing "
                                                                    "and stop-loss orders. "
                                                                    "The program started live trading on November 13, 2025."
                                                                ),
                                                                colSpan=3,
                                                                style={"whiteSpace": "normal",
                                                                       "fontStyle": "italic"},
                                                            )
                                                        ]),
                                                        html.Tr([html.Td("", colSpan=3,
                                                                          style={"height": LEFT_TABLE_GAPS})]),
                                                        html.Tr([
                                                            html.Th("Methodology", colSpan=3,
                                                                     className="bg-light"),
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Trading Style"),
                                                            html.Td(html.Span("✓ Momentum / Trend",
                                                                               style={"color": ACCENT_GREEN})),
                                                            html.Td(html.Span("✗ Mean Reversion",
                                                                               style={"color": SECONDARY_COLOR})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Decision Making"),
                                                            html.Td(html.Span("✓ Systematic",
                                                                               style={"color": ACCENT_GREEN})),
                                                            html.Td(html.Span("✗ Discretionary",
                                                                               style={"color": SECONDARY_COLOR})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Execution"),
                                                            html.Td(html.Span("✓ Fully automated*",
                                                                               style={"color": ACCENT_GREEN})),
                                                            html.Td(html.Span("✗ Manual",
                                                                               style={"color": SECONDARY_COLOR})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(
                                                                html.Small(
                                                                    "*Order generation and routing are fully systematic "
                                                                    "and automated; fills remain subject to exchange, "
                                                                    "FCM, and market conditions.",
                                                                    className="text-muted fst-italic",
                                                                ),
                                                                colSpan=3,
                                                            ),
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Instruments"),
                                                            html.Td("NQ / MNQ (Nasdaq-100 E-mini & Micro)", colSpan=2),
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Exchanges"),
                                                            html.Td("CME Group", colSpan=2),
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Account Start Date"),
                                                            html.Td(inception_str, colSpan=2),
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Initial Capital"),
                                                            html.Td(f"${STARTING_CAPITAL:,.0f}", colSpan=2),
                                                        ]),
                                                        html.Tr([html.Td("", colSpan=3,
                                                                          style={"height": LEFT_TABLE_GAPS})]),
                                                        html.Tr([
                                                            html.Th("Risk Controls", colSpan=3,
                                                                     className="bg-light"),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ Stop Losses",
                                                                               style={"color": ACCENT_GREEN})),
                                                            html.Td(html.Span("✓ Position Sizing",
                                                                               style={"color": ACCENT_GREEN})),
                                                            html.Td(html.Span("✓ High-Water Mark",
                                                                               style={"color": ACCENT_GREEN})),
                                                        ]),
                                                    ]),
                                                ],
                                                striped=False, bordered=True,
                                                hover=True, size="sm",
                                            )
                                        ),
                                    ],
                                    outline=True, className="mb-4",
                                ),
                                width=6,
                            ),

                            # RIGHT: Fee Structure  (mirrors Y&Q's Transaction Fees card)
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader(
                                            html.H6("Fee Structure", className="mb-0"),
                                            className=HEADER_ROW_CLASS,
                                        ),
                                        dbc.CardBody(
                                            dbc.Table(
                                                [
                                                    html.Thead(
                                                        html.Tr([html.Th("Terms & Fees",
                                                                          colSpan=2,
                                                                          className=HEADER_ROW_CLASS)])
                                                    ),
                                                    html.Tbody([
                                                        html.Tr([html.Td("Management Fee"),
                                                                 html.Td("None")]),
                                                        html.Tr([html.Td("Performance Fee"),
                                                                 html.Td(
                                                                     "Monthly incentive fee on net new trading profits "
                                                                     "(subject to High-Water Mark), determined by reference "
                                                                     "to the S&P 500 monthly return (the Benchmark) per the "
                                                                     "AlgoMinds Disclosure Document — graduated slabs when "
                                                                     "the Benchmark is positive; different rule when the "
                                                                     "Benchmark is zero or negative (see Fee Slab Structure)."
                                                                 )]),
                                                        html.Tr([html.Td("High-Water Mark"),
                                                                 html.Td("Yes — fee only on new net gains above prior HWM")]),
                                                        html.Tr([html.Td("Fee Frequency"),
                                                                 html.Td("Monthly")]),
                                                        html.Tr([html.Td(""), html.Td("")]),
                                                        html.Tr([
                                                            html.Th("Fee Slab Structure",
                                                                     colSpan=2,
                                                                     className="bg-light"),
                                                        ]),
                                                        *_fee_slab_structure_rows(),
                                                        html.Tr([html.Td(""), html.Td("")]),
                                                        html.Tr([
                                                            html.Th("Account Information",
                                                                     colSpan=2,
                                                                     className="bg-light"),
                                                        ]),
                                                        html.Tr([html.Td("Minimum Investment"),
                                                                 html.Td("$30,000")]),
                                                        html.Tr([html.Td("Notional Funding"),
                                                                 html.Td("Available")]),
                                                        html.Tr([html.Td("Broker / FCM"),
                                                                 html.Td("TradeStation")]),
                                                        html.Tr([html.Td("Liquidity"),
                                                                 html.Td("Withdrawals with 7 days' notice")]),
                                                        html.Tr([html.Td("Lockup Period"),
                                                                 html.Td("None")]),
                                                    ]),
                                                ],
                                                striped=False, bordered=True,
                                                hover=True, size="sm",
                                                className="table-responsive",
                                            )
                                        ),
                                    ],
                                    outline=True, className="mb-4",
                                ),
                                width=6,
                            ),
                        ],
                        justify="start",
                        className="mb-2",
                    ),

                    # ── Metrics row  (mirrors Y&Q: perf metrics left, stats right)
                    dbc.Row(
                        [
                            # LEFT: Performance Metrics
                            dbc.Col(
                                [
                                    dbc.Card(
                                        [
                                            dbc.CardHeader(
                                                html.H6("Performance Metrics", className="mb-0")
                                            ),
                                            dbc.CardBody(
                                                dbc.Table.from_dataframe(
                                                    perf_df,
                                                    striped=False, bordered=True,
                                                    hover=True, size="sm",
                                                    className="fixed-cols",
                                                ) if not perf_df.empty
                                                else html.P("No data.")
                                            ),
                                        ],
                                        outline=True, className="mb-2",
                                    ),
                                ],
                                width=6,
                            ),
                            # RIGHT: Monthly Performance Statistics
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader(
                                            html.H6("Monthly Performance Statistics",
                                                    className="mb-0")
                                        ),
                                        dbc.CardBody(
                                            dbc.Table.from_dataframe(
                                                stats_df,
                                                striped=False, bordered=True,
                                                hover=True, size="sm",
                                                className="fixed-cols",
                                            ) if not stats_df.empty
                                            else html.P("No data.")
                                        ),
                                        dbc.CardFooter(
                                            html.Small(
                                                f"Statistics calculated from actual monthly return data "
                                                f"from {inception_str} to {latest_str}.",
                                                className="text-muted fst-italic",
                                            )
                                        ),
                                    ],
                                    outline=True, className="mb-2",
                                ),
                                width=6,
                            ),
                        ],
                        justify="start",
                        className="mb-2",
                    ),

                    # ── Investor Information  (full width, mirrors Y&Q) ─────────
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Card(
                                    [
                                        dbc.CardHeader(
                                            html.H6("Investor Information", className="mb-0")
                                        ),
                                        dbc.CardBody(
                                            dbc.Row([
                                                dbc.Col(
                                                    dbc.Table(
                                                        [
                                                            html.Thead(html.Tr([
                                                                html.Th("Terms & Fees"),
                                                                html.Th("Details"),
                                                            ])),
                                                            html.Tbody([
                                                                html.Tr([html.Td("Performance Fee"),
                                                                         html.Td(
                                                                             "Graduated vs S&P 500 Benchmark (Disclosure Document), "
                                                                             "monthly, HWM"
                                                                         )]),
                                                                html.Tr([html.Td("High Water Mark"),
                                                                         html.Td("Yes")]),
                                                                html.Tr([html.Td("Lockup Period"),
                                                                         html.Td("None")]),
                                                                html.Tr([html.Td("Liquidity"),
                                                                         html.Td("Withdrawals with 7 days' notice")]),
                                                                html.Tr([html.Td("Minimum Investment"),
                                                                         html.Td("$30,000")]),
                                                                html.Tr([html.Td("Notional Funding"),
                                                                         html.Td("Available")]),
                                                                html.Tr([html.Td("Execution FCM"),
                                                                         html.Td("TradeStation")]),
                                                            ]),
                                                        ],
                                                        striped=False, bordered=True,
                                                        hover=True, size="sm",
                                                    ),
                                                    width=6,
                                                ),
                                                dbc.Col(
                                                    dbc.Table(
                                                        [
                                                            html.Thead(html.Tr([
                                                                html.Th("Account Stats"),
                                                                html.Th("Current"),
                                                            ])),
                                                            html.Tbody([
                                                                html.Tr([
                                                                    html.Td("Starting Capital"),
                                                                    html.Td(f"${STARTING_CAPITAL:,.0f}"),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td("Current NAV (after fees)"),
                                                                    html.Td(
                                                                        f"${_display_summary_df['bot_end_after_fees'].iloc[-1]:,.2f}"
                                                                        if not _display_summary_df.empty else "—"
                                                                    ),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td("Total Net Gain"),
                                                                    html.Td(
                                                                        f"${net_totals.get('bot_net_dollar', 0):,.2f}"
                                                                        if net_totals else "—"
                                                                    ),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td("Total Fees Paid"),
                                                                    html.Td(
                                                                        f"${net_totals.get('bot_fees_dollar', 0):,.2f}"
                                                                        if net_totals else "—"
                                                                    ),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td("Inception Date"),
                                                                    html.Td(inception_str),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td("Months trading (approx.)"),
                                                                    html.Td(months_trading_elapsed_approx()),
                                                                ]),
                                                            ]),
                                                        ],
                                                        striped=False, bordered=True,
                                                        hover=True, size="sm",
                                                    ),
                                                    width=6,
                                                ),
                                            ])
                                        ),
                                    ],
                                    outline=True, className="mb-4",
                                ),
                                width=12,
                            ),
                        ],
                        className="mb-2",
                    ),

                    # ── Drawdown chart (wrapper keeps SVG from overlapping footer)
                    html.Div(
                        [
                            dcc.Graph(
                                id="drawdown-graph",
                                figure=build_drawdown_figure(),
                                config={"displayModeBar": False, "responsive": True},
                                style={
                                    "width": "100%",
                                    "minHeight": "360px",
                                    "marginBottom": "0",
                                },
                            ),
                        ],
                        className="mb-0",
                        style={
                            "marginBottom": "2.5rem",
                            "paddingBottom": "1.75rem",
                            "overflow": "visible",
                        },
                    ),

                    # ── Important Disclosure ──────────────────────────────────
                    dbc.Row(
                        dbc.Col(
                            html.Div(
                                [
                                    html.Strong("Important Disclosure: ", className="text-dark"),
                                    "This tear sheet is provided for informational purposes only and should not "
                                    "be interpreted as an offer, solicitation, or recommendation to invest. "
                                    "Performance information, if shown, may be unaudited and should be reviewed "
                                    "together with the applicable offering documents, advisory agreement, and risk "
                                    "disclosures. For more information about this strategy, please contact Hughes "
                                    "and Company at ",
                                    html.A("info@hughesandco.ltd", href="mailto:info@hughesandco.ltd"),
                                    " or 954 500 0500.",
                                ],
                                className="p-3 border rounded",
                                style={
                                    "backgroundColor": "#f8f9fa",
                                    "borderLeft": "4px solid #6c757d",
                                    "fontSize": "0.875rem",
                                },
                            ),
                            width=12,
                        ),
                        className="mb-4",
                    ),

                    html.Hr(className="my-4"),

                    # ── Footer / disclaimers  (identical to Y&Q) ───────────────
                    html.Div(
                        [
                            html.P(
                                "THE MOMENTUM PACER PROGRAM IS A PROPRIETARY TRADING STRATEGY. "
                                "THIS PERFORMANCE DATA IS FOR INFORMATIONAL PURPOSES ONLY AND IS "
                                "NOT A SOLICITATION TO INVEST. "
                                "PAST PERFORMANCE IS NOT INDICATIVE OF FUTURE RESULTS.",
                                className="text-center small fw-bold",
                            ),
                            html.P(
                                "Past performance is not necessarily indicative of future results. "
                                "The risk of loss in commodity trading can be substantial. "
                                "This information is for informational purposes only and does not "
                                "constitute investment advice or a solicitation to invest.",
                                className="text-center small text-muted fst-italic",
                            ),
                            html.P(
                                "For more information, contact Algominds Financial LLC",
                                className="text-center small text-muted mb-0",
                            ),
                        ],
                        className="pt-3 pb-5 mb-0",
                        style={"marginTop": "0.5rem"},
                    ),

                ],  # end main-app children
            ),  # end main-app Div
        ],
    )


app.layout = serve_layout


@app.callback(
    Output("disclaimer-screen", "style"),
    Output("main-app", "style"),
    Input("accept-button", "n_clicks"),
)
def show_main(n_clicks):
    if n_clicks and n_clicks > 0:
        return {"display": "none"}, {"display": "block"}
    return {"padding": "4rem", "textAlign": "center"}, {"display": "none"}


# ==============================================================================
if __name__ == "__main__":
    # Production (e.g. Cloudflare Tunnel): set MP_TS_PRODUCTION=1 to disable debug/reloader
    # (debug mode can confuse reverse proxies and cause 502s on callbacks).
    _prod = os.environ.get("MP_TS_PRODUCTION", "").strip().lower() in ("1", "true", "yes")
    _debug = not _prod
    print(f"[mp_ts] Momentum Pacer tearsheet starting...")
    print(f"[mp_ts] Data: {EXCEL_PATH.name}")
    print(f"[mp_ts] Open: http://127.0.0.1:8304  (production={_prod})")
    app.run(
        debug=_debug,
        use_reloader=_debug,
        port=8304,
        host="127.0.0.1",
    )
