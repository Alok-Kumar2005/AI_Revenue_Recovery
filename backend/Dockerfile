# ─── Backend Dockerfile ───────────────────────────────────────────────────────
# AI Revenue Recovery — FastAPI / Uvicorn container
#
# Build:  docker build -t ai-revenue-backend ./backend
# Run:    docker run --env-file .env -p 8000:8000 ai-revenue-backend
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# Metadata
LABEL maintainer="AI Revenue Recovery Team"
LABEL description="FastAPI backend for AI Revenue Recovery"

# Prevent .pyc files and enable stdout/stderr unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies required by psycopg2-binary
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the entire project (backend package + root-level files)
COPY . .

# Create a non-root user for security
RUN addgroup --system appgroup && \
    adduser  --system --ingroup appgroup appuser && \
    chown -R appuser:appgroup /app

USER appuser

# Expose the API port
EXPOSE 8000

# Health-check so Docker / Compose knows when the service is ready
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Start the ASGI server
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
