"""TKP public chart must plot cash-flow-neutralized StoneX performance, not raw balances."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_STATE = _REPO / "daily_returns_secret_state.json"

_JUMP_DATES = (
    ("2025-04-22", 133908.06, 235714.84, 100000.0),
    ("2025-10-29", 247142.92, 147162.63, -100000.0),
    ("2026-01-09", 149896.42, 99868.63, -50000.0),
)


@pytest.fixture(scope="module")
def tkp_mod():
    import tkp_ts

    return tkp_ts


@pytest.fixture(scope="module")
def state_rows():
    if not _STATE.exists():
        pytest.skip(f"missing {_STATE}")
    return json.loads(_STATE.read_text(encoding="utf-8"))


def _glenn_normalized_values(rows, baseline: float = 100_000.0) -> list[float]:
    """Mirror uploader.app.performance._normalized_values for TKP rows."""
    stonex_s, deposit_s, _ = rows if isinstance(rows, tuple) else (None, None, None)
    if stonex_s is None:
        import tkp_ts as m

        stonex_s, deposit_s, _ = m._extract_stonex_deposit_fee_series(rows)
    values: list[float] = []
    normalized = baseline
    prior_raw = None
    for dt in stonex_s.index:
        raw = float(stonex_s.loc[dt])
        cash = float(deposit_s.loc[dt]) if dt in deposit_s.index else 0.0
        if prior_raw is None:
            normalized = baseline
        else:
            adjusted = raw - cash
            dr = 0.0 if not prior_raw else adjusted / prior_raw - 1.0
            normalized = normalized * (1.0 + dr)
        values.append(round(normalized, 4))
        prior_raw = raw
    return values


def test_deposit_only_day_has_zero_glenn_return(tkp_mod):
    rows = [
        {"Date": "2026-01-01", "StoneX": "$100,000.00", "Deposit": ""},
        {"Date": "2026-01-02", "StoneX": "$200,000.00", "Deposit": "$100,000"},
    ]
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[0] == pytest.approx(tkp_mod.BASELINE_AMOUNT, abs=0.01)
    assert perf.iloc[1] == pytest.approx(tkp_mod.BASELINE_AMOUNT, abs=0.01)


def test_withdrawal_only_day_has_zero_glenn_return(tkp_mod):
    rows = [
        {"Date": "2026-01-01", "StoneX": "$200,000.00", "Deposit": ""},
        {"Date": "2026-01-02", "StoneX": "$100,000.00", "Deposit": "$-100,000"},
    ]
    perf = tkp_mod._performance_series_from_secret_rows(rows)
    assert perf.iloc[1] == pytest.approx(perf.iloc[0], abs=0.01)


def test_plus500_does_not_move_performance_curve(tkp_mod, state_rows):
  base_perf = tkp_mod._performance_series_from_secret_rows(state_rows)
  mutated = []
  for r in state_rows:
      row = dict(r)
      if row.get("Date", "").startswith("2026-07-09"):
          row["Plus500"] = "$999,999.99"
      mutated.append(row)
  mut_perf = tkp_mod._performance_series_from_secret_rows(mutated)
  assert base_perf.loc["2026-07-09"] == pytest.approx(mut_perf.loc["2026-07-09"], abs=0.01)


def test_stonex_trading_pnl_moves_performance_curve(tkp_mod, state_rows):
  base = tkp_mod._performance_series_from_secret_rows(state_rows)
  mutated = []
  for r in state_rows:
      row = dict(r)
      if row.get("Date", "").startswith("2026-07-09"):
          row["StoneX"] = "$83,500.00"
          row["Deposit"] = ""
          row["$PL"] = "$500.00"
      mutated.append(row)
  changed = tkp_mod._performance_series_from_secret_rows(mutated)
  assert base.loc["2026-07-09"] != pytest.approx(changed.loc["2026-07-09"], abs=0.01)


@pytest.mark.parametrize("date_str,prev_sx,new_sx,cash", _JUMP_DATES)
def test_major_cash_events_do_not_jump_performance(
    tkp_mod, state_rows, date_str, prev_sx, new_sx, cash
):
  perf = tkp_mod._performance_series_from_secret_rows(state_rows)
  dt = pytest.importorskip("pandas").to_datetime(date_str)
  before = perf.loc[:dt].iloc[-2]
  after = perf.loc[dt]
  raw_jump_pct = abs((new_sx - prev_sx) / prev_sx)
  perf_jump_pct = abs((after - before) / before) if before else 0
  assert raw_jump_pct > 0.25
  assert perf_jump_pct < 0.05


def test_tkp_and_glenn_daily_return_path_identical(tkp_mod, state_rows):
  tkp_rets = tkp_mod._glenn_aligned_daily_return_series(state_rows)
  stonex_s, deposit_s, _ = tkp_mod._extract_stonex_deposit_fee_series(state_rows)
  glenn_vals = _glenn_normalized_values((stonex_s, deposit_s, None), baseline=100_000.0)
  glenn_rets = [0.0]
  for i in range(1, len(glenn_vals)):
      glenn_rets.append(glenn_vals[i] / glenn_vals[i - 1] - 1.0)
  aligned = tkp_rets.reindex(stonex_s.index).fillna(0.0)
  for i, dt in enumerate(stonex_s.index):
      if i == 0:
          continue
      assert aligned.iloc[i] == pytest.approx(glenn_rets[i], abs=1e-9)


def test_tkp_chart_series_scales_glenn_baseline(tkp_mod, state_rows):
  tkp_perf = tkp_mod._performance_series_from_secret_rows(state_rows)
  stonex_s, deposit_s, _ = tkp_mod._extract_stonex_deposit_fee_series(state_rows)
  glenn = _glenn_normalized_values((stonex_s, deposit_s, None), baseline=100_000.0)
  scale = tkp_mod.BASELINE_AMOUNT / 100_000.0
  for i, dt in enumerate(stonex_s.index):
      assert tkp_perf.loc[dt] == pytest.approx(glenn[i] * scale, rel=1e-6)


def test_canonical_store_still_raw_stonex_for_tables(tkp_mod, state_rows):
  recs = tkp_mod._canonical_records_from_secret_rows(state_rows)
  by_date = {r["Date"]: r["NAV"] for r in recs}
  assert by_date["2026-07-09"] == pytest.approx(82838.14, abs=0.01)


def test_fee_hwm_synthetic_nav_unchanged(tkp_mod, state_rows):
  jul9 = next(r for r in state_rows if str(r.get("Date", "")).startswith("2026-07-09"))
  assert jul9["NAV"] == "$192,875.99"
  assert jul9["StoneX"] == "$82,838.14"
