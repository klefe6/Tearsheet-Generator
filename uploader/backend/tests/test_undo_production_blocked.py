"""Production downstream exports are not reversible from the uploader."""

from __future__ import annotations

from app import rollback as rollback_mod
from app.db import BATCH_COMMITTED
from tests.conftest import _make_client


def test_production_committed_batch_is_not_reversible():
    client = _make_client(
        export_downstream_enabled=True,
        export_target_env="production",
        export_dry_run=False,
        export_rollback_enabled=True,
        admin_api_token="test-token",
    )
    try:
        db = client.app.state.db
        batch_id = db.add_export_batch(
            app_env="sandbox",
            export_enabled=True,
            dry_run=False,
            row_count=1,
            payload={},
            status=BATCH_COMMITTED,
            actor="test",
            target_env="production",
            downstream_enabled=True,
        )
        batch = db.get_export_batch(batch_id)
        db.add_batch_item(
            batch_id=batch_id,
            source_row_id=1,
            program="TKP",
            date="2026-09-16",
            export_id=f"{batch_id}:1:TKP",
            target_env="production",
            operation="created",
            downstream_target="http://example/ingest",
            downstream_identifier="TKP:2026-09-16",
            before_state=None,
            after_state={"stonex_nlv": 555},
            before_checksum=None,
            after_checksum="sha256:x",
            export_result="success",
        )
        batch = db.get_export_batch(batch_id)
        plan = rollback_mod.evaluate(db, client.app.state.settings, batch)
        assert plan["reversible"] is False
        codes = {r["code"] for r in plan["blocking_reasons"]}
        assert "no_downstream_reversal_route" in codes
    finally:
        client.close()
