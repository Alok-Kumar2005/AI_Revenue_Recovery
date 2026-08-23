from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.database import ping_db
from backend.logger import logging

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

#  CORS (update origins for production)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#  Lifespan events

@app.on_event("startup")
async def on_startup() -> None:
    """Verify DB connectivity on startup."""
    logger.info("Starting AI Revenue Recovery API...")
    if ping_db():
        logger.info("Neon PostgreSQL connection: OK")
    else:
        logger.error("Neon PostgreSQL connection: FAILED — check .env credentials")


#  Root health check

@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": "AI Revenue Recovery API", "version": "0.1.0"}


@app.get("/health", tags=["health"])
async def health():
    db_ok = ping_db()
    return {
        "status": "healthy" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
    }


# ── Routers (Phase 2 — uncomment as each router is built) ────────────────────
# from backend.routers import webhook, cases, metrics, interventions
# app.include_router(webhook.router,        prefix="/webhook",  tags=["webhook"])
# app.include_router(cases.router,          prefix="/api",      tags=["cases"])
# app.include_router(metrics.router,        prefix="/api",      tags=["metrics"])
# app.include_router(interventions.router,  prefix="/api",      tags=["interventions"])
