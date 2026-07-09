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
│  ├─ performance.py   # deterministic mock $100k performance series
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

# 4) run
uvicorn app.main:app --reload --port 8090
```

Then open:

- Health:  http://127.0.0.1:8090/health
- Swagger: http://127.0.0.1:8090/docs

> Note: this backend does **not** bind any of the protected tearsheet ports
> (8301/8302/8303/8304 etc.). Pick a free port such as **8090**.

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
| `CORS_ALLOW_ORIGINS` | `localhost:3000,5173,127.:5173` | Comma-separated allowed frontend origins                       |
| `EXPORT_URL_{TKP,TCP,AGM,YQ}` | *(empty)*              | **Future** export targets — surfaced in preview, never called  |

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
| `GET /api/performance`        | open        | Normalized $100k series (TKP/TCP/AGM/YQ/SPX/NDX/BTC)    |
| `GET /api/rows/{program}?limit=7` | open    | Last N rows for a program (newest first)               |
| `POST /api/rows/{program}`    | **token**   | Validate + upsert one row by `(program, date)`         |
| `DELETE /api/rows/{program}/last` | **token** | Delete the most recent row; audited                  |
| `POST /api/export/all`        | **token**   | Dry-run preview of all unexported rows; audited        |
| `GET /api/audit?limit=50`     | open        | Recent audit events                                    |

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
idempotency, delete-last, export dry-run-by-default (and safe-when-enabled), and
sandbox/production auth.

---

## Not in this build (deliberately)

- No frontend UI.
- No real export transport to the four websites.
- No deployment, no service restarts, no production data.
- No changes to any existing tearsheet app.
