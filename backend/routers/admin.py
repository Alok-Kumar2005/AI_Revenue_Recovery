"""
backend/routers/admin.py
────────────────────────
Staging & Admin endpoints for system reset and test data seeding.

Prefix: /admin  (mounted under /api in main.py)
Endpoints:
  POST /api/admin/reset-test-cases  → Update all RevenueCase statuses to "PENDING"
  POST /api/admin/seed-test-cases   → Seed synthetic RevenueCase records with PENDING status
"""

import logging
import random
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Customer, RevenueCase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["Admin"])


class SeedResponse(BaseModel):
    status: str
    seeded_count: int
    case_ids: list[str]


class ResetResponse(BaseModel):
    status: str
    reset_count: int


@router.post(
    "/reset-test-cases",
    response_model=ResetResponse,
    summary="Reset all test cases to PENDING",
)
def reset_test_cases(db: Session = Depends(get_db)) -> ResetResponse:
    """
    Query all RevenueCase records in the database and update their status to 'PENDING'.
    """
    updated_rows = db.query(RevenueCase).update({RevenueCase.status: "PENDING"})
    db.commit()
    logger.info("[Admin] Reset %d RevenueCase records to PENDING", updated_rows)
    return ResetResponse(status="success", reset_count=updated_rows)


@router.post(
    "/seed-test-cases",
    response_model=SeedResponse,
    summary="Seed synthetic test revenue cases",
)
def seed_test_cases(
    count: int = Query(default=5, ge=1, le=100, description="Number of test cases to seed"),
    db: Session = Depends(get_db),
) -> SeedResponse:
    """
    Seed synthetic RevenueCase records with status='PENDING', test emails,
    and failure codes (AUTHENTICATION_FAILED, INSUFFICIENT_FUNDS, UPI_TIMEOUT).
    """
    failure_codes = [
        "AUTHENTICATION_FAILED",
        "INSUFFICIENT_FUNDS",
        "UPI_TIMEOUT",
    ]

    seeded_cases: list[RevenueCase] = []

    for i in range(count):
        short_id = uuid.uuid4().hex[:6]
        email = f"test_user_{short_id}@example.com"
        name = f"Test User {short_id.upper()}"
        phone = f"+91987{random.randint(1000000, 9999999)}"

        # Get or create test customer
        customer = db.query(Customer).filter(Customer.email == email).first()
        if not customer:
            customer = Customer(
                name=name,
                email=email,
                phone=phone,
            )
            db.add(customer)
            db.flush()

        failure_code = failure_codes[i % len(failure_codes)]
        amount = round(random.uniform(299.0, 9999.0), 2)
        risk_level = random.choice(["LOW", "MEDIUM", "HIGH"])

        case = RevenueCase(
            customer_id=customer.id,
            amount=amount,
            currency="INR",
            status="PENDING",
            risk_level=risk_level,
            failure_reason=failure_code,
            root_cause=f"Simulated {failure_code} failure",
            razorpay_payment_id=f"pay_seed_{uuid.uuid4().hex[:8]}",
            razorpay_order_id=f"order_seed_{uuid.uuid4().hex[:8]}",
        )
        db.add(case)
        seeded_cases.append(case)

    db.commit()
    case_ids = [str(c.id) for c in seeded_cases]
    logger.info("[Admin] Seeded %d synthetic test cases: %s", len(case_ids), case_ids)

    return SeedResponse(
        status="success",
        seeded_count=len(case_ids),
        case_ids=case_ids,
    )
