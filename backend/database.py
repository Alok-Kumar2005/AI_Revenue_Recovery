"""
backend/database.py
───────────────────
SQLAlchemy 2.0 engine & session setup for Neon PostgreSQL.

Provides:
  - Sync engine + SessionLocal  (used in Celery tasks, Alembic migrations)
  - Async engine + AsyncSessionLocal  (used in FastAPI route handlers)
  - get_db()      → sync FastAPI dependency
  - get_async_db() → async FastAPI dependency
"""

from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings
from backend.logger import logging

logger = logging.getLogger(__name__)

sync_engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,          
    pool_size=5,
    max_overflow=10,
    connect_args={
        "sslmode": "require",    
        "connect_timeout": 10,
    },
    echo=False,                  
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    bind=sync_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    connect_args={
        "ssl": "require",        # asyncpg uses 'ssl' not 'sslmode'
        "command_timeout": 10,
    },
    echo=False,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

def get_db() -> Generator[Session, None, None]:
    """Sync database dependency — for use with non-async route handlers."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database dependency — for use with async route handlers."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def sync_session() -> Generator[Session, None, None]:
    """Context-manager wrapper around SessionLocal."""
    with SessionLocal() as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


@asynccontextmanager
async def async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context-manager wrapper around AsyncSessionLocal."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def ping_db() -> bool:
    """Execute SELECT 1 on the sync engine. Returns True on success."""
    try:
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database ping successful.")
        return True
    except Exception as exc:
        logger.error("Database ping failed: %s", exc)
        return False
