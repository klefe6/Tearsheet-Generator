# Glenn Daily Uploader — Backend

Backend-only FastAPI service that lets Glenn enter daily values for the
**TKP / TCP / AGM / Y&Q** programs. It is completely self-contained: it does
**not** import or modify any existing tearsheet app, and this build **never**
calls the four public websites.

> Status: v1 kickstart. Sandbox-first, export is **dry-run only**, no deployment.

---

## Stack

- Python 3.10+
- FastAPI + Pydantic (v2) + `pydantic-settings`
- SQLite via the standard-library `sqlite3` (no ORM — minimal deps)

## Layout

```
uploader/backend/
├─ app/
│  ├─ config.py        # env-driven Settings (APP_ENV, EXPORT_ENABLED, ...)
│  ├─ programs.py      # program registry + field rules + row serializer
│  ├─ validation.py    # per-program validation + rejection rules
│  ├─ db.py            # SQLite storage (daily_rows, audit_events, export_batches)
│  ├─ performance.py   # /api/performance builder (combined + program modes)
│  ├─ benchmarks.py    # deterministic local SPX/NDX/BTC fixture (no external calls)
│  ├─ security.py      # bearer-token auth dependency
│  └─ main.py          # FastAPI app + routes (create_app factory)
├─ tests/              # pytest suite
├─ requirements.txt / requirements-dev.txt / pyproject.toml
├─ .env.example        # safe placeholders
└─ README.md
```

---

## Run locally

From `uploader/backend/`:

```bash
# 1) create an isolated venv (Python 3.10+; 3.13 is fine)
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Git Bash / macOS / Linux:
# source .venv/bin/activate

# 2) install runtime deps
pip install -r requirements.txt

# 3) configure (optional — sandbox defaults work out of the box)
cp .env.example .env      # then edit if needed

# 4) run (standard local dev port — see docs/LOCAL_DEV.md)
uvicorn app.main:app --reload --host 127.0.0.1 --port 8091
```

Or use the helper script:

```powershell
.\start_dev.ps1
```

Then open:

- Health:  http://127.0.0.1:8091/health
- Swagger: http://127.0.0.1:8091/docs

> Note: this backend does **not** bind any of the protected tearsheet ports
> (8301/8302/8303/8304 etc.). Standard local dev uses **8091** (backend) and
> **5173** (frontend). Avoid :8090 unless you have verified the SQLite schema;
> see `docs/LOCAL_DEV.md` for DB reset instructions.

### Future public URLs

| Environment | Frontend | Backend API |
| ----------- | -------- | ----------- |
| Sandbox     | `https://uploader-sandbox.hcresearch.ltd` | `https://uploader-sandbox.hcresearch.ltd/api` |
| Production  | `https://uploader.hcresearch.ltd` | `https://uploader.hcresearch.ltd/api` |

Local dev keeps `http://localhost:5173` (frontend) and `http://localhost:8091` (backend).
Configure `CORS_ALLOW_ORIGINS` in `.env` to include both local and public frontend
origins when deploying (see `.env.example`).

**Local DB reset** (stale schema on an old port/DB file): `python scripts/reset_local_db.py --confirm`
— see `docs/LOCAL_DEV.md`.

---

## Configuration

All config is environment-driven (loaded from `.env` if present). See
`.env.example` for the authoritative list.

| Variable             | Default                         | Meaning                                                        |
| -------------------- | ------------------------------- | -------------------------------------------------------------- |
| `APP_ENV`            | `sandbox`                       | `sandbox` (relaxed auth, dry-run) or `production`              |
| `EXPORT_ENABLED`     | `false`                         | Master switch for real exports (still never called in v1)      |
| `DATABASE_PATH`      | `data/uploader_sandbox.db`      | Local SQLite file                                              |
| `ADMIN_API_TOKEN`    | *(empty)*                       | Bearer token required for mutations in production              |
| `CORS_ALLOW_ORIGINS` | local dev + `uploader-*.hcresearch.ltd` | Comma-separated allowed frontend origins (see `.env.example`) |
| `EXPORT_URL_{TKP,TCP,AGM,YQ}` | *(empty)*              | **Future** export targets — surfaced in preview, never called  |
| `EXPORT_DOWNSTREAM_ENABLED` | `false`           | Master switch for downstream TKP/TCP/AGM export. `false` = `/api/export/all` is unchanged from before this feature existed |
| `EXPORT_DRY_RUN`     | `true`                          | Even with the switch on, compute + report only; write nothing |
| `EXPORT_TARGET_ENV`  | `sandbox`                       | `sandbox` (local files this backend owns) or `production` (not implemented — always fails) |
| `EXPORT_INCLUDE_YQ`  | `false`                         | Forward-compatible only; Y&Q has no destination yet regardless |
| `DOWNSTREAM_SANDBOX_DIR` | `data/downstream_sandbox`  | Where sandbox destination files are written |
| `DOWNSTREAM_API_TOKEN` | *(empty)*                     | Token for a future real production downstream call (not used yet) |

See `docs/downstream_export_contract.md` for the full downstream export contract.

---

## Auth behavior (explicit)

Auth applies only to **mutations** (`POST /api/rows/*`, `DELETE /api/rows/*/last`,
`POST /api/export/all`). All `GET` endpoints are always open.

- **Sandbox (`APP_ENV=sandbox`)** — auth is **intentionally relaxed** for local
  dev. Mutations are allowed **without** a token. If a token is supplied it is
  recorded on the audit actor, otherwise the actor is `sandbox`.
- **Production (`APP_ENV=production`)** — mutations **require** a valid token via
  either header:
  - `Authorization: Bearer <ADMIN_API_TOKEN>`
  - `X-API-Token: <ADMIN_API_TOKEN>`

  If `ADMIN_API_TOKEN` is not configured, mutations **fail closed** (`503`) —
  the service never falls open in production.

---

## Data model

Programs: `TKP`, `TCP`, `AGM`, `YQ` (Y&Q).

| Program | Fields                                                      |
| ------- | ---------------------------------------------------------- |
| TKP     | `date`, `stonex_nlv`, `plus500_nlv`, `cash_transfer`       |
| TCP     | `date`, `stonex_nlv`, `cash_transfer`                      |
| AGM     | `date`, `tradestation_nlv`, `cash_transfer`, `fee`         |
| YQ      | `date`, `stonex_nlv`, `cash_transfer`                      |

Validation rules:

- `date` required, ISO `YYYY-MM-DD`.
- NLV fields required and numeric.
- `cash_transfer` numeric, defaults to `0` when blank.
- `fee` exists **only** for AGM; rejected for TKP/TCP/YQ.
- `plus500_nlv` rejected for non-TKP.
- `tradestation_nlv` rejected for non-AGM.
- Idempotent **upsert by (program, date)** — re-posting a date updates in place.
- Every create/update/delete/export is written to the **audit trail**.

### Storage (SQLite)

- `daily_rows` — one row per `(program, date)` with a `UNIQUE(program, date)`
  constraint; wide table (nullable per-program value columns); an `exported`
  flag reset to `0` on every write so changes re-appear in the export preview.
- `audit_events` — append-only log (`ts, action, program, date, detail, actor`).
- `export_batches` — a saved JSON snapshot of each export preview (dry-run record).

---

## API endpoints

| Method & path                 | Auth (prod) | Description                                             |
| ----------------------------- | ----------- | ------------------------------------------------------ |
| `GET /health`                 | open        | `status`, `app_env`, `export_enabled`, `version`       |
| `GET /api/programs`           | open        | Program + field metadata for the frontend              |
| `GET /api/performance`        | open        | Chart-ready $100k performance series — see below       |
| `GET /api/rows/{program}?limit=7` | open    | Last N rows for a program (newest first)               |
| `POST /api/rows/{program}`    | **token**   | Validate + upsert one row by `(program, date)`         |
| `DELETE /api/rows/{program}/last` | **token** | Delete the most recent row; audited                  |
| `POST /api/export/all`        | **token**   | Dry-run preview of all unexported rows; audited        |
| `GET /api/audit?limit=50`     | open        | Recent audit events                                    |

### Performance (`GET /api/performance`)

Computed fresh from `daily_rows` on every request — no caching, so it reflects
the latest add/delete/export immediately.

Query params:

| Param         | Values                          | Notes                                              |
| ------------- | -------------------------------- | --------------------------------------------------- |
| `mode`        | `combined` (default) \| `program` |                                                     |
| `program`     | `TKP` \| `TCP` \| `AGM` \| `YQ`   | required when `mode=program` (else `422`)          |
| `benchmarks`  | e.g. `SPX,NDX,BTC`                | optional, `mode=program` only; ignored in combined |

**Combined mode** — one series per program (TKP/TCP/AGM/YQ) only, **no**
SPX/NDX/BTC. X-axis is each program's own trading-day index (`x: 0, 1, 2, ...`
— the frontend labels these "Day N"), not a shared calendar, so a program with
fewer rows simply ends earlier.

**Program mode** — the selected program's own series, X-axis = real ISO
dates, optionally overlaid with SPX/NDX/BTC benchmarks **rebased to $100,000
as of the program's first available date**. If the benchmark has no data on
that exact date, the first available point on/after it is used instead and a
warning is added.

Response shape:

```jsonc
{
  "mode": "combined" | "program",
  "x_axis": "trading_day" | "date",
  "base_value": 100000,
  "program": null | "TKP" | "TCP" | "AGM" | "YQ",
  "benchmarks": [],              // resolved symbols; always [] in combined mode
  "series": [                    // legend/metadata, one entry per line
    {"key": "TKP", "label": "TKP", "kind": "program", "point_count": 12}
  ],
  "points": {                    // actual data, keyed by series key
    "TKP": [{"x": 0, "y": 100000.0}, {"x": 1, "y": 100230.5}]
  },
  "last_updated_at": "2026-07-09T20:31:00+00:00",
  "warnings": []                 // missing/sparse-data notes; never crashes
}
```

Accounting rules:

- Program NLV per row (`app/programs.py::program_nlv`): TKP = StoneX + Plus500,
  TCP = StoneX, AGM = TradeStation, YQ = StoneX.
- **AGM `fee` is intentionally excluded** from performance — it's not yet
  confirmed whether `fee` is already netted out of `tradestation_nlv` or
  billed separately, so per "don't silently mix it in", only
  `tradestation_nlv` drives AGM's series today. Revisit once confirmed.
- Cash transfers are neutralized so deposits/withdrawals never appear as
  performance: `daily_return = (ending_nlv - cash_transfer) / prior_ending_nlv - 1`,
  compounded onto the $100,000 base. A series' first point is always exactly
  $100,000 regardless of that day's own transfer (there's no "prior" yet).
- Benchmark data (`app/benchmarks.py`) is a **deterministic local fixture**
  (no external calls) — real values are keyed off the calendar date via a
  fixed formula, so tests never depend on wall-clock time or network access.
  Swap it for real ingestion later behind the same two functions.

### Export safety

`POST /api/export/all` **never** calls the TKP/TCP/AGM/Y&Q websites in this build.

- Sandbox → always `dry_run: true`.
- Production → `dry_run: true` unless `EXPORT_ENABLED=true`.
- Even when `EXPORT_ENABLED=true`, external transport is **not implemented**, so
  `external_calls_made` is always `0`, `transport_implemented` is `false`, and no
  row is marked exported (no data loss).

---

## Tests

```bash
pip install -r requirements-dev.txt
pytest            # from uploader/backend/
```

Covered: health, program metadata, per-program field acceptance
(TKP StoneX+Plus500 / TCP StoneX / AGM TradeStation+Fee / YQ StoneX), the three
rejection rules (Fee non-AGM, Plus500 non-TKP, TradeStation non-AGM), upsert
idempotency, delete-last, export dry-run-by-default (and safe-when-enabled),
sandbox/production auth, and `/api/performance` (combined trading-day index,
program-mode real dates, benchmark rebasing + missing-data fallback, cash-transfer
neutralization, AGM fee exclusion, empty-data warnings, refresh-after-mutation).

---

## Not in this build (deliberately)

- No frontend UI.
- No real export transport to the four websites.
- No deployment, no service restarts, no production data.
- No changes to any existing tearsheet app.
