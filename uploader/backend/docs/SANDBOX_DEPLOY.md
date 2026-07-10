# Glenn Daily Uploader — public sandbox deploy (single-host Docker)

Recommended architecture: **one container** serves the built Vite UI at `/`, the
FastAPI API at `/api/*`, and `/health` for probes. **Vercel is not required.**

## Why single-host

| Concern | Single Docker | Vercel + separate backend |
| ------- | ------------- | ------------------------- |
| SQLite `/data` persistence | Native volume mount | Needs external DB or separate host |
| CORS | Same-origin (`/api`) — minimal | Cross-origin config required |
| DNS | One hostname | Frontend + API routing |
| Rollback | One image tag | Two deploy surfaces |
| Complexity | One Dockerfile | Two platforms + rewrites |

Local dev stays **split**: backend `:8091`, frontend Vite `:5173`.

## Build

From the `uploader/` directory:

```bash
docker build -t glenn-uploader-sandbox .
```

Frontend is built with `VITE_API_BASE_URL=/api` (see `frontend/.env.singlehost`).

## Run (sandbox)

```bash
docker run --rm -p 8091:8091 \
  -v glenn-uploader-data:/data \
  -e CORS_ALLOW_ORIGINS=https://uploader-sandbox.hcresearch.ltd,http://127.0.0.1:5173,http://localhost:5173 \
  glenn-uploader-sandbox
```

Or:

```bash
docker compose -f docker-compose.sandbox.yml up --build
```

Open `http://127.0.0.1:8091` — UI and API share the origin.

## Required sandbox environment

| Variable | Value |
| -------- | ----- |
| `APP_ENV` | `sandbox` |
| `SERVE_FRONTEND` | `true` |
| `DATABASE_PATH` | `/data/uploader_sandbox.db` |
| `BENCHMARK_CACHE_DIR` | `/data/benchmark_cache` |
| `DOWNSTREAM_SANDBOX_DIR` | `/data/downstream_sandbox` |
| `EXPORT_DOWNSTREAM_ENABLED` | `false` |
| `EXPORT_DRY_RUN` | `true` |
| `EXPORT_ENABLED` | `false` |
| `CORS_ALLOW_ORIGINS` | `https://uploader-sandbox.hcresearch.ltd,http://127.0.0.1:5173,http://localhost:5173` |

Mount a **persistent volume at `/data`** so SQLite and benchmark CSV caches
survive restarts.

## Public hostname

Point `uploader-sandbox.hcresearch.ltd` at the container host (Railway, Render,
Fly.io, VM, or Cloudflare Tunnel). No separate frontend host is needed.

Production (`uploader.hcresearch.ltd`) is **out of scope** for this document.

## Health check

`GET /health` → `{"status":"ok",...}`

## API-only image

`backend/Dockerfile` builds API without UI (`SERVE_FRONTEND=false` default).
Use `uploader/Dockerfile` for the public sandbox.
