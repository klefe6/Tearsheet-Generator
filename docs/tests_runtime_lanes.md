# TCP / TKP test runtime lanes

Use these lanes during development. The **final acceptance lane** remains the gate before production deployment when application logic changes.

> Durations below are measured on one machine on 2026-07-04. Future runs may vary with hardware load, workbook I/O, and environment state.

## When to use each lane

| Lane | Use when |
|------|----------|
| **Development** | Ordinary local work on helpers, contracts, mocked benchmarks, and UI/auth callbacks. Fast feedback; not sufficient alone before deploy. |
| **Focused feature** | You changed specific test files or modules and want targeted regression without the full suite. |
| **Workbook-backed** | Calculation, ledger, dashboard, or drawdown behavior that requires `tcp_alex.xlsx`. |
| **Final acceptance** | Pre-merge / pre-deploy sign-off; includes integration, persistence, import-isolation, and parity coverage. |

### Environment prerequisites

- **Workbook-mode tests**: `conftest.py` forces `TCP_V2_STATE_MODE=workbook` and clears `TCP_V2_STATE_PATH` overrides so developer `json_active` shells do not pollute layout or health assertions. If you run tests outside pytest, clear those variables manually.
- **Import-isolation tests** (`test_tcp_v2_shell.py`, hotfix import checks): stop preview servers on ports **8312** (and **8302** if not production) before running so port-listening assertions are reliable.
- **Benchmark/network tests**: `TCP_V2_SKIP_BENCHMARK_FETCH=1` is set in `conftest.py`; live SPXTR retrieval is not required for automated runs.

## Development lane

Fast command for ordinary work (unit, contract, mocked benchmark, shared-app UI/auth):

```bash
pytest -m "fast and not integration" -q
```

For the narrowest loop (excludes workbook-backed tests; typically under one minute on this machine):

```bash
pytest -m "fast and not integration and not workbook" -q
```

Measured on 2026-07-04: ~27 s for the narrow variant (67 tests).

## Focused feature lane

Run only directly affected test files:

```bash
pytest tests/test_tcp_access_daily_values.py tests/test_tearsheet_password_gate.py -q
```

Replace paths with the modules you changed. Measured UI/auth group (7 files): ~77 s vs ~421 s before fixture consolidation.

## Workbook-backed lane

```bash
pytest -m workbook -q
```

## Final acceptance lane

Complete integration coverage with slow-test report:

```bash
pytest tests -q --durations=20
```

Run this before merging application-logic changes or deploying to production.

## Measured full-suite comparison

| Metric | Before optimization | After optimization |
|--------|---------------------|-------------------|
| Duration | 2263 s (~38 min) | 718 s (~12 min) |
| Passed | 688 | 688 |
| Skipped | 14 | 14 |
| Failed | 0 | 0 |
| Reduction | — | ~68% (~25 min saved per run) |

Intermediate failed runs during optimization (613049, 532280) were superseded by the final green run (847649).

## Markers

| Marker | Meaning |
|--------|---------|
| `fast` | Safe for frequent local runs |
| `integration` | Seed, parity, persistence, import/reload, ledger acceptance |
| `workbook` | Requires local `tcp_alex.xlsx` |
| `network` | Benchmark retrieval (mocked in CI; live optional) |
| `browser` | Responsive / desktop layout contracts |

## Shared fixtures (session scope)

Immutable, read-only resources shared across tests:

- `tcp_ledger` / `ledger` — single workbook parse per session
- `tcp_canonical_nav` / `canonical` — single NAV snapshot per session
- `tcp_app_bundle` / `tcp_app` / `tcp_client` / `tcp_layout_text` — one Dash app per session

**Not shared:** mutation tests, JSON persistence tests, resilience disposable directories, and import-starts-no-server checks each use fresh temporary state or isolated imports.

## What was optimized

- Consolidated repeated workbook loads into session fixtures
- Consolidated repeated `create_app()` calls into `tcp_app_bundle`
- Session-scoped canonical NAV and dashboard propagation where safe
- Deterministic benchmark/network skipping via `TCP_V2_SKIP_BENCHMARK_FETCH`
- Test env isolation from developer `json_active` shells
- Auto-applied pytest markers and lane documentation

Coverage preserved: financial parity assertions, real-workbook acceptance, authentication, mutation authorization, revision conflicts, import-isolation, JSON locking/backup/atomic writes, and responsive/browser contracts.
