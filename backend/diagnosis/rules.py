"""
Deterministic gateway error code mapping rules.
"""
from typing import Dict, Any, Optional

# Mapping of explicit Razorpay / Gateway error codes to standardized root causes
RAZORPAY_ERROR_MAP = {
    "BAD_REQUEST_PAYMENT_INSUFFICIENT_BALANCE": "INSUFFICIENT_FUNDS",
    "BAD_REQUEST_PAYMENT_TIMED_OUT": "NETWORK_TIMEOUT",
    "BAD_REQUEST_PAYMENT_ACCOUNT_STAT_NOT_ACTIVE": "ACCOUNT_BLOCKED",
    "BAD_REQUEST_PAYMENT_CARD_HOLDER_AUTHENTICATION_FAILED": "AUTHENTICATION_FAILED",
}

def apply_rules(error_code: Optional[str], error_description: Optional[str] = "") -> Optional[Dict[str, Any]]:
    """
    Applies deterministic rules to classify payment failure root causes.

    Args:
        error_code: Gateway error code string (e.g. BAD_REQUEST_PAYMENT_INSUFFICIENT_BALANCE)
        error_description: Optional human readable error description string

    Returns:
        dict containing root_cause, confidence, source if matched, else None.
    """
    if not error_code and not error_description:
        return None

    code_upper = (error_code or "").strip().upper()
    desc_upper = (error_description or "").strip().upper()

    # Exact match on error_code
    if code_upper in RAZORPAY_ERROR_MAP:
        return {
            "root_cause": RAZORPAY_ERROR_MAP[code_upper],
            "confidence": 1.0,
            "source": "RULE_ENGINE"
        }

    # Substring / fuzzy search in code or description
    for key, root_cause in RAZORPAY_ERROR_MAP.items():
        if key in code_upper or key in desc_upper:
            return {
                "root_cause": root_cause,
                "confidence": 1.0,
                "source": "RULE_ENGINE"
            }

    return None
