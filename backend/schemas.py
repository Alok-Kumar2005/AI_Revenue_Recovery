from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_serializer


class _ORMBase(BaseModel):
    """Base class that enables ORM mode for all schemas."""
    model_config = ConfigDict(from_attributes=True)


# customer
class CustomerSchema(_ORMBase):
    """Lightweight customer representation returned inside case payloads."""
    id: uuid.UUID
    name: str
    email: str
    phone: Optional[str] = None

    @field_serializer("id")
    def serialize_id(self, v: uuid.UUID) -> str:
        return str(v)


# intervention
class InterventionSchema(_ORMBase):
    """Single outreach attempt serialised for API consumers."""
    id: uuid.UUID
    channel: str
    status: str
    message_payload: Optional[str] = None   # maps to message_content in ORM
    sent_at: Optional[datetime] = None

    @field_serializer("id")
    def serialize_id(self, v: uuid.UUID) -> str:
        return str(v)

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )

    @classmethod
    def from_orm_obj(cls, obj: Any) -> "InterventionSchema":
        """Build schema from an ORM Intervention, renaming message_content."""
        return cls(
            id=obj.id,
            channel=obj.channel,
            status=obj.status,
            message_payload=obj.message_content,
            sent_at=obj.sent_at,
        )


# audit log
class AuditLogSchema(_ORMBase):
    """Immutable audit-log entry returned in the case timeline."""
    id: uuid.UUID
    event: str          # maps to event_type in ORM
    actor: str
    details: Optional[dict] = None   # maps to payload in ORM
    created_at: datetime             # maps to timestamp in ORM

    @field_serializer("id")
    def serialize_id(self, v: uuid.UUID) -> str:
        return str(v)

    @classmethod
    def from_orm_obj(cls, obj: Any) -> "AuditLogSchema":
        """Build schema from an ORM AuditLog, renaming fields."""
        return cls(
            id=obj.id,
            event=obj.event_type,
            actor=obj.actor,
            details=obj.payload,
            created_at=obj.timestamp,
        )


# case details
class CaseDetailResponse(_ORMBase):
    """Full RevenueCase detail including related customer, interventions, and audit logs."""
    id: uuid.UUID
    razorpay_payment_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    amount: float
    currency: str
    status: str
    risk_level: str
    failure_reason: Optional[str] = None
    root_cause: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    # Joined relations
    customer: Optional[CustomerSchema] = None
    interventions: list[InterventionSchema] = []
    audit_logs: list[AuditLogSchema] = []

    @field_serializer("id")
    def serialize_id(self, v: uuid.UUID) -> str:
        return str(v)


class CaseListItem(_ORMBase):
    """Compact case representation for the paginated case list."""
    id: uuid.UUID
    amount: float
    currency: str
    status: str
    risk_level: str
    failure_reason: Optional[str] = None
    retry_count: int
    created_at: datetime
    customer: Optional[CustomerSchema] = None

    @field_serializer("id")
    def serialize_id(self, v: uuid.UUID) -> str:
        return str(v)


class CaseListResponse(BaseModel):
    """Paginated wrapper around a list of CaseListItem objects."""
    total: int
    limit: int
    offset: int
    items: list[CaseListItem]


# metrics summary
class MetricsSummaryResponse(BaseModel):
    """Live aggregate metrics for the recovery dashboard header cards."""
    total_at_risk_amount: float
    total_recovered_amount: float
    recovery_rate_pct: float            # 0-100
    active_cases_count: int
    recovered_cases_count: int
