"""
backend/routers/webhook.py
──────────────────────────
FastAPI router for Razorpay webhook events.

Endpoint:
  POST /webhook/razorpay

Behaviour:
  1. Verifies HMAC-SHA256 signature using RZP_WEBHOOK_SECRET
     (skipped gracefully when secret appears to be a mock/default value).
  2. Handles payment.failed events:
     - Upserts Customer record (get-or-create by email).
     - Creates RevenueCase with status PENDING.
     - Dispatches process_recovery_case Celery task.
  3. Returns {"status": "queued", "case_id": "<uuid>"} immediately.
"""

import hashlib
import hmac
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from backend.config import settings
from backend.database import sync_session
from backend.models import Customer, RevenueCase
from backend.tasks import process_recovery_case

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Sentinel values that indicate the secret is a placeholder ─────────────────
_MOCK_SECRETS = {"", "mock", "test", "your_webhook_secret", "changeme"}


def _is_mock_secret(secret: str) -> bool:
    return secret.strip().lower() in _MOCK_SECRETS


def _verify_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """
    Verify Razorpay HMAC-SHA256 webhook signature.

    Razorpay sends the signature in the X-Razorpay-Signature header.
    Expected MAC = HMAC-SHA256(webhook_secret, raw_body).hexdigest()
    """
    if _is_mock_secret(secret):
        logger.debug("Webhook secret is mock/default — skipping HMAC verification.")
        return True

    if not signature_header:
        logger.warning("Missing X-Razorpay-Signature header.")
        return False

    try:
        expected = hmac.new(
            secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)
    except Exception as exc:
        logger.error("HMAC verification error: %s", exc)
        return False


def _get_or_create_customer(session, email: str, name: str, phone: str | None) -> Customer:
    """Fetch existing Customer by email or insert a new one."""
    customer = session.query(Customer).filter(Customer.email == email).first()
    if customer is None:
        customer = Customer(
            name=name or email,
            email=email,
            phone=phone,
        )
        session.add(customer)
        session.flush()  # populate customer.id without committing
        logger.info("Created new customer: %s", email)
    else:
        logger.info("Found existing customer: %s (id=%s)", email, customer.id)
    return customer


@router.post("/razorpay", status_code=status.HTTP_200_OK)
async def razorpay_webhook(request: Request):
    """
    Ingest Razorpay payment.failed webhook events.

    Returns {"status": "queued", "case_id": "<uuid>"} immediately after
    dispatching the background recovery task.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # ── Signature verification ────────────────────────────────────────────────
    if not _verify_signature(raw_body, signature, settings.RZP_WEBHOOK_SECRET):
        logger.warning("Webhook signature verification failed.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook signature",
        )

    # ── Parse JSON payload ────────────────────────────────────────────────────
    try:
        payload: dict = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid JSON payload",
        )

    event = payload.get("event", "")
    logger.info("Received Razorpay event: %s", event)

    # Only handle payment failure events
    if event != "payment.failed":
        return {"status": "ignored", "event": event}

    # ── Extract payment details ───────────────────────────────────────────────
    payment: dict = payload.get("payload", {}).get("payment", {}).get("entity", {})

    email: str = (
        payment.get("email")
        or payment.get("customer_details", {}).get("email", "")
        or "unknown@example.com"
    )
    name: str = (
        payment.get("contact")
        or payment.get("customer_details", {}).get("name", "")
        or email.split("@")[0]
    )
    # Razorpay stores phone in 'contact' field; name may be absent
    # Prefer dedicated name field if available
    contact_name: str = payment.get("notes", {}).get("name", "") or name
    phone: str | None = payment.get("contact") or None

    razorpay_payment_id: str | None = payment.get("id")
    razorpay_order_id: str | None = payment.get("order_id")

    # Amount comes in paise (1 INR = 100 paise)
    amount_paise: int = int(payment.get("amount", 0))
    amount_inr: float = amount_paise / 100.0
    currency: str = payment.get("currency", "INR")

    error_code: str = payment.get("error_code", "")
    error_description: str = payment.get("error_description", "")

    logger.info(
        "payment.failed — id=%s order=%s amount=%.2f %s email=%s",
        razorpay_payment_id,
        razorpay_order_id,
        amount_inr,
        currency,
        email,
    )

    # ── DB write: upsert Customer + create RevenueCase ────────────────────────
    with sync_session() as session:
        customer = _get_or_create_customer(session, email, contact_name, phone)

        case = RevenueCase(
            customer_id=customer.id,
            razorpay_payment_id=razorpay_payment_id,
            razorpay_order_id=razorpay_order_id,
            amount=amount_inr,
            currency=currency,
            status="PENDING",
            failure_reason=error_description or error_code or "Unknown",
        )
        session.add(case)
        session.flush()  # populate case.id
        case_id = str(case.id)
        logger.info("Created RevenueCase: %s (PENDING)", case_id)
        # session commit happens on context manager exit

    # ── Dispatch Celery task ──────────────────────────────────────────────────
    process_recovery_case.delay(case_id)
    logger.info("Dispatched process_recovery_case for case_id=%s", case_id)

    return {"status": "queued", "case_id": case_id}
