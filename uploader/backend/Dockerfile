# Glenn Daily Uploader — backend (sandbox / public API host)
# Build context: backend/   Start: uvicorn app.main:app --host 0.0.0.0 --port $PORT

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=sandbox \
    DATABASE_PATH=/data/uploader_sandbox.db

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /data

EXPOSE 8091

# Railway/Render set PORT; default 8091 for local docker run.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8091}"]
