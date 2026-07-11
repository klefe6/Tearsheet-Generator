"""TCP glue for the Glenn Uploader ingest route.

Maps an uploader TCP row {date, stonex_nlv, cash_transfer} onto TCP v2's OWN
add-row machinery, so an ingested row is computed and persisted exactly like
an admin "Add Row":

  * ``stonex_nlv``    -> ``Cash Balance`` (== NLV for TCP's cash-settled
                         futures account) — the manual INPUT, from which
                         tcp_calculations.compute_tcp_row derives the
                         cash-transfer-neutral ``nav-x1`` the chart plots.
  * ``cash_transfer`` -> ``Cash Transfers`` (TCP's model rejects negative
                         transfers — surfaced as a clean rejection).
  * ``#`` (tranches)  -> carried forward from the prior row (phase 1 does
                         not change tranche count via ingest).

Idempotency by date against the CURRENT ledger:
  * date == latest row's date, same inputs      -> "unchanged" (no write)
  * date == latest row's date, changed inputs   -> "updated": delete last +
    re-add through the app's own persist functions (two audited revisions)
  * date >  latest row's date                   -> "created" (append)
  * anything older / interior                   -> rejected (phase 1 appends
    or replaces the latest row only — interior edits stay admin-only)

Dry-run uses tcp_admin.simulate_add_row (the same simulation the admin modal
shows) and never writes. NOTE (documented caveat): TCP v2 bakes its layout at
process start, so an ingested row reaches the LIVE page only after a TCP
restart — the state file itself is updated immediately and safely.
"""

from __future__ import annotations

from typing import Any, Mapping

from tcp_admin import simulate_add_row
from tcp_runtime_state import (
    load_runtime_snapshot,
    persist_add_row,
    persist_delete_last_row,
    state_record_to_fields,
)
from tearsheet_uploader_ingest import IngestConfig, IngestOutcome, IngestRejected


def _row_view(fields: Mapping[str, Any]) -> dict:
    """Audit-friendly subset of a TCP ledger record."""
    date_val = fields.get("Date")
    return {
        "date": date_val.isoformat() if hasattr(date_val, "isoformat") else str(date_val),
        "cash_balance": _as_float(fields.get("Cash Balance")),
        "cash_transfers": _as_float(fields.get("Cash Transfers") or 0),
        "tranches": _as_float(fields.get("#")),
        "nav_x1": _as_float(fields.get("nav-x1")),
    }


def _as_float(value: Any) -> Any:
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def build_tcp_ingest_config(cfg: Any, paths: Any, audit_path: Any = None) -> IngestConfig:
    """IngestConfig for TCP. `cfg`/`paths` are the app's own TCPConfig and
    resolved StatePaths — the same objects its admin persistence uses."""

    def apply(payload: dict, dry_run: bool) -> IngestOutcome:
        snapshot = load_runtime_snapshot(cfg, paths)
        if not snapshot.records:
            raise IngestRejected("TCP state has no records; seed the ledger first.")
        if not dry_run and (not snapshot.writable or cfg.state_mode != "json_active"):
            raise IngestRejected(
                "TCP state is not writable on this instance "
                f"(state_mode={cfg.state_mode}); ingest refused."
            )

        last = state_record_to_fields(snapshot.records[-1].fields)
        last_view = _row_view(last)
        date = payload["date"]
        cash_balance = payload["stonex_nlv"]
        cash_transfers = payload["cash_transfer"]
        if cash_transfers < 0:
            raise IngestRejected(
                "TCP's ledger model does not support negative cash transfers; "
                "record withdrawals via the TCP admin UI instead."
            )
        tranches = int(float(last.get("#") or 1))

        if date < last_view["date"]:
            raise IngestRejected(
                f"date {date} is older than TCP's latest row {last_view['date']} — "
                "ingest appends or replaces the latest row only."
            )

        if date == last_view["date"]:
            same = (
                abs(last_view["cash_balance"] - cash_balance) < 0.005
                and abs(last_view["cash_transfers"] - cash_transfers) < 0.005
            )
            if same:
                return IngestOutcome(
                    action="unchanged", before=last_view, after=last_view,
                    message=f"TCP {date} already has these values.",
                )
            if len(snapshot.records) < 2:
                raise IngestRejected(
                    "cannot replace TCP's only ledger row via ingest; "
                    "use the TCP admin UI."
                )
            prior = state_record_to_fields(snapshot.records[-2].fields)
            sim = simulate_add_row(
                prior, row_date=date, cash_balance=cash_balance,
                cash_transfers=cash_transfers, tranche_count=tranches,
            )
            if not sim.success or sim.proposed_row is None:
                raise IngestRejected(sim.error_message or "TCP rejected the row inputs.")
            after = _row_view(sim.proposed_row)
            if dry_run:
                return IngestOutcome(action="updated", before=last_view, after=after)
            deleted = persist_delete_last_row(
                cfg, paths, expected_revision=snapshot.state_revision,
                expected_final_date=last_view["date"], authenticated=True,
            )
            if not deleted.success:
                raise IngestRejected(f"replace failed at delete step: {deleted.error_message}")
            added = persist_add_row(
                cfg, paths, expected_revision=deleted.revision,
                row_date=date, cash_balance=cash_balance,
                cash_transfers=cash_transfers, tranche_count=tranches,
                authenticated=True,
            )
            if not added.success:
                raise IngestRejected(
                    f"replace failed at re-add step (last row was deleted, revision "
                    f"{deleted.revision}): {added.error_message}"
                )
            return IngestOutcome(action="updated", before=last_view, after=after)

        # date > latest: append.
        sim = simulate_add_row(
            last, row_date=date, cash_balance=cash_balance,
            cash_transfers=cash_transfers, tranche_count=tranches,
        )
        if not sim.success or sim.proposed_row is None:
            raise IngestRejected(sim.error_message or "TCP rejected the row inputs.")
        after = _row_view(sim.proposed_row)
        if dry_run:
            return IngestOutcome(action="created", before=last_view, after=after)
        added = persist_add_row(
            cfg, paths, expected_revision=snapshot.state_revision,
            row_date=date, cash_balance=cash_balance,
            cash_transfers=cash_transfers, tranche_count=tranches,
            authenticated=True,
        )
        if not added.success:
            raise IngestRejected(added.error_message or "TCP persist failed.")
        return IngestOutcome(action="created", before=last_view, after=after)

    return IngestConfig(
        program="TCP",
        required_fields=("stonex_nlv",),
        optional_fields=("cash_transfer",),
        apply=apply,
        audit_path=audit_path,
    )
