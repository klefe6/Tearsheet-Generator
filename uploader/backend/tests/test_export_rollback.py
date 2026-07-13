"""Export rollback: reversibility gating, saga execution, and failure recovery.

The load-bearing assertion in most of these tests is not "the API returned ok"
but "the destination file is byte-for-byte back at its pre-export state, and the
uploader rows were freed ONLY because that was true".
"""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app import rollback as rollback_mod
from app.db import (
    BATCH_COMMITTED,
    BATCH_NO_MUTATION,
    BATCH_ROLLED_BACK,
    Database,
)
from tests.conftest import _TMP, _cleanup, _make_client

TOKEN = "test-secret-token"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def _rollback_client(**overrides):
    """Sandbox client wired for a REAL downstream sandbox-file export, with
    rollback enabled and an admin token (rollback always requires one)."""
    tag = uuid4().hex
    sandbox_dir = _TMP / f"ds_{tag}"
    backup_dir = _TMP / f"bk_{tag}"
    defaults = dict(
        app_env="sandbox",
        export_enabled=False,
        admin_api_token=TOKEN,
        export_downstream_enabled=True,
        export_dry_run=False,
        export_target_env="sandbox",
        export_rollback_enabled=True,
        downstream_sandbox_dir=str(sandbox_dir),
        rollback_backup_dir=str(backup_dir),
    )
    defaults.update(overrides)
    client = _make_client(**defaults)
    client._sandbox_dir = sandbox_dir  # type: ignore[attr-defined]
    client._backup_dir = backup_dir  # type: ignore[attr-defined]
    return client


@pytest.fixture
def rb_client():
    client = _rollback_client()
    try:
        yield client
    finally:
        client.close()
        _cleanup(client)


def _dest(client, program: str) -> dict:
    path = Path(client._sandbox_dir) / f"{program.lower()}_rows.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("rows", {})


def _add(client, program: str, date: str, **fields):
    body = {"date": date, **fields}
    r = client.post(f"/api/rows/{program}", json=body)
    assert r.status_code in (200, 201), r.text
    return r


def _export(client) -> dict:
    r = client.post("/api/export/all")
    assert r.status_code == 200, r.text
    return r.json()


def _preview(client, batch_id=None) -> dict:
    url = (
        "/api/export/batches/latest/rollback/preview"
        if batch_id is None
        else f"/api/export/batches/{batch_id}/rollback/preview"
    )
    r = client.post(url, headers=AUTH)
    assert r.status_code == 200, r.text
    return r.json()


def _confirm(client, batch_id, token, reason="Incorrect source balance"):
    return client.post(
        f"/api/export/batches/{batch_id}/rollback/confirm",
        headers=AUTH,
        json={"confirmation_token": token, "reason": reason},
    )


def _codes(payload) -> set[str]:
    return {r["code"] for r in payload.get("blocking_reasons", [])}


def _db(client) -> Database:
    return Database(str(client._uploader_db_path))


# --- capability / flag / auth ----------------------------------------------
def test_rollback_disabled_by_default(sandbox_client):
    cap = sandbox_client.get("/api/export/rollback/capability").json()
    assert cap["rollback_supported"] is True
    assert cap["rollback_enabled"] is False
    assert "EXPORT_ROLLBACK_ENABLED" in cap["reason"]


def test_rollback_requires_token_even_in_sandbox(rb_client):
    """The relaxed sandbox auth path must NOT apply to a destructive endpoint."""
    r = rb_client.post("/api/export/batches/latest/rollback/preview")
    assert r.status_code == 401


def test_rollback_fails_closed_without_admin_token_configured():
    client = _rollback_client(admin_api_token=None)
    try:
        cap = client.get("/api/export/rollback/capability").json()
        assert cap["rollback_enabled"] is False
        assert "ADMIN_API_TOKEN" in cap["reason"]
        r = client.post("/api/export/batches/latest/rollback/preview", headers=AUTH)
        assert r.status_code == 503
    finally:
        client.close()
        _cleanup(client)


def test_preview_blocked_when_flag_off():
    client = _rollback_client(export_rollback_enabled=False)
    try:
        r = client.post("/api/export/batches/latest/rollback/preview", headers=AUTH)
        assert r.status_code == 200
        assert r.json()["reversible"] is False
        assert "rollback_disabled" in _codes(r.json())
    finally:
        client.close()
        _cleanup(client)


# --- reversibility gating ---------------------------------------------------
def test_dry_run_batch_cannot_be_rolled_back():
    client = _rollback_client(export_dry_run=True)
    try:
        _add(client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
        _export(client)
        # A dry run is not a rollback candidate at all -> there is no latest
        # mutating batch to find.
        out = _preview(client)
        assert out["reversible"] is False
        assert _codes(out) & {"no_batches", "dry_run_no_mutation"}
        assert _dest(client, "TKP") == {}  # nothing was written
    finally:
        client.close()
        _cleanup(client)


def test_no_batches_to_roll_back(rb_client):
    out = _preview(rb_client)
    assert out["reversible"] is False
    assert "no_batches" in _codes(out)


def test_batch_with_no_successful_write_is_not_reversible(rb_client):
    """An export that wrote nothing downstream is status=no_mutation."""
    _export(rb_client)  # no rows at all
    db = _db(rb_client)
    batch = db.get_export_batch(1)
    assert batch["status"] == BATCH_NO_MUTATION
    out = _preview(rb_client)
    assert out["reversible"] is False


def test_latest_committed_batch_preview_succeeds(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    exp = _export(rb_client)
    out = _preview(rb_client)

    assert out["reversible"] is True
    assert out["batch_id"] == exp["batch_id"]
    assert out["batch_status"] == BATCH_COMMITTED
    assert out["confirmation_token"]
    assert out["expires_at"]

    tkp = next(p for p in out["programs"] if p["program"] == "TKP")
    op = tkp["downstream_operations"][0]
    assert op["operation"] == "delete_created_row"
    assert op["date"] == "2026-07-10"
    assert op["current_state_matches_export"] is True
    # Sandbox destinations hold raw inputs only — no derived accounting exists
    # there to replay. Reported honestly rather than claimed.
    assert op["replay_required"] is False


def test_preview_is_read_only(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    _export(rb_client)
    before = _dest(rb_client, "TKP")
    _preview(rb_client)
    _preview(rb_client)
    assert _dest(rb_client, "TKP") == before
    db = _db(rb_client)
    assert db.get_export_batch(1)["status"] == BATCH_COMMITTED
    assert db.get_rollback_for_batch(1) is None


def test_older_batch_blocked_when_newer_batch_exists(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    first = _export(rb_client)["batch_id"]
    _add(rb_client, "TKP", "2026-07-11", stonex_nlv=106000, plus500_nlv=20000)
    _export(rb_client)

    out = _preview(rb_client, batch_id=first)
    assert out["reversible"] is False
    assert "newer_batch_exists" in _codes(out)


def test_yq_reported_as_having_no_destination(rb_client):
    _add(rb_client, "YQ", "2026-07-10", stonex_nlv=60000)
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    _export(rb_client)
    out = _preview(rb_client)

    # Y&Q never reaches a destination, so it can never appear as a reversible
    # program — and we say so rather than inventing support for it.
    assert all(p["program"] != "YQ" for p in out["programs"])
    assert _dest(rb_client, "YQ") == {}


def test_production_target_is_blocked_with_no_reversal_route(rb_client):
    """A production export has no downstream reversal endpoint; refuse honestly."""
    db = _db(rb_client)
    batch_id = db.add_export_batch(
        app_env="sandbox",
        export_enabled=True,
        dry_run=False,
        row_count=1,
        payload={},
        status=BATCH_COMMITTED,
        actor="admin",
        target_env="production",
        downstream_enabled=True,
    )
    db.add_batch_item(
        batch_id=batch_id,
        source_row_id=1,
        program="TKP",
        date="2026-07-10",
        export_id=f"{batch_id}:1:TKP",
        target_env="production",
        operation="created",
        downstream_target="https://tkp.example/api/uploader/ingest-daily-row",
        downstream_identifier="TKP:2026-07-10",
        before_state=None,
        after_state={"stonex_nlv": 105000},
        before_checksum=None,
        after_checksum="sha256:x",
        export_result="success",
    )
    out = _preview(rb_client, batch_id=batch_id)
    assert out["reversible"] is False
    assert "no_downstream_reversal_route" in _codes(out)


# --- checksum / snapshot guards ---------------------------------------------
def test_destination_modified_since_export_blocks_rollback(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    _export(rb_client)

    # Simulate a later manual change to the destination record.
    path = Path(rb_client._sandbox_dir) / "tkp_rows.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["rows"]["2026-07-10"]["stonex_nlv"] = 999999
    path.write_text(json.dumps(doc), encoding="utf-8")

    out = _preview(rb_client)
    assert out["reversible"] is False
    assert "downstream_modified_since_export" in _codes(out)
    # And the later change must survive — we refuse rather than overwrite it.
    assert _dest(rb_client, "TKP")["2026-07-10"]["stonex_nlv"] == 999999


def test_missing_snapshot_blocks_rollback(rb_client):
    """An 'updated' item with no before_state cannot be restored exactly."""
    db = _db(rb_client)
    batch_id = db.add_export_batch(
        app_env="sandbox", export_enabled=True, dry_run=False, row_count=1,
        payload={}, status=BATCH_COMMITTED, actor="admin", target_env="sandbox",
        downstream_enabled=True,
    )
    db.add_batch_item(
        batch_id=batch_id, source_row_id=1, program="TKP", date="2026-07-10",
        export_id=f"{batch_id}:1:TKP", target_env="sandbox", operation="updated",
        downstream_target="x", downstream_identifier="tkp_rows.json#rows.2026-07-10",
        before_state=None, after_state={"a": 1},
        before_checksum=None, after_checksum="sha256:x", export_result="success",
    )
    out = _preview(rb_client, batch_id=batch_id)
    assert out["reversible"] is False
    assert "missing_snapshot" in _codes(out)


def test_missing_downstream_identifier_blocks_rollback(rb_client):
    db = _db(rb_client)
    batch_id = db.add_export_batch(
        app_env="sandbox", export_enabled=True, dry_run=False, row_count=1,
        payload={}, status=BATCH_COMMITTED, actor="admin", target_env="sandbox",
        downstream_enabled=True,
    )
    db.add_batch_item(
        batch_id=batch_id, source_row_id=1, program="TKP", date="2026-07-10",
        export_id=f"{batch_id}:1:TKP", target_env="sandbox", operation="created",
        downstream_target="x", downstream_identifier=None,
        before_state=None, after_state={"a": 1},
        before_checksum=None, after_checksum="sha256:x", export_result="success",
    )
    out = _preview(rb_client, batch_id=batch_id)
    assert out["reversible"] is False
    assert "legacy_batch_missing_downstream_identity" in _codes(out)


def test_legacy_batch_without_items_is_not_reversible(rb_client):
    """Batches created before this feature have no snapshots — never auto-reverse."""
    db = _db(rb_client)
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO export_batches (ts, app_env, export_enabled, dry_run, "
            "row_count, payload, status, downstream_enabled) "
            "VALUES ('2026-01-01T00:00:00Z','sandbox',1,0,1,'{}','legacy',1)"
        )
    out = _preview(rb_client, batch_id=1)
    assert out["reversible"] is False
    assert "legacy_batch_missing_snapshot" in _codes(out)


# --- token guards -----------------------------------------------------------
def test_confirm_rejects_missing_token(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    r = _confirm(rb_client, batch_id, token="")
    assert r.status_code == 409
    assert "invalid_confirmation_token" in _codes(r.json())


def test_confirm_rejects_token_for_another_batch(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    first = _export(rb_client)["batch_id"]
    token = _preview(rb_client, batch_id=first)["confirmation_token"]

    _add(rb_client, "TKP", "2026-07-11", stonex_nlv=106000, plus500_nlv=20000)
    second = _export(rb_client)["batch_id"]

    r = _confirm(rb_client, second, token=token)
    assert r.status_code == 409
    assert "token_batch_mismatch" in _codes(r.json())


def test_expired_token_rejected(rb_client, monkeypatch):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    monkeypatch.setattr(rollback_mod, "TOKEN_TTL_SECONDS", -1)
    token = _preview(rb_client)["confirmation_token"]

    r = _confirm(rb_client, batch_id, token=token)
    assert r.status_code == 409
    assert "token_expired" in _codes(r.json())
    assert "2026-07-10" in _dest(rb_client, "TKP")  # untouched


def test_confirm_requires_reason(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    r = _confirm(rb_client, batch_id, token=token, reason="   ")
    assert r.status_code == 409
    assert "reason_required" in _codes(r.json())


def test_destination_changed_after_preview_rejects_confirm(rb_client):
    """CAS: the token is bound to the previewed downstream fingerprint."""
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]

    path = Path(rb_client._sandbox_dir) / "tkp_rows.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["rows"]["2026-07-10"]["stonex_nlv"] = 777777
    path.write_text(json.dumps(doc), encoding="utf-8")

    r = _confirm(rb_client, batch_id, token=token)
    assert r.status_code == 409
    codes = _codes(r.json())
    assert codes & {"downstream_modified_since_export", "destination_changed_since_preview"}
    assert _dest(rb_client, "TKP")["2026-07-10"]["stonex_nlv"] == 777777


# --- concurrency ------------------------------------------------------------
def test_lock_blocks_rollback_while_held(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]

    _db(rb_client).acquire_lock("export:someone-else")
    r = _confirm(rb_client, batch_id, token=token)
    assert r.status_code == 409
    assert "concurrent_operation" in _codes(r.json())
    assert "2026-07-10" in _dest(rb_client, "TKP")


def test_lock_blocks_export_while_held(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    _db(rb_client).acquire_lock("rollback:someone-else")
    r = rb_client.post("/api/export/all")
    assert r.status_code == 409


def test_lock_released_after_successful_rollback(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    assert _confirm(rb_client, batch_id, token=token).status_code == 200
    assert _db(rb_client).get_lock() is None


# --- the happy path, end to end ---------------------------------------------
def test_created_row_rollback_restores_exact_pre_export_state(rb_client):
    """Export -> preview -> confirm -> destination is EXACTLY pre-export."""
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    assert _dest(rb_client, "TKP") == {}  # pre-export state: no record

    batch_id = _export(rb_client)["batch_id"]
    assert "2026-07-10" in _dest(rb_client, "TKP")

    token = _preview(rb_client)["confirmation_token"]
    r = _confirm(rb_client, batch_id, token=token)
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["ok"] is True
    assert body["status"] == BATCH_ROLLED_BACK
    assert body["source_rows_unexported"] == 1
    tkp = next(p for p in body["programs"] if p["program"] == "TKP")
    assert tkp["records_reversed"] == 1
    assert tkp["replay_completed"] is True
    assert tkp["replay_from_date"] == "2026-07-10"

    # The whole point: byte-for-byte back to the pre-export state.
    assert _dest(rb_client, "TKP") == {}
    assert _db(rb_client).get_export_batch(batch_id)["status"] == BATCH_ROLLED_BACK


def test_updated_row_rollback_restores_prior_values(rb_client):
    """A replaced record must come back with its ORIGINAL values, not be deleted."""
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    _export(rb_client)
    original = dict(_dest(rb_client, "TKP")["2026-07-10"])

    # Change the row and export again -> this batch UPDATES the destination.
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=111111, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    assert _dest(rb_client, "TKP")["2026-07-10"]["stonex_nlv"] == 111111

    out = _preview(rb_client)
    assert out["reversible"] is True
    assert out["programs"][0]["downstream_operations"][0]["operation"] == "restore_prior_row"

    r = _confirm(rb_client, batch_id, token=out["confirmation_token"])
    assert r.status_code == 200, r.text
    assert _dest(rb_client, "TKP")["2026-07-10"] == original


def test_multi_program_rollback(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    _add(rb_client, "TCP", "2026-07-10", stonex_nlv=98000, cash_transfer=500)
    _add(rb_client, "AGM", "2026-07-10", tradestation_nlv=30000, fee=125.5)
    batch_id = _export(rb_client)["batch_id"]
    for p in ("TKP", "TCP", "AGM"):
        assert "2026-07-10" in _dest(rb_client, p)

    token = _preview(rb_client)["confirmation_token"]
    body = _confirm(rb_client, batch_id, token=token).json()
    assert {p["program"] for p in body["programs"]} == {"TKP", "TCP", "AGM"}
    assert body["source_rows_unexported"] == 3
    for p in ("TKP", "TCP", "AGM"):
        assert _dest(rb_client, p) == {}


# --- export eligibility -----------------------------------------------------
def test_rows_become_unexported_only_after_successful_rollback(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]

    # After export the row is no longer eligible.
    assert _export(rb_client)["total_rows"] == 0

    token = _preview(rb_client, batch_id=batch_id)["confirmation_token"]
    assert _confirm(rb_client, batch_id, token=token).status_code == 200

    # After rollback it is eligible again — exactly one row, not a duplicate.
    rows = _db(rb_client).get_unexported_rows()
    assert len(rows) == 1
    assert rows[0]["program"] == "TKP" and rows[0]["date"] == "2026-07-10"
    assert rows[0]["exported_batch_id"] is None


def test_reexport_after_rollback_creates_one_row_not_a_duplicate(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    _confirm(rb_client, batch_id, token=token)
    assert _dest(rb_client, "TKP") == {}

    _export(rb_client)
    dest = _dest(rb_client, "TKP")
    assert list(dest.keys()) == ["2026-07-10"]  # exactly one, upserted by date


def test_row_reexported_by_newer_batch_is_not_freed(rb_client):
    """Ownership guard: never clear an exported flag a newer batch now owns."""
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    first = _export(rb_client)["batch_id"]
    token = _preview(rb_client, batch_id=first)["confirmation_token"]

    # A newer batch re-exports the same row before the rollback is confirmed.
    db = _db(rb_client)
    db.mark_exported("TKP", "2026-07-10", first + 99)

    r = _confirm(rb_client, first, token=token)
    # Blocked outright by newer-batch detection, or (if it ran) the row is not freed.
    if r.status_code == 200:
        assert any(w["code"] == "source_row_reexported" for w in r.json()["warnings"])
        assert db.get_unexported_rows() == []


# --- idempotency ------------------------------------------------------------
def test_repeated_confirm_is_idempotent_and_does_not_execute_twice(rb_client):
    """A client that lost the response can safely retry."""
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]

    first = _confirm(rb_client, batch_id, token=token)
    assert first.status_code == 200
    rollback_id = first.json()["rollback_id"]

    # Re-export so the destination has a record again — if a replayed confirm
    # actually re-executed, it would wrongly delete this one.
    _export(rb_client)
    assert "2026-07-10" in _dest(rb_client, "TKP")

    second = _confirm(rb_client, batch_id, token=token)
    assert second.status_code == 200
    body = second.json()
    assert body["idempotent_replay"] is True
    assert body["rollback_id"] == rollback_id
    assert body["status"] == BATCH_ROLLED_BACK
    # The re-exported record survived: the replay mutated nothing.
    assert "2026-07-10" in _dest(rb_client, "TKP")

    rollbacks = _db(rb_client).get_rollback_for_batch(batch_id)
    assert rollbacks["id"] == rollback_id


def test_already_rolled_back_batch_preview_is_blocked(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    _confirm(rb_client, batch_id, token=token)

    out = _preview(rb_client, batch_id=batch_id)
    assert out["reversible"] is False
    assert "already_rolled_back" in _codes(out)


# --- audit ------------------------------------------------------------------
def test_audit_and_batch_items_are_never_deleted(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    _confirm(rb_client, batch_id, token=token)

    db = _db(rb_client)
    items = db.get_batch_items(batch_id)
    assert len(items) == 1
    assert items[0]["export_result"] == "success"  # original export audit intact
    assert items[0]["rollback_result"] == "reversed"
    assert items[0]["rolled_back_at"]
    assert items[0]["export_id"] == f"{batch_id}:{items[0]['source_row_id']}:TKP"

    rb = db.get_rollback_for_batch(batch_id)
    assert rb["status"] == "rolled_back"
    assert rb["reason"] == "Incorrect source balance"
    assert rb["actor"] == "admin"
    assert rb["backups"]  # backup locations recorded

    actions = {a["action"] for a in db.get_audit(limit=50)}
    assert {"export_rollback_started", "export_rollback_completed"} <= actions


def test_backup_file_is_written_before_mutation(rb_client):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    _confirm(rb_client, batch_id, token=token)

    backups = list(Path(rb_client._backup_dir).glob("*.json"))
    assert len(backups) == 1
    # The backup holds the PRE-rollback (i.e. post-export) content.
    doc = json.loads(backups[0].read_text(encoding="utf-8"))
    assert "2026-07-10" in doc["rows"]


# --- failure injection ------------------------------------------------------
def test_second_destination_fails_first_is_recovered_and_rows_stay_exported(
    rb_client, monkeypatch
):
    """Saga: a mid-rollback failure restores what was already mutated, leaves the
    uploader rows exported, and reports failure — never partial success.

    Items are processed in (program, date) order, so AGM is reversed first and
    TKP is made to fail after it: that is what forces a real recovery of an
    already-mutated destination rather than a no-op.
    """
    _add(rb_client, "AGM", "2026-07-10", tradestation_nlv=30000, fee=125.5)
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]

    agm_after = dict(_dest(rb_client, "AGM"))
    tkp_after = dict(_dest(rb_client, "TKP"))

    real = rollback_mod.rollback_sandbox_row
    calls: list[str] = []

    def flaky(sandbox_dir, program, date, before):
        calls.append(program)
        if program == "TKP":
            raise OSError("disk exploded")
        return real(sandbox_dir, program, date, before)

    monkeypatch.setattr(rollback_mod, "rollback_sandbox_row", flaky)

    r = _confirm(rb_client, batch_id, token=token)
    assert r.status_code == 409
    assert "rollback_failed" in _codes(r.json())
    assert calls == ["AGM", "TKP"]  # AGM really was mutated before TKP blew up

    # Both destinations are back at their PRE-ROLLBACK (post-export) state —
    # including AGM, which had already been reversed and was rolled forward again.
    assert _dest(rb_client, "AGM") == agm_after
    assert _dest(rb_client, "TKP") == tkp_after

    db = _db(rb_client)
    # Rows were NOT freed — the downstream writes are still in place.
    assert db.get_unexported_rows() == []
    assert db.get_export_batch(batch_id)["status"] == "rollback_failed"
    rb = db.get_rollback_for_batch(batch_id)
    assert rb["status"] == "rollback_failed"
    assert rb["verification"]["recovery"]["AGM"] == "restored"
    assert db.get_lock() is None  # lock always released


def test_backup_failure_prevents_any_mutation(rb_client, monkeypatch):
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    after = dict(_dest(rb_client, "TKP"))

    def boom(*a, **k):
        raise OSError("read-only filesystem")

    monkeypatch.setattr(rollback_mod.shutil, "copy2", boom)

    r = _confirm(rb_client, batch_id, token=token)
    assert r.status_code == 409
    assert "backup_failed" in _codes(r.json())

    # Not one destination byte changed, and the row stays exported.
    assert _dest(rb_client, "TKP") == after
    assert _db(rb_client).get_unexported_rows() == []
    assert _db(rb_client).get_lock() is None


def test_verification_failure_recovers_and_reports_failure(rb_client, monkeypatch):
    """If post-rollback verification does not prove the pre-export state, fail."""
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    after = dict(_dest(rb_client, "TKP"))

    monkeypatch.setattr(
        rollback_mod,
        "_verify",
        lambda settings, items: {"ok": False, "failures": [{"program": "TKP"}]},
    )

    r = _confirm(rb_client, batch_id, token=token)
    assert r.status_code == 409
    assert "rollback_failed" in _codes(r.json())
    assert _dest(rb_client, "TKP") == after  # recovered from backup
    assert _db(rb_client).get_unexported_rows() == []


def test_atomic_write_failure_leaves_prior_file_valid(rb_client, monkeypatch):
    """A crash during the destination write must not corrupt the existing file."""
    _add(rb_client, "TKP", "2026-07-10", stonex_nlv=105000, plus500_nlv=20000)
    batch_id = _export(rb_client)["batch_id"]
    token = _preview(rb_client)["confirmation_token"]
    path = Path(rb_client._sandbox_dir) / "tkp_rows.json"
    before_bytes = path.read_bytes()

    import app.downstream_export as dse

    monkeypatch.setattr(dse.os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("no")))

    r = _confirm(rb_client, batch_id, token=token)
    assert r.status_code == 409
    # os.replace never happened -> the original file is intact and still valid JSON.
    assert path.read_bytes() == before_bytes
    assert json.loads(path.read_text(encoding="utf-8"))["rows"]["2026-07-10"]
    assert _db(rb_client).get_unexported_rows() == []
