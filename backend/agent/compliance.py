from datetime import datetime, timezone, timedelta
from typing import Dict, Any


def check_compliance(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforces hard business & regulatory stopping rules.

    Rule 1 (Max Attempts): If retry_count >= 3 -> action: "STOP", reason: "MAX_ATTEMPTS_REACHED"
    Rule 2 (Minimum Amount): If amount < 100.0 -> action: "LOG_ONLY", reason: "AMOUNT_BELOW_THRESHOLD"
    Rule 3 (DND Hours): If current IST time is between 22:00 and 08:00 -> action: "DELAY", reason: "NIGHT_DND_WINDOW"

    Returns {"is_compliant": bool, "forced_action": str | None, "reason": str}
    """
    retry_count = case.get("retry_count", case.get("attempts", 0))
    amount = float(case.get("amount", 0.0))

    # Rule 1: Max Attempts
    if retry_count >= 3:
        return {
            "is_compliant": False,
            "forced_action": "STOP",
            "reason": "MAX_ATTEMPTS_REACHED",
        }

    # Rule 2: Minimum Amount
    if amount < 100.0:
        return {
            "is_compliant": False,
            "forced_action": "LOG_ONLY",
            "reason": "AMOUNT_BELOW_THRESHOLD",
        }

    # Rule 3: DND Hours (22:00 - 08:00 IST, UTC+5:30)
    ist_tz = timezone(timedelta(hours=5, minutes=30))
    # Allow optional override in case dictionary for deterministic testing
    if "current_time_ist" in case and isinstance(case["current_time_ist"], datetime):
        now_ist = case["current_time_ist"]
    else:
        now_ist = datetime.now(ist_tz)

    current_hour = now_ist.hour
    if current_hour >= 22 or current_hour < 8:
        return {
            "is_compliant": False,
            "forced_action": "DELAY",
            "reason": "NIGHT_DND_WINDOW",
        }

    return {
        "is_compliant": True,
        "forced_action": None,
        "reason": "COMPLIANT",
    }
