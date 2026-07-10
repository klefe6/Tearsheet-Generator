"""
Shared program Account Stats helpers (TKP / TCP / AGM).

Supports Proprietary and Client buckets with a derived Total column:
  Account Stats | Total | Client | Proprietary

Total counts and nominal assets are always computed from the two buckets — never
hardcoded separately. Return-range totals merge min/max across available ranges.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Row labels shared by client-facing program Account Stats tables.
PROGRAM_ACCOUNT_STAT_LABELS: Tuple[str, ...] = (
    "Nominal Assets Being Traded in the Program",
    "Total Accounts/Tranches Opened",
    "Accounts/Tranches Currently Open",
    "Accounts/Tranches Closed Profitably",
    "Accounts/Tranches Closed Unprofitably",
    "Range of Net Returns of Accounts/Tranches Closed",
)

PROGRAM_ACCOUNT_STAT_COLUMNS: Tuple[str, ...] = (
    "Total",
    "Client",
    "Proprietary",
)

NA_DISPLAY = "N/A"


@dataclass(frozen=True)
class ProgramBucketStats:
    nominal_assets: float
    total_opened: int
    currently_open: int
    closed_profitably: int
    closed_unprofitably: int
    closed_return_range: Optional[str] = None


@dataclass(frozen=True)
class ProgramAccountStats:
    proprietary: ProgramBucketStats
    client: ProgramBucketStats

    @property
    def total(self) -> ProgramBucketStats:
        return merge_program_bucket_stats(self.proprietary, self.client)


def merge_program_bucket_stats(
    proprietary: ProgramBucketStats,
    client: ProgramBucketStats,
) -> ProgramBucketStats:
    """Derive Total bucket stats from Proprietary + Client."""
    return ProgramBucketStats(
        nominal_assets=proprietary.nominal_assets + client.nominal_assets,
        total_opened=proprietary.total_opened + client.total_opened,
        currently_open=proprietary.currently_open + client.currently_open,
        closed_profitably=proprietary.closed_profitably + client.closed_profitably,
        closed_unprofitably=proprietary.closed_unprofitably + client.closed_unprofitably,
        closed_return_range=merge_closed_return_ranges(
            proprietary.closed_return_range,
            client.closed_return_range,
        ),
    )


_RANGE_PCT_RE = re.compile(
  r"(-?\d+(?:\.\d+)?)\s*%"
  r"(?:\s*(?:to|–|—|-)\s*(-?\d+(?:\.\d+)?)\s*%)?",
  re.IGNORECASE,
)


def _parse_closed_return_range(
    range_str: Optional[str],
) -> Optional[Tuple[float, float]]:
    if not range_str or range_str.strip().upper() == NA_DISPLAY:
        return None
    text = range_str.strip().replace("—", "–")
    # "0–1%" (single trailing %) — check before looser patterns
    bare = re.match(
        r"(-?\d+(?:\.\d+)?)\s*[–-]\s*(-?\d+(?:\.\d+)?)\s*%",
        text,
    )
    if bare:
        low, high = float(bare.group(1)), float(bare.group(2))
        return (min(low, high), max(low, high))
    # "0.36% to 4.2%" or "4.2%"
    match = _RANGE_PCT_RE.search(text)
    if match:
        low = float(match.group(1))
        high = float(match.group(2)) if match.group(2) is not None else low
        return (min(low, high), max(low, high))
    single = re.search(r"(-?\d+(?:\.\d+)?)\s*%", text)
    if single:
        val = float(single.group(1))
        return (val, val)
    return None


def merge_closed_return_ranges(
  proprietary_range: Optional[str],
  client_range: Optional[str],
) -> Optional[str]:
  """Combine closed-return ranges across buckets (min of lows, max of highs)."""
  prop_bounds = _parse_closed_return_range(proprietary_range)
  client_bounds = _parse_closed_return_range(client_range)
  if prop_bounds is None and client_bounds is None:
    return None
  if prop_bounds is None:
    return client_range
  if client_bounds is None:
    return proprietary_range
  low = min(prop_bounds[0], client_bounds[0])
  high = max(prop_bounds[1], client_bounds[1])
  return _format_closed_return_range(low, high)


def _format_closed_return_range(low: float, high: float) -> str:
  if abs(low - round(low)) < 1e-9 and abs(high - round(high)) < 1e-9:
    low_i, high_i = int(round(low)), int(round(high))
    if low_i == high_i:
      return f"{low_i}%"
    return f"{low_i}–{high_i}%"
  if abs(low - high) < 1e-9:
    return f"{low:g}%"
  return f"{low:g}% to {high:g}%"


def should_show_total_column(stats: ProgramAccountStats) -> bool:
  """True when both buckets contribute program stats (e.g. AGM)."""
  prop, client = stats.proprietary, stats.client
  return (
    client.total_opened > 0
    or client.currently_open > 0
    or client.closed_profitably > 0
    or client.closed_unprofitably > 0
    or client.nominal_assets > 0
  ) and (
    prop.total_opened > 0
    or prop.currently_open > 0
    or prop.closed_profitably > 0
    or prop.closed_unprofitably > 0
    or prop.nominal_assets > 0
  )


def _fmt_count(value: int) -> str:
  return str(int(value))


def _fmt_nominal(value: float) -> str:
  if value >= 1000 and abs(value % 1000) < 1e-9:
    thousands = int(round(value / 1000.0))
    return f"{thousands}k"
  return f"${value:,.0f}"


def _fmt_range(value: Optional[str]) -> str:
  return value if value else NA_DISPLAY


def format_program_account_stats_rows(
  stats: ProgramAccountStats,
  *,
  include_total: bool = True,
) -> List[Tuple[str, ...]]:
  """
  Rows for the program Account Stats table.

  With ``include_total=True`` each row is
  ``(label, total_display, client_display, proprietary_display)``.
  With ``include_total=False`` each row is
  ``(label, client_display, proprietary_display)`` (legacy TKP/TCP layout).
  """
  prop, client, total = stats.proprietary, stats.client, stats.total
  if include_total:
    row_builders = (
      lambda: (_fmt_nominal(total.nominal_assets), _fmt_nominal(client.nominal_assets), _fmt_nominal(prop.nominal_assets)),
      lambda: (_fmt_count(total.total_opened), _fmt_count(client.total_opened), _fmt_count(prop.total_opened)),
      lambda: (_fmt_count(total.currently_open), _fmt_count(client.currently_open), _fmt_count(prop.currently_open)),
      lambda: (_fmt_count(total.closed_profitably), _fmt_count(client.closed_profitably), _fmt_count(prop.closed_profitably)),
      lambda: (_fmt_count(total.closed_unprofitably), _fmt_count(client.closed_unprofitably), _fmt_count(prop.closed_unprofitably)),
      lambda: (_fmt_range(total.closed_return_range), _fmt_range(client.closed_return_range), _fmt_range(prop.closed_return_range)),
    )
  else:
    row_builders = (
      lambda: (_fmt_nominal(client.nominal_assets), _fmt_nominal(prop.nominal_assets)),
      lambda: (_fmt_count(client.total_opened), _fmt_count(prop.total_opened)),
      lambda: (_fmt_count(client.currently_open), _fmt_count(prop.currently_open)),
      lambda: (_fmt_count(client.closed_profitably), _fmt_count(prop.closed_profitably)),
      lambda: (_fmt_count(client.closed_unprofitably), _fmt_count(prop.closed_unprofitably)),
      lambda: (_fmt_range(client.closed_return_range), _fmt_range(prop.closed_return_range)),
    )
  return [
    (PROGRAM_ACCOUNT_STAT_LABELS[i], *row_builders[i]())
    for i in range(len(PROGRAM_ACCOUNT_STAT_LABELS))
  ]
