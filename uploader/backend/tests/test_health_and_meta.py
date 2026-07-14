"""Health and program metadata endpoints.

Performance-endpoint tests live in test_performance.py — the old mock-only
`normalization_base`/`series[key][0]` contract asserted here previously was
replaced by the real mode=combined|program contract built from stored rows.
"""

from __future__ import annotations


def test_health(sandbox_client):
    r = sandbox_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app_env"] == "sandbox"
    assert body["export_enabled"] is False
    assert body["export_downstream_enabled"] is False
    assert body["export_dry_run"] is True
    assert body["export_target_env"] == "sandbox"
    assert "version" in body


def test_program_metadata(sandbox_client):
    r = sandbox_client.get("/api/programs")
    assert r.status_code == 200
    programs = {p["code"]: p for p in r.json()["programs"]}
    assert set(programs) == {"TKP", "TCP", "AGM", "YQ"}

    def field_names(code):
        return [f["name"] for f in programs[code]["fields"]]

    assert field_names("TKP") == ["date", "stonex_nlv", "plus500_nlv", "cash_transfer"]
    assert field_names("TCP") == ["date", "stonex_nlv", "cash_transfer"]
    assert field_names("AGM") == ["date", "tradestation_nlv", "cash_transfer", "fee"]
    assert field_names("YQ") == ["date", "stonex_nlv", "cash_transfer"]

    # Y&Q label surfaced for the YQ code.
    assert programs["YQ"]["label"] == "Y&Q"


def _field_by_name(program: dict, name: str) -> dict:
    return next(f for f in program["fields"] if f["name"] == name)


def test_program_account_copy_metadata(sandbox_client):
    """Account numbers are exposed only on the four NLV fields that need copy."""
    r = sandbox_client.get("/api/programs")
    assert r.status_code == 200
    programs = {p["code"]: p for p in r.json()["programs"]}

    expected_accounts = {
        ("TKP", "stonex_nlv"): ("StoneX", "69060709"),
        ("TKP", "plus500_nlv"): ("Plus500", "50110102"),
        ("TCP", "stonex_nlv"): ("StoneX", "69060795"),
        ("AGM", "tradestation_nlv"): ("TradeStation", "210TGG51"),
    }

    for (code, field_name), (label, number) in expected_accounts.items():
        field = _field_by_name(programs[code], field_name)
        assert field["copy_to_clipboard"] is True
        assert field["account_label"] == label
        assert field["account_number"] == number

    no_account_fields = [
        ("TKP", "date"),
        ("TKP", "cash_transfer"),
        ("TCP", "date"),
        ("TCP", "cash_transfer"),
        ("AGM", "date"),
        ("AGM", "cash_transfer"),
        ("AGM", "fee"),
        ("YQ", "date"),
        ("YQ", "stonex_nlv"),
        ("YQ", "cash_transfer"),
    ]
    for code, field_name in no_account_fields:
        field = _field_by_name(programs[code], field_name)
        assert field["copy_to_clipboard"] is False
        assert "account_number" not in field
        assert "account_label" not in field
