"""Tests for Algominds v2 fee snapshot foundation."""
from __future__ import annotations

import ast
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

import algominds_v2_snapshots as snapshots

D = Decimal
TOLERANCE = D("0.01")


def _may_2026_snapshot() -> snapshots.AlgomindsV2FeeSnapshot:
    return snapshots.AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        prior_high_water_mark=D("44483.423270"),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        benchmark_base=D("30000"),
    )


def test_snapshot_builds_correct_fee_engine_input_fields() -> None:
    snapshot = _may_2026_snapshot()
    result = snapshots.compute_fee_snapshot(snapshot)
    assert result.fee_basis == snapshot.account_balance - snapshot.fee_removal
    assert result.eligible_profit == max(D("0"), result.fee_basis - snapshot.prior_high_water_mark)


def test_fee_basis_equals_account_balance_minus_fee_removal() -> None:
    snapshot = snapshots.AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("50000"),
        fee_removal=D("2967.84673"),
        prior_high_water_mark=D("40000"),
        spx_start=D("6528.52"),
        spx_end=D("7209.01"),
        benchmark_base=D("30000"),
    )
    result = snapshots.compute_fee_snapshot(snapshot)
    assert result.fee_basis == D("50000") - D("2967.84673")


def test_positive_fee_month_golden_like_case() -> None:
    result = snapshots.compute_fee_snapshot(_may_2026_snapshot())
    assert abs(result.current_estimated_fee - D("1330.249061")) < TOLERANCE
    assert abs(result.after_fee_nlv - D("48794.960939")) < TOLERANCE
    assert abs(result.next_high_water_mark - D("48794.960939")) < TOLERANCE


def test_zero_fee_month_hwm_holds() -> None:
    snapshot = snapshots.AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 6, 30),
        account_balance=D("48049.07"),
        fee_removal=D("0"),
        prior_high_water_mark=D("48794.960939"),
        spx_start=D("7580.06"),
        spx_end=D("7499.36"),
        benchmark_base=D("30000"),
    )
    result = snapshots.compute_fee_snapshot(snapshot)
    assert result.current_estimated_fee == D("0")
    assert result.next_high_water_mark == D("48794.960939")


def test_fee_removal_reduces_fee_basis_before_calculation() -> None:
    without = snapshots.compute_fee_snapshot(
        snapshots.AlgomindsV2FeeSnapshot(
            as_of_date=date(2026, 5, 31),
            account_balance=D("50000"),
            fee_removal=D("0"),
            prior_high_water_mark=D("40000"),
            spx_start=D("6528.52"),
            spx_end=D("7209.01"),
            benchmark_base=D("30000"),
        )
    )
    with_removal = snapshots.compute_fee_snapshot(
        snapshots.AlgomindsV2FeeSnapshot(
            as_of_date=date(2026, 5, 31),
            account_balance=D("50000"),
            fee_removal=D("2967.84673"),
            prior_high_water_mark=D("40000"),
            spx_start=D("6528.52"),
            spx_end=D("7209.01"),
            benchmark_base=D("30000"),
        )
    )
    assert with_removal.fee_basis < without.fee_basis
    assert with_removal.current_estimated_fee != without.current_estimated_fee


def test_liability_display_fields() -> None:
    result = snapshots.compute_fee_snapshot(_may_2026_snapshot())
    assert result.displayed_fee_owed > 0
    assert result.signed_fee_liability < 0
    assert result.displayed_fee_owed == -result.signed_fee_liability
    assert result.nlv == result.after_fee_nlv


@pytest.mark.parametrize(
    "factory,match",
    [
        (
            lambda: snapshots.AlgomindsV2FeeSnapshot(
                date(2026, 5, 31), D("-1"), D("0"), D("0"), D("100"), D("110")
            ),
            "account_balance",
        ),
        (
            lambda: snapshots.AlgomindsV2FeeSnapshot(
                date(2026, 5, 31), D("100"), D("-1"), D("0"), D("100"), D("110")
            ),
            "fee_removal",
        ),
        (
            lambda: snapshots.AlgomindsV2FeeSnapshot(
                date(2026, 5, 31), D("100"), D("200"), D("0"), D("100"), D("110")
            ),
            "account_balance must be >= fee_removal",
        ),
        (
            lambda: snapshots.AlgomindsV2FeeSnapshot(
                date(2026, 5, 31), D("100"), D("0"), D("0"), D("0"), D("110")
            ),
            "spx_start",
        ),
        (
            lambda: snapshots.AlgomindsV2FeeSnapshot(
                date(2026, 5, 31), D("100"), D("0"), D("0"), D("100"), D("110"), D("0")
            ),
            "benchmark_base",
        ),
    ],
)
def test_invalid_inputs_rejected(factory, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        snapshots.compute_fee_snapshot(factory())


def test_decimal_serialization_uses_strings() -> None:
    snapshot = _may_2026_snapshot()
    payload = snapshots.snapshot_to_dict(snapshot)
    assert isinstance(payload["account_balance"], str)
    assert isinstance(payload["fee_removal"], str)
    assert isinstance(payload["benchmark_base"], str)
    raw = snapshots.snapshot_to_json(snapshot)
    decoded = json.loads(raw)
    assert isinstance(decoded["account_balance"], str)
    assert "50125.21" in decoded["account_balance"]


def test_snapshot_json_round_trip() -> None:
    original = _may_2026_snapshot()
    restored = snapshots.snapshot_from_dict(snapshots.snapshot_to_dict(original))
    assert restored == original
    assert snapshots.compute_fee_snapshot(restored) == snapshots.compute_fee_snapshot(original)


def test_account_slug_optional_defaults_none() -> None:
    snapshot = _may_2026_snapshot()
    assert snapshot.account_slug is None


def test_account_slug_validated_when_present() -> None:
    snapshot = snapshots.AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        prior_high_water_mark=D("44483.423270"),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        benchmark_base=D("30000"),
        account_slug="prop",
    )
    assert snapshot.account_slug == "prop"
    snapshots.compute_fee_snapshot(snapshot)


@pytest.mark.parametrize("slug", ["PROP", "prop acct", "12345678901"])
def test_invalid_account_slug_rejected_on_snapshot(slug: str) -> None:
    snapshot = snapshots.AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("100"),
        fee_removal=D("0"),
        prior_high_water_mark=D("0"),
        spx_start=D("100"),
        spx_end=D("110"),
        account_slug=slug,
    )
    with pytest.raises(ValueError):
        snapshots.compute_fee_snapshot(snapshot)


def test_json_round_trip_preserves_account_slug() -> None:
    original = snapshots.AlgomindsV2FeeSnapshot(
        as_of_date=date(2026, 5, 31),
        account_balance=D("50125.21"),
        fee_removal=D("0"),
        prior_high_water_mark=D("44483.423270"),
        spx_start=D("7209.01"),
        spx_end=D("7580.06"),
        benchmark_base=D("30000"),
        account_slug="prop",
    )
    payload = snapshots.snapshot_to_dict(original)
    assert payload["account_slug"] == "prop"
    restored = snapshots.snapshot_from_dict(payload)
    assert restored.account_slug == "prop"
    assert restored == original


def test_snapshot_from_dict_without_account_slug_backward_compatible() -> None:
    payload = snapshots.snapshot_to_dict(_may_2026_snapshot())
    assert "account_slug" not in payload
    restored = snapshots.snapshot_from_dict(payload)
    assert restored.account_slug is None


def test_compute_fee_ignores_account_slug_identity() -> None:
    base = _may_2026_snapshot()
    with_slug = snapshots.AlgomindsV2FeeSnapshot(
        as_of_date=base.as_of_date,
        account_balance=base.account_balance,
        fee_removal=base.fee_removal,
        prior_high_water_mark=base.prior_high_water_mark,
        spx_start=base.spx_start,
        spx_end=base.spx_end,
        benchmark_base=base.benchmark_base,
        account_slug="prop",
    )
    assert snapshots.compute_fee_snapshot(base) == snapshots.compute_fee_snapshot(with_slug)


def test_forbidden_import_scan() -> None:
    source_path = Path(snapshots.__file__)
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    forbidden_roots = {
        "dash",
        "flask",
        "openpyxl",
        "pandas",
        "tkp_ts",
        "tcp_ts",
        "mp_ts",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                assert root not in forbidden_roots
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            assert root not in forbidden_roots
