import logging
from typing import Dict, Any

logger = logging.getLogger("agent.tools")


def send_email(recipient: str, subject: str, body: str) -> Dict[str, Any]:
    """Mock wrapper for sending email outreach."""
    logger.info(f"[TOOL: EMAIL] To: {recipient} | Subject: {subject}")
    return {
        "status": "SUCCESS",
        "channel": "EMAIL",
        "recipient": recipient,
        "subject": subject,
        "body": body,
    }


def send_sms(phone: str, message: str) -> Dict[str, Any]:
    """Mock wrapper for sending SMS outreach."""
    logger.info(f"[TOOL: SMS] To: {phone} | Message: {message}")
    return {
        "status": "SUCCESS",
        "channel": "SMS",
        "phone": phone,
        "message": message,
    }


def send_whatsapp(phone: str, message: str) -> Dict[str, Any]:
    """Mock wrapper for sending WhatsApp message."""
    logger.info(f"[TOOL: WHATSAPP] To: {phone} | Message: {message}")
    return {
        "status": "SUCCESS",
        "channel": "WHATSAPP",
        "phone": phone,
        "message": message,
    }


def trigger_payment_retry(transaction_id: str) -> Dict[str, Any]:
    """Mock wrapper for initiating automated payment retry."""
    logger.info(f"[TOOL: RETRY] Transaction ID: {transaction_id}")
    return {
        "status": "INITIATED",
        "channel": "RETRY_PAYMENT",
        "transaction_id": transaction_id,
    }


def escalate_to_support(case_id: str, reason: str) -> Dict[str, Any]:
    """Mock wrapper for escalating case to customer support agent."""
    logger.info(f"[TOOL: ESCALATE] Case ID: {case_id} | Reason: {reason}")
    return {
        "status": "ESCALATED",
        "channel": "ESCALATE",
        "case_id": case_id,
        "reason": reason,
    }


def execute_recovery_action(channel: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatcher tool that routes the decision to the corresponding tool handler.
    """
    ch = channel.upper()
    if ch == "EMAIL":
        return send_email(
            recipient=payload.get("customer_email", "customer@example.com"),
            subject=payload.get("message_subject", "Payment Nudge"),
            body=payload.get("message_body", ""),
        )
    elif ch == "SMS":
        return send_sms(
            phone=payload.get("customer_phone", "+919999999999"),
            message=payload.get("message_body", ""),
        )
    elif ch == "WHATSAPP":
        return send_whatsapp(
            phone=payload.get("customer_phone", "+919999999999"),
            message=payload.get("message_body", ""),
        )
    elif ch == "RETRY_PAYMENT":
        return trigger_payment_retry(
            transaction_id=payload.get("transaction_id", "TXN_UNKNOWN")
        )
    elif ch == "ESCALATE":
        return escalate_to_support(
            case_id=payload.get("case_id", "CASE_UNKNOWN"),
            reason=payload.get("reasoning", "Escalated by AI Agent"),
        )
    else:
        return {
            "status": "SKIPPED",
            "channel": channel,
            "message": f"No execution required for channel {channel}",
        }
