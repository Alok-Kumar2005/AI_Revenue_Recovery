#!/usr/bin/env bash
set -e

# Render assigns a dynamic PORT environment variable; default to 8000 for local / container runs
PORT="${PORT:-8000}"

echo "Starting Celery worker in background (--pool=solo --concurrency=1)..."
celery -A backend.celery_app worker --loglevel=info --pool=solo --concurrency=1 &

echo "Starting Uvicorn server on port ${PORT} in foreground (1 worker)..."
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT}" --workers 1
