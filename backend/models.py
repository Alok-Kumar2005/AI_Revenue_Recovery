"""
backend/models.py
─────────────────
SQLAlchemy 2.0 ORM models for AI Revenue Recovery.

Tables:
  customers         – customer identity + contact info
  revenue_cases     – each at-risk payment / abandoned checkout event
  interventions     – individual outreach attempt per case
  audit_logs        – immutable append-only AI decision trail
  recovery_metrics  – daily rollup stats (recovered ₹, success rate)
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    """
    Project-wide SQLAlchemy declarative base.
    All ORM models inherit from this so Alembic autogenerate can discover them.
    """
    pass

class UUIDPrimaryKeyMixin:
    """UUID primary key, Python-side default + PostgreSQL server default."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
        index=True,
    )


class TimestampMixin:
    """Automatic created_at / updated_at columns (timezone-aware)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )


# customer
class Customer(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A payer whose payment or checkout is at risk.
    One customer can have many revenue cases.
    """

    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Relationships
    cases: Mapped[list["RevenueCase"]] = relationship(
        "RevenueCase", back_populates="customer", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} email={self.email!r}>"


# revenue_cases 
class RevenueCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A single revenue-at-risk event — either a payment failure or an
    abandoned checkout detected via Razorpay.

    status values : PENDING | RECOVERED | FAILED | ESCALATED
    risk_level    : LOW | MEDIUM | HIGH
    """

    __tablename__ = "revenue_cases"

    # Razorpay identifiers
    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True
    )
    razorpay_order_id: Mapped[str | None] = mapped_column(
        String(255), index=True, nullable=True
    )

    # Financials
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)

    # Case status & risk classification
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False, index=True
    )
    risk_level: Mapped[str] = mapped_column(
        String(20), default="MEDIUM", nullable=False
    )

    # Failure diagnosis
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    root_cause: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Recovery tracking
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Foreign keys
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    customer: Mapped["Customer"] = relationship("Customer", back_populates="cases")
    interventions: Mapped[list["Intervention"]] = relationship(
        "Intervention", back_populates="case", cascade="all, delete-orphan"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="case", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<RevenueCase id={self.id} status={self.status!r} "
            f"amount={self.amount} {self.currency}>"
        )


# interventions 
class Intervention(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    A single outreach attempt made by the recovery agent for a given case.

    channel values : EMAIL | SMS | WHATSAPP | RETRY
    status  values : PENDING | SENT | DELIVERED | FAILED
    """

    __tablename__ = "interventions"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), default="PENDING", nullable=False
    )
    message_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped["RevenueCase"] = relationship(
        "RevenueCase", back_populates="interventions"
    )

    def __repr__(self) -> str:
        return (
            f"<Intervention id={self.id} channel={self.channel!r} "
            f"status={self.status!r}>"
        )


# Audit log
class AuditLog(UUIDPrimaryKeyMixin, Base):
    """
    Immutable append-only record of every AI decision and system event.
    Intentionally does NOT include an updated_at column.

    actor values : SYSTEM | ML_MODEL | AGENT | HUMAN
    """

    __tablename__ = "audit_logs"

    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    case: Mapped["RevenueCase"] = relationship(
        "RevenueCase", back_populates="audit_logs"
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} event={self.event_type!r} "
            f"actor={self.actor!r}>"
        )


# recovery merit
class RecoveryMetric(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """
    Daily rollup of recovery performance — used by the dashboard.
    One row per calendar day.
    """

    __tablename__ = "recovery_metrics"

    date: Mapped[date] = mapped_column(Date, nullable=False, index=True, unique=True)
    total_at_risk: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    total_recovered: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    successful_recoveries: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    failed_recoveries: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<RecoveryMetric date={self.date} recovered={self.total_recovered} "
            f"success={self.successful_recoveries}>"
        )
