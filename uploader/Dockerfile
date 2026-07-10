# Glenn Daily Uploader — single-host sandbox image
# Serves built Vite UI at /, FastAPI at /api/*, /health for probes.
#
# Build (from repo root):
#   docker build -f uploader/Dockerfile -t glenn-uploader-sandbox uploader
#
# Run (mount persistent /data for SQLite + benchmark cache):
#   docker run --rm -p 8091:8091 -v glenn-uploader-data:/data glenn-uploader-sandbox

# --- Frontend build -------------------------------------------------------
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build:singlehost

# --- Backend runtime ------------------------------------------------------
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=sandbox \
    SERVE_FRONTEND=true \
    FRONTEND_STATIC_DIR=/app/static \
    DATABASE_PATH=/data/uploader_sandbox.db \
    BENCHMARK_CACHE_DIR=/data/benchmark_cache \
    DOWNSTREAM_SANDBOX_DIR=/data/downstream_sandbox \
    EXPORT_DOWNSTREAM_ENABLED=false \
    EXPORT_DRY_RUN=true \
    EXPORT_ENABLED=false

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY --from=frontend-build /frontend/dist ./static

RUN mkdir -p /data

EXPOSE 8091

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8091/health')"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8091}"]
