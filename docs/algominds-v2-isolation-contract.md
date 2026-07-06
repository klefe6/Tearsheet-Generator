# Algominds v1 → v2 Isolation Contract

This document defines the boundary between the existing Algominds tearsheet
(Momentum Pacer) and the planned TKP/TCP-style Algominds v2 implementation.
It is a structural contract only — no application code or runtime state is
created by this lane.

Repository: `klefe6/Tearsheet-Generator`  
Development branch: `feature/algominds-v2-isolation`  
Development worktree: `.worktrees/algominds-v2`

---

## Existing Algominds v1 (Momentum Pacer)

| Item | Value |
| ---- | ----- |
| Entrypoint | `Momentum Pacer/mp_ts.py` |
| Production identity | Momentum Pacer / Algominds Financial LLC |
| Production port | `8304` |
| Hostname | `agm-ts.hcresearch.ltd` |
| Launcher | `reboot_mp_ts.bat` |
| Status | Preserved and untouched during v2 development |
| Role | Current production implementation and rollback reference |

v1 must not be modified, restarted, or replaced during v2 development lanes.

---

## Algominds v2 development

| Item | Value |
| ---- | ----- |
| Repository | Same `Tearsheet-Generator` repo |
| Worktree | `.worktrees/algominds-v2` |
| Branch | `feature/algominds-v2-isolation` (and successors) |
| Preview port | `8311` |
| Production port | **None** during development |
| Code prefix | `algominds_v2_` |
| Environment prefix | `ALGOMINDS_V2_*` |
| Preview state | Separate path under `tests/_algominds_preview_state/` (created in a later lane) |
| Production state | Separate path under `%LocalAppData%\HughesCompany\Algominds\` (created at cutover prep) |

### Hard prohibitions during development

- No fallback to TKP, TCP, or Momentum Pacer data when Algominds v2 state is empty.
- No shared writable JSON state with TKP (`daily_returns_secret_state.json`) or TCP (`tcp_daily_returns_secret_state.json`).
- No shared production environment file (`.tcp_production.env`, `.algominds_production.env`).
- No shared launcher (`reboot_mp_ts.bat`, `reboot_tcp_ts.bat`, `reboot_tkp_ts.bat`).
- No inheritance of `TCP_V2_*` or `TKP_*` credentials.
- No runtime creation in the isolation lane (no servers, no state files, no workbooks).
- No second permanent Algominds production application on any port during development.

### Naming

| Label | Use |
| ----- | --- |
| Product name | Algominds |
| Implementation labels | Algominds v1, Algominds v2 |
| Code prefix | `algominds_v2_` |
| Environment prefix | `ALGOMINDS_V2_` |

Do not use ambiguous `AGM` prefixes where they could be confused with the unrelated `AGM CO` project.

---

## Future production cutover (not implemented here)

Cutover may occur only after all of the following:

1. Historical accounting parity against the authoritative workbook.
2. Independent acceptance (separate from TCP v2 acceptance).
3. Explicit operator approval and a written cutover runbook.

### Intended cutover direction

| Step | Action |
| ---- | ------ |
| 1 | Algominds v2 passes parity and acceptance on preview port `8311`. |
| 2 | During an explicit maintenance window, v2 assumes production port `8304`. |
| 3 | Existing hostname `agm-ts.hcresearch.ltd` may be repointed to v2 only during that cutover. |
| 4 | v1 (`mp_ts.py`) is preserved temporarily as rollback — not deleted at initial cutover. |
| 5 | Rollback restores the prior launcher and runtime without data loss. |

Until cutover, port `8304` and hostname `agm-ts.hcresearch.ltd` remain owned by Algominds v1.

---

## Related tearsheets (out of scope)

| Application | Port | Notes |
| ----------- | ---- | ----- |
| TKP | 8301 | Must not be modified by Algominds v2 work |
| TCP v2 | 8302 | Must not be modified by Algominds v2 work |
| TCP v2 preview | 8312 | Distinct from Algominds v2 preview (`8311`) |
| Y&Q | 8303 | Unrelated |

---

## Revision history

| Date | Change |
| ---- | ------ |
| 2026-07-05 | Initial isolation contract established on `feature/algominds-v2-isolation` |
