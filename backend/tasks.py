"""
backend/tasks.py
────────────────
Celery background tasks for AI Revenue Recovery.

Task:
  process_recovery_case(case_id: str)
    → fetch RevenueCase + Customer from DB
    → run diagnosis engine (Step 3)
    → run AI recovery agent (Step 4)
    → persist Intervention, AuditLog, RecoveryMetric
    → update RevenueCase.status
"""

import logging
from datetime import date, datetime, timezone

from backend.celery_app import celery_app
from backend.database import sync_session
from backend.models import AuditLog, Customer, Intervention, RecoveryMetric, RevenueCase
from backend.diagnosis.classifier import diagnose_failure
from backend.agent.graph import run_recovery_agent

logger = logging.getLogger(__name__)

# Channels that represent a real outreach attempt (not a stop/escalation action)
_REAL_CHANNELS = {"EMAIL", "SMS", "WHATSAPP", "RETRY"}


@celery_app.task(name="tasks.process_recovery_case", bind=True, max_retries=3)
def process_recovery_case(self, case_id: str) -> dict:
    """
    End-to-end recovery pipeline for a single RevenueCase.

    Steps
    -----
    1. Fetch RevenueCase + Customer from DB.
    2. Run diagnosis engine → update root_cause on case.
    3. Run AI recovery agent → determine channel + outreach content.
    4. Persist Intervention record.
    5. Append AuditLog entry with full execution trace.
    6. Upsert RecoveryMetric for today.
    7. Update RevenueCase.status (RECOVERED / FAILED / DELAYED).

    Returns a summary dict that is stored as the Celery task result.
    """
    logger.info("[Task] Starting process_recovery_case for case_id=%s", case_id)

    # ── 1. Fetch RevenueCase ──────────────────────────────────────────────────
    with sync_session() as session:
        case: RevenueCase | None = (
            session.query(RevenueCase).filter(RevenueCase.id == case_id).first()
        )
        if case is None:
            logger.error("[Task] RevenueCase %s not found — aborting.", case_id)
            return {"error": f"RevenueCase {case_id} not found"}

        customer: Customer = case.customer

        # Snapshot values needed outside the session
        amount = case.amount
        currency = case.currency
        retry_count = case.retry_count
        failure_reason = case.failure_reason or ""
        rzp_payment_id = case.razorpay_payment_id or ""
        customer_name = customer.name
        customer_email = customer.email

    # ── 2. Diagnose failure ───────────────────────────────────────────────────
    try:
        diagnosis = diagnose_failure(
            error_code=failure_reason,
            error_description=failure_reason,
            context={
                "amount": amount,
                "retry_count": retry_count,
                "payment_method": "upi",   # default; richer data when available
                "bank_code": "OTHER",
            },
        )
        logger.info("[Task] Diagnosis result: %s", diagnosis)
    except Exception as exc:
        logger.warning("[Task] Diagnosis failed (%s). Using fallback.", exc)
        diagnosis = {
            "root_cause": "Unknown",
            "confidence": 0.0,
            "source": "FALLBACK",
        }

    # ── 3. Run AI recovery agent ──────────────────────────────────────────────
    case_data = {
        "case_id": case_id,
        "customer_name": customer_name,
        "customer_email": customer_email,
        "amount": amount,
        "currency": currency,
        "failure_reason": failure_reason,
        "retry_count": retry_count,
        "transaction_id": rzp_payment_id,
        "payment_method": "UPI",
        "payment_link": f"https://pay.example.com/retry/{rzp_payment_id or case_id}",
    }

    try:
        agent_result = run_recovery_agent(case_data=case_data, diagnosis=diagnosis)
        logger.info("[Task] Agent result: %s", agent_result)
    except Exception as exc:
        logger.error("[Task] Agent execution failed: %s", exc)
        agent_result = {
            "decision": {"chosen_channel": "FAILED", "urgency_level": "LOW", "reasoning": str(exc)},
            "compliance": {},
            "outreach_content": {"message_subject": "", "message_body": ""},
        }

    decision: dict = agent_result.get("decision", {})
    outreach: dict = agent_result.get("outreach_content", {})
    compliance: dict = agent_result.get("compliance", {})
    chosen_channel: str = decision.get("chosen_channel", "UNKNOWN").upper()

    # ── 4–7. DB writes: Intervention + AuditLog + RecoveryMetric + Case status ─
    with sync_session() as session:
        # Re-attach case to this new session
        case = session.query(RevenueCase).filter(RevenueCase.id == case_id).first()
        if case is None:
            logger.error("[Task] RevenueCase %s disappeared — aborting writes.", case_id)
            return {"error": "Case disappeared between reads"}

        # ── Update root_cause on case ─────────────────────────────────────────
        case.root_cause = diagnosis.get("root_cause", "Unknown")
        case.failure_reason = failure_reason or diagnosis.get("root_cause", "Unknown")

        # ── 4. Create Intervention record ─────────────────────────────────────
        is_real_outreach = chosen_channel in _REAL_CHANNELS
        intervention = Intervention(
            case_id=case.id,
            channel=chosen_channel,
            status="SENT" if is_real_outreach else "PENDING",
            message_content=outreach.get("message_body", ""),
            sent_at=datetime.now(timezone.utc) if is_real_outreach else None,
        )
        session.add(intervention)
        session.flush()

        # ── 5. Append AuditLog entry ──────────────────────────────────────────
        audit_payload = {
            "diagnosis": diagnosis,
            "decision": decision,
            "outreach": {
                "subject": outreach.get("message_subject", ""),
                "body_preview": (outreach.get("message_body", "") or "")[:200],
            },
            "compliance": compliance,
            "intervention_id": str(intervention.id),
        }
        audit = AuditLog(
            case_id=case.id,
            event_type="RECOVERY_PIPELINE_EXECUTED",
            actor="AGENT",
            payload=audit_payload,
            timestamp=datetime.now(timezone.utc),
        )
        session.add(audit)

        # ── 6. Upsert RecoveryMetric for today ────────────────────────────────
        today = date.today()
        metric: RecoveryMetric | None = (
            session.query(RecoveryMetric).filter(RecoveryMetric.date == today).first()
        )
        if metric is None:
            metric = RecoveryMetric(
                date=today,
                total_at_risk=amount,
                total_recovered=0.0,
                successful_recoveries=0,
                failed_recoveries=0,
            )
            session.add(metric)
        else:
            metric.total_at_risk += amount

        # ── 7. Update RevenueCase.status ──────────────────────────────────────
        if is_real_outreach:
            new_status = "RECOVERED"
            metric.total_recovered += amount
            metric.successful_recoveries += 1
        elif chosen_channel in {"ESCALATE", "STOP"}:
            new_status = "DELAYED"
        else:
            new_status = "FAILED"
            metric.failed_recoveries += 1

        case.status = new_status
        logger.info(
            "[Task] case_id=%s → status=%s channel=%s",
            case_id,
            new_status,
            chosen_channel,
        )
        # session commits on context manager exit

    return {
        "case_id": case_id,
        "status": new_status,
        "channel": chosen_channel,
        "root_cause": diagnosis.get("root_cause"),
    }
