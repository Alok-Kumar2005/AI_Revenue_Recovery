"""
backend/execution/nudges.py
────────────────────────────
Free Live & Mock messaging dispatchers:
- Email: Gmail SMTP with TLS and PDF attachments
- WhatsApp: CallMeBot API
- SMS / Push Alerts: Telegram Bot API

Handles dispatching messages and appending dispatch metadata / message IDs
to the case audit logs (AuditLog).
"""

import base64
import logging
import smtplib
import urllib.parse
import uuid
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, Optional
import httpx
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models import AuditLog

logger = logging.getLogger(__name__)


def send_email_nudge(
    to_email: str,
    subject: str,
    body_html: str,
    case_id: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Send an email nudge via Gmail SMTP (with optional PDF attachment) or fallback to mock log.
    Uses TLS connection on port 587 with SMTP_USER and SMTP_PASSWORD.
    """
    filename = f"Demand_Letter_{case_id[:8].upper()}.pdf" if case_id else "Demand_Letter.pdf"
    has_pdf = bool(pdf_bytes)

    if settings.MOCK_DISPATCH or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        mock_id = f"mock-email-{uuid.uuid4().hex[:8]}"
        attachment_note = f" [PDF attached: {filename}]" if has_pdf else ""
        logger.info(
            "[MOCK EMAIL SENT] To: %s | Subject: %s | ID: %s | Body: %s%s",
            to_email,
            subject,
            mock_id,
            body_html[:100],
            attachment_note,
        )
        return {
            "status": "mocked",
            "channel": "EMAIL",
            "message_id": mock_id,
            "recipient": to_email,
            "subject": subject,
            "pdf_attached": has_pdf,
            "details": "MOCK_DISPATCH enabled or SMTP credentials missing",
        }

    try:
        # Create multipart message container
        msg = MIMEMultipart("mixed")
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Message-ID"] = f"<smtp-{uuid.uuid4().hex[:12]}@{settings.SMTP_HOST}>"

        # HTML body
        msg_body = MIMEMultipart("alternative")
        html_part = MIMEText(body_html, "html", "utf-8")
        msg_body.attach(html_part)
        msg.attach(msg_body)

        # Attach PDF if available
        if pdf_bytes:
            pdf_attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
            pdf_attachment.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename,
            )
            msg.attach(pdf_attachment)

        # Connect to SMTP server via TLS
        smtp_port = int(settings.SMTP_PORT) if settings.SMTP_PORT else 587
        with smtplib.SMTP(settings.SMTP_HOST, smtp_port, timeout=15.0) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)

        message_id = msg["Message-ID"]
        logger.info(
            "[EMAIL DISPATCHED VIA GMAIL SMTP] To: %s | ID: %s | PDF Attached: %s",
            to_email,
            message_id,
            has_pdf,
        )
        return {
            "status": "sent",
            "channel": "EMAIL",
            "message_id": message_id,
            "recipient": to_email,
            "subject": subject,
            "pdf_attached": has_pdf,
            "details": f"Sent via {settings.SMTP_HOST}:{smtp_port}",
        }
    except Exception as exc:
        logger.error("[EMAIL DISPATCH FAILED] To: %s | Error: %s", to_email, exc)
        return {
            "status": "failed",
            "channel": "EMAIL",
            "error": str(exc),
            "recipient": to_email,
        }


def send_sms_nudge(
    to_phone: str,
    message: str,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send an SMS / Mobile Alert nudge via Telegram Bot API or fallback to mock log.
    When case_id is provided, a secure PDF download link is appended.
    """
    # Append PDF link to message if case_id is set
    formatted_message = message
    if case_id:
        base_url = settings.BASE_URL.rstrip("/")
        pdf_link = f"{base_url}/api/cases/{case_id}/pdf"
        formatted_message = f"{message}\n\n📄 Download demand letter: {pdf_link}"

    # Prepend recipient notice for Telegram alert clarity
    telegram_text = f"📱 [SMS ALERT FOR {to_phone}]\n\n{formatted_message}"

    if (
        settings.MOCK_DISPATCH
        or not settings.TELEGRAM_BOT_TOKEN
        or not settings.TELEGRAM_CHAT_ID
    ):
        mock_id = f"mock-telegram-sms-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MOCK SMS / TELEGRAM SENT] To: %s | ID: %s | Message: %s",
            to_phone,
            mock_id,
            formatted_message[:160],
        )
        return {
            "status": "mocked",
            "channel": "SMS",
            "message_id": mock_id,
            "recipient": to_phone,
            "details": "MOCK_DISPATCH enabled or Telegram Bot credentials missing",
        }

    try:
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": str(settings.TELEGRAM_CHAT_ID),
            "text": telegram_text,
        }
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            res_data = resp.json()

        if resp.status_code == 200 and res_data.get("ok"):
            msg_id = res_data.get("result", {}).get("message_id", uuid.uuid4().hex[:8])
            full_msg_id = f"tg-{msg_id}"
            logger.info(
                "[SMS/ALERT DISPATCHED VIA TELEGRAM] To: %s | Chat: %s | ID: %s",
                to_phone,
                settings.TELEGRAM_CHAT_ID,
                full_msg_id,
            )
            return {
                "status": "sent",
                "channel": "SMS",
                "message_id": full_msg_id,
                "recipient": to_phone,
                "telegram_chat_id": settings.TELEGRAM_CHAT_ID,
                "provider_status": "delivered",
            }
        else:
            err_desc = res_data.get("description", resp.text)
            logger.error("[TELEGRAM SMS ERROR] Status: %s | Error: %s", resp.status_code, err_desc)
            return {
                "status": "failed",
                "channel": "SMS",
                "error": err_desc,
                "recipient": to_phone,
            }
    except Exception as exc:
        logger.error("[SMS DISPATCH FAILED] To: %s | Error: %s", to_phone, exc)
        return {
            "status": "failed",
            "channel": "SMS",
            "error": str(exc),
            "recipient": to_phone,
        }


def send_whatsapp_nudge(
    to_phone: str,
    message: str,
    case_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a WhatsApp nudge via CallMeBot API or fallback to mock log.
    When case_id is provided, a PDF download link is appended.
    """
    formatted_message = message
    if case_id:
        base_url = settings.BASE_URL.rstrip("/")
        pdf_link = f"{base_url}/api/cases/{case_id}/pdf"
        formatted_message = f"{message}\n\n📄 View/download your demand letter: {pdf_link}"

    # Determine target phone number for CallMeBot
    # Strip whatsapp: prefix if present
    target_phone = to_phone.replace("whatsapp:", "").strip()
    if not target_phone or target_phone.startswith("mock-") or target_phone == "unknown":
        target_phone = settings.CALLMEBOT_PHONE or "+918090175358"

    if (
        settings.MOCK_DISPATCH
        or not settings.CALLMEBOT_API_KEY
    ):
        mock_id = f"mock-wa-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MOCK WHATSAPP SENT] To: %s | ID: %s | Message: %s",
            to_phone,
            mock_id,
            formatted_message[:160],
        )
        return {
            "status": "mocked",
            "channel": "WHATSAPP",
            "message_id": mock_id,
            "recipient": to_phone,
            "details": "MOCK_DISPATCH enabled or CALLMEBOT_API_KEY missing",
        }

    try:
        encoded_msg = urllib.parse.quote(formatted_message)
        url = (
            f"https://api.callmebot.com/whatsapp.php?"
            f"phone={target_phone}&text={encoded_msg}&apikey={settings.CALLMEBOT_API_KEY}"
        )

        with httpx.Client(timeout=15.0) as client:
            resp = client.get(url)

        # CallMeBot returns 200 with text confirmation or error inside response body
        if resp.status_code == 200:
            resp_text = resp.text
            if "error" in resp_text.lower() or "invalid" in resp_text.lower():
                logger.error("[CALLMEBOT ERROR RESPONSE] %s", resp_text)
                return {
                    "status": "failed",
                    "channel": "WHATSAPP",
                    "error": resp_text,
                    "recipient": to_phone,
                }

            msg_id = f"callmebot-{uuid.uuid4().hex[:8]}"
            logger.info(
                "[WHATSAPP DISPATCHED VIA CALLMEBOT] To: %s | ID: %s",
                target_phone,
                msg_id,
            )
            return {
                "status": "sent",
                "channel": "WHATSAPP",
                "message_id": msg_id,
                "recipient": to_phone,
                "provider_response": resp_text[:200],
            }
        else:
            logger.error("[CALLMEBOT HTTP ERROR] Status: %s | Body: %s", resp.status_code, resp.text)
            return {
                "status": "failed",
                "channel": "WHATSAPP",
                "error": f"HTTP {resp.status_code}: {resp.text}",
                "recipient": to_phone,
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
    Routes outreach nudge to appropriate channel dispatcher and appends audit log
    entry if db session provided.

    For EMAIL channel: generates and attaches a demand-letter PDF.
    For SMS/WHATSAPP channels: appends a PDF download link to the message.
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
        # Generate demand-letter PDF to attach
        pdf_bytes: Optional[bytes] = None
        if db is not None and case_id:
            try:
                from backend.models import Customer, RevenueCase
                from backend.services.pdf_generator import generate_demand_letter_pdf
                case_uuid = uuid.UUID(case_id) if isinstance(case_id, str) else case_id
                case_obj = db.query(RevenueCase).filter(RevenueCase.id == case_uuid).first()
                if case_obj:
                    customer_obj = case_obj.customer
                    if customer_obj is None:
                        customer_obj = Customer(
                            name="Unknown Customer",
                            email=recipient,
                            phone=None,
                        )
                        customer_obj.id = case_obj.customer_id  # type: ignore[assignment]
                    buf = generate_demand_letter_pdf(case=case_obj, customer=customer_obj)
                    pdf_bytes = buf.read()
            except Exception as pdf_exc:
                logger.warning("[PDF ATTACH FAILED] case=%s error=%s", case_id, pdf_exc)

        result = send_email_nudge(
            to_email=recipient,
            subject=subject,
            body_html=body,
            case_id=case_id,
            pdf_bytes=pdf_bytes,
        )
    elif ch_upper == "SMS":
        msg = (
            payload.get("message")
            or payload.get("message_body")
            or payload.get("body", "")
        )
        result = send_sms_nudge(to_phone=recipient, message=msg, case_id=case_id)
    elif ch_upper == "WHATSAPP":
        msg = (
            payload.get("message")
            or payload.get("message_body")
            or payload.get("body", "")
        )
        result = send_whatsapp_nudge(to_phone=recipient, message=msg, case_id=case_id)
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
                    "pdf_attached": result.get("pdf_attached", False),
                },
                timestamp=datetime.now(timezone.utc),
            )
            db.add(audit_log)
            db.flush()
        except Exception as exc:
            logger.error("Failed to append audit log for case %s: %s", case_id, exc)

    return result

