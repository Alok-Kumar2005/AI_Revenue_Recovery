"""
backend/execution/nudges.py
────────────────────────────
Live & Mock messaging dispatchers for Email (SendGrid), SMS (Twilio),
and WhatsApp (Twilio).

Handles dispatching messages and appending dispatch metadata / message IDs
to the case audit logs (AuditLog).
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import AuditLog

logger = logging.getLogger(__name__)


def send_email_nudge(to_email: str, subject: str, body_html: str) -> Dict[str, Any]:
    """
    Send an email nudge via Resend API (using SENDGRID_API_KEY config) or fallback to mock log.
    """
    if settings.MOCK_DISPATCH or not settings.SENDGRID_API_KEY:
        mock_id = f"mock-email-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MOCK EMAIL SENT] To: %s | Subject: %s | ID: %s | Body: %s",
            to_email,
            subject,
            mock_id,
            body_html[:100],
        )
        return {
            "status": "mocked",
            "channel": "EMAIL",
            "message_id": mock_id,
            "recipient": to_email,
            "subject": subject,
            "details": "MOCK_DISPATCH enabled or SENDGRID_API_KEY missing",
        }

    try:
        # Use resend SDK if installed, or fallback to httpx call to Resend API
        try:
            import resend

            resend.api_key = settings.SENDGRID_API_KEY
            params = {
                "from": settings.FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": body_html,
            }
            email_resp = resend.Emails.send(params)
            if isinstance(email_resp, dict):
                message_id = email_resp.get("id", f"resend-{uuid.uuid4().hex[:8]}")
            else:
                message_id = getattr(email_resp, "id", f"resend-{uuid.uuid4().hex[:8]}")

            logger.info(
                "[EMAIL DISPATCHED VIA RESEND] To: %s | ID: %s", to_email, message_id
            )
            return {
                "status": "sent",
                "channel": "EMAIL",
                "message_id": message_id,
                "recipient": to_email,
                "provider_response": (
                    email_resp if isinstance(email_resp, dict) else str(email_resp)
                ),
            }
        except ImportError:
            import httpx

            headers = {
                "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            }
            json_payload = {
                "from": settings.FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": body_html,
            }
            response = httpx.post(
                "https://api.resend.com/emails",
                headers=headers,
                json=json_payload,
                timeout=10.0,
            )
            res_data = response.json()
            if response.status_code in (200, 201, 202):
                message_id = res_data.get("id", f"resend-{uuid.uuid4().hex[:8]}")
                logger.info(
                    "[EMAIL DISPATCHED VIA RESEND HTTP] To: %s | ID: %s",
                    to_email,
                    message_id,
                )
                return {
                    "status": "sent",
                    "channel": "EMAIL",
                    "message_id": message_id,
                    "recipient": to_email,
                    "provider_response": res_data,
                }
            else:
                logger.error(
                    "[RESEND HTTP ERROR] Status: %s | Payload: %s",
                    response.status_code,
                    res_data,
                )
                return {
                    "status": "failed",
                    "channel": "EMAIL",
                    "error": str(res_data),
                    "recipient": to_email,
                }
    except Exception as exc:
        logger.error("[EMAIL DISPATCH FAILED] To: %s | Error: %s", to_email, exc)
        return {
            "status": "failed",
            "channel": "EMAIL",
            "error": str(exc),
            "recipient": to_email,
        }


def send_sms_nudge(to_phone: str, message: str) -> Dict[str, Any]:
    """
    Send an SMS nudge via Twilio API or fallback to mock log.
    """
    if (
        settings.MOCK_DISPATCH
        or not settings.TWILIO_ACCOUNT_SID
        or not settings.TWILIO_AUTH_TOKEN
    ):
        mock_id = f"mock-sms-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MOCK SMS SENT] To: %s | ID: %s | Message: %s",
            to_phone,
            mock_id,
            message[:100],
        )
        return {
            "status": "mocked",
            "channel": "SMS",
            "message_id": mock_id,
            "recipient": to_phone,
            "details": "MOCK_DISPATCH enabled or TWILIO credentials missing",
        }

    try:
        from twilio.rest import Client

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        res = client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_phone,
        )
        logger.info(
            "[SMS DISPATCHED] To: %s | SID: %s | Status: %s",
            to_phone,
            res.sid,
            res.status,
        )
        return {
            "status": "sent",
            "channel": "SMS",
            "message_id": res.sid,
            "recipient": to_phone,
            "provider_status": res.status,
        }
    except Exception as exc:
        logger.error("[SMS DISPATCH FAILED] To: %s | Error: %s", to_phone, exc)
        return {
            "status": "failed",
            "channel": "SMS",
            "error": str(exc),
            "recipient": to_phone,
        }


def send_whatsapp_nudge(to_phone: str, message: str) -> Dict[str, Any]:
    """
    Send a WhatsApp nudge via Twilio API or fallback to mock log.
    """
    if (
        settings.MOCK_DISPATCH
        or not settings.TWILIO_ACCOUNT_SID
        or not settings.TWILIO_AUTH_TOKEN
    ):
        mock_id = f"mock-wa-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MOCK WHATSAPP SENT] To: %s | ID: %s | Message: %s",
            to_phone,
            mock_id,
            message[:100],
        )
        return {
            "status": "mocked",
            "channel": "WHATSAPP",
            "message_id": mock_id,
            "recipient": to_phone,
            "details": "MOCK_DISPATCH enabled or TWILIO credentials missing",
        }

    try:
        from twilio.rest import Client

        from_number = settings.TWILIO_WHATSAPP_NUMBER
        if from_number and not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        to_number = (
            to_phone if to_phone.startswith("whatsapp:") else f"whatsapp:{to_phone}"
        )

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        res = client.messages.create(
            body=message,
            from_=from_number,
            to=to_number,
        )
        logger.info(
            "[WHATSAPP DISPATCHED] To: %s | SID: %s | Status: %s",
            to_number,
            res.sid,
            res.status,
        )
        return {
            "status": "sent",
            "channel": "WHATSAPP",
            "message_id": res.sid,
            "recipient": to_phone,
            "provider_status": res.status,
        }
    except Exception as exc:
        logger.error("[WHATSAPP DISPATCH FAILED] To: %s | Error: %s", to_phone, exc)
        return {
            "status": "failed",
            "channel": "WHATSAPP",
            "error": str(exc),
            "recipient": to_phone,
        }


def dispatch_nudge(
    case_id: str,
    channel: str,
    recipient: str,
    payload: Dict[str, Any],
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """
    Routes outreach nudge to appropriate channel dispatcher and appends audit log entry if db session provided.
    """
    ch_upper = channel.upper().strip()
    result: Dict[str, Any]

    if ch_upper == "EMAIL":
        subject = (
            payload.get("subject")
            or payload.get("message_subject")
            or "Payment Recovery Notice"
        )
        body = (
            payload.get("body_html")
            or payload.get("body")
            or payload.get("message_body")
            or payload.get("message", "")
        )
        result = send_email_nudge(to_email=recipient, subject=subject, body_html=body)
    elif ch_upper == "SMS":
        msg = (
            payload.get("message")
            or payload.get("message_body")
            or payload.get("body", "")
        )
        result = send_sms_nudge(to_phone=recipient, message=msg)
    elif ch_upper == "WHATSAPP":
        msg = (
            payload.get("message")
            or payload.get("message_body")
            or payload.get("body", "")
        )
        result = send_whatsapp_nudge(to_phone=recipient, message=msg)
    else:
        logger.warning("Unsupported channel for dispatch_nudge: %s", channel)
        result = {
            "status": "unsupported",
            "channel": channel,
            "error": f"Unsupported channel {channel}",
        }

    # Record AuditLog if db session is provided and case_id is set
    if db is not None and case_id:
        try:
            case_uuid = uuid.UUID(case_id) if isinstance(case_id, str) else case_id
            audit_log = AuditLog(
                case_id=case_uuid,
                event_type="NUDGE_DISPATCHED",
                actor="DISPATCHER",
                payload={
                    "channel": ch_upper,
                    "recipient": recipient,
                    "dispatch_result": result,
                    "message_id": result.get("message_id"),
                    "status": result.get("status"),
                },
                timestamp=datetime.now(timezone.utc),
            )
            db.add(audit_log)
            db.flush()
        except Exception as exc:
            logger.error("Failed to append audit log for case %s: %s", case_id, exc)

    return result
