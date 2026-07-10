"""
Algominds / Momentum Pacer — drawdown semantics helper (AGM-only).

The Momentum Pacer strategy is traded as ONE trading unit, but investors /
accounts / tranches may enter at different dates and funding levels. The same
dollar gain or loss can therefore represent a *different* percentage return or
drawdown depending on each account's starting balance and high watermark.

  * A $5k loss from a $50k strategy high watermark is a 10% strategy-unit
    drawdown.
  * The same $5k loss on a $30k tranche entered near the high is a 16.7%
    account/tranche drawdown.

One generic "drawdown" number can be technically accurate at strategy level
while being misleading for an account that joined later. This module keeps the
two concepts separate and provides a single source of truth for:

  * the copy / labels shown on the client- and admin-facing tearsheets, and
  * strategy-UNIT drawdown computed from the strategy net-value curve.

Account/tranche-level drawdown is deliberately NOT computed here. It requires a
per-tranche ledger (entry date, entry balance, current balance, tranche high
watermark) that does not exist in the current AGM data sources. Computing it
from the strategy net-value curve alone would be WRONG, so
``compute_account_tranche_drawdown`` returns an explicitly unavailable result
(renders as N/A) until that ledger exists — see the TODO there.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


# ── Labels (shared by client + admin) ─────────────────────────────────────
STRATEGY_UNIT_DRAWDOWN_LABEL = "Strategy Unit Drawdown"
STRATEGY_UNIT_DRAWDOWN_CHART_TITLE = "<u>Strategy Unit Drawdown from Peak</u>"
ACCOUNT_TRANCHE_DRAWDOWN_LABEL = "Account / Tranche Drawdown Since Entry"

NA_DISPLAY = "N/A"


# ── Client-facing copy (neutral / clarifying — never alarmist) ─────────────
CLIENT_STRATEGY_VS_ACCOUNT_NOTE = (
    "Strategy-level performance reflects the trading unit. Account-level return "
    "and drawdown may differ based on when an account entered the program."
)
CLIENT_STRATEGY_VS_ACCOUNT_TOOLTIP = (
    "Accounts may enter the strategy at different dates and balances. Because "
    "the strategy is traded as one unit, the same dollar gain or loss can "
    "represent a different percentage return or drawdown for each "
    "account/tranche."
)
ACCOUNT_TRANCHE_DRAWDOWN_UNAVAILABLE_NOTE = (
    "Account-level drawdown requires each account's entry date, starting "
    "balance, and high watermark."
)


# ── Admin-only copy (more explicit; NOT for the client page) ───────────────
ADMIN_DRAWDOWN_EXAMPLE_NOTE = (
    "A $5k loss from a $50k strategy high watermark is a 10% strategy-unit "
    "drawdown. The same $5k loss on a $30k tranche entered near the high is a "
    "16.7% account/tranche drawdown."
)
# TODO(tranche-drawdown): implement account/tranche-level drawdown once a
# per-tranche ledger exists. Required fields per tranche: entry balance, entry
# date, current balance, and tranche high watermark. Until then the client and
# admin pages show N/A for account/tranche drawdown rather than deriving a
# misleading number from strategy-unit NAV.
ADMIN_TRANCHE_TODO_PLACEHOLDER = (
    "Tranche-level drawdown requires entry balance, entry date, current "
    "balance, and tranche high watermark."
)


@dataclass(frozen=True)
class StrategyUnitDrawdown:
    """Strategy-UNIT (single trading-unit) drawdown, from the strategy NAV curve.

    Percentages are in PERCENT units and are <= 0.0 (0.0 exactly at a fresh
    high, negative below the running peak).
    """

    strategy_unit_starting_capital: Optional[float]
    strategy_unit_high_watermark: Optional[float]
    strategy_unit_current_nav: Optional[float]
    strategy_unit_current_drawdown_pct: Optional[float]
    strategy_unit_max_drawdown_pct: Optional[float]

    @property
    def available(self) -> bool:
        return self.strategy_unit_current_drawdown_pct is not None


@dataclass(frozen=True)
class AccountTrancheDrawdown:
    """Account/tranche drawdown since entry — NOT computed yet.

    All fields default to ``None`` (unavailable) because the per-tranche ledger
    they require does not exist yet. See the module docstring and
    ``compute_account_tranche_drawdown``.
    """

    account_or_tranche_starting_capital: Optional[float] = None
    account_or_tranche_high_watermark: Optional[float] = None
    account_or_tranche_current_nav: Optional[float] = None
    account_or_tranche_drawdown_pct: Optional[float] = None

    @property
    def available(self) -> bool:
        return self.account_or_tranche_drawdown_pct is not None


def compute_strategy_unit_drawdown(
    equity_values: Sequence[float],
) -> StrategyUnitDrawdown:
    """Strategy-unit drawdown from the strategy net-value curve (one trading unit).

    ``current drawdown = current NAV / running peak - 1`` (0 at a fresh high,
    otherwise negative). ``max drawdown`` is the worst such value over the
    series. Both are returned in percent units (e.g. ``-10.0`` == 10% below
    peak). An empty / all-``None`` series yields an unavailable result.
    """
    vals = [float(v) for v in equity_values if v is not None]
    if not vals:
        return StrategyUnitDrawdown(None, None, None, None, None)

    peak = vals[0]
    max_dd = 0.0
    for v in vals:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v / peak - 1.0) * 100.0
            if dd < max_dd:
                max_dd = dd

    starting = vals[0]
    current = vals[-1]
    hwm = max(vals)
    current_dd = (current / hwm - 1.0) * 100.0 if hwm > 0 else None
    return StrategyUnitDrawdown(
        strategy_unit_starting_capital=starting,
        strategy_unit_high_watermark=hwm,
        strategy_unit_current_nav=current,
        strategy_unit_current_drawdown_pct=current_dd,
        strategy_unit_max_drawdown_pct=max_dd,
    )


def compute_account_tranche_drawdown(*_args, **_kwargs) -> AccountTrancheDrawdown:
    """Account/tranche-level drawdown since entry — deliberately unavailable.

    TODO(tranche-drawdown): implement once a per-tranche ledger exists (entry
    date, entry balance, current balance, tranche high watermark). The strategy
    net-value curve alone CANNOT produce this, and deriving it from strategy
    NAV would be misleading, so this returns an unavailable result (renders as
    N/A) for now. Signature stays permissive so call sites can pass ledger data
    in unchanged once the source is wired.
    """
    return AccountTrancheDrawdown()


def format_drawdown_pct(pct: Optional[float]) -> str:
    """``'-10.0%'`` style; ``N/A`` when unavailable. Input is already in percent."""
    if pct is None:
        return NA_DISPLAY
    return f"{pct:.1f}%"
