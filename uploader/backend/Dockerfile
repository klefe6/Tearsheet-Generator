# API-only image (no bundled UI). Prefer uploader/Dockerfile for public sandbox.
# Build context: backend/
#   docker build -t glenn-uploader-api backend

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=sandbox \
    DATABASE_PATH=/data/uploader_sandbox.db \
    BENCHMARK_CACHE_DIR=/data/benchmark_cache

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /data

EXPOSE 8091

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8091}"]
