"""tearsheet_uploader_ingest framework: gating, auth, validation, idempotency.

Transport-agnostic tests against handle_ingest_request (no Flask needed) —
the same core every app route calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tearsheet_uploader_ingest import (
    DRY_RUN_ALLOWED_ENV,
    ENABLED_ENV,
    TOKEN_ENV,
    IngestConfig,
    IngestOutcome,
    IngestRejected,
    handle_ingest_request,
)

TOKEN = "test-ingest-token"


def _headers(token=TOKEN):
    return {"Authorization": f"Bearer {token}"} if token else {}


def _config(apply=None, audit_path=None):
    def default_apply(payload, dry_run):
        return IngestOutcome(action="created", before=None, after=dict(payload))

    return IngestConfig(
        program="TKP",
        required_fields=("stonex_nlv",),
        optional_fields=("plus500_nlv", "cash_transfer"),
        apply=apply or default_apply,
        audit_path=audit_path,
    )


def _payload(**overrides):
    body = {
        "program": "TKP",
        "date": "2026-07-10",
        "stonex_nlv": 123456.78,
        "plus500_nlv": 23456.78,
        "source": "glenn_uploader",
        "dry_run": True,
    }
    body.update(overrides)
    return body


@pytest.fixture
def enabled_env(monkeypatch):
    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.setenv(TOKEN_ENV, TOKEN)


def test_disabled_ingest_is_rejected(monkeypatch):
    monkeypatch.delenv(ENABLED_ENV, raising=False)
    monkeypatch.setenv(TOKEN_ENV, TOKEN)
    response, status = handle_ingest_request(_config(), _headers(), _payload(), "t")
    assert status == 403
    assert response["accepted"] is False
    assert response["action"] == "rejected"
    assert ENABLED_ENV in response["message"]


def test_missing_server_token_fails_closed(monkeypatch):
    monkeypatch.setenv(ENABLED_ENV, "true")
    monkeypatch.delenv(TOKEN_ENV, raising=False)
    response, status = handle_ingest_request(_config(), _headers(), _payload(), "t")
    assert status == 403
    assert "fail-closed" in response["message"]


def test_unauthenticated_and_wrong_token_rejected(enabled_env):
    _, status = handle_ingest_request(_config(), {}, _payload(), "t")
    assert status == 401
    _, status = handle_ingest_request(_config(), _headers("nope"), _payload(), "t")
    assert status == 401
    # X-Glenn-Uploader-Token header also works.
    response, status = handle_ingest_request(
        _config(), {"X-Glenn-Uploader-Token": TOKEN}, _payload(), "t"
    )
    assert status == 200 and response["accepted"] is True


def test_wrong_program_rejected(enabled_env):
    response, status = handle_ingest_request(
        _config(), _headers(), _payload(program="TCP"), "t"
    )
    assert status == 422
    assert "TKP rows only" in response["message"]


def test_invalid_date_and_missing_required_rejected(enabled_env):
    _, status = handle_ingest_request(
        _config(), _headers(), _payload(date="07/10/2026"), "t"
    )
    assert status == 422
    response, status = handle_ingest_request(
        _config(), _headers(), _payload(stonex_nlv=None), "t"
    )
    assert status == 422
    assert "stonex_nlv is required" in response["message"]


def test_unknown_field_rejected_fee_for_tkp(enabled_env):
    """fee sent to TKP is rejected loudly, never silently dropped."""
    response, status = handle_ingest_request(
        _config(), _headers(), _payload(fee=12.5), "t"
    )
    assert status == 422
    assert "unknown field(s) for TKP: fee" in response["message"]


def test_dry_run_flag_passes_through_and_defaults_true(enabled_env):
    seen = {}

    def apply(payload, dry_run):
        seen["dry_run"] = dry_run
        return IngestOutcome(action="created")

    body = _payload()
    del body["dry_run"]
    response, status = handle_ingest_request(_config(apply), _headers(), body, "t")
    assert status == 200
    assert seen["dry_run"] is True  # safe default
    assert response["dry_run"] is True

    handle_ingest_request(_config(apply), _headers(), _payload(dry_run=False), "t")
    assert seen["dry_run"] is False


def test_dry_run_can_be_refused(enabled_env, monkeypatch):
    monkeypatch.setenv(DRY_RUN_ALLOWED_ENV, "false")
    response, status = handle_ingest_request(
        _config(), _headers(), _payload(dry_run=True), "t"
    )
    assert status == 403
    assert DRY_RUN_ALLOWED_ENV in response["message"]


def test_apply_rejection_and_audit_trail(enabled_env, tmp_path):
    audit = tmp_path / "audit.jsonl"

    def apply(payload, dry_run):
        if payload["date"] == "2026-07-11":
            raise IngestRejected("older than latest row")
        return IngestOutcome(action="unchanged", before={"a": 1}, after={"a": 1})

    cfg = _config(apply, audit_path=audit)
    ok_resp, ok_status = handle_ingest_request(cfg, _headers(), _payload(), "1.2.3.4")
    assert (ok_status, ok_resp["action"]) == (200, "unchanged")
    assert ok_resp["before"] == {"a": 1}

    rej_resp, rej_status = handle_ingest_request(
        cfg, _headers(), _payload(date="2026-07-11"), "1.2.3.4"
    )
    assert (rej_status, rej_resp["action"]) == (422, "rejected")

    lines = [json.loads(line) for line in audit.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[0]["accepted"] is True and lines[0]["action"] == "unchanged"
    assert lines[1]["accepted"] is False and lines[1]["remote_addr"] == "1.2.3.4"
