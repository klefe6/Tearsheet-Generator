import quantstats.stats as _qs_stats
# ── Monkey-patch Gain/Pain to fix that ‘ME’ bug ──────────────────────────────
_qs_stats._orig_gain_to_pain_ratio = _qs_stats.gain_to_pain_ratio
def _patched_gain_to_pain_ratio(returns, rf=None, resolution='ME'):
    return _qs_stats._orig_gain_to_pain_ratio(returns, rf,
             resolution.replace('ME','M'))
_qs_stats.gain_to_pain_ratio = _patched_gain_to_pain_ratio

import pandas as pd, numpy as np, yfinance as yf, quantstats as qs
from quantstats import utils

from dash import Dash, html, dcc, Input, Output, State
import dash
import base64, io
import dash_bootstrap_components as dbc
import plotly.graph_objs as go

# ── 0) Map friendly names → filepaths ─────────────────────────────────────
strategy_map = {
    "Adalpha - Core Program":      r"C:\Coding Projects\Tearsheet Generator\Trade_Results.csv",
    "Numberline - Badoo Program":    r"C:\Coding Projects\Tearsheet Generator\Trade_Results_Numberline.csv",
    "AP Futures - Toto Program":   r"C:\Coding Projects\Tearsheet Generator\Trade_Results_APFutures.csv",
    "H&C - TKP":   r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents\3_Advisors Marketing (Tearsheets, PitchBooks, etc)\1. Tearsheet Project\TKP\VADI\TKP VADI.csv",
}

# ── 0.1) Preset fee schedules for the 3 built-ins ─────────────────────────
preset_fees = {
    strategy_map["Adalpha - Core Program"]:    {"maint": 2.00, "incentive": 20.0},
    strategy_map["Numberline - Badoo Program"]:  {"maint": 1.50, "incentive": 15.0},
    strategy_map["AP Futures - Toto Program"]:{ "maint": 2.50, "incentive": 25.0},
    strategy_map["H&C - TKP"]:{ "maint": 2.00, "incentive": 20.0},
}

# ── 1) LOAD & PREPARE RETURNS ────────────────────────────────────────────────
CSV = r"C:\Coding Projects\Tearsheet Generator\Trade_Results.csv"
df   = (pd.read_csv(CSV, parse_dates=["Date"])
            .set_index("Date").sort_index())
rets = df["Net liquidation Value"].pct_change().dropna()

# full-range dates
MIN_DATE = rets.index.min().date()
MAX_DATE = rets.index.max().date()

def make_all_figures(returns: pd.Series, include_spy: bool, include_gld: bool):
    eq = (1 + returns).cumprod()

    # download benchmarks (once)
    b_spy_full = utils.download_returns("^GSPC")
    b_gld_full = utils.download_returns("GLD")

    # align to your returns index
    b_spy = b_spy_full.reindex(returns.index).ffill().bfill()
    b_gld = b_gld_full.reindex(returns.index).ffill().bfill()

    fig_bench = go.Figure()
    # always add your strategy
    fig_bench.add_trace(
        go.Scatter(x=eq.index, y=eq.values, name="Strategy")
    )
    if include_spy:
        fig_bench.add_trace(
            go.Scatter(
                x=b_spy.index,
                y=(1 + b_spy).cumprod(),
                name="SPX",
                opacity=0.5
            )
        )
    if include_gld:
        fig_bench.add_trace(
            go.Scatter(
                x=b_gld.index,
                y=(1 + b_gld).cumprod(),
                name="GLD",
                opacity=0.5
            )
        )

    fig_bench.update_layout(
        title="Strategy vs Benchmarks",
        xaxis_title="Date", yaxis_title="Cumulative Return"
    )

    fig_bench.update_layout(
        title="Strategy vs SPX & GLD",
        xaxis_title="Date",
        yaxis_title="Cumulative Return"
    )

    # histogram
    fig_hist = go.Figure(go.Histogram(x=returns, nbinsx=50))
    fig_hist.update_layout(title="Daily Returns Distribution",
                           xaxis_title="Return", yaxis_title="Freq.",
                           bargap=0.1)

    # monthly bar
    m = returns.resample("M").apply(lambda x:(1+x).prod()-1)
    dfm = m.to_frame("Return")
    dfm["Year"]  = dfm.index.year.astype(str)
    dfm["Month"] = dfm.index.month_name().str[:3]
    pivot = dfm.pivot(index="Year",columns="Month",values="Return").fillna(0)
    months = pivot.columns.tolist()
    years  = pivot.index.tolist()
    fig_month = go.Figure([
        go.Bar(name=mo, x=years, y=pivot[mo].values) for mo in months
    ])
    fig_month.update_layout(barmode="group",
                             title="Monthly Returns",
                             xaxis_tickangle=-45,
                             xaxis_title="Year", yaxis_title="Return")

    # calendar heatmap
    daily_nav  = df["Net liquidation Value"].resample("D").ffill()
    daily_rets = daily_nav.pct_change().dropna()
    cal = pd.DataFrame({"Return":daily_rets})
    cal["Year"] = cal.index.year
    cal["Week"] = cal.index.to_series().dt.isocalendar().week
    cal["Dow"]  = cal.index.day_name().str[:3]
    dow_order = ["Mon","Tue","Wed","Thu","Fri"]
    pivot_cal = (
      cal
      .pivot_table(index=["Year","Week"],columns="Dow",values="Return",aggfunc="last")
      .reindex(columns=dow_order)
      .fillna(0)
    )
    fig_cal = go.Figure(go.Heatmap(
        z=pivot_cal.values,
        x=pivot_cal.columns,
        y=[f"{y}-W{w}" for y,w in pivot_cal.index],
        colorscale="RdYlGn", zmid=0
    ))
    fig_cal.update_layout(title="Calendar Heatmap of Daily Returns")

    # core curves
    fig_eq = go.Figure(go.Scatter(x=eq.index, y=eq.values, mode="lines"))
    fig_eq.update_layout(title="Cumulative Equity Curve",
                         xaxis_title="Date", yaxis_title="Equity")

    dd   = eq/eq.cummax() - 1
    fig_dd = go.Figure(go.Scatter(x=dd.index, y=dd.values, fill="tozeroy"))
    fig_dd.update_layout(title="Drawdown Curve",
                         xaxis_title="Date", yaxis_title="Drawdown")

    # rolling stats
    window = 30
    rs = (returns.rolling(window).mean()*252) / (returns.rolling(window).std()*np.sqrt(252))
    rv = returns.rolling(window).std()*np.sqrt(252)

    fig_rs = go.Figure(go.Scatter(x=rs.index, y=rs.values, mode="lines"))
    fig_rs.update_layout(title=f"Rolling {window}-Day Sharpe",
                         xaxis_title="Date",yaxis_title="Sharpe")

    fig_rv = go.Figure(go.Scatter(x=rv.index, y=rv.values, mode="lines"))
    fig_rv.update_layout(title=f"Rolling {window}-Day Vol",
                         xaxis_title="Date",yaxis_title="Volatility")

    return fig_bench, fig_hist, fig_month, fig_cal, fig_eq, fig_dd, fig_rs, fig_rv


def make_metric_cards(returns: pd.Series):
    # pull the full set of metrics (VaR/CVaR are only in "full" mode)
    stats = qs.reports.metrics(
        returns,
        mode="full",
        return_data=True,
        display=False
    )
    # only keep the four metrics we care about (missing ones become NaN)
    desired = ["Profit Factor", "Tail Ratio", "VaR 95%", "CVaR 95%"]
    stats = stats.reindex(desired)

    # figure out what the single column is actually called:
    val_col = stats.columns[0]

    cards = []
    for metric, row in stats.iterrows():
        value = row.iloc[0]   # grab that single value
        txt   = f"{value:.2f}" if pd.notna(value) else "–"
        cards.append(
            dbc.Col(
                dbc.Card(
                    dbc.CardBody([
                        html.H6(metric, className="card-title"),
                        html.H4(txt,    className="card-text")
                    ]),
                    className="mb-2"
                ),
                width=3
            )
        )
    return cards



app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
app.title="Comprehensive Tearsheet"

app.layout = dbc.Container([
    html.H1("Comprehensive Tearsheet", className="text-center my-3"),

    # ── date pickers + buttons ────────────────────────────────────────────────
    dbc.Row([
        dbc.Col(dcc.DatePickerSingle(
            id="start-date",
            date=MIN_DATE,
            min_date_allowed=MIN_DATE,
            max_date_allowed=MAX_DATE,
            initial_visible_month=MIN_DATE,
            display_format="YYYY-MM-DD"
        ), width="auto"),
        dbc.Col(dcc.DatePickerSingle(
            id="end-date",
            date=MAX_DATE,
            min_date_allowed=MIN_DATE,
            max_date_allowed=MAX_DATE,
            initial_visible_month=MAX_DATE,
            display_format="YYYY-MM-DD"
        ), width="auto"),
        dbc.Col(dbc.Button("Max Interval", id="max-interval", color="secondary"), width="auto"),
    ], align="center", className="mb-4"),

     # ── # OF STRATEGIES SELECTOR ───────────────────────────────────────────
    dbc.Row([
        dbc.Col(html.Label("# of Strategies:"), width="auto"),
        dbc.Col(
            dcc.Dropdown(
                id="num-strategies",
                options=[{"label": i, "value": i} for i in (1,2,3)],
                value=1,
                clearable=False,
                style={"width":"100px"}
            ),
            width="auto"
        ),
    ], align="center", className="mb-4"),


# ── Strategy 1 Controls (always visible) ─────────────────────────────────────────
    html.Div(id="strategy-1-controls", children=[
        html.H5("📈 Primary Strategy Controls"),
        dbc.Row([
            dbc.Col(dbc.Label("Select Existing:"), width="auto"),
            dbc.Col(
                dcc.Dropdown(
                    id="s1-existing",
                    options=[{"label": name, "value": path}
                            for name, path in strategy_map.items()],
                    placeholder="Choose…"
                ),
                width=3
            ),
            dbc.Col(html.Div("or"), width="auto"),
            dbc.Col(
                dcc.Upload(
                    id="upload-1",
                    children=html.Div(["📂 Drag & Drop or ", html.A("Select File")]),
                    style={
                        "border": "1px dashed #bbb", "padding": "10px",
                        "textAlign": "center", "cursor": "pointer"
                    }
                ),
                width=4
            ),
            dbc.Col(
                dbc.Button("🛈 Format Help", id="help-1", color="link"),
                width="auto"
            ),
        ], align="center", className="mb-3"),
        dbc.Modal(
            [
            dbc.ModalHeader("Accepted CSV Format"),
            dbc.ModalBody(html.Pre(
                "Required columns:\n - Date (MM/DD/YYYY)\n - Net liquidation Value"
            )),
            dbc.ModalFooter(
                dbc.Button("Close", id="close-1", className="ml-auto")
            )
            ],
            id="modal-1", is_open=False
        ),
        html.Div(id="upload-1-error", style={"color": "red"}),
        # sizing + fees
        html.Div([
            dbc.Label("Sizing Type:", html_for="s1-sizing"),
            dbc.RadioItems(
                id="s1-sizing",
                options=[
                    {"label": "Fixed", "value": "fixed"},
                    {"label": "Dynamic (Percentage of Account Size)",   "value": "pct"}
                ],
                inline=True, value="fixed"
            )
        ], className="mb-3"),
        html.Div([
            dbc.Label("Maintenance Fees (%)", html_for="s1-maint-fee"),
            dbc.Input(id="s1-maint-fee", type="number", min=0, step=0.01,
                    placeholder="e.g. 2.00"),
        ], className="mb-3"),
        html.Div([
            dbc.Label("Incentive Fees (%)", html_for="s1-incentive-fee"),
            dbc.Input(id="s1-incentive-fee", type="number", min=0, step=0.01,
                    placeholder="e.g. 20.0"),
        ], className="mb-3"),
    ]),

    # ── Strategy 2 Controls (hidden until num-strategies ≥ 2) ──────────────────────
    html.Div(id="strategy-2-controls", style={"display": "none"}, children=[
        html.H5("📈 Strategy 2 Controls"),
        dbc.Row([
            dbc.Col(dbc.Label("Select Existing:"), width="auto"),
            dbc.Col(
                dcc.Dropdown(
                    id="s2-existing",
                    options=[{"label": name, "value": path}
                            for name, path in strategy_map.items()],
                    placeholder="Choose…"
                ),
            ),
            dbc.Col(html.Div("or"), width="auto"),
            dbc.Col(
                dcc.Upload(id="upload-2", children="📂 Upload File 1",
                        style={"border":"1px dashed #bbb","padding":"8px","textAlign":"center"}),
                width=4
            ),
            dbc.Col(dbc.Button("🛈 Format Help", id="help-2", color="link"), width="auto"),
        ], align="center", className="mb-3"),
        dbc.Modal([
            dbc.ModalHeader("Accepted CSV Format"),
            dbc.ModalBody(html.Pre(
                "Required columns:\n - Date (MM/DD/YYYY)\n - Net liquidation Value"
            )),
            dbc.ModalFooter(dbc.Button("Close", id="close-2", className="ml-auto"))
        ], id="modal-2", is_open=False),
        html.Div(id="upload-2-error", style={"color":"red"}),
        # sizing + fees (same pattern as above)
                # ── Strategy 2 Sizing & Fees ─────────────────────────────────────────
        html.Div([
            dbc.Label("Sizing Type:", html_for="s2-sizing"),
            dbc.RadioItems(
                id="s2-sizing",
                options=[
                    {"label": "Fixed Size", "value": "fixed"},
                    {"label": "% Capital",   "value": "pct"}
                ],
                inline=True,
                value="fixed"
            )
        ], className="mb-3"),
        html.Div([
            dbc.Label("Maintenance Fees (%)", html_for="s2-maint-fee"),
            dbc.Input(
                id="s2-maint-fee",
                type="number", min=0, step=0.01,
                placeholder="e.g. 2.00"
            ),
        ], className="mb-3"),
        html.Div([
            dbc.Label("Incentive Fees (%)", html_for="s2-incentive-fee"),
            dbc.Input(
                id="s2-incentive-fee",
                type="number", min=0, step=0.01,
                placeholder="e.g. 20.0"
            ),
        ], className="mb-3"),

    ]),

    # ── Strategy 3 Controls (hidden until num-strategies = 3) ──────────────────────
    html.Div(id="strategy-3-controls", style={"display": "none"}, children=[
        html.H5("📈 Strategy 3 Controls"),
        dbc.Row([
            dbc.Col(dbc.Label("Select Existing:"), width="auto"),
            dbc.Col(
                dcc.Dropdown(
                    id="s3-existing",
                    options=[{"label": name, "value": path}
                            for name, path in strategy_map.items()],
                    placeholder="Choose…"
                ),
            ),
            dbc.Col(html.Div("or"), width="auto"),
            dbc.Col(
                dcc.Upload(id="upload-3", children="📂 Upload File 2",
                        style={"border":"1px dashed #bbb","padding":"8px","textAlign":"center"}),
                width=4
            ),
            dbc.Col(dbc.Button("🛈 Format Help", id="help-3", color="link"), width="auto"),
        ], align="center", className="mb-3"),
        dbc.Modal([
            dbc.ModalHeader("Accepted CSV Format"),
            dbc.ModalBody(html.Pre(
                "Required columns:\n - Date (MM/DD/YYYY)\n - Net liquidation Value"
            )),
            dbc.ModalFooter(dbc.Button("Close", id="close-3", className="ml-auto"))
        ], id="modal-3", is_open=False),
        html.Div(id="upload-3-error", style={"color":"red"}),
        # sizing + fees
                # ── Strategy 3 Sizing & Fees ─────────────────────────────────────────
        html.Div([
            dbc.Label("Sizing Type:", html_for="s3-sizing"),
            dbc.RadioItems(
                id="s3-sizing",
                options=[
                    {"label": "Fixed Size", "value": "fixed"},
                    {"label": "% Capital",   "value": "pct"}
                ],
                inline=True,
                value="fixed"
            )
        ], className="mb-3"),
        html.Div([
            dbc.Label("Maintenance Fees (%)", html_for="s3-maint-fee"),
            dbc.Input(
                id="s3-maint-fee",
                type="number", min=0, step=0.01,
                placeholder="e.g. 2.00"
            ),
        ], className="mb-3"),
        html.Div([
            dbc.Label("Incentive Fees (%)", html_for="s3-incentive-fee"),
            dbc.Input(
                id="s3-incentive-fee",
                type="number", min=0, step=0.01,
                placeholder="e.g. 20.0"
            ),
        ], className="mb-3"),
    ]),


    # ── Benchmark Toggles ─────────────────────────────────────────────────────
    dbc.Row([
        dbc.Col(html.Label("Include Benchmarks:"), width="auto"),
        dbc.Col(
            dbc.Checklist(
                id="bench-toggles",
                options=[
                    {"label": "SPX", "value": "SPX"},
                    {"label": "GLD", "value": "GLD"},
                ],
                value=["SPX", "GLD"],  # both on by default
                inline=True,
            ),
            width="auto"
        ),
    ], className="mb-4"),
    
    # ── Calculate ─────────────────────────────────────────────────────
    dbc.Row(
        dbc.Col(
            dbc.Button("Calculate", id="calculate-btn", color="primary"),
            width="auto"
        ),
        justify="center",
        className="my-4"  # adds equal margin above and below
    ),

    # ── metrics table (dynamic) ───────────────────────────────────────────────
    dbc.Row(
        dbc.Col(html.Div(id="metrics-table")),
        className="mb-4"
    ),

    # ── your figures ─────────────────────────────────────────────────────────
    dcc.Loading(dcc.Graph(id="bench-overlay")),
    dcc.Loading(dcc.Graph(id="returns-hist")),
    dcc.Loading(dcc.Graph(id="monthly-bar")),
    dcc.Loading(dcc.Graph(id="calendar-heatmap")),
    dcc.Loading(dcc.Graph(id="equity-curve")),
    dcc.Loading(dcc.Graph(id="drawdown-curve")),
    dcc.Loading(dcc.Graph(id="rolling-sharpe")),
    dcc.Loading(dcc.Graph(id="rolling-volatility")),

    # ── advanced risk cards ───────────────────────────────────────────────────
    html.H4("Advanced Risk Metrics", className="mt-4"),
    dbc.Row(id="adv-risk-cards"),

    # ── download button ───────────────────────────────────────────────────────
    dbc.Row(dbc.Col(dbc.Button("Download Metrics CSV", id="download-btn"),
                    width="auto"), justify="center", className="my-4"),
    dcc.Download(id="download-dataframe-csv"),

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
        className="my-4",
    ),
], fluid=True)


# ── reset MAX INTERVAL ─────────────────────────────────────────────────────
@app.callback(
    [
      Output("start-date", "date"),
      Output("end-date",   "date"),
      Output("start-date", "min_date_allowed"),
      Output("start-date", "max_date_allowed"),
      Output("end-date",   "min_date_allowed"),
      Output("end-date",   "max_date_allowed"),
    ],
    Input("max-interval","n_clicks"),
    [
      State("s1-existing","value"),
      State("upload-1","contents"),
      State("upload-1","filename"),
    ]
)
def reset_to_full(n_clicks, s1_path, upload_contents, upload_fname):
    # if never clicked, use global defaults
    if not n_clicks:
        return MIN_DATE, MAX_DATE, MIN_DATE, MAX_DATE, MIN_DATE, MAX_DATE

    # pick your DataFrame just like in update_all()
    if upload_contents:
        _, b64 = upload_contents.split(",", 1)
        txt = base64.b64decode(b64).decode("utf-8")
        df1 = pd.read_csv(io.StringIO(txt), parse_dates=["Date"])
    elif s1_path:
        df1 = pd.read_csv(s1_path,      parse_dates=["Date"])
    else:
        df1 = pd.read_csv(CSV,          parse_dates=["Date"])

    df1 = df1.set_index("Date").sort_index()
    lo = df1.index.min().date()
    hi = df1.index.max().date()

    # reset both date **values** and allowed range
    return lo, hi, lo, hi, lo, hi

@app.callback(
    [
        Output("strategy-2-controls", "style"),
        Output("strategy-3-controls", "style")
    ],
    Input("num-strategies", "value")
)
def toggle_strategy_blocks(n):
    # show block 2 if n>=2, block 3 if n==3
    style2 = {"display": "block"} if n >= 2 else {"display": "none"}
    style3 = {"display": "block"} if n >= 3 else {"display": "none"}
    return style2, style3

# ── as soon as the user uploads a file, clear out the corresponding “Select Existing” dropdown ──
@app.callback(
    Output("s1-existing", "value"),
    Input("upload-1",   "contents"),
    prevent_initial_call=True
)
def clear_s1_existing_on_upload(contents):
    if contents:
        return None
    return dash.no_update

@app.callback(
    Output("s2-existing", "value"),
    Input("upload-2",   "contents"),
    prevent_initial_call=True
)
def clear_s2_existing_on_upload(contents):
    if contents:
        return None
    return dash.no_update

@app.callback(
    Output("s3-existing", "value"),
    Input("upload-3",   "contents"),
    prevent_initial_call=True
)
def clear_s3_existing_on_upload(contents):
    if contents:
        return None
    return dash.no_update


# ── Auto-populate primary fees when an existing strategy is chosen ─────────
@app.callback(
    [ Output("s1-maint-fee",     "value"),
      Output("s1-incentive-fee", "value") ],
    Input("s1-existing", "value")
)
def populate_primary_fees(selected_path):
    if selected_path in preset_fees:
        fees = preset_fees[selected_path]
        return fees["maint"], fees["incentive"]
    return None, None


# ── Toggle the “Format Help” modal for Strategy 1 ───────────────────────────
@app.callback(
    Output("modal-1", "is_open"),
    [ Input("help-1",  "n_clicks"),
      Input("close-1", "n_clicks") ],
    [ State("modal-1", "is_open") ]
)
def toggle_modal1(open_click, close_click, is_open):
    # flip open state on either button
    if open_click or close_click:
        return not is_open
    return is_open


# ── only recalc when CALCULATE or MAX pressed ───────────────────────────────
@app.callback(
    [
      Output("bench-overlay","figure"),
      Output("returns-hist","figure"),
      Output("monthly-bar","figure"),
      Output("calendar-heatmap","figure"),
      Output("equity-curve","figure"),
      Output("drawdown-curve","figure"),
      Output("rolling-sharpe","figure"),
      Output("rolling-volatility","figure"),
      Output("adv-risk-cards","children"),
      Output("metrics-table","children"),
    ],
    [
      Input("calculate-btn","n_clicks"),
      Input("max-interval","n_clicks"),
      Input("bench-toggles","value"),
    ],
    [
      State("start-date","date"),
      State("end-date","date"),
    ]
)

def update_all(calc_clicks, max_clicks, selected_benchmarks, start_date, end_date):
    # 1) pick date range
    ctx = dash.callback_context
    if not ctx.triggered:
        s, e = MIN_DATE, MAX_DATE
    else:
        s = pd.to_datetime(start_date).date()
        e = pd.to_datetime(end_date).date()

    # 2) slice your strategy returns
    r = rets.loc[s:e]

    # 3) figures & cards
    include_spy = "SPX" in selected_benchmarks
    include_gld = "GLD" in selected_benchmarks
    figs  = make_all_figures(r, include_spy, include_gld)
    cards = make_metric_cards(r)

        # — determine friendly name for the primary strategy  —
    friendly_map = {v:k for k,v in strategy_map.items()}
    friendly_name = friendly_map.get(CSV, "Strategy")

    # — rebuild the metrics table, renaming that “Value” column to your program name —
    metrics_df = (
        qs.reports.metrics(r, mode="full", return_data=True, display=False)
          .reset_index()
          .rename(columns={"index":"Metric", "Value": friendly_name})
    )


    # 5) recompute benchmark returns aligned to r
    b_spy_full = utils.download_returns("^GSPC")
    b_spy      = b_spy_full.reindex(r.index).ffill().bfill()
    b_gld_full = utils.download_returns("GLD")
    b_gld      = b_gld_full.reindex(r.index).ffill().bfill()

    # 6) append benchmark columns, using .iloc[:,0] to grab the only column
    if include_spy:
        spy_stats = qs.reports.metrics(b_spy, mode="full", return_data=True, display=False)
        metrics_df["SPX"] = spy_stats.iloc[:,0].values

    if include_gld:
        gld_stats = qs.reports.metrics(b_gld, mode="full", return_data=True, display=False)
        metrics_df["GLD"] = gld_stats.iloc[:,0].values

    # 7) render the table
    table = dbc.Table.from_dataframe(metrics_df, striped=True, bordered=True, hover=True)

    return (*figs, cards, table)


def _validate(contents, filename):
    if not contents:
        return ""
    # decode & try to parse
    header, b64 = contents.split(",", 1)
    try:
        s = base64.b64decode(b64).decode("utf-8")
        df = pd.read_csv(io.StringIO(s))
    except Exception:
        return f"❌ {filename} parse error"
    # check columns
    required = {"Date", "Net liquidation Value"}
    if not required.issubset(df.columns):
        return f"❌ {filename} missing {required - set(df.columns)}"
    return ""

# validate each upload
@app.callback(
    Output("upload-1-error","children"),
    Input("upload-1","contents"),
    State("upload-1","filename")
)
def check1(contents, filename):
    if not contents:
        return ""
    err = _validate(contents, filename)
    return err or f"✅ {filename} accepted"

@app.callback(
    Output("upload-2-error","children"),
    Input("upload-2","contents"),
    State("upload-2","filename")
)
def check2(contents, filename):
    if not contents:
        return ""
    err = _validate(contents, filename)
    return err or f"✅ {filename} accepted"

@app.callback(
    Output("upload-3-error","children"),
    Input("upload-3","contents"),
    State("upload-3","filename")
)
def check3(contents, filename):
    if not contents:
        return ""
    err = _validate(contents, filename)
    return err or f"✅ {filename} accepted"

# disable Calculate if any visible upload has an error
@app.callback(
    Output("calculate-btn","disabled"),
    [
      Input("upload-1-error","children"),
      Input("upload-2-error","children"),
      Input("upload-3-error","children")
    ]
)
def disable_calc(e1, e2, e3):
    return any(msg.startswith("❌") for msg in (e1 or "", e2 or "", e3 or ""))

# grey-out fees when picking an existing file
@app.callback(
    [ Output("s1-maint-fee","disabled"),
      Output("s1-incentive-fee","disabled") ],
    Input("s1-existing","value")
)
def disable_s1_fees(val):
    return (True, True) if val else (False, False)

@app.callback(
    [ Output("s2-maint-fee","disabled"),
      Output("s2-incentive-fee","disabled") ],
    Input("s2-existing","value")
)
def disable_s2_fees(val):
    return (True, True) if val else (False, False)

@app.callback(
    [ Output("s3-maint-fee","disabled"),
      Output("s3-incentive-fee","disabled") ],
    Input("s3-existing","value")
)
def disable_s3_fees(val):
    return (True, True) if val else (False, False)

@app.callback(
    Output("download-dataframe-csv","data"),
    Input("download-btn","n_clicks"),
    prevent_initial_call=True
)

# ── Auto-populate fees for Strategy 2 dropdown ──────────────────────────────
@app.callback(
    [ Output("s2-maint-fee","value"), Output("s2-incentive-fee","value") ],
    Input("s2-existing","value")
)
def populate_s2_fees(selected):
    if selected in preset_fees:
        f = preset_fees[selected]
        return f["maint"], f["incentive"]
    return None, None

# ── Auto-populate fees for Strategy 3 dropdown ──────────────────────────────
@app.callback(
    [ Output("s3-maint-fee","value"), Output("s3-incentive-fee","value") ],
    Input("s3-existing","value")
)
def populate_s3_fees(selected):
    if selected in preset_fees:
        f = preset_fees[selected]
        return f["maint"], f["incentive"]
    return None, None

def download(n):
    df = qs.reports.metrics(rets,"full",return_data=True,display=False)
    return dcc.send_data_frame(df.to_csv,"metrics.csv")

if __name__=="__main__":
    app.run(debug=True,port=8077)
