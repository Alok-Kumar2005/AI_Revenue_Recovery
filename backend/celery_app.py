"""
backend/celery_app.py
─────────────────────
Celery application configuration for AI Revenue Recovery.

Broker strategy:
  - If settings.REDIS_URL is set   → uses Redis as broker + result backend
  - Otherwise                       → task_always_eager=True (in-process sync)
    This allows the full pipeline to run in tests and local dev
    without a running Redis daemon.
"""

from celery import Celery

from backend.config import settings

# ── Broker selection ──────────────────────────────────────────────────────────

_redis_url = settings.REDIS_URL.strip()
_use_redis = bool(_redis_url and _redis_url.startswith(("redis://", "rediss://")))

if _use_redis:
    celery_app = Celery(
        "ai_revenue_recovery",
        broker=_redis_url,
        backend=_redis_url,
        include=["backend.tasks"],
    )
    celery_app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        broker_connection_retry_on_startup=True,
    )
else:
    # ── Eager (in-process) fallback — no Redis required ──────────────────────
    celery_app = Celery(
        "ai_revenue_recovery",
        include=["backend.tasks"],
    )
    celery_app.conf.update(
        task_always_eager=True,          # execute tasks synchronously in-process
        task_eager_propagates=True,      # propagate exceptions in eager mode
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
    )

__all__ = ["celery_app"]
