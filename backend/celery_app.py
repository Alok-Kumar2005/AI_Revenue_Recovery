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


def _normalize_redis_url(url: str) -> str:
    """
    Append ssl_cert_reqs=CERT_NONE to a rediss:// URL if it is missing.
    Celery's Redis backend raises ValueError when this param is absent on TLS URLs.
    Upstash and other managed Redis providers use rediss:// (TLS) by default.
    """
    if not url.startswith("rediss://"):
        return url
    if "ssl_cert_reqs" in url:
        return url          # already present — leave untouched
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}ssl_cert_reqs=CERT_NONE"


# ── Broker selection ──────────────────────────────────────────────────────────

_raw_redis_url = settings.REDIS_URL.strip()
_use_redis = bool(
    _raw_redis_url and _raw_redis_url.startswith(("redis://", "rediss://"))
)
_redis_url = _normalize_redis_url(_raw_redis_url) if _use_redis else ""

if _use_redis:
    _is_tls = _redis_url.startswith("rediss://")
    _ssl_cfg = {"ssl_cert_reqs": None} if _is_tls else {}   # ssl.CERT_NONE == None

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
        # ── TLS settings required for rediss:// (Upstash / managed Redis) ──
        broker_use_ssl=_ssl_cfg if _is_tls else None,
        redis_backend_use_ssl=_ssl_cfg if _is_tls else None,
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
