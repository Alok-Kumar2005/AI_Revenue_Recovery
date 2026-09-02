#!/usr/bin/env bash

# Start a minimal health-check server returning JSON (prevents directory listing exposure)
python3 -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

class HealthCheck(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(b'{\"status\":\"ok\",\"service\":\"celery-worker\"}')

port = int(os.environ.get('PORT', 10000))
HTTPServer(('0.0.0.0', port), HealthCheck).serve_forever()
" &

# Ensure current directory is in Python path for backend imports
export PYTHONPATH=.

# Start Celery worker in foreground
celery -A backend.celery_app worker --loglevel=info --pool=solo --concurrency=1