"""
backend/models.py
─────────────────
SQLAlchemy 2.0 DeclarativeBase and shared column mixins.

All ORM models across the project should import `Base` from here and inherit
from it. This file intentionally contains ONLY the base + shared mixins — no
table definitions yet (those come in Phase 2 when the agent layer is added).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    Project-wide SQLAlchemy declarative base.

    All ORM models must inherit from this class so that Alembic's
    autogenerate can discover them via ``Base.metadata``.
    """
    pass


# ── Shared column mixins ────────────────────────────────────────────────────


class UUIDPrimaryKeyMixin:
    """Adds a UUID primary key column (server-generated via gen_random_uuid)."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default="gen_random_uuid()",
        index=True,
    )


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
