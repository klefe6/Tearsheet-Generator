"""Regression: Sept 16 / 555 production export cannot be undone from the uploader.

Reproduces the 2026-09-16 test workflow at the API layer: a committed production
batch with 555 downstream values is not reversible; preview must not issue a token.
"""

from __future__ import annotations

from app.db import BATCH_COMMITTED
from tests.conftest import _make_client

TOKEN = "test-secret-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_production_555_batch_preview_is_not_reversible():
    client = _make_client(
        export_downstream_enabled=True,
        export_target_env="production",
        export_dry_run=False,
        export_rollback_enabled=True,
        admin_api_token=TOKEN,
    )
    try:
        db = client.app.state.db
        batch_id = db.add_export_batch(
            app_env="production",
            export_enabled=True,
            dry_run=False,
            row_count=3,
            payload={},
            status=BATCH_COMMITTED,
            actor="glenn",
            target_env="production",
            downstream_enabled=True,
        )
        for program in ("TKP", "TCP", "AGM"):
            db.add_batch_item(
                batch_id=batch_id,
                source_row_id=1,
                program=program,
                date="2026-09-16",
                export_id=f"{batch_id}:1:{program}",
                target_env="production",
                operation="created",
                downstream_target="https://example/ingest",
                downstream_identifier=f"{program}:2026-09-16",
                before_state={"date": "2026-09-15"},
                after_state={"value": 555},
                before_checksum="sha256:before",
                after_checksum="sha256:after",
                export_result="success",
            )

        r = client.post(
            f"/api/export/batches/{batch_id}/rollback/preview",
            headers=AUTH,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["reversible"] is False
        assert body.get("confirmation_token") is None
        codes = {reason["code"] for reason in body["blocking_reasons"]}
        assert "no_downstream_reversal_route" in codes
    finally:
        client.close()
