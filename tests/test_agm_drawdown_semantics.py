"""AGM drawdown semantics: % of initial capital denominator and profile table."""
from __future__ import annotations

import pandas as pd
import pytest

import algominds_drawdown_semantics as agm_dd


def test_drawdown_pct_uses_initial_capital_not_peak():
  """$5k decline from $50k peak with $30k initial capital => 16.7%."""
  pct = agm_dd.drawdown_pct_of_initial_capital(45_000.0, 50_000.0, 30_000.0)
  assert pct == pytest.approx(-16.666666, rel=1e-4)


def test_compute_strategy_unit_drawdown_example():
  stats = agm_dd.compute_strategy_unit_drawdown(
      [30_000.0, 50_000.0, 45_000.0],
      initial_capital=30_000.0,
  )
  assert stats.strategy_unit_max_drawdown_pct == pytest.approx(-16.7, abs=0.05)
  assert stats.strategy_unit_current_drawdown_pct == pytest.approx(-16.7, abs=0.05)


def test_drawdown_series_pct_of_initial_capital_example():
  series = agm_dd.drawdown_series_pct_of_initial_capital(
      [30_000.0, 50_000.0, 45_000.0],
      initial_capital=30_000.0,
  )
  assert series == pytest.approx([0.0, 0.0, -16.666666], rel=1e-4)


def test_worst_drawdown_profile_depth_uses_initial_capital():
  idx = pd.date_range("2026-01-01", periods=3, freq="D")
  nav = pd.Series([30_000.0, 50_000.0, 45_000.0], index=idx)
  period = agm_dd.worst_drawdown_profile(nav, initial_capital=30_000.0)
  assert period is not None
  assert period.depth_decimal == pytest.approx(-16.7, abs=0.05)
  assert period.start_date == "2026-01-02"
  assert period.valley_date == "2026-01-03"


def test_build_drawdown_profile_dataframe_has_required_rows():
  idx = pd.date_range("2026-01-01", periods=3, freq="D")
  nav = pd.Series([30_000.0, 50_000.0, 45_000.0], index=idx)
  df = agm_dd.build_drawdown_profile_dataframe(nav, initial_capital=30_000.0)
  assert list(df["Metric"]) == list(agm_dd.DRAWDOWN_METRIC_ORDER)
  assert agm_dd.AGM_INCEPTION_COLUMN in df.columns
  depth = df.loc[df["Metric"] == "Depth", agm_dd.AGM_INCEPTION_COLUMN].iloc[0]
  assert depth == "-16.7%"


def test_build_drawdown_profile_includes_spx_when_benchmark_provided():
  idx = pd.date_range("2026-01-01", periods=3, freq="D")
  strategy = pd.Series([30_000.0, 50_000.0, 45_000.0], index=idx)
  benchmark = pd.Series([30_000.0, 33_000.0, 31_000.0], index=idx)
  df = agm_dd.build_drawdown_profile_dataframe(
      strategy,
      initial_capital=30_000.0,
      benchmark_nav=benchmark,
  )
  assert agm_dd.SPX_INCEPTION_COLUMN in df.columns


def test_client_layout_has_max_drawdown_profile_and_no_old_sentence(mp):
  layout_str = str(mp.serve_layout())
  assert "Maximum Drawdown Profile" in layout_str
  assert "agm-drawdown-profile-card" in layout_str
  assert "Strategy-level performance reflects the trading unit" not in layout_str
  assert "Account / Tranche Drawdown Since Entry" not in layout_str
  assert "agm-client-drawdown-note" not in layout_str


def test_client_layout_preserves_performance_summary_and_account_stats(mp):
  layout_str = str(mp.serve_layout())
  assert "Performance Summary" in layout_str
  assert "Account Stats" in layout_str
  assert "Total" in layout_str
  assert "Client" in layout_str
  assert "Proprietary" in layout_str


def test_drawdown_chart_uses_initial_capital_denominator(mp):
  fig = mp.build_drawdown_figure()
  dd = fig.data[0]
  eq = mp._daily_equity_frame()["client_net_value"].astype(float)
  pk = eq.cummax()
  expected = ((eq - pk) / float(mp.STARTING_CAPITAL) * 100.0).tolist()
  assert [float(v) for v in dd.y] == pytest.approx(expected, rel=1e-6)


def test_drawdown_chart_labels_initial_capital(mp):
  fig = mp.build_drawdown_figure()
  assert "% of Initial Capital" in fig.layout.title.text
  assert fig.data[0].name == agm_dd.STRATEGY_UNIT_DRAWDOWN_LABEL
  assert fig.layout.yaxis.title.text == "Drawdown (% of Initial Capital)"


def test_max_drawdown_profile_df_not_empty(mp):
  df = mp.build_agm_max_drawdown_profile_df()
  assert not df.empty
  assert agm_dd.AGM_INCEPTION_COLUMN in df.columns
  assert "Depth" in df["Metric"].values


@pytest.fixture(scope="module")
def mp():
  import mp_ts

  return mp_ts
