"""
backend/main.py
───────────────
FastAPI application entry point for AI Revenue Recovery.

Routes:
  GET  /                      → health check
  GET  /health                → detailed health check (DB ping)
  POST /webhook/razorpay      → Razorpay event ingestion
  GET  /api/metrics/summary   → live KPI aggregates
  GET  /api/cases             → paginated case list
  GET  /api/cases/{case_id}   → case detail + audit trail
  GET  /api/interventions     → recent interventions
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import ping_db
from backend.logger import logging
from backend.routers import chat, dashboard, webhook

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Revenue Recovery",
    description=(
        "Agent-powered platform that detects at-risk revenue and executes "
        "compliant recovery workflows across payment failures and checkout abandonment."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup() -> None:
    """Verify DB connectivity on startup."""
    logger.info("Starting AI Revenue Recovery API...")
    if ping_db():
        logger.info("Neon PostgreSQL connection: OK")
    else:
        logger.error("Neon PostgreSQL connection: FAILED — check .env credentials")

@app.get("/", tags=["health"])
async def root():
    return {"status": "active", "service": "AI Revenue Recovery API"}


@app.get("/health", tags=["health"])
async def health():
    db_ok = ping_db()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }


app.include_router(webhook.router,   prefix="/webhook", tags=["webhook"])
app.include_router(dashboard.router, prefix="/api",     tags=["dashboard"])
app.include_router(chat.router,      prefix="/api",     tags=["Chat"])
