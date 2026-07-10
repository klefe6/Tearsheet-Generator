"""GET /api/performance — combined mode, program mode, and benchmark rebasing."""

from __future__ import annotations

from datetime import date, timedelta


def _next_weekday(start: date, target_weekday: int) -> date:
    """First date on/after `start` that falls on `target_weekday` (Mon=0 ... Sun=6).

    Computed rather than hardcoded so these tests never depend on what
    particular weekday any specific calendar date happens to be.
    """
    offset = (target_weekday - start.weekday()) % 7
    return start + timedelta(days=offset)


_A_MONDAY = _next_weekday(date(2026, 7, 1), 0)
_A_SATURDAY = _next_weekday(date(2026, 7, 1), 5)


def _post(client, program, date_str, **fields):
    payload = {"date": date_str, **fields}
    r = client.post(f"/api/rows/{program}", json=payload)
    assert r.status_code == 200, r.text
    return r.json()


# --- combined mode ----------------------------------------------------------
def test_combined_mode_uses_trading_day_index(sandbox_client):
    d0, d1 = _A_MONDAY.isoformat(), (_A_MONDAY + timedelta(days=1)).isoformat()
    _post(sandbox_client, "TKP", d0, stonex_nlv=100000, plus500_nlv=0)
    _post(sandbox_client, "TKP", d1, stonex_nlv=101000, plus500_nlv=0)

    r = sandbox_client.get("/api/performance?mode=combined")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "combined"
    assert body["x_axis"] == "trading_day"
    assert body["base_value"] == 100000
    assert body["program"] is None

    tkp_points = body["points"]["TKP"]
    assert [p["x"] for p in tkp_points] == [0, 1]
    assert tkp_points[0]["y"] == 100000


def test_combined_mode_excludes_benchmarks(sandbox_client):
    _post(sandbox_client, "TCP", _A_MONDAY.isoformat(), stonex_nlv=50000)
    # Even if a client mistakenly asks for benchmarks in combined mode, they
    # must never appear — combined mode is programs-only by contract.
    r = sandbox_client.get("/api/performance?mode=combined&benchmarks=SPX,NDX,BTC")
    assert r.status_code == 200
    body = r.json()
    assert body["benchmarks"] == []
    for sym in ("SPX", "NDX", "BTC"):
        assert sym not in body["points"]
        assert all(s["key"] != sym for s in body["series"])


def test_combined_mode_shorter_program_ends_earlier(sandbox_client):
    dates = [(_A_MONDAY + timedelta(days=i)).isoformat() for i in range(3)]
    for i, d in enumerate(dates):
        _post(sandbox_client, "TKP", d, stonex_nlv=100000 + i * 1000, plus500_nlv=0)
    _post(sandbox_client, "TCP", dates[0], stonex_nlv=50000)

    body = sandbox_client.get("/api/performance?mode=combined").json()
    assert [p["x"] for p in body["points"]["TKP"]] == [0, 1, 2]
    assert [p["x"] for p in body["points"]["TCP"]] == [0]


def test_combined_mode_all_empty_returns_warnings_not_crash(sandbox_client):
    r = sandbox_client.get("/api/performance?mode=combined")
    assert r.status_code == 200
    body = r.json()
    for code in ("TKP", "TCP", "AGM", "YQ"):
        assert body["points"][code] == []
    assert len(body["warnings"]) >= 4


# --- program mode -------------------------------------------------------------
def test_program_mode_uses_real_dates(sandbox_client):
    dates = [(_A_MONDAY + timedelta(days=i)).isoformat() for i in range(3)]
    for i, d in enumerate(dates):
        _post(sandbox_client, "TKP", d, stonex_nlv=100000 + i * 500, plus500_nlv=0)

    r = sandbox_client.get("/api/performance?mode=program&program=TKP")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "program"
    assert body["x_axis"] == "date"
    assert body["program"] == "TKP"
    assert [p["x"] for p in body["points"]["TKP"]] == dates
    assert body["points"]["TKP"][0]["y"] == 100000


def test_program_mode_requires_program_param(sandbox_client):
    r = sandbox_client.get("/api/performance?mode=program")
    assert r.status_code == 422


def test_program_mode_empty_program_returns_warning_not_crash(sandbox_client):
    r = sandbox_client.get("/api/performance?mode=program&program=AGM")
    assert r.status_code == 200
    body = r.json()
    assert body["points"]["AGM"] == []
    assert len(body["warnings"]) >= 1


# --- benchmark rebasing ---------------------------------------------------
def test_benchmark_rebases_to_100000_at_program_start(sandbox_client):
    _post(sandbox_client, "TCP", _A_MONDAY.isoformat(), stonex_nlv=50000)
    r = sandbox_client.get("/api/performance?mode=program&program=TCP&benchmarks=SPX")
    body = r.json()
    assert body["benchmarks"] == ["SPX"]
    assert body["points"]["SPX"][0]["y"] == 100000
    assert any(s["key"] == "SPX" and s["kind"] == "benchmark" for s in body["series"])


def test_benchmark_missing_on_start_date_rolls_forward_with_warning(sandbox_client):
    # First row lands on a Saturday, which the deterministic fixture models as
    # a non-trading day (no benchmark value) — must roll forward and warn.
    _post(sandbox_client, "TCP", _A_SATURDAY.isoformat(), stonex_nlv=50000)
    r = sandbox_client.get("/api/performance?mode=program&program=TCP&benchmarks=SPX")
    body = r.json()
    assert body["points"]["SPX"][0]["y"] == 100000
    assert any("rebased" in w.lower() for w in body["warnings"])


def test_unknown_benchmark_symbol_is_ignored_with_warning(sandbox_client):
    _post(sandbox_client, "TCP", _A_MONDAY.isoformat(), stonex_nlv=50000)
    r = sandbox_client.get("/api/performance?mode=program&program=TCP&benchmarks=FOO")
    body = r.json()
    assert body["benchmarks"] == []
    assert "FOO" not in body["points"]
    assert any("FOO" in w for w in body["warnings"])


# --- accounting: cash-transfer neutralization + AGM fee exclusion -----------
def test_cash_transfer_is_neutralized(sandbox_client):
    d0, d1 = _A_MONDAY.isoformat(), (_A_MONDAY + timedelta(days=1)).isoformat()
    # No transfer: pure 1% trading gain.
    _post(sandbox_client, "TCP", d0, stonex_nlv=100000)
    _post(sandbox_client, "TCP", d1, stonex_nlv=101000, cash_transfer=0)
    # Same 1% trading gain, but a $5,000 deposit is layered on top of the NLV —
    # the deposit must be neutralized so the normalized series matches exactly.
    _post(sandbox_client, "YQ", d0, stonex_nlv=100000)
    _post(sandbox_client, "YQ", d1, stonex_nlv=106000, cash_transfer=5000)

    tcp = sandbox_client.get("/api/performance?mode=program&program=TCP").json()
    yq = sandbox_client.get("/api/performance?mode=program&program=YQ").json()

    tcp_day1 = tcp["points"]["TCP"][1]["y"]
    yq_day1 = yq["points"]["YQ"][1]["y"]
    assert tcp_day1 == 101000
    assert yq_day1 == tcp_day1  # deposit fully neutralized


def test_agm_fee_does_not_affect_performance(sandbox_client):
    d0, d1 = _A_MONDAY.isoformat(), (_A_MONDAY + timedelta(days=1)).isoformat()
    _post(sandbox_client, "AGM", d0, tradestation_nlv=30000, fee=0)
    _post(sandbox_client, "AGM", d1, tradestation_nlv=31000, fee=999999)

    body = sandbox_client.get("/api/performance?mode=program&program=AGM").json()
    expected = round(100000 * (31000 / 30000), 4)
    assert body["points"]["AGM"][1]["y"] == expected


# --- freshness (no caching) -------------------------------------------------
def test_performance_refreshes_after_row_changes(sandbox_client):
    empty = sandbox_client.get("/api/performance?mode=program&program=YQ").json()
    assert empty["points"]["YQ"] == []

    _post(sandbox_client, "YQ", _A_MONDAY.isoformat(), stonex_nlv=60000)
    after_add = sandbox_client.get("/api/performance?mode=program&program=YQ").json()
    assert len(after_add["points"]["YQ"]) == 1

    sandbox_client.delete("/api/rows/YQ/last")
    after_delete = sandbox_client.get("/api/performance?mode=program&program=YQ").json()
    assert after_delete["points"]["YQ"] == []


def test_performance_refreshes_after_export(sandbox_client):
    _post(sandbox_client, "TKP", _A_MONDAY.isoformat(), stonex_nlv=100000, plus500_nlv=0)
    before = sandbox_client.get("/api/performance?mode=combined").json()["last_updated_at"]

    sandbox_client.post("/api/export/all")
    after = sandbox_client.get("/api/performance?mode=combined").json()["last_updated_at"]
    assert after >= before


def test_last_updated_at_present_when_no_data(sandbox_client):
    body = sandbox_client.get("/api/performance?mode=combined").json()
    assert isinstance(body["last_updated_at"], str) and "T" in body["last_updated_at"]
