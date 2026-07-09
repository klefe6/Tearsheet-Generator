"""Health, program metadata, and performance endpoints."""

from __future__ import annotations


def test_health(sandbox_client):
    r = sandbox_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app_env"] == "sandbox"
    assert body["export_enabled"] is False
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


def test_performance_series(sandbox_client):
    r = sandbox_client.get("/api/performance")
    assert r.status_code == 200
    body = r.json()
    assert body["normalization_base"] == 100000
    series = body["series"]
    for key in ["TKP", "TCP", "AGM", "YQ", "SPX", "NDX", "BTC"]:
        assert key in series
        assert len(series[key]) > 0
        # Every series is normalized to start at the base value.
        assert series[key][0]["value"] == 100000
