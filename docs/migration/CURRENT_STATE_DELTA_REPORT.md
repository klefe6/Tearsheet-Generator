# Current-State Delta Report — VPS Reorganization

> Read-only reconciliation of prior reorganization/startup/migration audits against the current deployed worktree.
> Timestamp: 2026-08-01 (local, UTC-4).
> No code, data, services, Git, Fly, Cloudflare, DNS, or Azure resources were modified.

---

## 1. Executive verdict

**Portable deployment is still blocked by path and ownership gaps, not by architecture redesign.**

The ratified Windows Server 2022 / IIS / NSSM / Cloudflare Tunnel target remains valid. The historic move sequence **Y&Q → TKP → TCP → AGM → shared extraction** remains safe and should not be replaced.

What has changed since the prior audits:

- Production runtime is confirmed at `.worktrees/live-deploy-main` on `live-main` @ `3cfda4f`.
- Glenn Uploader ingest is merged on TKP/TCP/AGM; the July 13 “unmerged ingest” blocker is resolved.
- Launchers now refuse the dirty root checkout and pin the live worktree.
- Y&Q CSV resolution gained `YQ_CSV_PATH` and a repo-root fallback.
- Startup-folder autostart now exists and is enabled (contradicting the July 24 “no Startup entry” claim).

What has **not** changed enough for VPS cutover:

- No application body move is deployed. Only an unmerged Y&Q Phase-1 shim branch exists.
- TKP/AGM state paths remain `__file__`-anchored.
- OneDrive/protected-folder workbook and logo paths remain hard-coded.
- Production state still lives in/near the git worktree (except TCP AppData state).
- Uploader production and sandbox hostnames remain one shared Fly deployment (latest local evidence: 2026-07-30).
- Glenn frontend/backend are split across checkouts; Glenn launcher source-of-truth is not merged into `live-main`.

**Next safe implementation lane:** introduce central mutable-data and source-path configuration while retaining current defaults. Do **not** merge the parked Y&Q body move, do **not** extract shared modules, and do **not** provision Azure until path portability and dirty-deployed-checkout ownership are resolved.

---

## 2. Current Git and runtime baseline

### Git

| Checkout | Branch | SHA | Dirty / notes |
|---|---|---|---|
| `.worktrees/live-deploy-main` | `live-main` | `3cfda4f` | Partial dirty: on-disk `tkp_ts.py` differs from committed tip; `git status` blocked by dubious ownership (`BUILTIN/Administrators`) |
| Repo root | `fix/post-ingest-full-recalculation` | `c8b57b5` | Dirty: 8 modified + 2 untracked (`docs/migration/` among them); forks from `live-main` at `8fe8143` |
| `Tearsheet Generator-reorg-yq` | `feature/reorg-yq-phase1` | `a8bc22d` | Clean relative to its tip; **not merged** into `live-main` |
| `Tearsheet Generator-reorg-prep` | `chore/tearsheet-reorg-prep` | `a373e47` | Ancestor of `live-main` (merged/stale) |

Reported commit chain — **all present as ancestors of `live-main`**:

| SHA | Subject | On `live-main`? |
|---|---|---|
| `3cfda4f` | Add AGM downstream continuity regression coverage | Yes (tip) |
| `4fcdc74` | Deterministic layout tests with no live benchmark downloads | Yes |
| `069f892` | Use actual Y&Q source date and deployed checkout | Yes |
| `2fbcfcc` | Clarify TCP drawdown footnote | Yes |
| `f7911c9` | Use $50,000 per-tranche TCP drawdown base | Yes |
| `1a459e7` | Correct TCP Other Notes tranche copy | Yes |
| `c3e6a65` | Correct TCP drawdown nominal and duration calculations | Yes |

Worktree inventory: **48 worktrees** (plus external reorg/launcher trees). Only `live-deploy-main` is the authoritative production checkout.

### Runtime service matrix

| Service | Port | Current checkout | Current entrypoint | Matches historic audit? | Drift found |
|---|---:|---|---|---|---|
| Dashboard | 8006 | `C:\Coding Projects\HomePage` | `debug.py` via `.venv13` | Mostly | Binds `0.0.0.0`; process predates some merged selective-control commits |
| TKP public | 8301 | `live-deploy-main` | `tkp_ts.py` | Yes | Deployed file dirty vs committed tip |
| TCP public | 8302 | `live-deploy-main` | `tcp_ts_v2.py` | Yes | Listener PID changed since Jul 24 matrix |
| Y&Q public | 8303 | `live-deploy-main` | `yq_ts.py` | Mostly | Now launches via worktree PS1 + `YQ_CSV_PATH`; still no `/healthz` |
| AGM public | 8304 | `live-deploy-main\Momentum Pacer` | `mp_ts.py` | Yes | Manual JSON + ingest now live (was “not yet on disk”) |
| TKP staff | 8321 | `live-deploy-main` | `tkp_ts.py` (staff) | Yes | Manual, not auto-started by fleet |
| TCP staff | 8322 | `live-deploy-main` | `tcp_ts_v2.py` (staff) | Yes | Manual |
| AGM staff | 8324 | `live-deploy-main\Momentum Pacer` | `mp_ts.py` (staff) | Yes | Manual |
| Allocation | 8511 | `AGM_Allocation` | `app.py` | Yes | Binds `0.0.0.0` |
| Glenn FE | 5173 | **`live-deploy-main\uploader\frontend`** | Vite sandbox mode | Partial | Split from backend checkout |
| Glenn BE | 8091 | **dirty root `...\uploader\backend`** | uvicorn `app.main:app` | No | Split-brain vs FE / live tip |

Manager/HomePage startup:

- Startup-folder `HC Launch All Services.cmd` **exists and is enabled**.
- Active master `launch_all_services.py` observed as **terminal-owned**, not Startup-folder-owned; idle Startup wrappers remain.
- Manager HEAD synced with origin but **dirty/untracked operational files** remain; `setup_autostart.bat` changes uncommitted.
- HomePage HEAD equals `origin/main`; Glenn selective-control logic present in merged history, but active dashboard process may be stale relative to disk.

---

## 3. Prior-document accuracy assessment

| Document | Historic purpose | Still accurate | Partially stale | Superseded by | Current action |
|---|---|---|---|---|---|
| `docs/reorganization/dependency-map.md` | App closures, data, routes @ `a5beb25` | Structure/closures largely accurate | Ingest “not present”, AGM manual JSON “not on disk”, production assumed at root | This delta report §4–5 | Keep; annotate ingest/manual-JSON/live-worktree deltas |
| `docs/reorganization/external-contracts.md` | Frozen bats/ports/routes/Manager/HomePage | Bat names, ports, routes still frozen | Uploader ingest status flipped from unmerged→merged; root path contracts now mediated by live-worktree guards | This delta + Azure build spec | Keep contracts; update ingest status |
| `docs/reorganization/file-classification.md` | Move targets and do-not-move data | Classification still correct | No moves executed on `live-main`; shims not yet created | Unmerged `feature/reorg-yq-phase1` for Y&Q only | Keep as move plan; do not recreate |
| `docs/reorganization/migration-sequence.md` | Y&Q→TKP→TCP→AGM→shared | Sequence still safest | P0 dirty-tree/ingest blockers partly changed shape; Phase 1 Y&Q exists off-branch | This delta §5/§9 | Retain sequence; park merge until path config |
| `docs/reorganization/regression-plan.md` | Per-phase gates | Still required | Some gate line numbers drifted with ingest/TCP/AGM commits | Live tests @ `3cfda4f` | Keep; refresh line refs when implementing |
| `docs/reorganization/risks-and-blockers.md` | Reorg blockers/path env proposals | R1/R2/R3/R8/R9 still real | B2 ingest-unmerged **resolved**; dirty-tree location shifted to live/root divergence | This delta §6/§12 | Keep risk IDs; update B2 status |
| `docs/migration/AZURE_VM_BUILD_SPECIFICATION.md` | Ratified Windows VPS architecture | **Authoritative** | Region/handoff inputs still pending | — | Do not redesign |
| `docs/migration/PHASE_2_EXECUTION_PLAN.md` | Gated provision→cutover | Gate structure valid | Baseline commit/value anchors lag current tip | This delta + future Gate 2.5 refresh | Keep; update baseline SHA/values at reconcile |
| `docs/migration/MIGRATION_INPUT_VERIFICATION.md` | Handoff package check | Still accurate: AI_HANDOFF empty | — | — | Still blocks homepage/DNS/tunnel/workbook gates |
| `docs/migration/LOCAL_DEPLOYMENT_AUDIT.md` | Jul 24 runtime audit | Ports/apps/data inventory useful | Startup “none”, commit `f540135`, no-ingest assumptions stale | This delta report | Historic baseline only |
| `docs/migration/LOCAL_DEPLOYMENT_ACTION_ITEMS.md` | AI-01…AI-16 | Most still open | AI-03 OS choice **ratified**; AI-12 reorg still post-path-config | Azure spec + this delta | Track remaining AIs |
| `docs/migration/LOCAL_DEPLOYMENT_MANIFEST.json` | Machine-readable Jul 24 snapshot | Structural | PIDs/commit/startup stale | This delta §2 | Do not treat as live |
| `docs/migration/PRODUCTION_RECONCILIATION_BASELINE.json` | Value anchors | Method valid | Values/dates are Jul 26; tip now `3cfda4f` | Gate 2.5 refresh | Preserve stale-TCP/Y&Q flags; do not “fix” data |

**Contradictions worth preserving:**

1. Prior reorg audit assumed root checkout as live → **false now**; live-deploy-main is canonical.
2. Jul 24 audit said no Startup entry → **false**; enabled CMD exists (ownership of the live master launcher is still not Startup-folder-true).
3. Older Ubuntu/Nginx/systemd pilot language, where present, is **historical** and superseded by Windows/IIS/NSSM.
4. Older uploader handoff comments claiming unimplemented production transport / isolated sandbox are **obsolete**.

---

## 4. Changes since the previous audit

| Area | Prior | Current | Implication |
|---|---|---|---|
| Live tip | `f540135` (Jul 24) | `3cfda4f` | TCP 50k-tranche drawdown, Y&Q source-date, AGM continuity tests landed |
| Ingest bridge | Unmerged / absent in live tree | Merged on TKP/TCP/AGM | Reorg P0.2 ingest conflict risk reduced, but entrypoints still root-canonical |
| Launchers | Root-capable | Refuse dirty root; pin live-deploy-main | Good for production identity; hard-codes laptop path layout |
| Y&Q data path | `__file__` sibling only | `YQ_CSV_PATH` → sibling → main-root `yq.csv` | Partial portability; still laptop-root default |
| AGM manual JSON | Planned/not on disk | Live R/W + ingest + cold-start recalc | Mutable AGM state is real production data |
| Startup | Audit claimed none | Enabled Startup CMD present | NSSM still required for VPS; local recovery remains mixed |
| Uploader transport | Stub / dry-run narrative | Production POST implemented | Separation before cutover is mandatory |
| Reorg dirs | Planned | Still absent on `live-main` | Moves have not begun in production |

---

## 5. Actual reorganization progress

| Application | Prior planned state | Current actual state | Remaining move | Shim status | Blocker |
|---|---|---|---|---|---|
| Y&Q | Phase 1 first move to `apps/yq` + root shim | Body still full root `yq_ts.py` on `live-main`; move exists only on `feature/reorg-yq-phase1` | Merge parked branch after path anchoring | Shim **not** on live; exists off-branch | Dirty/divergent checkouts; `YQ_CSV_PATH`/logo/port still laptop-shaped |
| TKP | Phase 2 after path anchor of state JSON | Full root `tkp_ts.py`; no `apps/tkp` | Anchor state path, then move body | No shim | `__file__` state anchor; OneDrive workbook; dirty deployed file |
| TCP | Phase 3 move v2 + exclusive state modules | Full root `tcp_ts_v2.py` + `tcp_state`/`tcp_runtime_state` | Move after TKP | No shim | AppData already portable; workbook default still OneDrive |
| AGM | Phase 4 move algominds + `mp_ts` body | Full `Momentum Pacer/mp_ts.py` + root `algominds_*` | Explicit `MP_DATA_DIR`, then move | No shim | Data/`__file__` anchors; bat cd contract |
| Shared | Phase 5 last | No `shared/`, `config/`, or `services/` on `live-main` | After all app moves | N/A | Blast radius across TKP/TCP/AGM + Gold_Maker/tsgen |

Target directories on `live-main`: **`apps/`, `shared/`, `config/`, `services/` do not exist.**

Legacy entrypoints still required: `tkp_ts.py`, `tcp_ts_v2.py`, `yq_ts.py`, `Momentum Pacer/mp_ts.py`, all root `reboot_*.bat/.ps1` names, root env files, `assets/`.

Tests still import root module names (`tkp_ts`, `tcp_ts_v2`, `yq_ts`, `mp_ts`).

**Do not repeat completed moves:** none are completed on the deployed branch. Do not re-merge reorg-prep/repo-map (already ancestors).

---

## 6. Remaining hard-coded-path blockers

Delta only (not a full reinventoried path scan):

| Path dependency | Historic status | Current status | Active consumer | VPS blocker | Recommended config key |
|---|---|---|---|---|---|
| TKP workbook under protected Documents | Flagged critical | **Still hard-coded** `tkp_ts.py:244-246` | TKP boot seed | **Yes — Critical** | `TKP_WORKBOOK_PATH` |
| Shared OneDrive logo PNG | Flagged | Still hard-coded TKP/TCP | TKP/TCP startup | Yes — High | `TEARSHEET_LOGO_PATH` |
| Y&Q logo `Pictures\yq.png` | Flagged | Still hard-coded | Y&Q startup | Yes — Medium | `YQ_LOGO_PATH` |
| TKP state via `dirname(__file__)` | R1 | **Unresolved** | TKP R/W ledger | **Yes — Critical** if body moves or checkout relocates | `TKP_STATE_PATH` / repo-root anchor |
| AGM manual JSON via `mp_ts` dir | R3 | Unresolved | AGM R/W continuation | Yes — High | `AGM_MANUAL_ROWS_PATH` |
| AGM fee workbook / balances / benchmarks | R3 | Still under `Momentum Pacer/` relative paths | AGM | Yes — High | `AGM_DATA_DIR` / `MP_DATA_DIR` |
| TCP workbook OneDrive default | Env-able already | Default still OneDrive; prod uses AppData state | TCP fallback | Medium (prod state OK) | `TCP_V2_WORKBOOK_PATH` (exists) |
| TCP AppData state/benchmark | Documented | Still correct via `.tcp_production.env` | TCP prod | Low for Windows VPS | Keep `TCP_V2_STATE_*` |
| Y&Q CSV | R2 | **Partially fixed** via `YQ_CSV_PATH` + root fallback | Y&Q read-only | Medium | Keep/extend `YQ_CSV_PATH` → `E:\H&C\data\yq\` |
| Dirty-root absolute guard path | New | Hard-coded laptop path in all prod PS1/BAT | Launchers | Yes for VPS layout | `HC_DIRTY_ROOT` / deploy root config |
| Manager/HomePage `BASE_DIR` | Out-of-repo | Still points at laptop Coding Projects paths | Fleet controls | Yes | Fleet runtime JSON / service manifest |
| Glenn BE dirty-root path | New drift | Active uvicorn from root uploader | Local Glenn | Yes — identity risk | Canonical launcher → live-deploy-main |
| Ingest audit JSONL at worktree | New post-merge | Written beside apps | TKP/TCP/AGM ingest | Medium | `GLENN_UPLOADER_INGEST_AUDIT_DIR` |

Fixed since audit (do not re-fix):

- Missing ingest routes → merged.
- AGM manual rows absent → implemented.
- Y&Q CSV only beside module → env + root fallback.
- Unprotected dirty-root launches → refused.

---

## 7. Current mutable-data ownership

| Data item | Current path | Readers | Writers | Production/sandbox identity | Backup status | Remaining migration action |
|---|---|---|---|---|---|---|
| TKP ledger | `{live-deploy-main}/daily_returns_secret_state.json` (`__file__`) | TKP UI, ingest, health/table | Admin UI, ingest | Production (local) | Ad-hoc / untracked | Move to `E:\H&C\data\tkp\` via config; never git-mv |
| TKP Excel seed | Protected Documents path | TKP boot (row-capped) | None in-app | Production source dependency | Not in handoff | Kevin supplies via `C:\AI_HANDOFF`; relocate |
| TCP ledger | `%LOCALAPPDATA%\HughesCompany\TCP\state\...` | TCP runtime | Atomic `tcp_state` | Production (AppData) | Backup sibling JSON | Point env to `E:\H&C\data\tcp\` |
| TCP workbook | OneDrive default / env override | Fallback seed | None | Source | Unknown on VPS | Confirm `TCP_V2_WORKBOOK_PATH` |
| AGM TradeStation CSV | `Momentum Pacer/data/daily_balances/balances_210TGG51_20OCT2025_07JUL2026.csv` | `algominds_daily_balances` | **Never** | Production pinned history | File in tree | Copy to data disk; keep read-only |
| AGM manual JSON | `Momentum Pacer/momentum_pacer_manual_daily_rows.json` | AGM merge/UI | Admin + ingest | Production continuation | Ad-hoc | Config path → `E:\H&C\data\agm\` |
| AGM fee workbook | `Momentum Pacer/Momentum Fee Calculation.xlsx` | AGM fee/reference | None in-app | Production source | Symlink risk noted | Dereference copy to data disk |
| Y&Q monthly CSV | Main root `yq.csv` via `YQ_CSV_PATH` | Y&Q only | None | Production input; stale intentional | Untracked | `E:\H&C\data\yq\`; do not fabricate periods |
| Uploader SQLite | Fly `/data/uploader_sandbox.db` (shared) | Uploader API | Startup schema, rows, export batches/audit, exclusions, rollback, backfill | **Shared prod+sandbox hostname** | Local backups only; remote inventory unresolved | Separate prod DB/volume before trusting hostname split |
| Ingest audit JSONL | Worktree / Momentum Pacer | Ops | Ingest framework | Production audit | Gitignored | Relocate to `E:\H&C\logs\ingest\` |
| Benchmark caches | TCP AppData/`_runtime`; AGM CSV caches | Apps | Cache writers | Regenerable | Optional | `E:\H&C\data\<app>\cache\` |

**AGM precedence (confirmed, protected):**

```text
pinned TradeStation CSV
→ manual daily JSON continuation (admin / Glenn ingest)
→ accounting, fee, monthly, chart and website calculations
```

Do not rewrite protected continuation values (2026-07-22…07-24, July 29 NLV). Do not open financial workbooks in apps that could save them.

---

## 8. Startup portability delta

| Service | Current local startup issue | Already solved? | Remaining VPS requirement | Pre-provisioning or post-provisioning |
|---|---|---|---|---|
| Fleet master | Startup CMD enabled but live master often terminal-owned; idle wrappers | Partially | Replace with NSSM auto-start/recovery | Pre: design manifest; Post: NSSM register |
| TKP/TCP/AGM public | Live-worktree launchers + dirty-root refuse | Mostly | NSSM service per app; env from Key Vault; fixed WD | Post-provisioning |
| Y&Q | PS1 prefers `.venv310` but historic bare-python risk; no `/healthz` | Partially | Force `.venv310`; add health/identity endpoint; config CSV/logo | Pre: health/path; Post: NSSM |
| Staff 832x | Manual-only | Intentional locally | NSSM staff services + Cloudflare Access | Post |
| Dashboard | `0.0.0.0:8006`, kill/reboot powers; possible stale process vs disk | No | Bind loopback; optional service | Post |
| Glenn | FE live-deploy / BE dirty-root; launcher unmerged on stale branch | No | Canonical launcher pinned to live tip; uploader stays on Fly (not VM service) | Pre |
| Selective stop/start | Improved aliases/grouping; unsafe port-kill matching + parent respawn | Partially | Prefer NSSM restart over port-kill; fix listener-only PID match | Pre (code) / Post (ops) |
| cloudflared | Running; ingress cloud-managed | Same | Parallel Azure tunnel; export mapping still missing from handoff | Blocked on input; Post for connector |
| Identity/health | `/healthz` on TKP/TCP/AGM; Y&Q `/` only; Glenn `/health` discloses mode flags | Partial | Standardize health + safe git/env identity fields | Pre |

---

## 9. Uploader environment-separation delta

Latest local deployment observation: **2026-07-30**. No live Fly/DNS mutation was performed in this audit.

| Surface | Status | Evidence summary |
|---|---|---|
| Application | **Confirmed shared** | Both hostnames → `glenn-uploader-sandbox` |
| Database | **Confirmed shared** | `/data/uploader_sandbox.db` |
| Volume | **Confirmed shared** | `uploader_data` @ `/data` |
| Secrets | **Confirmed shared scope; values unresolved** | One app secret set; no hostname split |
| Environment variables | **Confirmed shared** | Sandbox-labeled app serving both hostnames |
| Export permissions | **Confirmed shared / unsafe for hostname isolation** | Captured health: production target + real writes enabled while `APP_ENV=sandbox` |
| Downstream target | **Confirmed shared production-target capability; URL identities unresolved** | Code POSTs to configured ingest URLs; exact destinations not re-probed |
| Cloudflare route | **Confirmed shared origin path (Jul 30); current DNS unresolved** | DNS-only to same Fly IPs historically |
| Hostname labels | **Confirmed isolated labels only** | Names differ; workload did not |

### Separation plan only (do not execute)

1. Freeze config changes; treat shared DB as current source until ownership decided.
2. Decide whether shared DB seeds production or remains sandbox history.
3. Provision new `glenn-uploader-prod` app + dedicated volume; **never attach** the sandbox volume to prod.
4. Build distinct sandbox vs production artifacts/labels.
5. Independent secret sets; sandbox fail-closed (no production ingest URLs/token; dry-run; auth required for mutations).
6. Approved write freeze → Fly volume snapshot + SQLite-consistent backup (hashes, counts, export flags, exclusions).
7. Restore a **copy** into prod DB; validate on temporary hostname with exports disabled.
8. Dry-run downstream classification without marking rows exported from dry-run.
9. Move `uploader.hcresearch.ltd` only after identity/auth validation.
10. Enable real production export under separate approval.
11. Merge a Glenn launcher that cds to `live-deploy-main`, verifies expected commit, refuses dirty/stale trees.

Must prevent: duplicate exports; loss of exported flags; sandbox writes into production; production writes from sandbox hostname; re-export of historic rows.

---

## 10. Remaining move matrix

Only moves **not** already completed on `live-main`:

| Current path | Proposed path | Current consumers | Shim required | Risk | Tests | Rollback | Timing |
|---|---|---|---|---|---|---|---|
| Path defaults in TKP/TCP/AGM/Y&Q (state, CSV, workbooks, logos, audits) | Config/env keys defaulting to **current** paths | All four apps + launchers | No code move | Medium — mis-default could empty ledgers | Per-app golden + G-TKP-2 style row-count gates | Revert config commit; restart bats | **Before VPS provisioning** |
| Fleet/service definitions (Manager + HomePage duplicates) | Single service manifest consumed by both | Manager, HomePage, future NSSM | Compatibility read of old maps | Medium — control-plane drift | Dashboard start/kill dry checks without killing prod | Revert manifest commit | Before VPS provisioning |
| Glenn launcher (unmerged stale branch) | Tracked launcher under live tip / Manager pointing at live-deploy-main | Local Glenn FE/BE | Keep root bat name if contracted | High if wrong checkout | FE+BE health + commit identity | Revert launcher; stop wrong processes manually | Before VPS provisioning |
| `yq_ts.py` body | `apps/yq/yq_app.py` + root shim | `reboot_yq_ts.*`, tests | **Yes** | Medium after path config | G-YQ | `git revert` phase commit | During private VPS sandbox preparation |
| `tkp_ts.py` body | `apps/tkp/tkp_app.py` + root shim | bats, tests, ingest | Yes | **Critical** without prior state anchor | G-TKP + 838+ row gate | revert + state restore | After private parity validation |
| `tcp_ts_v2.py` + `tcp_state`/`tcp_runtime_state` | `apps/tcp/` + shims | bats, scripts, tests | Yes | High | G-TCP replay | revert | After private parity validation |
| `algominds_*` + `mp_ts` body | `apps/agm/` + `Momentum Pacer/mp_ts.py` shim | bats, tests, HomePage folder ref | Yes (esp. `Momentum Pacer/mp_ts.py`) | High | G-AGM | revert | After private parity validation |
| Production state files | `E:\H&C\data\<app>\` | Apps via config | N/A (data copy, not git mv) | Critical if path wrong | Hash/count/date vs baseline | Keep laptop authoritative | During controlled production cutover |
| Shared `tearsheet_*` / tri-app `tcp_*` | `shared/*` + `config/` | TKP/TCP/AGM (+ Gold_Maker/tsgen for disclosure) | Permanent root shims | High blast radius | Full gate suite | reverse-order revert | After cutover |

**Not recommended now:** speculative shared-module extraction before app moves and path config. Dependency graph still shows tri-app cycles (`tcp_dashboard⇄tcp_drawdown`, `tcp_config⇄tearsheet_runtime_mode`).

---

## 11. Testing and rollback gaps

| Gap | Status | Needed before next lane lands |
|---|---|---|
| Golden captures vs current tip | Jul 26 baseline exists; tip advanced to `3cfda4f` | Refresh non-destructive goldens (esp. TCP 50k copy, AGM continuity, Y&Q label) |
| G-TKP-2 empty-ledger detector | Documented; still essential | Must run after any TKP path/move change |
| Y&Q health gate | Still `/` only | Add `/healthz` or identity endpoint in path/health lane |
| Deployed dirty `tkp_ts.py` vs commit | Unreconciled | Diff/quarantine before any TKP move |
| Uploader remote backup/restore drill | Not evidenced | Required before hostname cutover |
| Selective kill reliability | Known false-success / respawn risks | Do not rely on it for VPS; use NSSM |
| Rollback rehearsal | Documented in risks doc | Still valid: revert rename commits; restore timestamped state copies outside repo |

---

## 12. Risk-ranked unresolved work

| Rank | Item | Severity | Why it blocks portability |
|---|---|---|---|
| 1 | TKP/AGM/Y&Q mutable paths not config-first; TKP `__file__` state anchor | Critical | Checkout relocation or body move can empty/mis-point ledgers |
| 2 | TKP protected-folder workbook dependency + empty AI_HANDOFF | Critical | File will not exist on VPS; handoff incomplete |
| 3 | Uploader prod/sandbox still one Fly app/DB/volume (as of Jul 30) | Critical | Sandbox hostname can share production export capability |
| 4 | Dirty deployed `tkp_ts.py` + root/`live-main` divergence + admin-owned `.git` | High | Ambiguous production identity / blocked git ops |
| 5 | Glenn split checkout + unmerged/stale launcher | High | Wrong code can serve API vs UI |
| 6 | No NSSM/service-account startup model yet | High | Reboot leaves fleet down; Startup-folder ownership incomplete |
| 7 | Hard-coded logos / laptop absolute launcher guards / Manager paths | High | Windows VPS layout `E:\H&C\` will not match |
| 8 | Missing tunnel/DNS/SiteGround handoff inputs | High | Blocks ingress/homepage/cutover gates, not private VM build |
| 9 | Dashboard `0.0.0.0` + public `/admin` surfaces | Medium-High | Must lock down before DNS cutover |
| 10 | Y&Q still weak health/debug posture | Medium | Ops blindness on VPS |
| 11 | Unmerged Y&Q reorg branch temptation | Medium | Premature move before path config |
| 12 | Shared extraction | Low now | Correctly deferred |

---

## 13. Recommended next implementation lane

### Lane name

**Central path configuration with current defaults retained**

### Why this lane (evidence-based)

- Y&Q body move has **not** landed on `live-main`; choosing Y&Q move next would resurrect R2 without finishing path portability.
- TCP already has the right pattern (`TCP_V2_*` path env). TKP/AGM/Y&Q need the same treatment **before** any `git mv`.
- Azure build spec requires state on `E:\H&C\data\`, not inside the git worktree.
- Dirty deployed checkout and Glenn split-brain make structural moves unsafe this week.

### In scope

1. Add env/config keys for:
   - `TKP_STATE_PATH`, `TKP_WORKBOOK_PATH`
   - `AGM_DATA_DIR` / manual-rows / fee workbook / balances overrides
   - `YQ_CSV_PATH` (already), `YQ_LOGO_PATH`
   - `TEARSHEET_LOGO_PATH`
   - ingest audit directory
2. Defaults **must equal current laptop paths** so behavior is bit-identical until VPS env files differ.
3. Add/standardize safe health/identity fields (commit, checkout root, resolved data paths — no secrets).
4. Document the config keys into `E:\H&C\config` / secrets rendering plan (docs only in this lane if code lands separately).
5. Keep ports, routes, launcher names, calculations, and state contents unchanged.

### Out of scope

- Merging `feature/reorg-yq-phase1`
- Shared-module extraction
- Financial calculation changes
- Uploader exports / Fly / Cloudflare / DNS / Azure provisioning
- Cleaning dirty worktrees
- Opening protected Documents folder

### Immediate prerequisites before coding the lane

- Quarantine/reconcile dirty `live-deploy-main\tkp_ts.py` vs `3cfda4f` (operator decision; no silent overwrite).
- Confirm Kevin will supply TKP workbook via `C:\AI_HANDOFF` (still missing).

---

## 14. Explicit items that do not need to be rediscovered again

- App dependency closures for TKP/TCP/AGM/Y&Q (dependency-map).
- Frozen external contracts: bat names, ports 8301–8304 / 8321–8322–8324, routes, Manager/HomePage bat consumers.
- File classification classes and do-not-move production data list.
- Historic migration sequence Y&Q → TKP → TCP → AGM → shared.
- Regression gate framework and rollback recipe shape.
- Ratified Azure Windows Server 2022 D4s v5 + IIS/ARR + NSSM + Tunnel architecture.
- Local startup chain shape: Startup CMD → Manager PS1 → `launch_all_services.py` → `service_config` / fleet JSON → reboot scripts.
- Protected financial invariants (StoneX/Plus500 roles; TCP $50k tranche; Y&Q stale intentional; AGM CSV→manual→calc; no uploader destructive ops in audit lanes).
- That Ubuntu/Nginx/systemd is not the target.
- That ~48 worktrees exist and only `live-deploy-main` is production.
- That AI_HANDOFF lacked the four migration inputs as of Jul 26 verification.

---

## Lane status summary

| Lane | Status | Completion % | Blockers | Current commit | Next action |
|---|---|---:|---|---|---|
| Current-state delta audit | Complete | 100% | None for reporting | `live-main` @ `3cfda4f` | Begin path-config implementation lane |
| Path configuration (recommended) | Not started | 0% | Dirty deployed `tkp_ts.py`; missing TKP workbook handoff | `3cfda4f` | Spec+implement env defaults == current paths |
| Y&Q body move behind shim | Parked off-branch | ~10% (branch exists) | Path config incomplete; not merged | `a8bc22d` on `feature/reorg-yq-phase1` | Merge only after path lane + clean live tip |
| TKP/TCP/AGM moves | Not started | 0% | Path anchoring; dirty identity | `3cfda4f` | After Y&Q move proves shim pattern on live |
| Shared extraction | Not started | 0% | App moves incomplete | `3cfda4f` | After cutover |
| NSSM/VPS service model | Designed only | ~20% (spec) | Path config; clean deploy checkout; secrets layout | Azure spec ratified | After path lane; during private VM prep |
| Uploader prod/sandbox separation | Runbook only | ~15% | Shared Fly app as of Jul 30; remote state unresolved | runbook on `live-main` | Execute separation plan under freeze |
| Azure provision/cutover | Blocked | ~10% (architecture ratified) | Region; AI_HANDOFF inputs; path portability | Spec 2026-07-26 | Gate 2.0 closure in parallel with path lane |

### Lane Progress

* **Done:** Prior reorganization docs; ratified Windows VPS architecture; live tip advanced through TCP 50k / Y&Q source-date / AGM continuity; ingest merged; live-worktree launcher guards; this delta reconciliation.
* **Working:** None (read-only phase complete).
* **Remaining:** Path/config abstraction; dirty-deploy reconciliation; Glenn canonical launcher; uploader separation execution; NSSM private deploy; handoff inputs; cutover gates.
* **Completion:** Structural reorg toward VPS portability ≈ **25%**. Architecture and audits ≈ **70%**. Safe cutover readiness ≈ **15%**.
* **Next best action:** Implement central path configuration with defaults pinned to current laptop paths; do not merge Y&Q move or provision Azure in the same lane.

---

*End of delta report. Read-only. No production code, data, services, Git, Fly, Cloudflare, DNS, or Azure changes were made.*
