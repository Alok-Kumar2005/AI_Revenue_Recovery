#!/usr/bin/env bash

# Bind Python HTTP server to $PORT so Render passes health checks
python -m http.server ${PORT:-10000} &

# Ensure current directory is in Python path for backend imports
export PYTHONPATH=.

# Start Celery worker in foreground
celery -A backend.celery_app worker --loglevel=info --pool=solo --concurrency=1