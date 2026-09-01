"""
backend/routers/webhooks.py
────────────────────────────
FastAPI router for automated payment reconciliation webhooks.

Prefix : /api   (mounted in main.py)

Endpoints:
  POST /api/webhooks/payment   → Ingest real payment provider webhooks
                                  (generic, Stripe payment_intent.succeeded,
                                   Razorpay payment.captured)
  POST /api/webhooks/simulate  → UI-driven simulation for testing reconciliation

Reconciliation behaviour:
  1. Match incoming payload to an existing RevenueCase by case_id, invoice_id,
     or customer_email.
  2. Idempotency guard: if the case is already RECOVERED return immediately.
  3. If PENDING or IN_RECOVERY:
     - Set status → RECOVERED
     - Record recovered_at timestamp and payment transaction reference on the
       case's razorpay_payment_id field (repurposed as generic payment_ref).
     - Append an AuditLog entry with event_type PAYMENT_RECONCILED.
     - Upsert today's RecoveryMetric row to keep dashboard KPIs fresh.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import AuditLog, RecoveryMetric, RevenueCase

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class PaymentWebhookPayload(BaseModel):
    """
    Generic payment webhook body.  Covers:
      * Stripe   – event = "payment_intent.succeeded", data.object.id = pi_xxx
      * Razorpay – event = "payment.captured",  payload.payment.entity.id = pay_xxx
      * Generic  – case_id / invoice_id / customer_email directly in root.
    """

    # Provider event envelope (optional – used for Stripe / Razorpay format)
    event: Optional[str] = None

    # Stripe shape: data.object contains the PaymentIntent
    data: Optional[dict] = None

    # Razorpay shape: payload.payment.entity contains the payment object
    payload: Optional[dict] = None

    # Generic / direct shape
    case_id: Optional[str] = None
    invoice_id: Optional[str] = None
    customer_email: Optional[str] = None
    amount_paid: Optional[float] = None
    currency: Optional[str] = "INR"
    provider: Optional[str] = "generic"
    payment_id: Optional[str] = None

    model_config = {"extra": "allow"}


class SimulatePaymentRequest(BaseModel):
    """Payload for the UI-driven payment simulation endpoint."""

    case_id: str = Field(..., description="UUID of the RevenueCase to reconcile")
    amount_paid: float = Field(..., gt=0, description="Amount that was paid")
    provider: str = Field(default="Razorpay", description="Payment provider label")
    payment_id: Optional[str] = Field(
        default=None, description="Provider transaction ID (auto-generated if omitted)"
    )

    model_config = {"extra": "allow"}


class ReconciliationResult(BaseModel):
    status: str
    case_id: str
    amount_paid: float
    provider: str
    payment_ref: Optional[str] = None
    message: Optional[str] = None


# ── Helpers ────────────────────────────────────────────────────────────────────

def _generate_payment_ref(provider: str) -> str:
    """Generate a plausible-looking transaction reference for simulation."""
    short = uuid.uuid4().hex[:9].upper()
    prefix_map = {
        "stripe": "pi",
        "razorpay": "pay",
        "payu": "txn",
        "cashfree": "cf",
    }
    prefix = prefix_map.get(provider.lower(), "txn")
    return f"{prefix}_{short}"


def _reconcile_case(
    db: Session,
    case: RevenueCase,
    amount_paid: float,
    provider: str,
    payment_ref: str,
) -> ReconciliationResult:
    """
    Core reconciliation logic.

    Idempotency: returns ALREADY_RECOVERED without side-effects if the case
    is already in RECOVERED state.
    Transitions PENDING / IN_RECOVERY -> RECOVERED and writes an AuditLog entry.
    """
    case_id_str = str(case.id)

    # ── Idempotency guard ─────────────────────────────────────────────────────
    if case.status == "RECOVERED":
        logger.info("[Webhook] Case %s already RECOVERED — skipping.", case_id_str[:8])
        return ReconciliationResult(
            status="ALREADY_RECOVERED",
            case_id=case_id_str,
            amount_paid=amount_paid,
            provider=provider,
            payment_ref=payment_ref,
            message="Case was already in RECOVERED state; no changes made.",
        )

    # ── State transition ──────────────────────────────────────────────────────
    case.status = "RECOVERED"
    # Repurpose razorpay_payment_id as a generic payment reference store
    case.razorpay_payment_id = payment_ref
    case.updated_at = datetime.now(timezone.utc)

    # ── Audit log ─────────────────────────────────────────────────────────────
    audit = AuditLog(
        case_id=case.id,
        event_type="PAYMENT_RECONCILED",
        actor="SYSTEM",
        payload={
            "event": "PAYMENT_RECONCILED",
            "provider": provider,
            "payment_ref": payment_ref,
            "amount_paid": amount_paid,
            "currency": case.currency,
            "detail": (
                f"Automated reconciliation via {provider}. Txn ID: {payment_ref}"
            ),
        },
        timestamp=datetime.now(timezone.utc),
    )
    db.add(audit)

    # ── Upsert today's RecoveryMetric ─────────────────────────────────────────
    today = date.today()
    metric = db.query(RecoveryMetric).filter(RecoveryMetric.date == today).first()
    if metric is None:
        metric = RecoveryMetric(
            date=today,
            total_at_risk=0.0,
            total_recovered=amount_paid,
            successful_recoveries=1,
            failed_recoveries=0,
        )
        db.add(metric)
    else:
        metric.total_recovered = float(metric.total_recovered) + amount_paid
        metric.successful_recoveries = int(metric.successful_recoveries) + 1

    db.flush()
    logger.info(
        "[Webhook] Case %s reconciled via %s — txn=%s amount=%.2f",
        case_id_str[:8],
        provider,
        payment_ref,
        amount_paid,
    )

    return ReconciliationResult(
        status="RECOVERED",
        case_id=case_id_str,
        amount_paid=amount_paid,
        provider=provider,
        payment_ref=payment_ref,
        message=f"Case successfully reconciled via {provider}.",
    )


def _find_case(
    db: Session,
    case_id: Optional[str] = None,
    invoice_id: Optional[str] = None,
    customer_email: Optional[str] = None,
) -> RevenueCase:
    """
    Attempt to locate a RevenueCase by case_id -> invoice_id -> customer email
    (in priority order).  Raises HTTP 404 if no match is found.
    """
    case: Optional[RevenueCase] = None

    if case_id:
        try:
            uid = uuid.UUID(case_id)
            case = db.query(RevenueCase).filter(RevenueCase.id == uid).first()
        except ValueError:
            pass  # not a valid UUID — fall through to other matchers

    if case is None and invoice_id:
        # Try matching against razorpay_order_id as invoice surrogate
        case = (
            db.query(RevenueCase)
            .filter(RevenueCase.razorpay_order_id == invoice_id)
            .first()
        )

    if case is None and customer_email:
        from backend.models import Customer  # local import to avoid circular dep
        customer = (
            db.query(Customer)
            .filter(Customer.email == customer_email)
            .first()
        )
        if customer:
            case = (
                db.query(RevenueCase)
                .filter(
                    RevenueCase.customer_id == customer.id,
                    RevenueCase.status.in_(["PENDING", "IN_RECOVERY"]),
                )
                .order_by(RevenueCase.created_at.desc())
                .first()
            )

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No RevenueCase found matching the provided "
                "case_id / invoice_id / customer_email."
            ),
        )

    return case


# ── POST /api/webhooks/payment ─────────────────────────────────────────────────

@router.post(
    "/webhooks/payment",
    response_model=ReconciliationResult,
    summary="Ingest automated payment success webhook",
    tags=["Webhooks"],
)
def receive_payment_webhook(
    body: PaymentWebhookPayload,
    db: Session = Depends(get_db),
) -> ReconciliationResult:
    """
    Receive a payment-success event from Stripe, Razorpay, or a generic provider
    and auto-reconcile the matching RevenueCase to RECOVERED.

    Supported event types:
    - **Stripe** ``payment_intent.succeeded`` – reads ``data.object.{id, amount, metadata}``
    - **Razorpay** ``payment.captured`` – reads ``payload.payment.entity.{id, amount, email}``
    - **Generic** – reads ``case_id``, ``amount_paid``, ``provider``, ``payment_id`` directly

    The endpoint is idempotent: calling it multiple times for the same already-
    RECOVERED case returns ``status = "ALREADY_RECOVERED"`` with HTTP 200.
    """
    event = (body.event or "").lower()
    logger.info("[Webhook] /payment received event=%r", event)

    # ── Stripe: payment_intent.succeeded ─────────────────────────────────────
    if event == "payment_intent.succeeded":
        obj = (body.data or {}).get("object", {})
        payment_ref = obj.get("id") or _generate_payment_ref("stripe")
        amount_paid = float(obj.get("amount", 0)) / 100.0  # Stripe uses cents
        provider = "Stripe"
        meta = obj.get("metadata", {})
        case_id = meta.get("case_id") or body.case_id
        customer_email = obj.get("receipt_email") or body.customer_email
        invoice_id = obj.get("invoice") or body.invoice_id

    # ── Razorpay: payment.captured ────────────────────────────────────────────
    elif event == "payment.captured":
        entity = (body.payload or {}).get("payment", {}).get("entity", {})
        payment_ref = entity.get("id") or _generate_payment_ref("razorpay")
        amount_paid = float(entity.get("amount", 0)) / 100.0  # paise -> INR
        provider = "Razorpay"
        case_id = (entity.get("notes") or {}).get("case_id") or body.case_id
        customer_email = entity.get("email") or body.customer_email
        invoice_id = entity.get("order_id") or body.invoice_id

    # ── Generic / direct payload ──────────────────────────────────────────────
    else:
        payment_ref = body.payment_id or _generate_payment_ref(body.provider or "generic")
        amount_paid = body.amount_paid or 0.0
        provider = body.provider or "generic"
        case_id = body.case_id
        customer_email = body.customer_email
        invoice_id = body.invoice_id

    case = _find_case(db, case_id=case_id, invoice_id=invoice_id, customer_email=customer_email)
    return _reconcile_case(db, case, amount_paid, provider, payment_ref)


# ── POST /api/webhooks/simulate ────────────────────────────────────────────────

@router.post(
    "/webhooks/simulate",
    response_model=ReconciliationResult,
    summary="Simulate an incoming payment for UI testing",
    tags=["Webhooks"],
)
def simulate_payment(
    body: SimulatePaymentRequest,
    db: Session = Depends(get_db),
) -> ReconciliationResult:
    """
    Simulate a successful payment for a specific case — used by the frontend
    "Simulate Incoming Payment" button.

    Behaves identically to the real webhook handler but accepts a simplified
    body and always generates a synthetic transaction ID when none is provided.
    The endpoint is fully idempotent.
    """
    logger.info(
        "[Simulate] case_id=%s provider=%s amount=%.2f",
        body.case_id,
        body.provider,
        body.amount_paid,
    )

    payment_ref = body.payment_id or _generate_payment_ref(body.provider)
    case = _find_case(db, case_id=body.case_id)
    return _reconcile_case(db, case, body.amount_paid, body.provider, payment_ref)
