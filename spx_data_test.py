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

# ============================================================================
# Download SPX data and compute metrics
# ============================================================================

def fetch_spx_data(start, end):
    df = yf.download(
        '^GSPC',
        start=start,
        end=end,
        auto_adjust=True,
        progress=False
    )
    df = df['Close'].ffill()
    returns = df.pct_change().dropna()
    return df, returns

# Calculate performance metrics using quantstats
# ============================================================================
def calculate_period_metrics(returns: pd.Series, period_name: str, start_date: pd.Timestamp) -> dict:
    returns = returns.squeeze()
    if len(returns) < 2:
        fields = [
            "Cumulative Return", "Annualized Return", "Average Daily Return",
            "% Winning Days", "% Losing Days", "Max Drawdown",
            "Time to Recover", "Sharpe", "Volatility"
        ]
        return {f: "—" for f in fields}

    cum_growth = (returns + 1).prod() - 1
    days = (returns.index.max() - start_date).days + 1
    years = days / 365.0 if days > 0 else 1
    ann_return = (cum_growth + 1) ** (1 / years) - 1
    avg_daily = returns.mean()
    win_rate = qs.stats.win_rate(returns)
    loss_rate = 1 - win_rate
    max_dd = qs.stats.max_drawdown(returns)
    sharpe = qs.stats.sharpe(returns, rf=0)
    vol_pct = qs.stats.volatility(returns)

    # recovery calculation
    nav = (1 + returns).cumprod()
    dd_series = nav / nav.cummax() - 1
    if dd_series.min() < 0:
        trough = dd_series.idxmin()
        peak = nav[nav.index <= trough].max()
        recovered = nav[nav >= peak]
        recovery_days = (recovered.index[0] - trough).days if not recovered.empty else float('inf')
    else:
        recovery_days = 0

    recovery_str = f"{int(recovery_days)} days" if recovery_days != float('inf') else "ongoing"

    return {
        "Cumulative Return": f"{cum_growth*100:.1f}%",
        "Annualized Return": f"{ann_return*100:.1f}%",
        "Average Daily Return": f"{avg_daily*100:.3f}%",
        "% Winning Days": f"{win_rate*100:.1f}%",
        "% Losing Days": f"{loss_rate*100:.1f}%",
        "Max Drawdown": f"{max_dd*100:.1f}%",
        "Time to Recover": recovery_str,
        "Sharpe": f"{sharpe:.2f}",
        "Volatility": f"{vol_pct*100:.1f}%"
    }

# Fetch data
# ============================================================================
start_date = datetime(2020, 1, 1)
end_date = datetime.today()
spx_prices, spx_returns = fetch_spx_data(start_date, end_date)

# Define period boundaries
one_year_start = end_date - pd.DateOffset(years=1)
two_year_start = end_date - pd.DateOffset(years=2)

one_year_ret = spx_returns[spx_returns.index >= one_year_start]
two_year_ret = spx_returns[spx_returns.index >= two_year_start]
inception_ret = spx_returns.copy()

one_year_metrics = calculate_period_metrics(one_year_ret, "1 Year", one_year_start)
two_year_metrics = calculate_period_metrics(two_year_ret, "2 Year", two_year_start)
inception_metrics = calculate_period_metrics(inception_ret, "Inception", spx_returns.index.min())

# Assemble metrics DataFrame
metric_labels = list(one_year_metrics.keys())
metrics_df = pd.DataFrame({
    "Metric": metric_labels,
    "1 Year": [one_year_metrics[m] for m in metric_labels],
    "2 Year": [two_year_metrics[m] for m in metric_labels],
    "Inception": [inception_metrics[m] for m in metric_labels]
})

# Monthly returns for SPX
# ============================================================================
monthly = spx_prices.resample('M').last().pct_change().dropna() * 100
month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
years = sorted(monthly.index.year.unique())

month_data = {"Year": years}
for month_num, month_name in enumerate(month_names, start=1):
    col = []
    for yr in years:
        mask = (monthly.index.year == yr) & (monthly.index.month == month_num)
        subset = monthly[mask]
        if not subset.empty:
            # subset is a Series; grab the first value as a float
            val = float(subset.iloc[0])
            col.append(f"{val:.2f}%")
        else:
            col.append("—")
    month_data[month_name] = col

# Year Total
month_data["Year Total"] = [
    f"{float(monthly[monthly.index.year == yr].sum()):.2f}%"
    for yr in years
]

monthly_df = pd.DataFrame(month_data)

# Build SPX figure
# ============================================================================
def build_spx_figure():
    cum = (1 + spx_returns).cumprod()
    fig = go.Figure(
        data=[go.Scatter(x=cum.index, y=cum.values, name="SPX", line={"width":2})],
        layout=go.Layout(title="SPX Cumulative Return", xaxis_title="Date", yaxis_title="Cumulative Return")
    )
    return fig

# Dash App
# ============================================================================
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], title="SPX Dashboard")
app.layout = html.Div(
    style={"width":"80%","margin":"0 auto"},
    children=[
        html.H2("S&P 500 (^GSPC) Analysis", className="text-center my-4"),
        dcc.Graph(id="spx-cum", figure=build_spx_figure(), config={"displayModeBar":False}),
        html.H4("Monthly Returns", className="mt-4"),
        dbc.Table.from_dataframe(monthly_df, striped=True, bordered=True, hover=True, size="sm", className="mb-4"),
        html.H4("Performance Metrics", className="mt-4"),
        dbc.Table.from_dataframe(metrics_df, striped=True, bordered=True, hover=True, size="sm")
    ]
)

if __name__ == "__main__":
    app.run(debug=True, port=8076)
