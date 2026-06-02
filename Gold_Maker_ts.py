import os
import base64
from datetime import datetime

import pandas as pd
import numpy as np
import plotly.graph_objs as go

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import yfinance as yf
import quantstats as qs
from quantstats import utils
from collections import OrderedDict

# ==============================================================================
# 1) Read & encode the logo file as base64 (for Dash layout)
# ==============================================================================
logo_path = r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents\2_Hughes & Company Marketing\Branded Logo\Trianle-Only-Logo.png"
try:
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode("utf-8")
    logo_src = f"data:image/png;base64,{logo_b64}"
except FileNotFoundError:
    print(f"Error: Logo file not found at {logo_path}")
    logo_src = ""

# ==============================================================================
# 2) Read VADI DataFrame and validate
# ==============================================================================
# ── Give your strategy a single, reusable name ─────────────────────────────
STRATEGY_NAME = "TGM"     # ← change this to whatever you like

# ── CONFIG: Pick exactly which benchmarks to show ───────────────────────────
# Simply comment out any you don’t want to plot; leave the rest in the list
BENCHMARKS = [
    "^SP500TR",  # SPX Total Return
    "AGG",       # US Aggregate Bond
    "GLD",       # Gold ETF
    "BTC-USD",   # Bitcoin
    "ETH-USD",   # Ethereum
]

csv_path = r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents\3_Advisors Marketing (Tearsheets, PitchBooks, etc)\1. Tearsheet Project\TKP\VADI\GLD_Maker_VADI.csv"
try:
    VADI_df = pd.read_csv(csv_path, encoding="utf-8")
except UnicodeDecodeError:
    VADI_df = pd.read_csv(csv_path, encoding="cp1252")

# Ensure 'Date' column exists
if 'Date' not in VADI_df.columns:
    raise KeyError("CSV file must contain a 'Date' column")

# Convert 'Date' to datetime and set as index
VADI_df['Date'] = pd.to_datetime(VADI_df['Date'])
VADI_df.set_index('Date', inplace=True)

# map display‐name → raw symbol
bench_symbols = OrderedDict([
    ("SPXTR", "^SP500TR"),
    ("AGG Adj Close",    "AGG"),
    ("GLD",    "GLD"),
    ("BTC",    "BTC-USD"),
    ("ETH",    "ETH-USD"),
])

# Only keep the ones you listed in CONFIG
bench_symbols = {name:sym for name,sym in bench_symbols.items() if sym in BENCHMARKS}

# Download, align, and compute returns, cum, drawdown
bench_ret, bench_cum, bench_dd = {}, {}, {}
for name, sym in bench_symbols.items():
    full = utils.download_returns(sym)
    # align + fill gaps
    ret  = full.reindex(VADI_df.index).ffill().bfill().dropna()
    cum  = (1 + ret).cumprod()
    dd   = (cum / cum.cummax() - 1) * 100

    bench_ret[name] = ret
    bench_cum[name] = cum
    bench_dd[name]  = dd

# Find VADI column (try 'VADI', 'VADI', 'Value', 'Index')
possible_VADI_columns = ['VADI', 'VADI', 'Value', 'Index']
VADI_column = None
for col in possible_VADI_columns:
    if col in VADI_df.columns:
        VADI_column = col
        break
if VADI_column is None:
    numeric_cols = VADI_df.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        VADI_column = numeric_cols[0]
    else:
        raise KeyError("No numeric column found in CSV for VADI data (tried: 'VADI', 'VADI', 'Value', 'Index')")

# Calculate daily returns
daily_returns = VADI_df[VADI_column].pct_change().dropna()
# after setting VADI_df.index…
baseline = VADI_df[VADI_column].iloc[0]

# ==============================================================================
# 3) Calculate non-compounded monthly returns (today vs last-month’s close)
# ==============================================================================
# turn your index into Year-Month periods
month_period = VADI_df.index.to_period("M")

# 1) last NAV of each month
month_last = VADI_df.groupby(month_period)[VADI_column].last()

# 2) opening NAV for each month = previous month’s last (shifted)
month_first = month_last.shift(1)

# for the very first month, fall back to your series’ true first NAV
first_period = month_last.index.min()
month_first.loc[first_period] = VADI_df[VADI_column].iloc[0]

# 3) compute simple % change vs prior-month close
monthly_simple = (month_last - month_first) / month_first * 100

# now build the calendar-style table
years       = sorted(monthly_simple.index.year.unique())
month_names = ["Jan","Feb","Mar","Apr","May","Jun",
               "Jul","Aug","Sep","Oct","Nov","Dec"]

monthly_data = {"Year": [str(y) for y in years]}

for idx, mname in enumerate(month_names, start=1):
    vals = []
    for y in years:
        p = pd.Period(f"{y}-{idx:02d}", freq="M")
        if p in monthly_simple.index:
            pct = monthly_simple[p]
            vals.append(f"{pct:.2f}%")
        else:
            vals.append("")     # <<– blank instead of “0.00%”
    monthly_data[mname] = vals

# Year Total stays as before
monthly_data["Year Total"] = [
    f"{monthly_simple[monthly_simple.index.year == y].sum():.2f}%"
    for y in years
]

monthly_df = pd.DataFrame(monthly_data)


# ─────────────────────────────────────────────────────────────────────────────
# 4) Calculate daily performance metrics (with # of days, drawdown stats, etc.)
# ─────────────────────────────────────────────────────────────────────────────
def calculate_period_metrics(returns: pd.Series, start_date: pd.Timestamp) -> dict:
    returns = returns.squeeze()
    # if too short, return placeholders for every metric
    keys = [
        "Cumulative Return", "Annualized Return", "Avg Daily Return",
        "Number of Trading Days", "% Winning Days", "% Losing Days",
        "Best 3 Days", "Worst 3 Days",
        "Number of Drawdowns", "Drawdown Area",
        "Avg Drawdown Depth", "Avg Drawdown Duration",
        "Sharpe", "Sortino", "Calmar", "Omega", "Volatility"
    ]
    if len(returns) < 2:
        return dict.fromkeys(keys, "—")

    # 1) Basic returns
    cum_growth   = (returns + 1).prod() - 1
    total_days   = (returns.index.max() - start_date).days 
    ann_return   = (cum_growth + 1) ** (1 / (total_days / 365.0)) - 1
    avg_daily    = returns.mean()
    win_rate     = qs.stats.win_rate(returns)
    loss_rate    = 1 - win_rate
    top3         = returns.nlargest(3) * 100
    worst3       = returns.nsmallest(3) * 100
    nb_days      = len(returns)

    # 2) Risk‐adjusted metrics
    sharpe       = qs.stats.sharpe(returns, rf=0)
    sortino      = qs.stats.sortino(returns)
    calmar       = qs.stats.calmar(returns)
    omega        = qs.stats.omega(returns)
    vol_pct      = qs.stats.volatility(returns) * 100

    # 3) Drawdown series & area
    nav          = (1 + returns).cumprod()
    dd           = nav / nav.cummax() - 1
    # compute area under the *absolute* drawdown curve in %·days
    days_since_start = (dd.index - dd.index[0]).total_seconds() / 86400.0
    area         = np.trapz(-dd.values * 100, days_since_start)

    # 4) individual drawdown episodes for number, average depth & length
    segments = []
    in_dd    = False
    for t, v in zip(dd.index, dd.values):
        if not in_dd and v < 0:
            in_dd   = True
            start_t = t
            worst   = v
        elif in_dd and v < worst:
            worst = v
        elif in_dd and v >= 0:
            segments.append((start_t, t, worst))
            in_dd = False
    if in_dd:
        segments.append((start_t, dd.index[-1], worst))

    num_dd = len(segments)
    if segments:
        depths  = [-seg[2] * 100 for seg in segments]        # positive %
        lengths = [(seg[1] - seg[0]).days for seg in segments]
        avg_depth   = float(np.mean(depths))
        avg_length  = float(np.mean(lengths))
    else:
        avg_depth   = 0.0
        avg_length  = 0.0

    return {
        "Cumulative Return":      f"{cum_growth*100:.1f}%",
        "Annualized Return":      f"{ann_return*100:.1f}%",
        "Avg Daily Return":       f"{avg_daily*100:.3f}%",
        "Number of Trading Days": f"{nb_days}",
        "% Winning Days":         f"{win_rate*100:.1f}%",
        "% Losing Days":          f"{loss_rate*100:.1f}%",
        "Best 3 Days":            ", ".join(f"{x:.2f}%" for x in top3),
        "Worst 3 Days":           ", ".join(f"{x:.2f}%" for x in worst3),
        "Number of Drawdowns":    f"{num_dd}",
        "Drawdown Area":          f"{area:.1f} %·days",
        "Avg Drawdown Depth":     f"{avg_depth:.1f}%",
        "Avg Drawdown Duration":  f"{avg_length:.0f} days",
        "Sharpe":                 f"{sharpe:.2f}",
        "Sortino":                f"{sortino:.2f}",
        "Calmar":                 f"{calmar:.2f}",
        "Omega":                  f"{omega:.2f}",
        "Volatility":             f"{vol_pct:.1f}%"
    }

# ── Define period boundaries ────────────────────────────────────────────────
inception_start = VADI_df.index.min()
inception_end   = VADI_df.index.max()

# trailing‐twelve‐months ends today, starts one year ago
ttm_end   = inception_end
ttm_start = ttm_end - pd.DateOffset(years=1)


# ── Slice your series ───────────────────────────────────────────────────────
one_year_returns   = daily_returns.loc[ttm_start:ttm_end].dropna()
inception_returns  = daily_returns.copy()

spxtr_series      = bench_ret["SPXTR"]
spxtr_one_year     = spxtr_series .loc[ttm_start:ttm_end].dropna()
spxtr_inception   = spxtr_series.loc[inception_start:inception_end].dropna()

# ── Compute metrics ─────────────────────────────────────────────────────────
one_year_metrics        = calculate_period_metrics(one_year_returns,  ttm_start)
inception_metrics       = calculate_period_metrics(inception_returns,  inception_start)
spxtr_one_year_metrics  = calculate_period_metrics(spxtr_one_year,    ttm_start)
spxtr_inception_metrics = calculate_period_metrics(spxtr_inception,    inception_start)

# ── Assemble the DataFrame ─────────────────────────────────────────────────
metric_labels = [
    "Cumulative Return", "Annualized Return", "Avg Daily Return",
    "Number of Trading Days", "% Winning Days", "% Losing Days",
    "Best 3 Days", "Worst 3 Days", 
    "Number of Drawdowns", 
    "Avg Drawdown Depth", "Avg Drawdown Duration",
    "Drawdown Area",
    "Sharpe", "Sortino", "Calmar", "Omega", "Volatility"
]

daily_perf = {
    "Metric":                 metric_labels,
    f"{STRATEGY_NAME} (1 Year/TTM)":    [one_year_metrics[l]         for l in metric_labels],
    "SPXTR (1 Year/TTM)":         [spxtr_one_year_metrics[l]    for l in metric_labels],
    f"{STRATEGY_NAME} (Inception)": [inception_metrics[l]         for l in metric_labels],
    "SPXTR (Inception)":      [spxtr_inception_metrics[l]   for l in metric_labels],
}

daily_perf_df = pd.DataFrame(daily_perf)


# ─────────────────────────────────────────────────────────────────────────────
# 11) Compute Worst (Max) Drawdown Profile, Inception Only
# ─────────────────────────────────────────────────────────────────────────────
def drawdown_profile(returns: pd.Series) -> dict:
    """
    Returns the single worst drawdown episode:
      - Depth
      - Start Date (peak)
      - Decline Period (peak→valley)
      - Valley Date
      - Recovery Period (valley→peak, or Ongoing)
      - End Date (recovery date or 'TBD')
      - Total Range (peak→recovery, or Ongoing)
    """
    nav   = (1 + returns).cumprod()
    dd    = nav / nav.cummax() - 1

    # find the absolute trough of drawdown
    trough = dd.idxmin()
    # find the most recent peak before that trough
    peak   = nav[:trough].idxmax()
    # first time after trough the NAV returns to that peak level
    rec = nav[trough:][nav[trough:] >= nav[peak]]
    rec_idx = rec.index[0] if not rec.empty else None

    depth = dd.min() * 100
    decline_days = (trough - peak).days
    recovery_days = (rec_idx - trough).days if rec_idx is not None else None
    total_days    = (rec_idx - peak).days   if rec_idx is not None else None



    return {
        "Depth":                       f"{depth:.1f}%",
        "Start Date":           peak.strftime("%Y-%m-%d"),
        "Decline Period":f"{decline_days} days",
        "Valley Date":                 trough.strftime("%Y-%m-%d"),
        "Recovery Period":             f"{recovery_days} days" if recovery_days is not None else "Ongoing",
        "End Date":                    rec_idx.strftime("%Y-%m-%d") if rec_idx is not None else "TBD",
        "Total Duration": f"{total_days} days" if total_days is not None else "Ongoing",
    }

# ── Define the slices (only inception for both series) ────────────────────────
period_slices = {
    f"{STRATEGY_NAME} (Inception)": inception_returns,
    "SPXTR (Inception)":             spxtr_inception,
}

# ── Build the single “Worst Drawdown” DataFrame ─────────────────────────────
# this will have one row per metric, and one column per series
max_dd_df = (
    pd.DataFrame({ col: drawdown_profile(sr)
                   for col, sr in period_slices.items() })
      .rename_axis("Metric")      # row-index name
      .reset_index()              # turn index into a column
)



# ==============================================================================
# 5) Hard-coded “Additional Information”
# ==============================================================================
additional_info = [
    ("Investment Type", "Managed Account"),
    ("Fee Structure", "0% Annual / 20% Performance"),
    ("High Water Mark", "Yes"),
    ("Lockup Period", "None"),
    ("Liquidity", "Daily"),
    ("Notional Funding", "Yes"),
    ("Execution FCM", "StoneX Financial"),
    ("Introducing Broker", "Hughes & Company LLC"),
]

# ==============================================================================
# 6) Legal disclaimers & footer contact
# ==============================================================================
disclaimer_text = (
    "THE RISK OF LOSS IN COMMODITY INTEREST TRADING CAN BE SUBSTANTIAL. YOU SHOULD, THEREFORE, "
    "CAREFULLY CONSIDER WHETHER SUCH TRADING IS SUITABLE FOR YOU IN LIGHT OF YOUR FINANCIAL CONDITION. "
    "THE HIGH DEGREE OF LEVERAGE IN COMMODITY INTEREST TRADING MEANS INVESTMENTS SHOULD BE MADE WITH RISK "
    "CAPITAL ONLY. ALL INFORMATION ABOVE IS COMPILED WITH THE INTENTION OF BEING FULLY CORRECT, THOUGH THERE "
    "IS NO GUARANTEE ALL INFORMATION IS CORRECT AND COULD BE SUBJECT TO UNINTENTIONAL CLERICAL ITEMS. "
    "PAST PERFORMANCE IS NOT NECESSARILY INDICATIVE OF FUTURE RESULTS.\n\n"
    "PLEASE ENSURE THAT YOU ARE FULLY AWARE AND UNDERSTAND ALL RISKS, FEES, AND OTHER CONCERNS RELATED TO YOUR "
    "INVESTMENT BY REQUESTING THE COMPLETE DISCLOSURE DOCUMENT & INVESTMENT MANAGEMENT AGREEMENT MATERIALS BY "
    "REACHING OUT DIRECTLY TO THE ADVISOR."
)
footer_contact = (
    "HUGHES & COMPANY LLC • NFA ID 0423388 • 330 Himmararshee, Ste 110, FTL, FL 33312 • 954-500-0500 • www.hughesandco.ltd"
)

# ==============================================================================
# 7) Helper: Build Plotly “VADI” figure
# ==============================================================================
def build_VADI_figure():
    fig = go.Figure(
        data=[
            go.Scatter(
                x=VADI_df.index,
                y=VADI_df[VADI_column],
                mode="lines",
                line={"color": "#0b5394"},
                name="VADI",
            )
        ],
        )
        # give it the same white template + visible grid lines
    fig.update_layout(
            template="ggplot2",
            title="<u>VADI, Since Inception</u>",
            xaxis_title="Date",
            yaxis_title="Value Added Daily Index",
            margin={"l": 60, "r": 20, "t": 50, "b": 50},
        )
    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=True)
    
    return fig

# ==============================================================================
# 8) Helper: Build advanced figures
# ==============================================================================
def build_advanced_figures():
    qs.extend_pandas()
    figs = {}
    placeholder = dict(title={"x":0.5},
                       margin={"l":60,"r":20,"t":50,"b":50},
                       plot_bgcolor="#ffffff")
    for fid in ["bench_vs_benchmarks","returns_histogram","drawdown_curve"]:
        figs[fid] = go.Figure(layout=placeholder)

    if daily_returns.empty or len(daily_returns) < 2:
        return figs

    # 1) Cumulative Return: Strategy vs Benchmarks
    strat_cum = (1 + daily_returns).cumprod()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=strat_cum.index, y=strat_cum.values,
        name=STRATEGY_NAME, line={"width":2}))
    for name, cum in bench_cum.items():
        fig.add_trace(go.Scatter(
            x=cum.index, y=cum.values,
            name=name, opacity=0.6))
    figs["bench_vs_benchmarks"] = fig.update_layout(
        title=f"{STRATEGY_NAME} vs " + ", ".join(bench_cum.keys()),
        xaxis_title="Date", yaxis_title="Cumulative Return"
    )

    # 2) Returns Histogram
    figs["returns_histogram"] = go.Figure(
        go.Histogram(x=daily_returns * 100, name=STRATEGY_NAME, nbinsx=150, marker_line_width=1,)
    ).update_layout(
        title="Daily Returns Distribution",
        xaxis_title="Return (%)", yaxis_title="Frequency"
    )


    # 5) Drawdown Curve: Strategy & Benchmarks
    strat_dd = strat_cum / strat_cum.cummax() - 1
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=strat_dd.index, y=strat_dd * 100,
        name=STRATEGY_NAME, line={"width":2}))
    for name, dd in bench_dd.items():
        fig.add_trace(go.Scatter(
            x=dd.index, y=dd.values,
            name=name, opacity=0.6, line={"dash":"dot"}))
    figs["drawdown_curve"] = fig.update_layout(
        title=f"Drawdown Curve — {STRATEGY_NAME} vs " + ", ".join(bench_dd.keys()),
        xaxis_title="Date", yaxis_title="Drawdown (%)"
    )

    return figs

# Pre-compute advanced figures so dummy_figs exists for the hidden panel
dummy_figs = build_advanced_figures()

def build_drawdown_figure():
    fig = go.Figure()
    # Strategy drawdown
    strat_dd = (1 + daily_returns).cumprod()
    strat_dd = strat_dd / strat_dd.cummax() - 1
    fig.add_trace(go.Scatter(
        x=strat_dd.index, y=strat_dd*100,
        name=STRATEGY_NAME, line={"color":"#0b5394"}))
    # Each benchmark
    for name, dd in bench_dd.items():
        fig.add_trace(go.Scatter(
            x=dd.index, y=dd.values,
            name=f"{name} Drawdown", opacity=0.6))
    fig.update_layout(
        title=f"Drawdown — {STRATEGY_NAME} vs " + ", ".join(bench_dd.keys()),
        xaxis_title="Date", yaxis_title="Drawdown (%)"
    )
    return fig

# ── 9) Construct the Dash App ────────────────────────────────────────────────
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
    title="H&C – TKP",
)

def serve_layout():
    last_updated = VADI_df.index.max().strftime("%B %d, %Y")
    advanced_graphs = [
        "bench-overlay",
        "returns_histogram",
        "drawdown_curve",
    ]

    return html.Div(
        id="page-container",
        style={"width": "80%", "margin": "0 auto"},
        children=[
            # ── Header ─────────────────────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(html.Img(src=logo_src, style={"height": "100px"}), width=2),
                    dbc.Col(
                        html.Div(
                            [
                                html.H2("Hughes & Company LLC", className="text-center"),
                                html.H5("The Gold Maker Program", className="text-center text-muted"),
                            ],
                            style={"lineHeight": "1.2", "paddingTop": "20px"},
                        ),
                        width=8,
                    ),
                    dbc.Col(
                        html.H4(f"Last Updated: {last_updated}", className="text-end text-muted"),
                        width=2,
                        style={"paddingTop": "30px"},
                    ),
                ],
                align="center",
                style={"backgroundColor": "#e9ecef", "padding": "10px 0"},
            ),
            html.Hr(),

            # ── Description ────────────────────────────────────────────────────
            html.Div(
                [
                    html.P(
                        "Hughes & Company LLC is an introducing brokerage firm with expertise in the futures options industry. "
                        "TKP is a systematic program which utilizes options on the S&P 500 Index in intraday trading and "
                        "put/call assignment to achieve long-biased stable returns with daily visibility.",
                        className="lead text-center",
                    ),
                    html.P(
                        "Principals: Daniel V. Hughes III  |  Inception: April 2023  |  "
                        "Products Traded: E-Mini Micro S&P 500 Options  |  Styles: Short Options",
                        className="text-center mb-5",
                    ),
                ]
            ),

            # ── VADI Chart ─────────────────────────────────────────────────────
            dcc.Graph(
                id="VADI-graph",
                figure=build_VADI_figure(),
                config={"displayModeBar": False},
            ),
            html.P(
                "This VADI chart visualizes the growth of a $1,000 investment from inception to today. "
                "VADI stands for Value Added Daily Index; it reflects composite, non-compounded performance, "
                "net of all fees.",
                className="text-center fst-italic small mb-5",
            ),

            # ── Performance Summary ────────────────────────────────────────────
            html.H5("Performance Summary", className="text-center mb-2"),
            dbc.Table.from_dataframe(
                monthly_df,
                striped=True,
                bordered=True,
                hover=True,
                size="sm",
                className="table-responsive mb-5",
                style={"width": "95%", "margin": "0 auto"},
            ),

            # ── Metrics & Info ─────────────────────────────────────────────────
                        dbc.Row(
                [
                    # Daily Performance Metrics
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H6("Performance Metrics", className="mb-0")),
                                dbc.CardBody(
                                    dbc.Table.from_dataframe(
                                        daily_perf_df,
                                        striped=True,
                                        bordered=True,
                                        hover=True,
                                        size="sm",
                                    )
                                ),
                            ],
                            outline=True,
                            className="mb-4",
                        ),
                        width=7,
                    ),

                    # Additional Information
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H6("Additional Information", className="mb-0")),
                                dbc.CardBody(
                                    html.Ul(
                                        [html.Li(f"{label}: {value}") for label, value in additional_info]
                                        + [
                                            html.Li(
                                                html.Em(
                                                    "Please request our Disclosure Document for full details."
                                                ),
                                                className="mt-2",
                                            )
                                        ]
                                    )
                                ),
                            ],
                            outline=True,
                            className="mb-4",
                        ),
                        width=5,
                    ),
                ],
                justify="center",
                className="mb-5",
            ),

            # ── Drawdown Profiles ────────────────────────────────────────────────
            dbc.Row(
                [
                    # Max Drawdown Profile
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H6("MAXIMUM DRAWDOWN PROFILE", className="mb-0")),
                                dbc.CardBody(
                                    dbc.Table.from_dataframe(
                                        max_dd_df,
                                        striped=True,
                                        bordered=True,
                                        hover=True,
                                        size="sm",
                                    )
                                ),
                            ],
                            outline=True,
                            className="mb-4",
                        ),
                        width=12,
                    ),
                ],
                justify="center",
                className="mb-5",
            ),

            html.Hr(),

            # ── Advanced Charts (hidden until toggled) ─────────────────────────
            html.Div(
                id="advanced-section",
                style={"display": "none"},
                children=[
                    html.H4("Advanced Risk Metrics & Visualizations", className="text-center my-4"),
                    *[
                        dbc.Row(
                            dbc.Col(
                                dcc.Graph(
                                    id=graph_id,
                                    figure=dummy_figs.get(graph_id, go.Figure()),
                                    config={"displayModeBar": False},
                                ),
                                width=12
                            ),
                            className="mb-4",
                        )
                        for graph_id in advanced_graphs
                    ],
                ],
            ),
            html.Hr(),

            # ── Disclaimer ────────────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.P(disclaimer_text, className="text-muted small"),
                    width=12
                ),
                className="mb-4",
            ),

            # ── Important Disclosure ──────────────────────────────────────────────────
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

            # ── Toggle & Footer ───────────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(html.Div(), width=8),
                    dbc.Col(
                        dbc.Button("Show More", id="toggle-advanced", color="secondary", size="sm"),
                        width=4,
                        className="d-flex justify-content-end mb-4",
                    ),
                ]
            ),
            dbc.Row(
                dbc.Col(html.P(footer_contact, className="text-center small text-muted"), width=12),
                className="mb-2",
            ),
            dbc.Row(
                [
                    dbc.Col(html.Div(), width=8),
                    dbc.Col(
                        dbc.ButtonGroup(
                            [
                                dbc.Button("Full Width", id="btn-full", outline=True, size="sm"),
                                dbc.Button("80% Width", id="btn-80", outline=True, size="sm"),
                                dbc.Button("Mobile Width", id="btn-50", outline=True, size="sm"),
                            ]
                        ),
                        width=4,
                        className="d-flex justify-content-end mb-4",
                    ),
                ]
            ),
        ],
    )

app.layout = serve_layout


# ==============================================================================
# 10) Toggle “Advanced” section
# ==============================================================================
@app.callback(
    [
        Output("advanced-section", "style"),
        Output("toggle-advanced", "children"),
    ],
    [Input("toggle-advanced", "n_clicks")],
    [State("advanced-section", "style"), State("toggle-advanced", "children")],
)
def toggle_advanced(n_clicks, current_style, current_label):
    if not n_clicks:
        return {"display": "none"}, "Show More"
    if current_style.get("display", "") == "none":
        return {"display": "block"}, "Hide"
    return {"display": "none"}, "Show More"

# ====================================================================
# Resize page width
@app.callback(
    Output("page-container", "style"),
    [
      Input("btn-full", "n_clicks"),
      Input("btn-80",   "n_clicks"),
      Input("btn-50",   "n_clicks"),
    ],
    State("page-container", "style"),
)
def resize_page(click_full, click_80, click_50, current_style):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_style
    clicked = ctx.triggered[0]["prop_id"].split(".")[0]
    margin = "0 auto"
    if clicked=="btn-full": return {"width":"100%","margin":margin}
    if clicked=="btn-80":   return {"width":"80%","margin":margin}
    if clicked=="btn-50":   return {"width":"95%","margin":margin}
    return current_style

# ====================================================================
# Populate your benchmark overlay when VADI-graph is first drawn
@app.callback(
    Output("bench-overlay", "figure"),
    Input("VADI-graph","figure"),
)
def update_bench(_):
    strat_cum = (1 + daily_returns).cumprod()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=strat_cum.index, y=strat_cum.values,
        name=STRATEGY_NAME, line={"width":2}))
    for name, cum in bench_cum.items():
        fig.add_trace(go.Scatter(
            x=cum.index, y=cum.values,
            name=name, opacity=0.6))
    fig.update_layout(
        title=f"{STRATEGY_NAME} vs " + ", ".join(bench_cum.keys()),
        xaxis_title="Date", yaxis_title="Cumulative Return"
    )
    return fig

def resize_page(click_full, click_80, click_50, current_style):
    ctx = dash.callback_context
    if not ctx.triggered:
        return current_style

    clicked_id = ctx.triggered[0]["prop_id"].split(".")[0]
    margin = "0 auto"

    if clicked_id == "btn-full":
        return {"width": "100%", "margin": margin}
    elif clicked_id == "btn-80":
        return {"width": "80%", "margin": margin}
    elif clicked_id == "btn-50":
        return {"width": "95%", "margin": margin}
    return current_style

if __name__=="__main__":
    app.run(debug=True, port=8075)