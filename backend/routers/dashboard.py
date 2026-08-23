"""
backend/routers/dashboard.py
─────────────────────────────
FastAPI router exposing analytical read endpoints for the AI Revenue Recovery dashboard.

Prefix : /api   (mounted in main.py)

Endpoints:
  GET /api/metrics/summary        → MetricsSummaryResponse
  GET /api/cases                  → CaseListResponse  (paginated, filterable by status)
  GET /api/cases/{case_id}        → CaseDetailResponse (eager-loads customer, interventions, audit_logs)
  GET /api/interventions          → list[InterventionSchema] (recent, sorted by sent_at desc)

Implementation note
───────────────────
Routes use the *sync* SQLAlchemy session (get_db / psycopg2 driver) so they
work correctly under both Uvicorn (production) and FastAPI TestClient (testing)
without the event-loop-closed errors that asyncpg triggers when connections
are reused across threads.
"""

from __future__ import annotations

import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import AuditLog, Customer, Intervention, RecoveryMetric, RevenueCase
from backend.schemas import (
    AuditLogSchema,
    CaseDetailResponse,
    CaseListItem,
    CaseListResponse,
    CustomerSchema,
    InterventionSchema,
    MetricsSummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── GET /api/metrics/summary ───────────────────────────────────────────────────

@router.get(
    "/metrics/summary",
    response_model=MetricsSummaryResponse,
    summary="Live recovery KPI aggregates",
    tags=["metrics"],
)
def get_metrics_summary(
    db: Session = Depends(get_db),
) -> MetricsSummaryResponse:
    """
    Compute live aggregate metrics from `revenue_cases` and `recovery_metrics`.

    - total_at_risk_amount   : sum of amounts for PENDING + ESCALATED cases
    - total_recovered_amount : sum of amounts for RECOVERED cases (from revenue_cases)
                               + sum of total_recovered from recovery_metrics table
    - recovery_rate_pct      : recovered / (at_risk + recovered) * 100
    - active_cases_count     : count of PENDING + ESCALATED cases
    - recovered_cases_count  : count of RECOVERED cases
    """
    # ── Aggregate from revenue_cases ──────────────────────────────────────────
    row = db.query(
        func.coalesce(
            func.sum(RevenueCase.amount).filter(
                RevenueCase.status.in_(["PENDING", "ESCALATED"])
            ),
            0.0,
        ).label("at_risk_amount"),
        func.coalesce(
            func.sum(RevenueCase.amount).filter(
                RevenueCase.status == "RECOVERED"
            ),
            0.0,
        ).label("recovered_amount"),
        func.count(RevenueCase.id).filter(
            RevenueCase.status.in_(["PENDING", "ESCALATED"])
        ).label("active_count"),
        func.count(RevenueCase.id).filter(
            RevenueCase.status == "RECOVERED"
        ).label("recovered_count"),
    ).one()

    at_risk_amount: float = float(row.at_risk_amount)
    recovered_from_cases: float = float(row.recovered_amount)
    active_cases_count: int = int(row.active_count)
    recovered_cases_count: int = int(row.recovered_count)

    # ── Additional recovered amount from recovery_metrics rollup ──────────────
    metrics_row = db.query(
        func.coalesce(
            func.sum(RecoveryMetric.total_recovered), 0.0
        ).label("metrics_recovered")
    ).one()
    recovered_from_metrics: float = float(metrics_row.metrics_recovered)

    total_recovered = max(recovered_from_cases, recovered_from_metrics)
    total_at_risk = at_risk_amount

    # ── Recovery rate ─────────────────────────────────────────────────────────
    denominator = total_at_risk + total_recovered
    recovery_rate_pct = (total_recovered / denominator * 100.0) if denominator > 0 else 0.0

    return MetricsSummaryResponse(
        total_at_risk_amount=round(total_at_risk, 2),
        total_recovered_amount=round(total_recovered, 2),
        recovery_rate_pct=round(recovery_rate_pct, 2),
        active_cases_count=active_cases_count,
        recovered_cases_count=recovered_cases_count,
    )


# ── GET /api/cases ─────────────────────────────────────────────────────────────

@router.get(
    "/cases",
    response_model=CaseListResponse,
    summary="Paginated list of revenue cases",
    tags=["cases"],
)
def list_cases(
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        description="Filter by case status: PENDING | RECOVERED | FAILED | ESCALATED",
    ),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: Session = Depends(get_db),
) -> CaseListResponse:
    """
    Return a paginated list of revenue cases, optionally filtered by status.
    Each item includes the associated customer's basic info.
    """
    query = (
        db.query(RevenueCase)
        .options(joinedload(RevenueCase.customer))
        .order_by(RevenueCase.created_at.desc())
    )

    if status_filter:
        query = query.filter(RevenueCase.status == status_filter.upper())

    total: int = query.count()
    cases = query.offset(offset).limit(limit).all()

    items: list[CaseListItem] = []
    for case in cases:
        customer_schema = (
            CustomerSchema.model_validate(case.customer) if case.customer else None
        )
        items.append(
            CaseListItem(
                id=case.id,
                amount=case.amount,
                currency=case.currency,
                status=case.status,
                risk_level=case.risk_level,
                failure_reason=case.failure_reason,
                retry_count=case.retry_count,
                created_at=case.created_at,
                customer=customer_schema,
            )
        )

    return CaseListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


# ── GET /api/cases/{case_id} ───────────────────────────────────────────────────

@router.get(
    "/cases/{case_id}",
    response_model=CaseDetailResponse,
    summary="Fetch a single case with full audit trail",
    tags=["cases"],
)
def get_case_detail(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> CaseDetailResponse:
    """
    Return full details for a single RevenueCase identified by UUID.
    Eager-loads related Customer, Interventions, and AuditLogs.
    """
    case = (
        db.query(RevenueCase)
        .options(
            joinedload(RevenueCase.customer),
            joinedload(RevenueCase.interventions),
            joinedload(RevenueCase.audit_logs),
        )
        .filter(RevenueCase.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RevenueCase {case_id} not found",
        )

    # ── Serialise related objects ─────────────────────────────────────────────
    customer_schema = (
        CustomerSchema.model_validate(case.customer) if case.customer else None
    )

    interventions_schema = [
        InterventionSchema.from_orm_obj(iv) for iv in case.interventions
    ]

    # Sort audit logs oldest-first for timeline display
    sorted_logs = sorted(case.audit_logs, key=lambda al: al.timestamp)
    audit_logs_schema = [AuditLogSchema.from_orm_obj(al) for al in sorted_logs]

    return CaseDetailResponse(
        id=case.id,
        razorpay_payment_id=case.razorpay_payment_id,
        razorpay_order_id=case.razorpay_order_id,
        amount=case.amount,
        currency=case.currency,
        status=case.status,
        risk_level=case.risk_level,
        failure_reason=case.failure_reason,
        root_cause=case.root_cause,
        retry_count=case.retry_count,
        created_at=case.created_at,
        updated_at=case.updated_at,
        customer=customer_schema,
        interventions=interventions_schema,
        audit_logs=audit_logs_schema,
    )


# ── GET /api/interventions ─────────────────────────────────────────────────────

@router.get(
    "/interventions",
    response_model=list[InterventionSchema],
    summary="Recent outreach interventions sorted by sent_at desc",
    tags=["interventions"],
)
def list_interventions(
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    db: Session = Depends(get_db),
) -> list[InterventionSchema]:
    """
    Return the most recent intervention records, sorted by sent_at descending.
    Records where sent_at is NULL appear last.
    """
    interventions = (
        db.query(Intervention)
        .order_by(Intervention.sent_at.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [InterventionSchema.from_orm_obj(iv) for iv in interventions]
