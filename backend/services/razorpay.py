"""
backend/services/razorpay.py
─────────────────────────────
Live Razorpay Payment Link Service.

Generates dynamic Razorpay Payment Links for AI Recovery Agent outreach.
"""

import logging
import razorpay
from backend.config import settings

logger = logging.getLogger(__name__)


def generate_payment_link(case_id: str, amount: float, email: str) -> str:
    """
    Generate a Razorpay Payment Link for a specific revenue recovery case.

    :param case_id: UUID string of the RevenueCase
    :param amount: Recovery amount in INR (converted to paise internally)
    :param email: Customer email address
    :return: Generated payment short URL (e.g., https://rzp.io/i/xxxx)
    """
    key_id = settings.RAZORPAY_KEY_ID or settings.RZP_KEY
    key_secret = settings.RAZORPAY_KEY_SECRET or settings.RZP_SECRET

    # Fallback for mock environment or missing keys
    if not key_id or key_id.startswith("rzp_test_mock"):
        logger.info("[Razorpay Service] Using mock payment link for case %s", case_id[:8])
        return f"https://rzp.io/i/mock_{str(case_id)[:8]}"

    try:
        client = razorpay.Client(auth=(key_id, key_secret))
        amount_paise = int(round(amount * 100))

        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": f"Payment Recovery for Case {case_id}",
            "customer": {
                "email": email,
            },
            "notify": {
                "email": True,
                "sms": True,
            },
            "reminder_enable": True,
            "notes": {
                "case_id": str(case_id),
            },
            "callback_url": f"{settings.BASE_URL}/api/webhooks/razorpay",
            "callback_method": "get",
        }

        res = client.payment_link.create(payload)
        short_url = res.get("short_url")
        if short_url:
            logger.info("[Razorpay Service] Created payment link %s for case %s", short_url, case_id[:8])
            return short_url
        
        fallback_url = f"https://rzp.io/i/mock_{str(case_id)[:8]}"
        logger.warning("[Razorpay Service] short_url missing in response, using fallback %s", fallback_url)
        return fallback_url

    except Exception as exc:
        logger.error("[Razorpay Service] Error generating payment link for case %s: %s", case_id[:8], exc)
        return f"https://rzp.io/i/mock_{str(case_id)[:8]}"
