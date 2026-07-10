# Local development — Glenn Daily Uploader backend

## Standard ports

| Service | Port | URL |
| ------- | ---- | --- |
| Backend (dev/smoke) | **8091** | `http://127.0.0.1:8091` |
| Frontend (Vite) | **5173** | `http://127.0.0.1:5173` |

> **Do not use :8090** unless you explicitly verify the database. An older
> process on :8090 often points at a **stale SQLite file** from an earlier
> schema (missing columns such as `tradestation_nlv` or `fee`). `/health`
> still returns 200, but `/api/rows/*` and `/api/performance` return 500.
> The backend now refuses to start when the on-disk schema is outdated.

## Database path

Configured via `DATABASE_PATH` (default: `data/uploader_sandbox.db`, relative
to the `backend/` working directory). The file is gitignored.

### Why :8091 worked but :8090 failed

- **:8091 smoke test** used `DATABASE_PATH=data/audit_smoke.db` — a **new file**
  with the current schema.
- **:8090** typically reuses `data/uploader_sandbox.db` created before column
  additions. `CREATE TABLE IF NOT EXISTS` does not add missing columns, so
  queries fail at runtime.

### Reset local DB (sandbox only)

Backs up the existing file, then creates a fresh schema:

```powershell
cd backend
python scripts/reset_local_db.py --confirm
```

Requires `APP_ENV=sandbox` (the default).

## Start backend

```powershell
cd backend
.\start_dev.ps1
```

Or manually:

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8091
```

## API smoke (no frontend)

With the backend running:

```powershell
.\scripts\smoke_api.ps1
```

## Frontend wiring

The Vite frontend calls `VITE_API_BASE_URL` (not `INTERNAL_API_ORIGIN`).
For local dev, create `frontend/.env.local`:

```
VITE_API_BASE_URL=http://127.0.0.1:8091/api
```

See `frontend/.env.local.example` in the frontend worktree.

## Export behavior (current build)

`POST /api/export/all` is wired and returns 200, but by default:

- **Does not push** to live TKP/TCP/AGM/Y&Q websites.
- Saves an export **preview** in SQLite (`export_batches` table).
- Optional downstream sandbox JSON (`data/downstream_sandbox/`) only when
  `EXPORT_DOWNSTREAM_ENABLED=true` and `EXPORT_DRY_RUN=false`.

Y&Q is always reported **skipped** (no destination).

## CORS

Default `CORS_ALLOW_ORIGINS` includes local Vite and:

- `https://uploader-sandbox.hcresearch.ltd`
- `https://uploader.hcresearch.ltd`

Override in `.env` when deploying.

## Docker / sandbox deploy readiness

See **`docs/SANDBOX_DEPLOY.md`** for the recommended **single-host** image
(`uploader/Dockerfile`): built Vite UI at `/`, API at `/api/*`, `/health`.

`backend/Dockerfile` remains API-only. Mount a volume at `/data` for SQLite
and benchmark cache persistence. Required env for public sandbox:

```
APP_ENV=sandbox
SERVE_FRONTEND=true
DATABASE_PATH=/data/uploader_sandbox.db
BENCHMARK_CACHE_DIR=/data/benchmark_cache
EXPORT_DOWNSTREAM_ENABLED=false
EXPORT_DRY_RUN=true
CORS_ALLOW_ORIGINS=https://uploader-sandbox.hcresearch.ltd,http://localhost:5173
```

Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Health check path: `/health`
