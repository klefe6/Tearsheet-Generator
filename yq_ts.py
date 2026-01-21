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
logo_path = r"C:\Users\H&CDanHughes\Pictures\yq.png"
try:
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode("utf-8")
    logo_src = f"data:image/png;base64,{logo_b64}"
except FileNotFoundError:
    print(f"Error: Logo file not found at {logo_path}")
    logo_src = ""
# ─── Brand colors ────────────────────────────────
WHITE_BG     = "#ffffff"
GREY_BG      = "#EBEBEB"   # matches ggplot2's plot_bgcolor
PRIMARY_COLOR = "#28a745"  # your "green," Y&Q theme color
SECONDARY_COLOR = "#CCCCCC"

LEFT_TABLE_GAPS = "20px"
RIGHT_TABLE_GAPS = "30px"

HEADER_ROW_CLASS = "bg-light"

# ==============================================================================
# HELPER FUNCTIONS & CONSTANTS (Safe additions - won't affect current functionality)
# ==============================================================================

# Constants for magic numbers used throughout the code
TRADING_DAYS_PER_YEAR = 252
BUSINESS_DAYS_PER_YEAR = 365
BASELINE_AMOUNT = 100000
NOMINAL_ASSETS = 300000
ACCOUNT_COUNT = 4
OPEN_ACCOUNTS = 2
CLOSED_PROFITABLE = 2
CLOSED_UNPROFITABLE = 0
MIN_RETURN = 0.36
MAX_RETURN = 4.2
AVERAGE_MARGIN_USAGE = 1.77
TRANSACTION_FEE_PER_CONTRACT = 0.30

def validate_file_path(file_path):
    """Validate that file exists and is accessible"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"Cannot read file: {file_path}")
    return file_path

def validate_nav_data(df: pd.DataFrame) -> bool:
    """Validate NAV dataframe structure and content"""
    if df.empty:
        return False
    
    if df.index.has_duplicates:
        print("Warning: Duplicate dates found, removing duplicates")
        df = df[~df.index.duplicated(keep="first")]
    
    if df.isnull().any().any():
        print("Warning: Missing values found in NAV data")
    
    return True

def safe_logo_loading(logo_path: str) -> str:
    """Safely load logo with fallback"""
    try:
        with open(logo_path, "rb") as f:
            logo_b64 = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{logo_b64}"
    except FileNotFoundError:
        print(f"Error: Logo file not found at {logo_path}")
        return ""
    except Exception as e:
        print(f"Error loading logo: {e}")
        return ""

def safe_benchmark_download(symbol: str, max_retries: int = 3) -> pd.Series:
    """Download benchmark data with retry logic"""
    for attempt in range(max_retries):
        try:
            return utils.download_returns(symbol)
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"Failed to download {symbol} after {max_retries} attempts: {e}")
                return pd.Series(dtype=float)
            print(f"Attempt {attempt + 1} failed for {symbol}, retrying...")
            import time
            time.sleep(1)  # Brief delay before retry
    return pd.Series(dtype=float)

def create_monthly_calendar(monthly_simple):
    """Create monthly calendar table from monthly simple returns"""
    years = sorted(monthly_simple.index.year.unique())
    months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    
    monthly_data = {"Year": [str(y) for y in years]}
    
    for idx, m in enumerate(months, start=1):
        monthly_data[m] = [
            f"{monthly_simple.get(pd.Period(f'{y}-{idx:02d}'), 0):.2f}%"
            if pd.Period(f'{y}-{idx:02d}') in monthly_simple.index
            else ""
            for y in years
        ]
    
    # Calculate year totals
    yearly_simple = monthly_simple.groupby(monthly_simple.index.year).sum()
    monthly_data["Year Total"] = [
        f"{yearly_simple.get(y, 0):.2f}%"
        for y in years
    ]
    
    return pd.DataFrame(monthly_data)

# Safe helper function for monthly calendar (alternative to inline logic)
def build_monthly_calendar_safe(monthly_simple_series):
    """Alternative monthly calendar builder with error handling"""
    try:
        years = sorted(monthly_simple_series.index.year.unique())
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        
        monthly_data = {"Year": [str(y) for y in years]}
        
        for idx, m in enumerate(months, start=1):
            monthly_data[m] = [
                f"{monthly_simple_series.get(pd.Period(f'{y}-{idx:02d}'), 0):.2f}%"
                if pd.Period(f'{y}-{idx:02d}') in monthly_simple_series.index
                else ""
                for y in years
            ]
        
        # Calculate year totals
        yearly_simple = monthly_simple_series.groupby(monthly_simple_series.index.year).sum()
        monthly_data["Year Total"] = [
            f"{yearly_simple.get(y, 0):.2f}%"
            for y in years
        ]
        
        return pd.DataFrame(monthly_data)
    except Exception as e:
        print(f"Warning: Error building monthly calendar: {e}")
        return pd.DataFrame()  # Return empty DataFrame as fallback

# ==============================================================================
# 3) CONFIGURATION
#    Strategy name, benchmark list, and NAV CSV path
# ==============================================================================
STRATEGY_NAME = "Blue Whale Program"

BENCHMARKS = [
    "^SP500TR",   # S&P 500 Total Return
    "CTA",        # CTA Index (if available)
    "AGG",        # US Aggregate Bond
    "GLD",        # Gold ETF
    "BTC-USD",    # Bitcoin
    "ETH-USD",    # Ethereum
]

csv_path = r"C:\Program Files\Coding Projects\Tearsheet Generator\yq.csv"

# ============================================================================== 
# 4) LOAD & VALIDATE NAV DATA (CSV with monthly performance data)
# ==============================================================================
import sys

try:
    # Load CSV data
    raw_df = pd.read_csv(csv_path, encoding='latin-1')
    
    # Clean column names (remove special characters)
    raw_df.columns = raw_df.columns.str.replace(' ', ' ').str.strip()
    
    # Find the actual ROR column
    ror_col = None
    for col in raw_df.columns:
        if 'Actual' in col and 'ROR' in col:
            ror_col = col
            break
    
    if ror_col is None:
        print(f"Could not find Actual ROR column. Available: {raw_df.columns.tolist()}")
        sys.exit(1)
    
    # Rename columns
    raw_df = raw_df.rename(columns={
        'Year(yyyy)': 'year',
        'Month(mm)': 'month',
        ror_col: 'actual_ror'
    })
    
    # Filter out empty rows
    raw_df = raw_df[raw_df['year'].notna() & raw_df['month'].notna()].copy()
    
    # Convert to numeric
    raw_df['year'] = pd.to_numeric(raw_df['year'], errors='coerce')
    raw_df['month'] = pd.to_numeric(raw_df['month'], errors='coerce')
    raw_df['actual_ror'] = pd.to_numeric(raw_df['actual_ror'], errors='coerce')
    
    # Create date index
    raw_df['date'] = pd.to_datetime(raw_df[['year', 'month']].assign(day=1))
    raw_df = raw_df.set_index('date').sort_index()
    
    # Build equity curve from $100k using actual ROR percentages
    equity_curve = []
    current_value = BASELINE_AMOUNT
    for ror in raw_df['actual_ror']:  # Fixed: start from index 0, not 1
        if pd.notna(ror):
            current_value = current_value * (1 + ror / 100.0)
        equity_curve.append(current_value)
    
    # Create NAV_df with the equity curve
    NAV_df = pd.DataFrame({'nav-x1': equity_curve}, index=raw_df.index)
    
    print(f"CSV data loaded successfully ({len(NAV_df)} months)")
    print(f"Date range: {NAV_df.index.min().strftime('%Y-%m')} to {NAV_df.index.max().strftime('%Y-%m')}")
    print(f"Final value: ${NAV_df['nav-x1'].iloc[-1]:,.2f}")
        
except Exception as e:
    print(f"Failed to load CSV data: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Make sure pandas named the column correctly
if NAV_df.columns[0] != "nav‑x1" and NAV_df.columns[0] != "nav-x1":
    NAV_df.rename(columns={NAV_df.columns[0]: "nav-x1"}, inplace=True)

# Date is already set as index from CSV processing

# Drop exact duplicates so .asfreq() works
if NAV_df.index.has_duplicates:
    NAV_df = NAV_df[~NAV_df.index.duplicated(keep="first")]

# For monthly data, we don't need to reindex to business days
# NAV_df = NAV_df.asfreq(us_bd)  # Commented out for monthly data

print("NAV data loaded successfully (Date + nav-x1).")



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

print(f"Using NAV column: {NAV_col}")


# ==============================================================================
# 6) MONTHLY RETURNS (from CSV data)
#    Use actual ROR percentages from the CSV data
# ==============================================================================
# The raw_df is already loaded above in the data loading section
# Use actual ROR percentages (already in percentage format, so divide by 100)
monthly_returns = raw_df['actual_ror'] / 100.0

# For compatibility with existing code, create daily_returns as monthly_returns
daily_returns = monthly_returns

# Define baseline for compatibility with existing code
baseline = NAV_df[NAV_col].iloc[0]


# ==============================================================================
# 7) DOWNLOAD & ALIGN BENCHMARKS
#    For each symbol, get daily returns, align to NAV dates, then compute cum & drawdown
# ==============================================================================
bench_map = OrderedDict([
    ("SPXTR", "^SP500TR"),
    ("CTA",   "CTA"),       # CTA Index
    ("AGG",   "AGG"),
    ("GLD",   "GLD"),
    ("BTC",   "BTC-USD"),
    ("ETH",   "ETH-USD"),
])
# Filter to only those you configured
bench_map = {k:v for k,v in bench_map.items() if v in BENCHMARKS}

bench_ret, bench_cum, bench_dd = {}, {}, {}
for name, sym in bench_map.items():
    try:
        # 1) get evenly-spaced returns series
        full_ret = utils.download_returns(sym)
        
        # Add safe validation (won't break existing functionality)
        if full_ret is None or full_ret.empty:
            print(f"Warning: No data for {sym}, skipping")
            continue
            
        aligned = full_ret.reindex(NAV_df.index).ffill().bfill().dropna()
        # 2) cumulative growth
        cum = (1 + aligned).cumprod()
        # 3) drawdown in %
        dd = (cum / cum.cummax() - 1) * 100

        bench_ret[name] = aligned
        bench_cum[name] = cum
        bench_dd[name]  = dd
        
    except Exception as e:
        print(f"Warning: Failed to load {sym}: {e}")
        continue

# ==============================================================================
# 8) MONTHLY SIMPLE RETURNS (NON-COMPOUNDED) 
#    + MONTH-CELLS THAT SUM TO TRUE YEAR-OVER-YEAR RETURN
# ==============================================================================

# 8a) Month-end and month-start NAV
mp          = NAV_df.index.to_period("M")
month_last  = NAV_df[NAV_col].groupby(mp).last()
month_first = month_last.shift(1)
month_first.loc[month_last.index.min()] = baseline  # first-month start = baseline

# 8b) Compute each month's change **relative** to fixed baseline
monthly_simple = raw_df.groupby(raw_df.index.to_period("M"))["actual_ror"].last()

 
 

 
 
 
 
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

# Safe helper function for monthly calendar (alternative to inline logic)
def build_monthly_calendar_safe(monthly_simple_series):
    """Alternative monthly calendar builder with error handling"""
    try:
        years = sorted(monthly_simple_series.index.year.unique())
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        
        monthly_data = {"Year": [str(y) for y in years]}
        
        for idx, m in enumerate(months, start=1):
            monthly_data[m] = [
                f"{monthly_simple_series.get(pd.Period(f'{y}-{idx:02d}'), 0):.2f}%"
                if pd.Period(f'{y}-{idx:02d}') in monthly_simple_series.index
                else ""
                for y in years
            ]
        
        # Calculate year totals
        yearly_simple = monthly_simple_series.groupby(monthly_simple_series.index.year).sum()
        monthly_data["Year Total"] = [
            f"{yearly_simple.get(y, 0):.2f}%"
            for y in years
        ]
        
        return pd.DataFrame(monthly_data)
    except Exception as e:
        print(f"Warning: Error building monthly calendar: {e}")
        return pd.DataFrame()  # Return empty DataFrame as fallback

# ==============================================================================
# 9) MONTHLY PERFORMANCE METRICS
#    Define a helper to compute all your key stats over any period using monthly data
# ==============================================================================
def calculate_period_metrics_monthly(returns: pd.Series, start_date: pd.Timestamp) -> dict:
    """
    Given a series of monthly returns (in percentage format like 0.749 for 0.749%),
    compute cumulative return, annualized, avg monthly,
    win/loss counts & rates, top/bottom 3 months, Sharpe Ratio, and Max Drawdown.
    """
    keys = [
        "Cumulative Return", "Annualized Return", "Avg Monthly Return",
        # "Sharpe Ratio",  # Commented out - can be restored if needed
        # "Max Monthly Drawdown*",  # Commented out - can be restored if needed
        "Number of Months", "% Winning Months", "% Losing Months",
        "Best 3 Months", "Worst 3 Months",
    ]
    if len(returns) < 2:
        return dict.fromkeys(keys, "—")

    # Convert percentage to decimal for calculations (0.749% -> 0.00749)
    returns_decimal = returns / 100.0
    
    # Calculate compounded cumulative return (not simple sum)
    cum = (1 + returns_decimal).prod() - 1
    months = len(returns_decimal)
    # Annualize using compounded rate
    years = months / 12.0
    annualized = (1 + cum) ** (1 / years) - 1 if years > 0 else 0
    avg = returns_decimal.mean()

    # Calculate Sharpe Ratio (using risk-free rate = 0)
    # Annualized Sharpe = (monthly avg return / monthly std dev) * sqrt(12)
    # Commented out - can be restored if needed
    # monthly_std = returns_decimal.std()
    # sharpe_ratio = (avg / monthly_std) * np.sqrt(12) if monthly_std > 0 else 0
    
    # Calculate Maximum Drawdown
    # Commented out - can be restored if needed
    # cum_returns = (1 + returns_decimal).cumprod()
    # running_max = cum_returns.cummax()
    # drawdown = (cum_returns - running_max) / running_max
    # max_drawdown = drawdown.min()

    wins = (returns_decimal > 0).sum()
    losses = (returns_decimal < 0).sum()

    # For display, use original percentage values
    top3 = returns.nlargest(3)
    bot3 = returns.nsmallest(3)

    return {
        "Cumulative Return":      f"{cum*100:.1f}%",
        "Annualized Return":      f"{annualized*100:.1f}%",
        "Avg Monthly Return":     f"{avg*100:.3f}%",
        # "Sharpe Ratio":           f"{sharpe_ratio:.2f}",  # Commented out - can be restored if needed
        # "Max Monthly Drawdown*":  f"{max_drawdown*100:.2f}%",  # Commented out - can be restored if needed
        "Number of Months":       str(months),
        "% Winning Months":       f"{wins} ({wins/months*100:.1f}%)",
        "% Losing Months":        f"{losses} ({losses/months*100:.1f}%)",
        "Best 3 Months":          ", ".join(f"{v:.2f}%" for v in top3),
        "Worst 3 Months":         ", ".join(f"{v:.2f}%" for v in bot3),
    }

# ── List of the metrics in the order you want them shown ────────────────────
metric_labels = [
    "Cumulative Return",
    "Annualized Return",
    "Avg Monthly Return",
    # "Sharpe Ratio",  # Commented out - can be restored if needed
    # "Max Monthly Drawdown*",  # Commented out - can be restored if needed
    "Number of Months",
    "% Winning Months",
    "% Losing Months",
    "Best 3 Months",
    "Worst 3 Months"
]

# ── Define period boundaries ────────────────────────────────────────────────
inception_start = NAV_df.index.min()
# For exactly 12 months, go back 11 months from max (to include current month = 12 total)
ttm_start       = NAV_df.index.max() - pd.DateOffset(months=11)

# ── Slice your strategy series (monthly data) ─────────────────────────────────────────────
one_year_returns  = monthly_simple.loc[ttm_start:].dropna()
inception_returns = monthly_simple.copy()

# ── Slice your SPXTR series ────────────────────────────────────────────────
# Check if SPXTR data was successfully downloaded
if "SPXTR" in bench_ret:
    spxtr_series       = bench_ret["SPXTR"]
    spxtr_one_year     = spxtr_series.loc[ttm_start:].dropna()
    spxtr_inception    = spxtr_series.loc[inception_start:].dropna()
else:
    # Create empty series if SPXTR failed to download
    print("Warning: SPXTR benchmark data not available, using empty series")
    spxtr_series       = pd.Series(dtype=float)
    spxtr_one_year     = pd.Series(dtype=float)
    spxtr_inception    = pd.Series(dtype=float)

# ── Compute metrics (monthly version) ─────────────────────────────────────────────────────────
one_year_metrics       = calculate_period_metrics_monthly(one_year_returns,  ttm_start)
inception_metrics      = calculate_period_metrics_monthly(inception_returns, inception_start)

# ── Assemble your DataFrame ────────────────────────────────────────────────
monthly_perf_df = pd.DataFrame({
    "Metric": metric_labels,
    f"{STRATEGY_NAME} (1 Year/TTM)":    [one_year_metrics[m] for m in metric_labels],
    f"{STRATEGY_NAME} (Inception)":     [inception_metrics[m] for m in metric_labels],
})

# ==============================================================================
# Build blank Maximum Drawdown Profile DataFrame (to be filled in later)
# ==============================================================================
max_dd_df = pd.DataFrame({
    "Metric": ["Depth", "Decline Period", "Recovery Period", "Total Duration", "Start Date", "Valley Date", "End Date"],
    f"{STRATEGY_NAME} (Inception)": ["", "", "", "", "", "", ""],
})

# ==============================================================================
# 10) Calculate Monthly Performance Statistics (from actual data)
# ==============================================================================
def calculate_monthly_stats(returns: pd.Series) -> dict:
    """
    Calculate monthly performance statistics from actual monthly return data.
    """
    if len(returns) < 2:
        return {
            "Number of Positive Months": "—",
            "Number of Negative Months": "—", 
            "Average Winning Month %": "—",
            "Average Losing Month %": "—",
            "Best Single Month %": "—",
            "Worst Single Month %": "—",
            "Longest Winning Streak": "—",
            "Longest Losing Streak": "—",
        }
    
    # Separate winning and losing months
    positive_months = returns[returns > 0]
    negative_months = returns[returns < 0]
    
    # Calculate streaks
    streak_signs = (returns > 0).astype(int)
    
    # Find longest winning and losing streaks
    winning_streaks = []
    losing_streaks = []
    current_streak = 1
    current_sign = streak_signs.iloc[0]
    
    for i in range(1, len(streak_signs)):
        if streak_signs.iloc[i] == current_sign:
            current_streak += 1
        else:
            if current_sign == 1:
                winning_streaks.append(current_streak)
            else:
                losing_streaks.append(current_streak)
            current_streak = 1
            current_sign = streak_signs.iloc[i]
    
    # Add the final streak
    if current_sign == 1:
        winning_streaks.append(current_streak)
    else:
        losing_streaks.append(current_streak)
    
    longest_winning = max(winning_streaks) if winning_streaks else 0
    longest_losing = max(losing_streaks) if losing_streaks else 0
    
    return {
        "Number of Positive Months": f"{len(positive_months)} ({len(positive_months)/len(returns)*100:.1f}%)",
        "Number of Negative Months": f"{len(negative_months)} ({len(negative_months)/len(returns)*100:.1f}%)",
        "Average Winning Month %": f"{positive_months.mean():.2f}%" if len(positive_months) > 0 else "0.00%",
        "Average Losing Month %": f"{negative_months.mean():.2f}%" if len(negative_months) > 0 else "0.00%",
        "Best Single Month %": f"{returns.max():.2f}%",
        "Worst Single Month %": f"{returns.min():.2f}%",
        "Longest Winning Streak": f"{longest_winning} months",
        "Longest Losing Streak": f"{longest_losing} months",
    }


# Download benchmark data and compound returns
def download_and_compound_benchmark(symbol, start_date, end_date, baseline_amount):
    """
    Download benchmark data and compound returns from start date to end date
    """
    try:
        print(f"Downloading {symbol} data from {start_date} to {end_date}...")
        
        # Download data
        data = yf.download(
            symbol,
            start=start_date,
            end=end_date,
            auto_adjust=True,
            progress=False
        )
        
        if data.empty:
            print(f"Warning: No data found for {symbol}")
            return pd.Series(dtype=float, index=pd.date_range(start=start_date, end=end_date, freq='ME'))
        
        # Handle multi-level columns from yfinance
        if isinstance(data.columns, pd.MultiIndex):
            # Get the close prices from the multi-level column
            close_prices = data['Close'].iloc[:, 0] if data['Close'].ndim > 1 else data['Close']
        else:
            close_prices = data['Close']
        
        # Get monthly close prices (use 'ME' instead of deprecated 'M')
        monthly_prices = close_prices.resample('ME').last()
        
        # Calculate monthly returns
        monthly_returns = monthly_prices.pct_change().dropna()
        
        # Compound returns from baseline amount
        compounded_values = [baseline_amount]
        for return_rate in monthly_returns:
            compounded_values.append(compounded_values[-1] * (1 + return_rate))
        
        # Create series with proper dates
        dates = monthly_prices.index[1:]  # Skip first date since we don't have return for it
        compounded_series = pd.Series(compounded_values[1:], index=dates)
        
        print(f"{symbol} data processed: {len(compounded_series)} months")
        print(f"{symbol} final value: ${compounded_series.iloc[-1]:,.2f}")
        return compounded_series
        
    except Exception as e:
        print(f"Warning: Error downloading {symbol} data: {e}")
        import traceback
        traceback.print_exc()
        return pd.Series(dtype=float, index=pd.date_range(start=start_date, end=end_date, freq='ME'))

# Download and compound SPX Total Return data
spx_compounded = download_and_compound_benchmark(
    "^SP500TR", 
    "2011-04-01", 
    "2025-10-01", 
    BASELINE_AMOUNT
)


# ==============================================================================
# 11) Build the "Monthly Performance Statistics" DataFrame
# ==============================================================================

# Calculate monthly statistics for the Blue Whale Program (inception)
monthly_stats_inception = calculate_monthly_stats(monthly_simple)

# Create DataFrame with monthly statistics
monthly_stats_df = pd.DataFrame({
    "Metric": list(monthly_stats_inception.keys()),
    f"{STRATEGY_NAME} (Inception)": list(monthly_stats_inception.values()),
})

# ==============================================================================
# 12) Calculate Comparative Performance Metrics
# ==============================================================================
def calculate_comparative_metrics(blue_whale_returns, spx_nav_data):
    """
    Calculate comparative metrics for Blue Whale vs SPX
    """
    # Calculate monthly returns for both strategies from their NAV data
    blue_whale_monthly_returns = blue_whale_returns.pct_change().dropna() * 100  # Convert to percentage
    spx_monthly_returns = spx_nav_data.pct_change().dropna() * 100  # Convert to percentage
    
    # Ensure all series have the same length (align dates)
    min_length = min(len(blue_whale_monthly_returns), len(spx_monthly_returns))
    
    blue_whale_aligned = blue_whale_monthly_returns.iloc[-min_length:]
    spx_aligned = spx_monthly_returns.iloc[-min_length:]
    
    # Calculate total returns from NAV data
    blue_whale_total_return = ((blue_whale_returns.iloc[-1] / blue_whale_returns.iloc[0]) - 1) * 100
    spx_total_return = ((spx_nav_data.iloc[-1] / spx_nav_data.iloc[0]) - 1) * 100
    
    def calculate_metrics(returns, total_return, name):
        if len(returns) == 0:
            return {key: "—" for key in ["Total Return", "Win Rate", "Loss Rate", "Avg Win", "Avg Loss", "Best Month", "Worst Month", "Max Streak Win", "Max Streak Loss"]}
        
        # Basic metrics
        positive_months = returns[returns > 0]
        negative_months = returns[returns < 0]
        
        win_rate = len(positive_months) / len(returns) * 100 if len(returns) > 0 else 0
        loss_rate = len(negative_months) / len(returns) * 100 if len(returns) > 0 else 0
        
        avg_win = positive_months.mean() if len(positive_months) > 0 else 0
        avg_loss = negative_months.mean() if len(negative_months) > 0 else 0
        
        best_month = returns.max()
        worst_month = returns.min()
        
        # Calculate streaks
        streak_signs = (returns > 0).astype(int)
        max_win_streak = 0
        max_loss_streak = 0
        current_streak = 1
        current_sign = streak_signs.iloc[0] if len(streak_signs) > 0 else 0
        
        for i in range(1, len(streak_signs)):
            if streak_signs.iloc[i] == current_sign:
                current_streak += 1
            else:
                if current_sign == 1:
                    max_win_streak = max(max_win_streak, current_streak)
                else:
                    max_loss_streak = max(max_loss_streak, current_streak)
                current_streak = 1
                current_sign = streak_signs.iloc[i]
        
        # Add final streak
        if current_sign == 1:
            max_win_streak = max(max_win_streak, current_streak)
        else:
            max_loss_streak = max(max_loss_streak, current_streak)
        
        return {
            "Total Return": f"{total_return:.1f}%",
            "Win Rate": f"{win_rate:.1f}%",
            "Loss Rate": f"{loss_rate:.1f}%",
            "Avg Win": f"{avg_win:.2f}%",
            "Avg Loss": f"{avg_loss:.2f}%",
            "Best Month": f"{best_month:.2f}%",
            "Worst Month": f"{worst_month:.2f}%",
            "Max Streak Win": f"{max_win_streak} months",
            "Max Streak Loss": f"{max_loss_streak} months"
        }
    
    # Calculate metrics for each strategy
    blue_whale_metrics = calculate_metrics(blue_whale_aligned, blue_whale_total_return, "Blue Whale")
    spx_metrics = calculate_metrics(spx_aligned, spx_total_return, "SPX")
    
    # Create comparative DataFrame
    metrics = [
        "Total Return", "Win Rate", "Loss Rate", "Avg Win", "Avg Loss", 
        "Best Month", "Worst Month", "Max Streak Win", "Max Streak Loss"
    ]
    
    comparative_df = pd.DataFrame({
        "Metric": metrics,
        "Blue Whale Program": [blue_whale_metrics[m] for m in metrics],
        "SPX Total Return": [spx_metrics[m] for m in metrics]
    })
    
    return comparative_df

# Calculate comparative metrics
comparative_metrics_df = calculate_comparative_metrics(
    NAV_df[NAV_col], 
    spx_compounded
)

# ==============================================================================
# 12) Hard-coded "Additional Information"
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
        ("Management Fee",     "None"),
        ("Performance Fee",    "20% of Trading Profits, Quarterly, High-Water Mark"),
        ("High Water Mark",    "Yes"),
        ("Lockup Period",      "None"),
        ("Liquidity",          "Withdrawals with 7 days' notice; no lock-up"),
        ("Minimum Investment", "$100,000 (advisor may reduce)"),
        ("Additional Contributions", "$10,000+"),
        ("Notional Funding",   "Yes (see disclosure below)"),
        ("Execution FCM",      "Client choice (StoneX Financial default)"),
    ],
}

# ==============================================================================
# 13) Legal disclaimers & footer contact
# ==============================================================================
hcdisclaimer_text = (
    "THE BLUE WHALE PROGRAM IS A PROPRIETARY TRADING STRATEGY. "
    "THIS PERFORMANCE DATA IS FOR INFORMATIONAL PURPOSES ONLY AND IS NOT A SOLICITATION TO INVEST. "
    "PAST PERFORMANCE IS NOT INDICATIVE OF FUTURE RESULTS."
)

disclaimer_text = (
    "Past performance is not necessarily indicative of future results. The risk of loss in commodity trading can be substantial. "
    "This information is for informational purposes only and does not constitute investment advice or a solicitation to invest."
)

footer_contact = (
    "For more information, contact Y & Q Investments, LLC"
)

# ==============================================================================
# 14) Helper: Build Plotly “NAV” figure
# ==============================================================================
def build_NAV_figure():
    fig = go.Figure()
    
    # Add main NAV line
    fig.add_trace(go.Scatter(
        x=NAV_df.index,
        y=NAV_df[NAV_col],
        mode="lines",
        line={"color": PRIMARY_COLOR},
        name=STRATEGY_NAME
    ))
    
    

    fig.update_layout(
        title={
            "text": "<u>Compounded NAV Since Inception</u>",
            "x": 0.5,
            "xanchor": "center"
        },
        template="ggplot2",
        plot_bgcolor=GREY_BG,
        paper_bgcolor=WHITE_BG,
        xaxis_title="Date",
        yaxis_title="Normalized NAV ($100k baseline)",
        autosize=True,               # ← responsive sizing
        margin={"l": 40, "r": 10, "t": 40, "b": 40}
    )

    fig.update_xaxes(showgrid=True)
    fig.update_yaxes(showgrid=True)
    return fig

# Safe helper function for NAV figure building (alternative to main function)
def safe_build_NAV_figure():
    """Safe version of NAV figure builder with error handling"""
    try:
        return build_NAV_figure()
    except Exception as e:
        print(f"Warning: Error building NAV figure: {e}")
        # Return a simple fallback figure
        fig = go.Figure()
        fig.add_annotation(
            text="Error loading NAV data",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(
            title="Error Loading NAV Data",
            xaxis_title="Date",
            yaxis_title="Value"
        )
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

# Safe helper function for drawdown figure building (alternative to main function)
def safe_build_drawdown_figure():
    """Safe version of drawdown figure builder with error handling"""
    try:
        return build_drawdown_figure()
    except Exception as e:
        print(f"Warning: Error building drawdown figure: {e}")
        # Return a simple fallback figure
        fig = go.Figure()
        fig.add_annotation(
            text="Error loading drawdown data",
            xref="paper", yref="paper",
            x=0.5, y=0.5, showarrow=False
        )
        fig.update_layout(
            title="Error Loading Drawdown Data",
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
    title="Y&Q – Blue Whale Program",
)

def serve_layout():
    # Calculate first Monday of current month after the 2nd
    from datetime import datetime, timedelta
    import calendar
    
    today = datetime.now()
    # Get first day of current month
    first_day = today.replace(day=1)
    
    # Find first Monday of the month
    # Monday is weekday 0 in Python
    days_ahead = 0 - first_day.weekday()  # Monday is 0
    if days_ahead <= 0:  # Target day already happened this week
        days_ahead += 7
    
    first_monday = first_day + timedelta(days=days_ahead)
    
    # If first Monday is before the 3rd, move to next Monday
    if first_monday.day <= 2:
        first_monday += timedelta(days=7)
    
    last_updated = first_monday.strftime("%B %d, %Y")

    return dbc.Container(
        id="page-container",
        fluid=True,        # ⇒ always 100% on xs, sm; constrained on md+ breakpoints
        className="py-4",
                style={"maxWidth": "1400px"},  # Match TKP width exactly
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
                                html.H2("Y & Q Investment Fund Pool", className="text-center"),
                                html.H5("Blue Whale Program", className="text-center text-muted"),
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
                                    html.H5(last_updated, className="text-end", style={"color": "#28a745"}),
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
                                        className="d-block text-end text-secondary mb-1",
                                    ),
                                    # show the date underneath in one line
                                    html.Small(
                                        last_updated,
                                        className="d-block text-end",
                                        style={"color": "#28a745"}
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
                "Y & Q Investments, LLC — CTA & CPO; NFA member since 2010. Blue Whale Trading Program (inception April 2011).",
                className="lead text-center",
            ),
            html.P(
                "Instruments: S&P 500 E-mini, Nasdaq-100 E-mini, standard S&P 500 futures; may trade foreign futures/options. Objective: Capital preservation + consistent returns via premium collection with dynamic risk adjustments.",
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
                "This chart visualizes the growth of a $100,000 investment from inception to today. "
                "NAV stands for Net Asset Value; it reflects the compounded performance, net of all fees.",
                className="text-center small",
                style={"marginTop": "4rem"}  # gives some breathing room
            ),

            html.P(
                "This chart shows the compounded growth of the Blue Whale Program from inception to present. "
                "All profits are reinvested and compounded over time, demonstrating the power of systematic options selling.",
                className="text-center small",
                style={"marginBottom": "3rem"}
            ),


            # ── Performance Summary ────────────────────────────────────────────
            html.H5("Performance Summary", className="text-center mb-2"),
            dbc.Table(
                [
                    html.Thead(
                        html.Tr([
                            html.Th(
                                col, 
                                style={
                                    "backgroundColor": GREY_BG, 
                                    "color": "#000",
                                    "borderLeft": "3px solid #dee2e6" if col == "Year Total" else "none"
                                }
                            )
                            for col in monthly_df.columns
                        ])
                    ),
                    html.Tbody([
                        html.Tr([
                            html.Td(
                                monthly_df.iloc[i][col],
                                style={
                                    "backgroundColor": (
                                        "#d4edda" if col != "Year" and monthly_df.iloc[i][col] != "" and float(monthly_df.iloc[i][col].replace("%", "")) > 0
                                        else "#f8d7da" if col != "Year" and monthly_df.iloc[i][col] != "" and float(monthly_df.iloc[i][col].replace("%", "")) < 0
                                        else "white"
                                    ),
                                    "borderLeft": "3px solid #dee2e6" if col == "Year Total" else "none"
                                }
                            )
                            for col in monthly_df.columns
                        ])
                        for i in range(len(monthly_df))
                    ])
                ],
                bordered=True,
                hover=True,
                size="sm",
                className="table-responsive mb-5",
                style={"width": "100%", "margin": "0 auto", "pageBreakInside": "avoid"},
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
                        "The Blue Whale Program is a systematic options trading strategy focused on selling options on the E-Mini S&P 500 futures, Nasdaq-100 E-mini, and standard S&P 500 futures. Core approach: Sell OTM index options (predominantly short strangles); also uses credit/debit spreads and may buy options for risk control. The strategy aims to generate consistent returns through premium collection while managing risk through proprietary position sizing and strike selection. The program has been actively trading since April 2011 and compounds profits through systematic reinvestment. Advisor may alter strategies; material changes will be noticed to clients."
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
                                                                    html.Td(html.Span("✗ Mean Reversion", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
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
                                                            html.Td(html.Span("✗ Automated", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
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
                                                                    html.Td(html.Span("✗ Straight Futures", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
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
                                                                    html.Td(html.Span("✗ Covered Options", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),),
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
                                                            html.Td(html.Span("✗ Medium (500-2000 Contracts)", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"})),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✓ High (>2000 Contracts)", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"})),
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
                                                            html.Td(html.Span("--"), style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("15000"), style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}),
                                                        ]),
                                                    ]),
                                                ]),
                                                html.Tr([
                                                    html.Td([
                                                        "Holding Periods ",
                                                        html.Span("(*to verify*)", style={"backgroundColor": "yellow", "color": "black"})
                                                    ]),
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
                                                    html.Th([
                                                        "Risk Management ",
                                                        html.Span("(*to verify*)", style={"backgroundColor": "yellow", "color": "black"})
                                                    ], colSpan=3, className=HEADER_ROW_CLASS),
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
                                                            html.Td(html.Span("✗ VaR Considerations", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}, id="var-considerations")),
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
                                                            html.Td(html.Span("✓ Position Reductions", style={"color": PRIMARY_COLOR, "marginRight": "0.5rem"}, id="position-reductions")),
                                                        ]),
                                                        html.Tr([
                                                            html.Td(html.Span("✗ Position Offsets (Hedges)", style={"color": SECONDARY_COLOR, "marginRight": "0.5rem"}, id="position-hedges")),
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
                                                    html.Th("Transaction Fees (per Contract)", colSpan=3, className=HEADER_ROW_CLASS),
                                                ]),
                                                html.Tr([
                                                    html.Td("Commission"),
                                                    html.Td("$1.00"),
                                                    html.Td(),
                                                ]),
                                                html.Tr([
                                                    html.Td("Exchange Fee"),
                                                    html.Td("$0.10"),
                                                    html.Td(),
                                                ]),
                                                html.Tr([
                                                    html.Td("NFA Fee"),
                                                    html.Td("$0.01"),
                                                    html.Td(),
                                                ]),
                                                html.Tr([
                                                    html.Td("Give Up Fee"),
                                                    html.Td("$0.50"),
                                                    html.Td(),
                                                ]),
                                                html.Tr([
                                                    html.Td(html.Strong("Total All-In Fees")),
                                                    html.Td(html.Strong("$1.11 or $1.61")),
                                                    html.Td(),
                                                ]),
                                                html.Tr([
                                                    html.Td(
                                                        html.Small(
                                                            "* Give up fee is waived if account is traded at StoneX Financial.",
                                                            style={"fontStyle": "italic", "color": "#6c757d"}
                                                        ),
                                                        colSpan=3
                                                    ),
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
            # Row 1: Performance Metrics & Monthly Performance Statistics (side by side)
            dbc.Row(
                [
                    # ── LEFT SIDE: Performance Metrics ─────────────────────
                    dbc.Col(
                        [
                            # Performance Metrics
                            dbc.Card(
                                [
                                    dbc.CardHeader(html.H6("Performance Metrics", className="mb-0")),
                                    dbc.CardBody(
                                        dbc.Table.from_dataframe(
                                            monthly_perf_df,
                                            striped=False,
                                            bordered=True,
                                            hover=True,
                                            size="sm",
                                            className="fixed-cols",
                                        )
                                    ),
                                    # dbc.CardFooter(
                                    #     html.Small([
                                    #         html.Span("Sharpe Ratio (*to verify*)", style={"backgroundColor": "yellow", "color": "black"}),
                                    #         " calculated using risk-free rate = 0% (assumes all returns are excess returns). ",
                                    #         html.Span("Max Monthly Drawdown* (*to verify*)", style={"backgroundColor": "yellow", "color": "black"}),
                                    #         " calculated from monthly NAV data (not intraday drawdowns)."
                                    #     ], className="text-muted fst-italic")
                                    # ),
                                ],
                                outline=True,
                                className="mb-2",
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
                                ],
                                outline=True,
                                className="mb-2",
                            ),
                        ],
                        width=6,
                    ),

                    # ── RIGHT SIDE: Monthly Performance Statistics ─────────────────────
                    dbc.Col(
                        [
                            # Monthly Performance Statistics
                            dbc.Card(
                                [
                                    dbc.CardHeader(html.H6("Monthly Performance Statistics", className="mb-0")),
                                    dbc.CardBody(
                                        dbc.Table.from_dataframe(
                                            monthly_stats_df,
                                            striped=False,
                                            bordered=True,
                                            hover=True,
                                            size="sm",
                                            className="fixed-cols",
                                        )
                                    ),
                                    dbc.CardFooter(
                                        html.Small(
                                            "Statistics calculated from actual monthly return data from April 2011 to September 2025.",
                                            className="text-muted fst-italic"
                                        )
                                    ),
                                ],
                                outline=True,
                                className="mb-2",
                            ),
                        ],
                        width=6,
                    ),
                ],
                justify="start",
                className="mb-2",
            ),

            # Row 2: Investor Information (full width below)
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Card(
                                                    [
                                                        dbc.CardHeader(html.H6("Investor Information", className="mb-0")),
                                                        dbc.CardBody(
                                                            dbc.Row([
                                                                # Left side: Terms & Fees
                                                                dbc.Col(
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
                                                                    ),
                                                                    width=6
                                                                ),
                                                                # Right side: Account Stats
                                                                dbc.Col(
                                                                    dbc.Table(
                                                                        [
                                                                            html.Thead(
                                                                                html.Tr([
                                                                                    html.Th("Account Stats"),
                                                                                    html.Th("Current"),
                                                                                    html.Th("Historical"),
                                                                                ])
                                                                            ),
                                                                            html.Tbody([
                                                                                html.Tr([
                                                                                    html.Td("Total Accounts Currently Traded"),
                                                                                    html.Td("128"),
                                                                                    html.Td("—")
                                                                                ]),
                                                                                html.Tr([
                                                                                    html.Td("Total Nominal AUM"),
                                                                                    html.Td("$140,033,575"),
                                                                                    html.Td("—")
                                                                                ]),
                                                                                html.Tr([
                                                                                    html.Td("Currently Traded Pursuant to Program"),
                                                                                    html.Td("$85,164,605"),
                                                                                    html.Td("—")
                                                                                ]),
                                                                                html.Tr([
                                                                                    html.Td("Accounts Closed Profitably"),
                                                                                    html.Td("—"),
                                                                                    html.Td("111")
                                                                                ]),
                                                                                html.Tr([
                                                                                    html.Td("Accounts Closed Unprofitably"),
                                                                                    html.Td("—"),
                                                                                    html.Td("10")
                                                                                ]),
                                                                                html.Tr([
                                                                                    html.Td("Best Closed Account Return"),
                                                                                    html.Td("—"),
                                                                                    html.Td("+255.76%")
                                                                                ]),
                                                                                html.Tr([
                                                                                    html.Td("Worst Closed Account Return"),
                                                                                    html.Td("—"),
                                                                                    html.Td("-16.60%")
                                                                                ]),
                                                                            ]),
                                                                        ],
                                                                        striped=False,
                                                                        bordered=True,
                                                                        hover=True,
                                                                        size="sm",
                                                                    ),
                                                                    width=6
                                                                ),
                                                            ])
                                                        ),
                                                    ],
                                                    outline=True,
                                                    className="mb-2",
                                                ),
                        width=12,
                    ),
                ],
                justify="start",
                className="mb-2",
            ),

            # ── Notional Funding Disclosure ────────────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    dbc.Card(
                        [
                            dbc.CardHeader(html.H6("Special Notional Funding Disclosure", className="mb-0")),
                            dbc.CardBody([
                                html.P("Notional funding is allowed (partially funded accounts). This increases leverage and magnifies volatility, margin calls, and percentage returns (and losses).", className="mb-2"),
                                html.P("Performance fees are computed on Nominal Account Size (not cash equity).", className="mb-2"),
                                html.H6("Funding Level Impact on Returns:", className="mb-2"),
                                dbc.Table([
                                    html.Thead([
                                        html.Tr([
                                            html.Th("Funding Level"),
                                            html.Th("Leverage"),
                                            html.Th("Example: +10% Strategy Return"),
                                            html.Th("Example: -10% Strategy Return"),
                                        ])
                                    ]),
                                    html.Tbody([
                                        html.Tr([
                                            html.Td("100% Funded"),
                                            html.Td("1:1"),
                                            html.Td("+10.0%"),
                                            html.Td("-10.0%"),
                                        ]),
                                        html.Tr([
                                            html.Td("50% Funded"),
                                            html.Td("2:1"),
                                            html.Td("+20.0%"),
                                            html.Td("-20.0%"),
                                        ]),
                                        html.Tr([
                                            html.Td("25% Funded"),
                                            html.Td("4:1"),
                                            html.Td("+40.0%"),
                                            html.Td("-40.0%"),
                                        ]),
                                    ])
                                ], striped=True, bordered=True, hover=True, size="sm"),
                                html.P("Higher leverage increases both potential gains and losses. Consider your risk tolerance carefully.", className="mt-2 text-muted small"),
                                html.P(
                                    "For more detailed information regarding notional funding, please refer to the complete disclosure document.",
                                    className="mt-2 text-muted small fw-bold"
                                ),
                            ]),
                        ],
                        outline=True,
                        className="mb-4",
                    ),
                    width=12
                ),
                className="mb-4",
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
                color="success",
                style={"backgroundColor": "#28a745", "borderColor": "#28a745"}
            )
        ],
        style={"padding": "4rem", "textAlign": "center"}
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
    app.run(debug=True, port=8071)