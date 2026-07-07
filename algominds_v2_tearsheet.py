"""
Algominds v2 tearsheet view model — normalized, deterministic data for the
investor-tearsheet layout. No HTML here; layout modules consume this only.

Data preference order for an account:
  1. Real saved snapshot (per-account preview state) — single-point series.
  2. Deterministic preview fixture data, clearly labelled as such.

Preview fixture data is generated in memory only and is never written to any
state file. Nothing in this module mutates state.

Fee-rule assumptions that are not yet final are isolated in
FEE_STRUCTURE_ASSUMPTION_NOTE / fee_structure_rows() below.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Optional

from algominds_v2.fee_engine import NEGATIVE_BDR_RATE, SLAB_RATES, crystallize_month
from algominds_v2_accounts import AccountProfile
from algominds_v2_account_state_paths import (
    load_latest_snapshot_for_account,
    resolve_preview_state_path,
)
from algominds_v2_snapshot_state import compute_latest_snapshot_result
from algominds_v2_state import read_preview_state

FIRM_NAME = "Algominds Financial LLC"
PROGRAM_NAME = "Momentum Pacer Program"

DATA_MODE_SNAPSHOT = "snapshot"
DATA_MODE_PREVIEW_FIXTURE = "preview-fixture"

PREVIEW_FIXTURE_NOTICE = (
    "Preview fixture data — deterministic demo values for layout preview only. "
    "Not actual trading performance and not production state."
)

# ASSUMPTION (not final business rules): the slab descriptions below restate the
# v1 tearsheet's Disclosure Document wording; the rates come from the v2 fee
# engine (algominds_v2.fee_engine.SLAB_RATES / NEGATIVE_BDR_RATE). Confirm final
# wording against the AlgoMinds Disclosure Document before production cutover.
FEE_STRUCTURE_ASSUMPTION_NOTE = (
    "Preview wording — pending confirmation against the AlgoMinds Financial LLC "
    "Disclosure Document. Rates shown are the v2 fee-engine slab rates."
)

_SLAB_BAND_DESCRIPTIONS = (
    "Net new profits from $0 up through 100% of the Benchmark's monthly dollar return (0–1×)",
    "Portion exceeding 100% but not more than 200% of that Benchmark dollar return (1×–2×)",
    "Portion exceeding 200% but not more than 300% (2×–3×)",
    "Portion exceeding 300% but not more than 400% (3×–4×)",
    "Portion exceeding 400% of the Benchmark's monthly dollar return (>4×)",
)

# Deterministic monthly gross-return and SPX-return cycles for preview fixture
# data. Fixed values (no clock, no randomness) so the fixture is reproducible.
_FIXTURE_GROSS_RETURN_CYCLE = (
    Decimal("0.0620"),
    Decimal("0.0240"),
    Decimal("-0.0180"),
    Decimal("0.0410"),
    Decimal("0.0090"),
    Decimal("0.0330"),
    Decimal("-0.0070"),
    Decimal("0.0280"),
)
_FIXTURE_SPX_RETURN_CYCLE = (
    Decimal("0.0210"),
    Decimal("0.0120"),
    Decimal("-0.0140"),
    Decimal("0.0180"),
    Decimal("0.0040"),
    Decimal("0.0150"),
    Decimal("-0.0060"),
    Decimal("0.0110"),
)
FIXTURE_MONTH_COUNT = 8


@dataclass(frozen=True)
class SeriesPoint:
    when: date
    value: Decimal


@dataclass(frozen=True)
class TearsheetSeries:
    label: str
    points: tuple[SeriesPoint, ...]


@dataclass(frozen=True)
class SummaryRow:
    month_label: str
    spx_start: Optional[Decimal]
    spx_end: Optional[Decimal]
    account_start: Optional[Decimal]
    account_end_after_fees: Optional[Decimal]
    spx_return_pct: Optional[Decimal]
    gross_return_pct: Optional[Decimal]
    fees_pct: Optional[Decimal]
    net_return_pct: Optional[Decimal]
    cumulative_net_pct: Optional[Decimal]


@dataclass(frozen=True)
class LabelValueRow:
    label: str
    value: str


@dataclass(frozen=True)
class FeeSlabRow:
    slab: str
    band: str
    rate: str


@dataclass(frozen=True)
class TearsheetViewModel:
    account_slug: str
    display_name: str
    firm_name: str
    program_name: str
    inception_date: date
    starting_balance: Decimal
    benchmark_base: Decimal
    number_of_units: int
    exchange_fee_tier: str
    last_updated_label: str
    data_mode: str
    data_notice: Optional[str]
    intro_paragraphs: tuple[str, ...]
    nav_series: tuple[TearsheetSeries, ...]
    summary_rows: tuple[SummaryRow, ...]
    summary_totals: tuple[LabelValueRow, ...]
    performance_metrics: tuple[LabelValueRow, ...]
    performance_stats: tuple[LabelValueRow, ...]
    fee_structure_rows: tuple[FeeSlabRow, ...]
    fee_terms: tuple[LabelValueRow, ...]
    investor_terms: tuple[LabelValueRow, ...]
    account_stats: tuple[LabelValueRow, ...]
    drawdown_series: TearsheetSeries

    @property
    def is_preview_fixture(self) -> bool:
        return self.data_mode == DATA_MODE_PREVIEW_FIXTURE


def _fmt_money(value: Decimal) -> str:
    return f"${value:,.2f}"


def _fmt_money_whole(value: Decimal) -> str:
    return f"${value:,.0f}"


def _fmt_pct(value: Decimal) -> str:
    return f"{value:.2f}%"


def _month_label(d: date) -> str:
    return d.strftime("%b-%Y")


def _add_months(d: date, months: int) -> date:
    month_index = (d.month - 1) + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def fee_structure_rows() -> tuple[FeeSlabRow, ...]:
    """Slab table rows sourced from the v2 fee engine rates (see assumption note)."""
    rows = [
        FeeSlabRow(
            slab=f"Slab {i + 1}",
            band=_SLAB_BAND_DESCRIPTIONS[i],
            rate=f"{rate * 100:.0f}%",
        )
        for i, rate in enumerate(SLAB_RATES)
    ]
    return tuple(rows)


def negative_benchmark_rate_label() -> str:
    return f"{NEGATIVE_BDR_RATE * 100:.0f}%"


@dataclass(frozen=True)
class _FixtureMonth:
    month_start: date
    spx_start: Decimal
    spx_end: Decimal
    account_start: Decimal
    account_end_after_fees: Decimal
    gross_return: Decimal
    fee_dollars: Decimal
    spx_return: Decimal


def build_preview_fixture_months(profile: AccountProfile) -> tuple[_FixtureMonth, ...]:
    """
    Deterministic month-by-month fixture path for an account profile.

    Gross returns and SPX returns follow fixed cycles; fees come from the real
    v2 fee engine (crystallize_month) so fee behaviour matches production math.
    Fees are treated as removed at each month end, so after-fee NLV is the next
    month's starting balance.
    """
    months: list[_FixtureMonth] = []
    balance = profile.starting_balance
    hwm = profile.starting_balance
    spx = profile.starting_spx
    for i in range(FIXTURE_MONTH_COUNT):
        month_start = _add_months(profile.inception_date.replace(day=1), i)
        gross_return = _FIXTURE_GROSS_RETURN_CYCLE[i % len(_FIXTURE_GROSS_RETURN_CYCLE)]
        spx_return = _FIXTURE_SPX_RETURN_CYCLE[i % len(_FIXTURE_SPX_RETURN_CYCLE)]
        spx_end = (spx * (1 + spx_return)).quantize(Decimal("0.01"))
        gross_balance = (balance * (1 + gross_return)).quantize(Decimal("0.01"))
        result = crystallize_month(
            gross_balance,
            Decimal("0"),
            hwm,
            spx,
            spx_end,
            profile.benchmark_base,
        )
        months.append(
            _FixtureMonth(
                month_start=month_start,
                spx_start=spx,
                spx_end=spx_end,
                account_start=balance,
                account_end_after_fees=result.after_fee_nlv.quantize(Decimal("0.01")),
                gross_return=gross_return,
                fee_dollars=result.current_period_fee.quantize(Decimal("0.01")),
                spx_return=spx_return,
            )
        )
        balance = result.after_fee_nlv.quantize(Decimal("0.01"))
        hwm = result.next_high_water_mark
        spx = spx_end
    return tuple(months)


def _intro_paragraphs(profile: AccountProfile, data_notice: Optional[str]) -> tuple[str, ...]:
    inception_str = profile.inception_date.strftime("%B %d, %Y")
    paragraphs = [
        f"{FIRM_NAME} — CTA & CPO. {PROGRAM_NAME} "
        f"({profile.display_name}, inception {inception_str}).",
        "Instruments: Nasdaq-100 E-mini (NQ) / Micro Nasdaq-100 (MNQ). "
        "Objective: Systematic momentum capture in the Nasdaq-100 futures with "
        "adaptive position sizing and disciplined risk management. "
        "The S&P 500 (SPX) is shown as a benchmark for context only. "
        "Per the Disclosure Document, the monthly incentive (performance) fee is "
        "determined against the S&P 500 (the Benchmark), on net new trading "
        "profits and subject to a high-water mark.",
    ]
    return tuple(paragraphs)


def _fee_terms() -> tuple[LabelValueRow, ...]:
    return (
        LabelValueRow("Management Fee", "None"),
        LabelValueRow(
            "Performance Fee",
            "Monthly incentive fee on net new trading profits (subject to "
            "High-Water Mark), determined by reference to the S&P 500 monthly "
            "return (the Benchmark) — graduated slabs when the Benchmark is "
            "positive; flat "
            + negative_benchmark_rate_label()
            + " of qualifying net new profits when the Benchmark is zero or negative.",
        ),
        LabelValueRow("High-Water Mark", "Yes — fee only on new net gains above prior HWM"),
        LabelValueRow("Fee Frequency", "Monthly"),
    )


def _investor_terms(profile: AccountProfile) -> tuple[LabelValueRow, ...]:
    return (
        LabelValueRow(
            "Performance Fee",
            "Graduated vs S&P 500 Benchmark (Disclosure Document), monthly, HWM",
        ),
        LabelValueRow("High Water Mark", "Yes"),
        LabelValueRow("Benchmark Base", _fmt_money_whole(profile.benchmark_base)),
        LabelValueRow("Trading Units", str(profile.number_of_units)),
        LabelValueRow("Exchange Fee Tier", profile.exchange_fee_tier),
        LabelValueRow("Minimum Investment", _fmt_money_whole(profile.starting_balance)),
    )


def _drawdown_from_nav(points: tuple[SeriesPoint, ...], label: str) -> TearsheetSeries:
    peak: Optional[Decimal] = None
    dd_points: list[SeriesPoint] = []
    for point in points:
        peak = point.value if peak is None else max(peak, point.value)
        dd_pct = (
            (point.value / peak - 1) * 100 if peak and peak > 0 else Decimal("0")
        )
        dd_points.append(SeriesPoint(point.when, dd_pct.quantize(Decimal("0.01"))))
    return TearsheetSeries(label=label, points=tuple(dd_points))


def _performance_metrics_from_months(
    months: tuple[_FixtureMonth, ...],
    profile: AccountProfile,
) -> tuple[LabelValueRow, ...]:
    if not months:
        return ()
    start = months[0].account_start
    end = months[-1].account_end_after_fees
    cumulative = (end / start - 1) * 100 if start > 0 else Decimal("0")
    net_returns = [
        (m.account_end_after_fees / m.account_start - 1) * 100 for m in months
    ]
    avg = sum(net_returns, Decimal("0")) / len(net_returns)
    wins = sum(1 for r in net_returns if r > 0)
    losses = sum(1 for r in net_returns if r < 0)
    best = max(net_returns)
    worst = min(net_returns)
    return (
        LabelValueRow("Cumulative Net Return", _fmt_pct(cumulative)),
        LabelValueRow("Avg Monthly Net Return", f"{avg:.3f}%"),
        LabelValueRow("Number of Months", str(len(months))),
        LabelValueRow(
            "% Winning Months", f"{wins} ({Decimal(wins) / len(months) * 100:.1f}%)"
        ),
        LabelValueRow(
            "% Losing Months", f"{losses} ({Decimal(losses) / len(months) * 100:.1f}%)"
        ),
        LabelValueRow("Best Single Month", _fmt_pct(best)),
        LabelValueRow("Worst Single Month", _fmt_pct(worst)),
    )


def _performance_stats_from_months(
    months: tuple[_FixtureMonth, ...],
) -> tuple[LabelValueRow, ...]:
    if not months:
        return ()
    net_returns = [
        (m.account_end_after_fees / m.account_start - 1) * 100 for m in months
    ]
    pos = [r for r in net_returns if r > 0]
    neg = [r for r in net_returns if r < 0]
    n = len(net_returns)
    avg_win = sum(pos, Decimal("0")) / len(pos) if pos else None
    avg_loss = sum(neg, Decimal("0")) / len(neg) if neg else None
    return (
        LabelValueRow(
            "Number of Positive Months", f"{len(pos)} ({Decimal(len(pos)) / n * 100:.1f}%)"
        ),
        LabelValueRow(
            "Number of Negative Months", f"{len(neg)} ({Decimal(len(neg)) / n * 100:.1f}%)"
        ),
        LabelValueRow(
            "Average Winning Month %", _fmt_pct(avg_win) if avg_win is not None else "—"
        ),
        LabelValueRow(
            "Average Losing Month %", _fmt_pct(avg_loss) if avg_loss is not None else "—"
        ),
        LabelValueRow("Best Single Month %", _fmt_pct(max(net_returns))),
        LabelValueRow("Worst Single Month %", _fmt_pct(min(net_returns))),
    )


def _summary_rows_from_months(
    months: tuple[_FixtureMonth, ...],
) -> tuple[SummaryRow, ...]:
    rows: list[SummaryRow] = []
    if not months:
        return ()
    baseline = months[0].account_start
    for m in months:
        net_return = (
            (m.account_end_after_fees / m.account_start - 1) * 100
            if m.account_start > 0
            else Decimal("0")
        )
        fees_pct = (
            (m.fee_dollars / m.account_start) * 100 if m.account_start > 0 else Decimal("0")
        )
        cumulative = (
            (m.account_end_after_fees / baseline - 1) * 100 if baseline > 0 else Decimal("0")
        )
        rows.append(
            SummaryRow(
                month_label=_month_label(m.month_start),
                spx_start=m.spx_start,
                spx_end=m.spx_end,
                account_start=m.account_start,
                account_end_after_fees=m.account_end_after_fees,
                spx_return_pct=(m.spx_return * 100).quantize(Decimal("0.01")),
                gross_return_pct=(m.gross_return * 100).quantize(Decimal("0.01")),
                fees_pct=fees_pct.quantize(Decimal("0.01")),
                net_return_pct=net_return.quantize(Decimal("0.01")),
                cumulative_net_pct=cumulative.quantize(Decimal("0.01")),
            )
        )
    return tuple(rows)


def _summary_totals_from_months(
    months: tuple[_FixtureMonth, ...],
) -> tuple[LabelValueRow, ...]:
    if not months:
        return ()
    start = months[0].account_start
    end = months[-1].account_end_after_fees
    total_fees = sum((m.fee_dollars for m in months), Decimal("0"))
    net_dollar = end - start
    net_pct = (end / start - 1) * 100 if start > 0 else Decimal("0")
    return (
        LabelValueRow("Net %", _fmt_pct(net_pct)),
        LabelValueRow("Net $", _fmt_money(net_dollar)),
        LabelValueRow("Total Fees $", _fmt_money(total_fees)),
    )


def _nav_series_from_months(
    months: tuple[_FixtureMonth, ...],
    profile: AccountProfile,
) -> tuple[TearsheetSeries, ...]:
    if not months:
        return ()
    nav_points = [SeriesPoint(months[0].month_start, months[0].account_start)]
    spx_points = [SeriesPoint(months[0].month_start, months[0].account_start)]
    spx_cum = Decimal("1")
    for m in months:
        month_end = _add_months(m.month_start, 1)
        nav_points.append(SeriesPoint(month_end, m.account_end_after_fees))
        spx_cum *= 1 + m.spx_return
        spx_points.append(
            SeriesPoint(month_end, (months[0].account_start * spx_cum).quantize(Decimal("0.01")))
        )
    return (
        TearsheetSeries(label="Momentum Pacer (Net of Fees)", points=tuple(nav_points)),
        TearsheetSeries(label="SPX (rebased)", points=tuple(spx_points)),
    )


def _account_stats(
    profile: AccountProfile,
    current_nav: Optional[Decimal],
    total_fees: Optional[Decimal],
    displayed_fee_owed: Optional[Decimal],
) -> tuple[LabelValueRow, ...]:
    rows = [
        LabelValueRow("Starting Capital", _fmt_money_whole(profile.starting_balance)),
        LabelValueRow(
            "Current NAV (after fees)",
            _fmt_money(current_nav) if current_nav is not None else "—",
        ),
        LabelValueRow(
            "Total Net Gain",
            _fmt_money(current_nav - profile.starting_balance)
            if current_nav is not None
            else "—",
        ),
        LabelValueRow(
            "Fees (period shown)" if displayed_fee_owed is None else "Estimated Fee Owed",
            _fmt_money(total_fees)
            if total_fees is not None
            else (_fmt_money(displayed_fee_owed) if displayed_fee_owed is not None else "—"),
        ),
        LabelValueRow("Inception Date", profile.inception_date.strftime("%B %d, %Y")),
    ]
    return tuple(rows)


def build_tearsheet_view_model(
    profile: AccountProfile,
    *,
    state_root: Path | str | None = None,
) -> TearsheetViewModel:
    """
    Build the normalized tearsheet view model for an account.

    Prefers real saved snapshot data; falls back to deterministic preview
    fixture data (clearly labelled) so the layout always renders complete.
    Read-only: never writes or mutates state.
    """
    state_path = resolve_preview_state_path(profile.account_slug, state_root=state_root)
    preview = read_preview_state(state_path)
    snapshot = load_latest_snapshot_for_account(
        profile.account_slug, state_root=state_root
    )

    if snapshot is not None:
        result = compute_latest_snapshot_result(state_path)
        nav_points = (
            SeriesPoint(profile.inception_date, profile.starting_balance),
            SeriesPoint(snapshot.as_of_date, result.after_fee_nlv.quantize(Decimal("0.01"))),
        )
        nav_series = (
            TearsheetSeries(label="Momentum Pacer (Net of Fees)", points=nav_points),
        )
        spx_return_pct = (
            (snapshot.spx_end / snapshot.spx_start - 1) * 100
            if snapshot.spx_start > 0
            else None
        )
        net_pct = (
            (result.after_fee_nlv / profile.starting_balance - 1) * 100
            if profile.starting_balance > 0
            else Decimal("0")
        )
        gross_pct = (
            (snapshot.account_balance / profile.starting_balance - 1) * 100
            if profile.starting_balance > 0
            else Decimal("0")
        )
        fee_pct = (
            (result.current_estimated_fee / profile.starting_balance) * 100
            if profile.starting_balance > 0
            else Decimal("0")
        )
        summary_rows = (
            SummaryRow(
                month_label=_month_label(snapshot.as_of_date),
                spx_start=snapshot.spx_start,
                spx_end=snapshot.spx_end,
                account_start=profile.starting_balance,
                account_end_after_fees=result.after_fee_nlv.quantize(Decimal("0.01")),
                spx_return_pct=spx_return_pct.quantize(Decimal("0.01"))
                if spx_return_pct is not None
                else None,
                gross_return_pct=gross_pct.quantize(Decimal("0.01")),
                fees_pct=fee_pct.quantize(Decimal("0.01")),
                net_return_pct=net_pct.quantize(Decimal("0.01")),
                cumulative_net_pct=net_pct.quantize(Decimal("0.01")),
            ),
        )
        summary_totals = (
            LabelValueRow("Net %", _fmt_pct(net_pct.quantize(Decimal("0.01")))),
            LabelValueRow(
                "Net $",
                _fmt_money(
                    (result.after_fee_nlv - profile.starting_balance).quantize(
                        Decimal("0.01")
                    )
                ),
            ),
            LabelValueRow(
                "Estimated Fee Owed",
                _fmt_money(result.displayed_fee_owed.quantize(Decimal("0.01"))),
            ),
        )
        metrics = (
            LabelValueRow("Cumulative Net Return", _fmt_pct(net_pct.quantize(Decimal("0.01")))),
            LabelValueRow(
                "After-Fee NLV", _fmt_money(result.after_fee_nlv.quantize(Decimal("0.01")))
            ),
            LabelValueRow(
                "Next High-Water Mark",
                _fmt_money(result.next_high_water_mark.quantize(Decimal("0.01"))),
            ),
            LabelValueRow(
                "Benchmark $ Return (period)",
                _fmt_money(result.benchmark_dollar_return.quantize(Decimal("0.01"))),
            ),
        )
        stats = (
            LabelValueRow("Snapshot Date", snapshot.as_of_date.isoformat()),
            LabelValueRow(
                "Gross Balance", _fmt_money(snapshot.account_balance)
            ),
            LabelValueRow(
                "Eligible Profit", _fmt_money(result.eligible_profit.quantize(Decimal("0.01")))
            ),
            LabelValueRow(
                "Current Estimated Fee",
                _fmt_money(result.current_estimated_fee.quantize(Decimal("0.01"))),
            ),
        )
        data_mode = DATA_MODE_SNAPSHOT
        data_notice = None
        last_updated_label = (
            preview.last_updated_utc or snapshot.as_of_date.strftime("%B %d, %Y")
        )
        drawdown = _drawdown_from_nav(nav_points, "Momentum Pacer Drawdown")
        account_stats = _account_stats(
            profile,
            result.after_fee_nlv.quantize(Decimal("0.01")),
            None,
            result.displayed_fee_owed.quantize(Decimal("0.01")),
        )
    else:
        months = build_preview_fixture_months(profile)
        nav_series = _nav_series_from_months(months, profile)
        nav_points = nav_series[0].points
        summary_rows = _summary_rows_from_months(months)
        summary_totals = _summary_totals_from_months(months)
        metrics = _performance_metrics_from_months(months, profile)
        stats = _performance_stats_from_months(months)
        data_mode = DATA_MODE_PREVIEW_FIXTURE
        data_notice = PREVIEW_FIXTURE_NOTICE
        last_updated_label = _add_months(
            months[-1].month_start, 1
        ).strftime("%B %d, %Y")
        drawdown = _drawdown_from_nav(nav_points, "Momentum Pacer Drawdown")
        total_fees = sum((m.fee_dollars for m in months), Decimal("0"))
        account_stats = _account_stats(
            profile,
            months[-1].account_end_after_fees,
            total_fees,
            None,
        )

    return TearsheetViewModel(
        account_slug=profile.account_slug,
        display_name=profile.display_name,
        firm_name=FIRM_NAME,
        program_name=PROGRAM_NAME,
        inception_date=profile.inception_date,
        starting_balance=profile.starting_balance,
        benchmark_base=profile.benchmark_base,
        number_of_units=profile.number_of_units,
        exchange_fee_tier=profile.exchange_fee_tier,
        last_updated_label=last_updated_label,
        data_mode=data_mode,
        data_notice=data_notice,
        intro_paragraphs=_intro_paragraphs(profile, data_notice),
        nav_series=nav_series,
        summary_rows=summary_rows,
        summary_totals=summary_totals,
        performance_metrics=metrics,
        performance_stats=stats,
        fee_structure_rows=fee_structure_rows(),
        fee_terms=_fee_terms(),
        investor_terms=_investor_terms(profile),
        account_stats=account_stats,
        drawdown_series=drawdown,
    )
