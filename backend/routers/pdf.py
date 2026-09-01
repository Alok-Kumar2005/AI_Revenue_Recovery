"""
backend/routers/pdf.py
──────────────────────
FastAPI router that exposes PDF generation for revenue cases.

Prefix : /api   (mounted in main.py)

Endpoints:
  GET /api/cases/{case_id}/pdf  → Streams a demand-letter PDF for the given case.
"""

from __future__ import annotations

import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db
from backend.models import Customer, RevenueCase
from backend.services.pdf_generator import generate_demand_letter_pdf

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/cases/{case_id}/pdf",
    summary="Generate and stream a demand-letter PDF for a revenue case",
    response_class=Response,
    tags=["pdf"],
    responses={
        200: {
            "content": {"application/pdf": {}},
            "description": "Demand letter PDF rendered inline.",
        },
        404: {"description": "Case not found"},
    },
)
def get_case_pdf(
    case_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """
    Fetch the case and its associated customer from the database, generate a
    professional demand-letter PDF using ReportLab, and return it as an inline
    PDF response that browsers can render directly.
    """
    case = (
        db.query(RevenueCase)
        .options(joinedload(RevenueCase.customer))
        .filter(RevenueCase.id == case_id)
        .first()
    )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RevenueCase {case_id} not found",
        )

    customer: Customer | None = case.customer
    if customer is None:
        # Fallback: create a minimal stub so the PDF still renders
        customer = Customer(
            name="Unknown Customer",
            email="unknown@example.com",
            phone=None,
        )
        customer.id = case.customer_id  # type: ignore[assignment]

    logger.info(
        "[PDF] Generating demand letter for case=%s customer=%s",
        str(case_id)[:8],
        customer.email,
    )

    pdf_buffer = generate_demand_letter_pdf(case=case, customer=customer)
    pdf_bytes  = pdf_buffer.read()

    filename = f"Demand_Letter_{str(case_id)[:8].upper()}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
            "Cache-Control": "no-store",
        },
    )
