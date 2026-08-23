"""
backend/test_webhook.py
────────────────────────
End-to-end verification test for the Razorpay webhook pipeline.

Simulates a Razorpay payment.failed webhook payload, sends it to the
FastAPI app via TestClient, then verifies all four DB rows are created:
  ✅ Customer
  ✅ RevenueCase
  ✅ Intervention
  ✅ AuditLog

Run:
  python backend/test_webhook.py
"""

import hashlib
import hmac
import json
import sys
import time
from datetime import datetime, timezone

# ── Bootstrap: ensure project root is on sys.path ─────────────────────────────
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force UTF-8 output on Windows to avoid cp1252 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings
from backend.database import sync_session
from backend.models import AuditLog, Customer, Intervention, RevenueCase

# ── Test client ────────────────────────────────────────────────────────────────
client = TestClient(app, raise_server_exceptions=True)

# ── Synthetic Razorpay payload ─────────────────────────────────────────────────
TEST_EMAIL = f"test_webhook_{int(time.time())}@example.com"
TEST_NAME  = "Webhook Test User"
TEST_PHONE = "+919999000001"

PAYLOAD = {
    "event": "payment.failed",
    "account_id": "acc_test_123",
    "contains": ["payment"],
    "payload": {
        "payment": {
            "entity": {
                "id": f"pay_test_{int(time.time())}",
                "order_id": f"order_test_{int(time.time())}",
                "amount": 49900,          # ₹499.00 in paise
                "currency": "INR",
                "email": TEST_EMAIL,
                "contact": TEST_PHONE,
                "notes": {
                    "name": TEST_NAME,
                },
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Payment processing failed due to insufficient funds",
                "method": "upi",
                "status": "failed",
                "created_at": int(datetime.now(timezone.utc).timestamp()),
            }
        }
    },
}

RAW_BODY = json.dumps(PAYLOAD).encode("utf-8")


def _make_signature(secret: str, body: bytes) -> str:
    """Compute HMAC-SHA256 signature exactly as Razorpay does."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_SEP = "=" * 55   # ASCII separator — safe on any Windows codepage

def _ok(msg: str):   print(f"  {GREEN}[OK]  {msg}{RESET}")
def _fail(msg: str): print(f"  {RED}[FAIL] {msg}{RESET}")
def _info(msg: str): print(f"  {YELLOW}[INFO] {msg}{RESET}")


def run_test():
    print(f"\n{BOLD}{_SEP}{RESET}")
    print(f"{BOLD}  AI Revenue Recovery -- Webhook Pipeline E2E Test{RESET}")
    print(f"{BOLD}{_SEP}{RESET}\n")

    errors: list[str] = []

    # ── Step 1: Send webhook ──────────────────────────────────────────────────
    print(f"{BOLD}[1/5] Sending POST /webhook/razorpay …{RESET}")
    secret = settings.RZP_WEBHOOK_SECRET
    signature = _make_signature(secret, RAW_BODY)

    response = client.post(
        "/webhook/razorpay",
        content=RAW_BODY,
        headers={
            "Content-Type": "application/json",
            "X-Razorpay-Signature": signature,
        },
    )

    if response.status_code == 200:
        _ok(f"HTTP 200 OK — response: {response.json()}")
    else:
        _fail(f"Unexpected HTTP {response.status_code}: {response.text}")
        errors.append("HTTP status != 200")

    data = response.json() if response.status_code == 200 else {}
    if data.get("status") == "queued":
        _ok("Response contains status=queued")
    else:
        _fail(f"Expected status=queued, got: {data.get('status')!r}")
        errors.append("status != queued")

    case_id: str = data.get("case_id", "")
    if case_id:
        _ok(f"case_id returned: {case_id}")
    else:
        _fail("No case_id in response")
        errors.append("missing case_id")

    if not case_id:
        _summary(errors)
        return

    # ── Step 2: Verify Customer ───────────────────────────────────────────────
    print(f"\n{BOLD}[2/5] Verifying Customer row …{RESET}")
    with sync_session() as session:
        customer = session.query(Customer).filter(Customer.email == TEST_EMAIL).first()
    if customer:
        _ok(f"Customer found: id={customer.id}  email={customer.email}")
    else:
        _fail(f"Customer NOT found for email={TEST_EMAIL}")
        errors.append("Customer row missing")

    # ── Step 3: Verify RevenueCase ────────────────────────────────────────────
    print(f"\n{BOLD}[3/5] Verifying RevenueCase row …{RESET}")
    with sync_session() as session:
        case = session.query(RevenueCase).filter(RevenueCase.id == case_id).first()
    if case:
        _ok(f"RevenueCase found: id={case.id}  status={case.status}  root_cause={case.root_cause}")
        if case.status in ("PENDING", "RECOVERED", "FAILED", "DELAYED"):
            _ok(f"status value '{case.status}' is valid")
        else:
            _fail(f"Unexpected status: {case.status}")
            errors.append(f"Unexpected RevenueCase status: {case.status}")
    else:
        _fail(f"RevenueCase NOT found for id={case_id}")
        errors.append("RevenueCase row missing")

    # ── Step 4: Verify Intervention ───────────────────────────────────────────
    print(f"\n{BOLD}[4/5] Verifying Intervention row …{RESET}")
    with sync_session() as session:
        intervention = (
            session.query(Intervention)
            .filter(Intervention.case_id == case_id)
            .first()
        )
    if intervention:
        _ok(
            f"Intervention found: id={intervention.id}  "
            f"channel={intervention.channel}  status={intervention.status}"
        )
    else:
        _fail(f"Intervention NOT found for case_id={case_id}")
        errors.append("Intervention row missing")

    # ── Step 5: Verify AuditLog ───────────────────────────────────────────────
    print(f"\n{BOLD}[5/5] Verifying AuditLog row …{RESET}")
    with sync_session() as session:
        audit = (
            session.query(AuditLog)
            .filter(AuditLog.case_id == case_id)
            .first()
        )
    if audit:
        _ok(
            f"AuditLog found: id={audit.id}  "
            f"event={audit.event_type}  actor={audit.actor}"
        )
        if audit.payload:
            _ok("AuditLog payload is populated")
        else:
            _info("AuditLog payload is empty (non-critical)")
    else:
        _fail(f"AuditLog NOT found for case_id={case_id}")
        errors.append("AuditLog row missing")

    _summary(errors)


def _summary(errors: list[str]):
    print(f"\n{BOLD}{_SEP}{RESET}")
    if not errors:
        print(f"{GREEN}{BOLD}  ALL ASSERTIONS PASSED -- Pipeline is operational [OK]{RESET}")
        print(f"{BOLD}{_SEP}{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}  FAILURES ({len(errors)}):{RESET}")
        for e in errors:
            print(f"    {RED}* {e}{RESET}")
        print(f"{BOLD}{_SEP}{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    run_test()
