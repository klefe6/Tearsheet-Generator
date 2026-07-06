# Algominds v2 Config Contract

Configuration foundation for Algominds v2 preview and application lanes. This
module defines constants and parsing only — no servers, no state files, no
workbook access.

Repository: `klefe6/Tearsheet-Generator`  
Module: `algominds_v2_config.py`  
Related: `docs/algominds-v2-isolation-contract.md`

---

## Environment prefix

All Algominds v2 runtime overrides use:

```text
ALGOMINDS_V2_*
```

Do not reuse `TCP_V2_*`, `TKP_*`, or ambiguous `AGM_*` prefixes.

---

## Preview port

| Item | Value |
| ---- | ----- |
| Default | `8311` |
| Override | `ALGOMINDS_V2_PREVIEW_PORT` |

### Protected ports

The following ports must not be selected as preview bind ports:

| Port | Owner |
| ---- | ----- |
| 8301 | TKP |
| 8302 | TCP v2 production |
| 8304 | Algominds v1 / Momentum Pacer production |

Invalid values (non-integer, below 1, above 65535, or protected) are rejected
at config load time.

---

## State path

| Item | Value |
| ---- | ----- |
| Default filename | `algominds_daily_returns_secret_state.json` |
| Default location | Repository root |
| Override | `ALGOMINDS_V2_STATE_PATH` |

Config loading **never** creates the state file. Preview state under
`tests/_algominds_preview_state/` may be introduced in a later lane.

---

## Production env filename (constant only)

```text
.algominds_production.env
```

Declared as `DEFAULT_ENV_FILENAME` for future cutover lanes. Config loading
does not read or create this file.

---

## Side-effect prohibitions

`load_algominds_v2_config()` must not:

- start or bind a server;
- read workbooks;
- create state or `.env` files;
- import TKP, TCP, Momentum Pacer, Dash, Flask, or workbook libraries.

Callers may pass an explicit `env` mapping for tests instead of mutating
`os.environ`.

---

## Relationship to isolation contract

This module implements the port and state-path conventions documented in
`docs/algominds-v2-isolation-contract.md`. Future lanes (preview app, daily
ingestion, persistence) will consume `AlgomindsV2Config` without changing
`algominds_v2/fee_engine.py` or `fee_ledger.py`.

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-06 | Initial config foundation on `feature/algominds-v2-config` |
