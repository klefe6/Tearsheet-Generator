import os
import base64
import openpyxl
from datetime import datetime

import pandas as pd
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

import numpy as np
import plotly.graph_objs as go

import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

import yfinance as yf

import quantstats as qs
from quantstats import utils
from collections import OrderedDict

# ==============================================================================
# 1) BUSINESS-DAY CALENDAR
#    Create a CustomBusinessDay that drops weekends & US federal holidays
# ==============================================================================
us_bd = CustomBusinessDay(calendar=USFederalHolidayCalendar())

# ==============================================================================
# 2) LOGO ENCODING & ESTHETICS
#    Read your branded logo and encode it as base64 for Dash images
# ==============================================================================
logo_path = r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents\2_Hughes & Company Marketing\Branded Logo\Trianle-Only-Logo.png"
try:
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode("utf-8")
    logo_src = f"data:image/png;base64,{logo_b64}"
except FileNotFoundError:
    print(f"Error: Logo file not found at {logo_path}")
    logo_src = ""
# ─── Brand colors ────────────────────────────────
WHITE_BG     = "#ffffff"
GREY_BG      = "#EBEBEB"   # matches ggplot2’s plot_bgcolor
PRIMARY_COLOR = "#0D3562"  # your “blue,” user‐changeable
SECONDARY_COLOR = "#CCCCCC"

LEFT_TABLE_GAPS = "20px"
RIGHT_TABLE_GAPS = "30px"

HEADER_ROW_CLASS = "bg-light"

# ==============================================================================
# 3) CONFIGURATION
#    Strategy name, benchmark list, and NAV CSV path
# ==============================================================================
STRATEGY_NAME = "TKP"

BENCHMARKS = [
    "^SP500TR",   # S&P 500 Total Return
    "AGG",        # US Aggregate Bond
    "GLD",        # Gold ETF
    "BTC-USD",    # Bitcoin
    "ETH-USD",    # Ethereum
]

xlsx_path = (
    r"C:\Users\H&CDanHughes\Hughes & Company\Hughes & Company - Documents\3_Advisors Marketing (Tearsheets, PitchBooks, etc)\1. Tearsheet Project\TKP\VADI\tkp_alex.xlsx"
)

# ============================================================================== 
# 4) LOAD & VALIDATE NAV DATA (Excel cols B=Date, M=nav‑x1)
# ==============================================================================
import sys

try:
    # Load only columns B and M, parse B as Date
    NAV_df = pd.read_excel(
        xlsx_path,
        sheet_name="Sheet1",
        usecols="B,M",              # Excel columns B and M
        header=0,                   # first row is header
        parse_dates=["Date"],       # parse the B‑column into datetime
        engine="openpyxl",
    )
except Exception as e:
    print(f"❌ Failed to load NAV data: {e}")
    sys.exit(1)

# Make sure pandas named the second column correctly
if NAV_df.columns[1] != "nav‑x1" and NAV_df.columns[1] != "nav-x1":
    NAV_df.rename(columns={NAV_df.columns[1]: "nav-x1"}, inplace=True)

# Set Date as the index
NAV_df.set_index("Date", inplace=True)

# Drop exact duplicates so .asfreq() works
if NAV_df.index.has_duplicates:
    NAV_df = NAV_df[~NAV_df.index.duplicated(keep="first")]

# Reindex to your custom business‑day calendar
NAV_df = NAV_df.asfreq(us_bd)

print("✅ NAV data loaded successfully (Date + nav‑x1).")



# ==============================================================================
# 5) SELECT NAV VALUE COLUMN
#    Look for one of your preferred names first (e.g. "CL" or "NAV"),
#    then fall back to the first numeric column if none are present.
#    To change later, just update NAV_CANDIDATES.
# ==============================================================================
NAV_CANDIDATES = [
    "nav-x1",    # your composite Net Liquidation Value column in the sheet
       # alternative name you might use in the future
]

for cand in NAV_CANDIDATES:
    if cand in NAV_df.columns:
        NAV_col = cand
        break
else:
    # fallback: first purely numeric column
    numeric_cols = NAV_df.select_dtypes(include=[np.number]).columns
    if not numeric_cols.empty:
        NAV_col = numeric_cols[0]
    else:
        raise KeyError(
            f"None of {NAV_CANDIDATES!r} present and no numeric column found."
        )

print(f"▶️ Using NAV column: {NAV_col}")


# ==============================================================================
# 6) NON-COMPOUNDED DAILY RETURNS
#    Compute each day's P&L as a % of starting NAV (baseline)
# ==============================================================================
baseline = NAV_df[NAV_col].iloc[0]
daily_returns = NAV_df[NAV_col].diff().div(baseline).dropna()





# ==============================================================================
# 7) DOWNLOAD & ALIGN BENCHMARKS
#    For each symbol, get daily returns, align to NAV dates, then compute cum & drawdown
# ==============================================================================
bench_map = OrderedDict([
    ("SPXTR", "^SP500TR"),
    ("AGG",   "AGG"),
    ("GLD",   "GLD"),
    ("BTC",   "BTC-USD"),
    ("ETH",   "ETH-USD"),
])
# Filter to only those you configured
bench_map = {k:v for k,v in bench_map.items() if v in BENCHMARKS}

bench_ret, bench_cum, bench_dd = {}, {}, {}
for name, sym in bench_map.items():
    # 1) get evenly-spaced returns series
    full_ret = utils.download_returns(sym)
    aligned = full_ret.reindex(NAV_df.index).ffill().bfill().dropna()
    # 2) cumulative growth
    cum = (1 + aligned).cumprod()
    # 3) drawdown in %
    dd = (cum / cum.cummax() - 1) * 100

    bench_ret[name] = aligned
    bench_cum[name] = cum
    bench_dd[name]  = dd

# ==============================================================================
# 8) MONTHLY SIMPLE RETURNS (NON-COMPOUNDED) 
#    + MONTH-CELLS THAT SUM TO TRUE YEAR-OVER-YEAR RETURN
# ==============================================================================

# 8a) Month-end and month-start NAV
mp          = NAV_df.index.to_period("M")
month_last  = NAV_df[NAV_col].groupby(mp).last()
month_first = month_last.shift(1)
month_first.loc[month_last.index.min()] = baseline  # first-month start = baseline

# 8b) Compute each month’s change **relative** to fixed baseline
monthly_simple = (month_last - month_first) / baseline * 100

 
 
 
 
 
 
 
# 8c) Sum those 12 numbers to get the Year Total
yearly_simple = monthly_simple.groupby(monthly_simple.index.year).sum()

# 8d) Build the “calendar” table
years  = sorted(monthly_simple.index.year.unique())
months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

monthly_data = {"Year": [str(y) for y in years]}

for idx, m in enumerate(months, start=1):
    monthly_data[m] = [
        # look up period in monthly_simple; if missing, blank
        f"{monthly_simple.get(pd.Period(f'{y}-{idx:02d}'), 0):.2f}%"
        if pd.Period(f"{y}-{idx:02d}") in monthly_simple.index
        else ""
        for y in years
    ]

# 8e) Use the sum-of-months for Year Total
monthly_data["Year Total"] = [
    f"{yearly_simple.get(y, 0):.2f}%"
    for y in years
]

monthly_df = pd.DataFrame(monthly_data)



# ==============================================================================
# 9) DAILY PERFORMANCE METRICS
#    Define a helper to compute all your key stats over any period
# ==============================================================================
def calculate_period_metrics(returns: pd.Series, start_date: pd.Timestamp) -> dict:
    """
    Given a series of non-compounded daily returns,
    compute cumulative return, annualized, avg daily,
    win/loss counts & rates, top/bottom 3 days.
    """
    keys = [
        "Cumulative Return", "Annualized Return", "Avg Daily Return",
        "Number of Trading Days", "% Winning Days", "% Losing Days",
        "Best 3 Days", "Worst 3 Days",
    ]
    if len(returns) < 2:
        return dict.fromkeys(keys, "—")

    cum = returns.sum()
    days = len(returns)
    # annualize simple sum-of-daily
    annualized = cum * 365.0 / (returns.index.max() - start_date).days
    avg = returns.mean()

    wins = (returns > 0).sum()
    losses = (returns < 0).sum()

    top3 = returns.nlargest(3) * 100
    bot3 = returns.nsmallest(3) * 100

    return {
        "Cumulative Return":      f"{cum*100:.1f}%",
        "Annualized Return":      f"{annualized*100:.1f}%",
        "Avg Daily Return":       f"{avg*100:.3f}%",
        "Number of Trading Days": str(days),
        "% Winning Days":         f"{wins} ({wins/days*100:.1f}%)",
        "% Losing Days":          f"{losses} ({losses/days*100:.1f}%)",
        "Best 3 Days":            ", ".join(f"{v:.2f}%" for v in top3),
        "Worst 3 Days":           ", ".join(f"{v:.2f}%" for v in bot3),
    }

# ── List of the metrics in the order you want them shown ────────────────────
metric_labels = [
    "Cumulative Return",
    "Annualized Return",
    "Avg Daily Return",
    "Number of Trading Days",
    "% Winning Days",
    "% Losing Days",
    "Best 3 Days",
    "Worst 3 Days"
]

# ── Define period boundaries ────────────────────────────────────────────────
inception_start = NAV_df.index.min()
ttm_start       = NAV_df.index.max() - pd.DateOffset(years=1)

# ── Slice your strategy series ─────────────────────────────────────────────
one_year_returns  = daily_returns.loc[ttm_start:].dropna()
inception_returns = daily_returns.copy()

# ── Slice your SPXTR series ────────────────────────────────────────────────
spxtr_series       = bench_ret["SPXTR"]
spxtr_one_year     = spxtr_series.loc[ttm_start:].dropna()
spxtr_inception    = spxtr_series.loc[inception_start:].dropna()

# ── Compute metrics ─────────────────────────────────────────────────────────
one_year_metrics       = calculate_period_metrics(one_year_returns,  ttm_start)
inception_metrics      = calculate_period_metrics(inception_returns, inception_start)

# ── Assemble your DataFrame ────────────────────────────────────────────────
daily_perf_df = pd.DataFrame({
    "Metric": metric_labels,
    f"{STRATEGY_NAME} (1 Year/TTM)":    [one_year_metrics[m] for m in metric_labels],
    f"{STRATEGY_NAME} (Inception)":     [inception_metrics[m] for m in metric_labels],
})




# ──────────────────────────────────────────────────────────────────────────────
# CONFIG: choose your drawdown method
# ──────────────────────────────────────────────────────────────────────────────
# True  = standard peak-to-trough drawdown (quantstats style)
# False = custom baseline-relative drawdown
USE_QUANTSTATS_DD_STRATEGY   = False   # TKP
USE_QUANTSTATS_DD_BENCHMARKS = True  # SPXTR & others
SHOW_DD_PRICE = False   # True ⇒ “2025-02-20 (152345.67)”, False ⇒ “2025-02-20”

# ==============================================================================
# 10) Compute Worst (Max) Drawdown Profile, Inception Only
# ==============================================================================
def drawdown_profile(
    nav: pd.Series,
    baseline: float,
    use_quantstats: bool,
    show_price: bool,
    price_series: pd.Series
) -> dict:
    """
    Returns the single worst drawdown episode,
    with optional price display.
    """
    # 1) running peak & choose drawdown series
    running_max = nav.cummax()
    if use_quantstats:
        dd_series = (nav / running_max - 1) * 100
    else:
        dd_series = (nav - running_max) / baseline * 100

    # 2) find trough and its preceding peak
    trough = dd_series.idxmin()
    peak   = nav.loc[:trough].idxmax()

    # 3) format dates and optional prices
    peak_date   = peak.strftime("%Y-%m-%d")
    valley_date = trough.strftime("%Y-%m-%d")

    if show_price:
        peak_str   = f"{peak_date} - {price_series.loc[peak]:,.2f}"
        valley_str = f"{valley_date} - {price_series.loc[trough]:,.2f}"
    else:
        peak_str   = peak_date
        valley_str = valley_date

     # 4) recovery logic
    rec      = nav[trough:][nav[trough:] >= nav[peak]]
    rec_idx  = rec.index[0] if not rec.empty else None
    decline_days = (trough - peak).days

    if rec_idx:
        # fully recovered
        end_date   = rec_idx.strftime("%Y-%m-%d")
        if show_price:
            price = price_series.loc[rec_idx]
            end_str = f"{end_date} - {price:,.2f}"
        else:
            end_str = end_date

        recovery_days = (rec_idx - trough).days
        total_days    = (rec_idx - peak).days
        recovery_text = f"{recovery_days} days"
        total_text    = f"{total_days} days"

    else:
        # still in drawdown
        # inside your `else:` for “not recovered”:
        last_date     = nav.index.max()
        last_price    = price_series.loc[last_date]
        peak_price    = price_series.loc[peak]
        trough_price  = price_series.loc[trough]

        remaining_pct = (peak_price - last_price) / (peak_price - trough_price) * 100

        last_date = nav.index.max()
        if show_price:
            last_price = price_series.loc[last_date]
            end_str = (
                f"TBD - Current Price is {last_price:,.2f}, "
                f"{remaining_pct:.1f} % of the current drawdown is left for a full recovery"
            )
        else:
            end_str = "TBD"

        recovery_days = (last_date - trough).days
        total_days    = (last_date - peak).days
        recovery_text = f"Ongoing for {recovery_days} days"
        total_text    = f"Ongoing for {total_days} days"

    # 5) worst depth
    depth = dd_series.min()

    # assemble result with dynamic field names
    result = {
        "Depth":           f"{depth:.1f}%",
        "Decline Period":  f"{decline_days} days",
        "Recovery Period": recovery_text,
        "Total Duration":  total_text
    }

    if show_price:
        result["Start Date & Price"]    = peak_str
        result["Valley Date & Price"]   = valley_str
        result["End Date & Price"]      = end_str
    else:
        result["Start Date"]            = peak_str
        result["Valley Date"]           = valley_str
        result["End Date"]              = end_str

    return result

spxtr_price_series = (
    yf.download(
        "^SP500TR",
        start="2023-04-01",
        end="2025-07-01",
        auto_adjust=True,
        progress=False
    )[['Close']]
    .squeeze()
    .reindex(NAV_df.index)
    .ffill()
)

# ==============================================================================
# 11) Build the “Worst Drawdown” DataFrame
# ==============================================================================
# Strategy NAV + baseline
strategy_nav      = NAV_df[NAV_col]
strategy_baseline = strategy_nav.iloc[0]

# SPXTR NAV scaled to strategy baseline
spxtr_returns    = bench_ret["SPXTR"]
spxtr_nav        = (1 + spxtr_returns.loc[inception_start:]).cumprod() * strategy_baseline
spxtr_baseline   = strategy_baseline

# Make sure you have the raw SPXTR close-price series defined as spxtr_price_series
# e.g.: spxtr_price_series = utils.download_price("^SP500TR").reindex(NAV_df.index).ffill()

period_slices = {
    f"{STRATEGY_NAME} (Inception)": (
        strategy_nav,
        strategy_baseline,
        USE_QUANTSTATS_DD_STRATEGY,
        SHOW_DD_PRICE,
        strategy_nav        # use NAV as price series for TKP
    ),
    "SPXTR (Inception)": (
        spxtr_nav,
        spxtr_baseline,
        USE_QUANTSTATS_DD_BENCHMARKS,
        SHOW_DD_PRICE,
        spxtr_price_series  # your SPXTR close-price Series
    ),
}

max_dd_df = (
    pd.DataFrame({
        name: drawdown_profile(
            nav,
            baseline,
            use_flag,
            show_price,
            price_series
        )
        for name, (nav, baseline, use_flag, show_price, price_series)
            in period_slices.items()
    })
    .rename_axis("Metric")
    .reset_index()
)


# ==============================================================================
# 12) Hard-coded “Additional Information”
# ==============================================================================
grouped_info = {
    "Account Stats": [
        ("Nominal Assets Being Traded in the Program", "300k"),
        ("Total Accounts/Tranches Opened",           "4"),
        ("Accounts/Tranches Currently Open",         "2"),
        ("Accounts/Tranches Closed Profitably",      "2"),
        ("Accounts/Tranches Closed Unprofitably",    "0"),
        ("Range of Net Returns of Accounts/Tranches Closed", "0.36% to 4.2%"),
    ],
    "Terms & Fees": [
        ("Investment Type",    "Managed Account"),
        ("Fee Structure",      "0% Annual / 20% Performance"),
        ("High Water Mark",    "Yes"),
        ("Lockup Period",      "None"),
        ("Liquidity",          "Daily"),
        ("Notional Funding",   "Yes"),
        ("Execution FCM",      "StoneX Financial"),
    ],
}

# ==============================================================================
# 13) Legal disclaimers & footer contact
# ==============================================================================
hcdisclaimer_text = (
    "UNTIL TKP IS OFFICIALLY OPENED TO OUTSIDE INVESTORS BY THE INTRODUCING BROKER, "
    "THE STRATEGY REMAINS PROPRIETARY AND THIS PAGE OR DESCRIPTION IS NOT A SOLICITATION TO INVEST. "
    "NO SUBSCRIPTION DOCUMENTS HAVE BEEN ISSUED, AND TKP WILL ONLY BECOME AVAILABLE ONCE THE IB "
    "PUBLISHES THE APPROPRIATE SUBSCRIPTION MATERIALS AND DECLARES THE PROGRAM OPEN FOR OUTSIDE INVESTMENT."
)

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
# 14) Helper: Build Plotly “NAV” figure
# ==============================================================================
def build_NAV_figure():
    fig = go.Figure(
        go.Scatter(
            x=NAV_df.index,
            y=NAV_df[NAV_col],
            mode="lines",
            line={"color": PRIMARY_COLOR},
            name="NAV"
        )
    )

    fig.update_layout(
        title={
            "text": "<u>Non-Compounded NAV Since Inception</u>",
            "x": 0.5,
            "xanchor": "center"
        },
        template="ggplot2",
        plot_bgcolor=GREY_BG,
        paper_bgcolor=WHITE_BG,
        xaxis_title="Date",
        yaxis_title="Value Added Daily Index",
        autosize=True,               # ← responsive sizing
        margin={"l": 40, "r": 10, "t": 40, "b": 40}
    )

    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=True)
    return fig


# ==============================================================================
# 15) Helper: Build Plotly “Drawdown” figure
# ==============================================================================
def build_drawdown_figure():
    fig = go.Figure()
    # build NAV
    strat_nav = (1 + daily_returns).cumprod()
    # baseline-relative drawdown
    strat_max = strat_nav.cummax()
    strat_dd  = (strat_nav - strat_max) / baseline * 100

    fig.add_trace(go.Scatter(
        x=strat_dd.index,
        y=strat_dd,
        name=STRATEGY_NAME + " DD (baseline)",
        line={"color":PRIMARY_COLOR}
    ))

    for name, cum in bench_cum.items():
        bench_max = cum.cummax()
        bench_dd_baseline = (cum - bench_max) / baseline * 100
        fig.add_trace(go.Scatter(
            x=bench_dd_baseline.index,
            y=bench_dd_baseline.values,
            name=f"{name} DD (baseline)",
            opacity=0.6
        ))

    fig.update_layout(
        title="Drawdown vs Peak (baseline-denominator)",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)"
    )
    return fig

# ==============================================================================
# 15) Construct the Dash App
# ==============================================================================
app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, "/assets/styles.css"],
    suppress_callback_exceptions=True,
    title="H&C – TKP",
)

def serve_layout():
    last_updated = NAV_df.index.max().strftime("%B %d, %Y")

    return dbc.Container(
        id="page-container",
        fluid=True,        # ⇒ always 100% on xs, sm; constrained on md+ breakpoints
        className="py-4",
        children=[
            # ── Header ─────────────────────────────────────────────────────────
            dbc.Row(
                [
                    dbc.Col(
                        html.Img(
                            src=logo_src,
                            className="img-fluid",               # makes it scale down on small screens
                            style={
                                "maxHeight": "100px",            # never exceed 100px tall
                                "height": "auto",
                                "width": "auto",
                            },
                            alt="Hughes & Company Logo"
                        ),
                        width=2,
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.H2("Hughes & Company LLC", className="text-center"),
                                html.H5("The Keymaker Program", className="text-center text-muted"),
                            ],
                            style={"lineHeight": "1.2", "paddingTop": "20px"},
                        ),
                        width=8,
                    ),
                    dbc.Col(
                    html.Div(
                        [
                            # desktop style (only on md and up)
                            html.Div(
                                [
                                    html.H6("Last Updated", className="text-end text-secondary mb-1"),
                                    html.H5(last_updated, className="text-end text-primary"),
                                ],
                                className="d-none d-md-block",   # hide on small viewports
                                style={"paddingTop": "30px"}
                            ),
                            # mobile style (only on sm and down)
                            html.Div(
                                [
                                    # re-add “Last Updated” label
                                    html.Small(
                                        "Last Updated",
                                        className="d-block text-end text-primary mb-1",
                                    ),
                                    # show the date underneath in one line
                                    html.Small(
                                        last_updated,
                                        className="d-block text-end text-primary",
                                    ),
                                ],
                                className="d-block d-md-none",
                                style={"paddingTop": "20px"}
                            ),
                        ]
                    ),
                    width=2,
                ),
                ],
                align="center",
                style={"backgroundColor": GREY_BG, "padding": "10px 0", "pageBreakInside": "avoid"},  # Prevent header split
                className="header-row",
            ),
            html.Hr(),

            # ── Description ────────────────────────────────────────────────────
            html.Div(
                [
                    html.P(
                        "Hughes & Company LLC is an introducing brokerage firm with expertise in the futures options industry. ",
                        className="lead text-center",
                    ),
                    html.P(
                        "Principals: Daniel V. Hughes III | Inception: April 2023 | Products Traded: E-Mini Micro S&P 500 Options | Styles: Short Options",
                        className="text-center mb-5",
                    ),
                ],
                className="description",
            ),

            # ── NAV Chart ─────────────────────────────────────────────────────
            dcc.Graph(
                id="NAV-graph",
                figure=build_NAV_figure(),
                config={"displayModeBar": False, "responsive": True},
                style={
                    "width": "100%",
                    "maxWidth": "100%",  # Ensure it doesn't exceed page width
                    "maxHeight": "400px",  # Cap height to fit on page
                    "pageBreakInside": "avoid",
                    #"overflow": "hidden",  # Prevent overflow
                },
            ),
            html.P(
                "This chart visualizes the growth of a $150,000 investment from inception to today. "
                "NAV stands for Net Asset Value; it reflects the non-compounded performance, net of all fees.",
                className="text-center small",
                style={"marginTop": "4rem"}  # gives some breathing room
            ),

            html.P(
                "Please note that all percentages shown are relative to the initial amount invested. "
                "Also note that performance may vary depending on the time of entry due to the fixed-sizing nature of this strategy.",
                className="text-center small",
                style={"marginBottom": "3rem"}
            ),

            # ── Performance Summary ────────────────────────────────────────────
            html.H5("Performance Summary", className="text-center mb-2"),
            dbc.Table(
                [
                    html.Thead(
                        html.Tr([
                            html.Th(col, style={"backgroundColor": GREY_BG, "color": "#000"})
                            for col in monthly_df.columns
                        ])
                    ),
                    html.Tbody([
                        html.Tr([html.Td(monthly_df.iloc[i][col]) for col in monthly_df.columns])
                        for i in range(len(monthly_df))
                    ])
                ],
                bordered=True,
                hover=True,
                size="sm",
                className="table-responsive mb-5",
                style={"width": "95%", "margin": "0 auto", "pageBreakInside": "avoid"},
            ),

            # ── General and Sector Information Tables ──────────────────────────
dbc.Row(
    [
        # ── Left Side: Strategy Overview ─────────────────────────────
        dbc.Col(
            dbc.Card(
                [
                    dbc.CardHeader(html.H6("Strategy Overview", className="mb-0"), className=HEADER_ROW_CLASS),
                    dbc.CardBody(
                        dbc.Table(
                            [
                                # header
                                html.Thead(
                                    html.Tr([ html.Th("Strategy Description", colSpan=3, className=HEADER_ROW_CLASS) ]),
                                    className="bg-light"
                                ),

                                # body
                                html.Tbody([
                                    # description row
                                    html.Tr([
                                        html.Td(
                                            [
                                                html.P(
                                                    "The Keymaker Program (TKP) is a unique offering by Hughes & Company LLC which utilizes specific strike daily options on the S&P 500 Index. It is oriented to achieve long-biased stable returns through intraday scalping of a proprietarily selected Put strikes in the nearest expiring option chain of the Micro ES product suite, and is most active in Volatile environments. The strategy simultaneously was built to allow for Put assignments for underlying Micro Futures Contracts, writing proprietarily selected Call strikes in sequential fashion to mitigate both drawdown depth and duration regardless of market environment. TKP has been designed as a long term, positively performing, market-neutral offering, with daily visibility and liquidity."
                                                ),
                                            ],
                                            colSpan=3,
                                            style={
                                                "whiteSpace": "normal",
                                                "fontStyle": "italic",
                                            }
                                        )
                                    ]),

                                    # spacer
                                    html.Tr([
                                        html.Td("", colSpan=3, style={"height": LEFT_TABLE_GAPS})
                                    ]),
                                                html.Tr([
                                                    html.Th(
                                                    "Methodology",
                                                    colSpan=3,
                                                    #style={"backgroundColor": GREY_BG},  
                                                    className= "bg-light",
                                                    )
                                                ]),
                                                html.Tr([
                                                    html.Td("Trading Style"),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td([
                                                                html.Tr([
                                                                    html.Td(html.Span("✓ Mean Reversion", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td(html.Span("✗ Technical", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td(html.Span("✗ Fundamental", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                            ]),
                                                            html.Td(),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td([
                                                                html.Tr([
                                                                    html.Td(html.Span("✗ Breakout", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td(html.Span("✓ Premium Collection", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td(html.Span("✗ Arbitrage", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                            ]),
                                                            html.Td(),
                                                        ]),
                                                    ]),
                                                ]),
                                                html.Tr([
                                                    html.Td("Decision Making Style"),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td(html.Span("✓ Systematic", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                            html.Td(),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td(html.Span("✗ Discretionary", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                            html.Td(),
                                                        ]),
                                                    ]),
                                                ]),
                                                html.Tr([
                                                    html.Td("Execution Style"),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td(html.Span("✓ Automated", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                            html.Td(),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td(html.Span("✓ Manual", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                            html.Td(),
                                                        ]),
                                                    ]),
                                                ]),
                                                html.Tr([
                                                    html.Td("Position Types"),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td([
                                                                html.Tr([
                                                                    html.Td(html.Span("✓ Straight Futures", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td(html.Span("✗ Futures Spreads", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td(html.Span("✗ Cross Product Spreads", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                            ]),
                                                            html.Td(),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td([
                                                                html.Tr([
                                                                    html.Td(html.Span("✓ Covered Options", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td(html.Span("✓ Uncovered Options", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),
                                                                html.Tr([
                                                                    html.Td(html.Span("✗ Options Spreads", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
                                                                ]),

                                                            ]),
                                                            html.Td(),
                                                        ]),
                                                    ]),
                                                ]),
                                                html.Tr([
                                                    html.Td("", colSpan=3, style={"height": LEFT_TABLE_GAPS}),
                                                ]),  # Blank row above Activity Profile
                                                html.Tr([
                                                    html.Th("Activity Profile", colSpan=3, className=HEADER_ROW_CLASS),
                                                ]),
                                                html.Tr([
                                                    html.Td("Trading Frequency"),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td("Contracts Traded/Year/Million", style={"text-decoration": "underline"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ Low (<500 Contracts)", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ Medium (500-2000 Contracts)", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ High (>2000 Contracts)", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td("Approximate Average", style={"text-decoration": "underline"}), 
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("--"), style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("1000"), style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("--"), style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                    ]),
                                                ]),
                                                html.Tr([
                                                    html.Td("Holding Periods"),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td("Time Period", style={"text-decoration": "underline"}), 
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ Intraday", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ 1-30 Days", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ 1-3 Months", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ 4+ Months", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td("Percentage (Totals 100%)", style={"text-decoration": "underline"}), 
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("95 %"), style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("5 %"), style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("-- %"), style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("-- %"), style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                    ]),
                                                ]),
                                            ]),
                                        ],
                                        striped=False,
                                        bordered=True,
                                        hover=True,
                                        size="sm",
                                        className="table-responsive",
                                    )
                                ),
                            ],
                            outline=True,
                            className="mb-4",
                        ),
                        width=6,
                    ),

                    # ── Right Side: Sector Information ─────────────────────
                    dbc.Col(
                        dbc.Card(
                            [
                                dbc.CardHeader(html.H6("Trading Universe & Risk Profile", className="mb-0"), className=HEADER_ROW_CLASS),
                                dbc.CardBody(
                                    dbc.Table(
                                        [
                                            html.Thead(
                                                html.Tr([
                                                    html.Th("Product Exchanges", colSpan=3, className=HEADER_ROW_CLASS),
                                                ])
                                            ),
                                            html.Tbody([
                                                html.Tr([
                                                    html.Td("North America"),
                                                    html.Td("Europe"),
                                                    html.Td("Asia/Pacific"),
                                                ]),
                                                html.Tr([
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td(html.Span("✓ CME Group / MGX", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ ICE US", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ CFE", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]), 
                                                        html.Tr([
                                                            html.Td(html.Span("✗ LME", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ NODAL", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td(html.Span("✗ ICE UK / Financial", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ Eurex", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ Euronext", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                        html.Span("✗ DGCX", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td(html.Span("✗ SGX", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ HKFE", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ OSE / TOCOM", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ SAFEX", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ Bursa Malaysia", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                    ]),
                                                ]),
                                                html.Tr([
                                                    html.Td("", colSpan=3, style={"height": RIGHT_TABLE_GAPS}),
                                                ]),  # Blank row above Futures Products Traded
                                                html.Tr([
                                                    html.Th("Futures Products Traded", colSpan=3, className=HEADER_ROW_CLASS),
                                                ]),
                                                html.Tr([
                                                    html.Td("Financial Instruments"),
                                                    html.Td("Agricultural Commodities"),
                                                    html.Td("Other Asset Classes"),
                                                ]),
                                                html.Tr([
                                                    html.Td([
                                                        html.Tr(html.Td(html.Span("✓ Equity Indices", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}))),
                                                        html.Tr(html.Td(html.Span("✗ Volatility Indices", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                        html.Tr(html.Td(html.Span("✗ Interest Rates", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                        html.Tr(html.Td(html.Span("✗ Currencies", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                    ]),
                                                    html.Td([
                                                        html.Tr(html.Td(html.Span("✗ Grains / Oilseeds", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                        html.Tr(html.Td(html.Span("✗ Softs", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                        html.Tr(html.Td(html.Span("✗ Dairy", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                        html.Tr(html.Td(html.Span("✗ Meats / Livestock", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                    ]),
                                                    html.Td([
                                                        html.Tr(html.Td(html.Span("✗ Metals", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                        html.Tr(html.Td(html.Span("✗ Renewable Fuels", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                        html.Tr(html.Td(html.Span("✗ Cryptocurrencies", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}))),
                                                    ]),
                                                ]),

                                                html.Tr([
                                                    html.Td("", colSpan=3, style={"height": RIGHT_TABLE_GAPS}),
                                                ]),  # Blank row above Risk Management
                                                
                                                html.Tr([
                                                    html.Th("Risk Management", colSpan=3, className=HEADER_ROW_CLASS),
                                                ]),
                                                
                                                html.Tr([
                                                    html.Td("Average Margin Usage"),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td("1.77 %"),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        
                                                    ]),
                                                ]),

                                                html.Tr([
                                                    html.Td([
                                                        # Main label
                                                        html.Div("Exchange Margin Ratios"),
                                                        # Explanatory text in a smaller font
                                                        html.Small(
                                                            "This is not cost-bearing, but is a measure of the exchange-required minimum funds to be in the account versus the Nominal Trade Size (150 k)",
                                                            style={
                                                                "fontSize": "0.75rem",
                                                                "color": "#6c757d",
                                                                "marginTop": "0.25rem",  # a little breathing room
                                                                "display": "block"
                                                            }
                                                        ),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td("Ranges", style={"text-decoration": "underline"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ 0-10 %", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ 10-25 %", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ 25-50 %", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ 50 %+", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                    ]),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td("Percentage", style={"text-decoration": "underline"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("94.8 %", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("5.2 %", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("-- %", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("-- %", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                    ]),
                                                ]),

                                                html.Tr([
                                                    html.Td("Risk Controls"),
                                                    html.Td([
                                                        html.Tr([
                                                            html.Td(html.Span("✗ Stop Losses", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}, id="stop-losses")),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ VaR Considerations", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}, id="var-considerations")),
                                                        ]),
                                                        #html.Tr([
                                                        #    html.Td(html.Span("Fixed Stop Losses", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        #]),
                                                    ]),
                                                    html.Td([
                                                        #html.Tr([
                                                        #    html.Td(html.Span("Trailing Stops", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        #]),
                                                        #html.Tr([
                                                        #    html.Td(html.Span("Anti-Martingale", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        #]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ Position Reductions", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}, id="position-reductions")),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ Position Offsets (Hedges)", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}, id="position-hedges")),
                                                        ]),
                                                    ]),
                                                ]),

                                                # Tooltips for Risk Controls
                                                dbc.Tooltip(
                                                    "Mechanisms to limit potential losses in volatile markets.",
                                                    target="risk-controls",
                                                    placement="top",
                                                ),

                                                # Tooltip for Stop Losses
                                                dbc.Tooltip(
                                                    "Orders that close a position at a predefined price to cap losses.",
                                                    target="stop-losses",
                                                    placement="top",
                                                ),

                                                # Tooltip for VaR Considerations
                                                dbc.Tooltip(
                                                    "Statistical estimate of potential loss over a given period at a chosen confidence level.",
                                                    target="var-considerations",
                                                    placement="top",
                                                ),

                                                # Tooltip for Position Reductions
                                                dbc.Tooltip(
                                                    "Gradual decrease in position size to reduce exposure as risk increases.",
                                                    target="position-reductions",
                                                    placement="top",
                                                ),

                                                # Tooltip for Position Offsets (Hedges)
                                                dbc.Tooltip(
                                                    "Taking opposite or correlated positions to hedge against adverse moves.",
                                                    target="position-hedges",
                                                    placement="top",
                                                ),
                                                
                                                html.Tr([
                                                    html.Td("", colSpan=3, style={"height": RIGHT_TABLE_GAPS}),
                                                ]),  # Blank row above Transaction Fees
                                                html.Tr([
                                                    html.Th("Transaction Fees", colSpan=3, className=HEADER_ROW_CLASS),
                                                ]),
                                                html.Tr([
                                                    html.Td("Weighted Average All-In Fees per Contract"),
                                                    html.Td("~ $0.30"),
                                                    html.Td(),
                                                ]),
                                            ]),
                                        ],
                                        striped=False,
                                        bordered=True,
                                        hover=True,
                                        size="sm",
                                        className="table-responsive",
                                    )
                                ),
                            ],
                            outline=True,
                            className="mb-4",
                        ),
                        width=6,
                    ),
                ],
                justify="start",
                className="mb-2",
            ),

            # ── Metrics & Info ─────────────────────────────────────────────────────────────────────
            dbc.Row(
                [
                    # ── LEFT SIDE: Metrics + Drawdown ─────────────────────
                    dbc.Col(
                        [
                            # Performance Metrics
                            dbc.Card(
                                [
                                    dbc.CardHeader(html.H6("Performance Metrics", className="mb-0")),
                                    dbc.CardBody(
                                        dbc.Table.from_dataframe(
                                            daily_perf_df,
                                            striped=False,
                                            bordered=True,
                                            hover=True,
                                            size="sm",
                                            className="fixed-cols",
                                        )
                                    ),
                                ],
                                outline=True,
                                className="mb-4",
                            ),

                            # Maximum Drawdown Profile
                            dbc.Card(
                                [
                                    dbc.CardHeader(html.H6("Maximum Drawdown Profile", className="mb-0")),
                                    dbc.CardBody(
                                        dbc.Table.from_dataframe(
                                            max_dd_df,
                                            striped=False,
                                            bordered=True,
                                            hover=True,
                                            size="sm",
                                            className="fixed-cols",
                                        )
                                    ),
                                    dbc.CardFooter(
                                        html.Small(
                                            "Both TKP & SPXTR drawdown stats are reflective of the same $150,000 fixed nominal exposure at start of drawdown period.",
                                            className="text-muted fst-italic"
                                        )
                                    ),
                                ],
                                outline=True,
                                className="mb-4",
                            ),
                        ],
                        width=6,
                    ),

                    # ── RIGHT SIDE: Additional Information ─────────────────
                    dbc.Col(
                                                dbc.Card(
                                                    [
                                                        dbc.CardHeader(html.H6("Investor Information", className="mb-0")),
                                                        dbc.CardBody(
                                                            html.Div(
                                                                [
                                                                    dbc.Table(
                                                    [
                                                        html.Thead(
                                                            html.Tr([
                                                                html.Th("Terms & Fees"),
                                                                html.Th("Details"),
                                                            ])
                                                        ),
                                                        html.Tbody([
                                                            html.Tr([
                                                                html.Td(label),
                                                                html.Td(value)
                                                            ])
                                                            for label, value in grouped_info["Terms & Fees"]
                                                        ]),
                                                    ],
                                                    striped=False,
                                                    bordered=True,
                                                    hover=True,
                                                    size="sm",
                                                    className="mb-3"
                                                ),
                                                dbc.Table(
                                                [
                                                    html.Thead(
                                                        html.Tr([
                                                            html.Th("Account Stats"),
                                                            html.Th("Proprietary"),
                                                            html.Th("Client"),
                                                        ])
                                                    ),
                                                    html.Tbody([
                                                        html.Tr([
                                                            html.Td("Nominal Assets Being Traded in the Program"),
                                                            html.Td("$300,000"),
                                                            html.Td("0")
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Total Accounts/Tranches Opened"),
                                                            html.Td("4"),
                                                            html.Td("0")
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Accounts/Tranches Currently Open"),
                                                            html.Td("2"),
                                                            html.Td("0")
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Accounts/Tranches Closed Profitably"),
                                                            html.Td("2"),
                                                            html.Td("0")
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Accounts/Tranches Closed Unprofitably"),
                                                            html.Td("0"),
                                                            html.Td("0")
                                                        ]),
                                                        html.Tr([
                                                            html.Td("Range of Net Returns of Accounts/Tranches Closed"),
                                                            html.Td("0.36% to 4.2%"),
                                                            html.Td("N/A")
                                                        ]),
                                                    ]),
                                                ],
                                                striped=False,
                                                bordered=True,
                                                hover=True,
                                                size="sm",
                                                className="mb-3"
                                            ),
                                            html.P(
                                                "Other Notes:",
                                                className="small fw-bold mb-1 mt-2"
                                            ),
                                            html.P(
                                                "TKP allows for efficient, opportunistic deployments of capital in and out of the program in fixed nominal trading levels of $150,000 per tranche. The program will remain perpetually funded with permanent capital of the Introducing Broker in the form of a minimum of two tranches ($300,000 Nominal). The IB itself also has historically allocated more tranches, and closed tranches profitably, and plans on continuing in doing so, in what it considers opportunities for additional capital deployment based on drawdowns of the program itself, with expected recoveries. This capability is allowed for investors as well, with the announcement of any tranche opening or closure by/of the IB shared for complete disclosure and additional visibility for the benefit of all potential participants.",
                                                className="mt-2",
                                                style={"fontSize": "0.9rem"}
                                            ),
                                        ]
                                    )
                                ),
                            ],
                            outline=True,
                            className="mb-4",
                        ),
                        width=6,
                    ),
                ],
                justify="start",
                className="mb-2",
            ),

            # ── H&C Disclaimer ────────────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.P(hcdisclaimer_text, className="text-muted small"),
                    width=12
                ),
                className="mb-4",
            ),
            
            # ── General Disclaimer ────────────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.P(disclaimer_text, className="text-muted small"),
                    width=12
                ),
                className="mb-4",
            ),

            # ── Toggle & Footer ───────────────────────────────────────────────
            dbc.Row(
                dbc.Col(html.P(footer_contact, className="text-center small text-muted"), width=12),
                className="mb-2",
            ),
        ],
    )

dcc_store = dcc.Store(id="disclaimer-accepted", storage_type="session")

disclaimer_screen = html.Div(
    id="disclaimer-screen",
    children=html.Div(
        children=[
            html.H2("Important Notice", className="mb-4"),
            html.P(
                "By clicking “Accept,” you agree that the performance figures shown are strictly informational and do not amount to investment advice, a solicitation, or an offer to invest or participate in this strategy. This material is not intended to solicit funds.",
                className="lead mb-5"
            ),
            dbc.Button(
                "Accept & Continue",
                id="accept-button",
                color="primary"
            )
        ]
    )
)

main_app = html.Div(
    id="main-app",
    style={"display": "none"},
    children=serve_layout()
)

app.layout = html.Div([
    dcc_store,
    disclaimer_screen,
    main_app
])

@app.callback(
    Output("disclaimer-screen", "style"),
    Output("main-app", "style"),
    Input("accept-button", "n_clicks")
)
def show_main(n_clicks):
    if n_clicks and n_clicks > 0:
        return {"display": "none"}, {"display": "block"}
    return {"padding": "4rem", "textAlign": "center"}, {"display": "none"}



if __name__ == "__main__":
    app.run(debug=True, port=8076)