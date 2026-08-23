"""
backend/test_dashboard.py
──────────────────────────
Integration test script for the AI Revenue Recovery dashboard API.

Spins up the FastAPI app with TestClient, seeds dummy DB records,
then exercises all four dashboard endpoints and asserts response structure.

Run:
  python backend/test_dashboard.py
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import date, datetime, timezone

# ── Bootstrap: project root on sys.path ───────────────────────────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Force UTF-8 on Windows to avoid cp1252 UnicodeEncodeError
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi.testclient import TestClient
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.database import sync_session
from backend.main import app
from backend.models import AuditLog, Customer, Intervention, RecoveryMetric, RevenueCase

# ── Colour helpers ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"
_SEP   = "=" * 60

def _ok(msg: str):   print(f"  {GREEN}[OK]   {msg}{RESET}")
def _fail(msg: str): print(f"  {RED}[FAIL] {msg}{RESET}")
def _info(msg: str): print(f"  {YELLOW}[INFO] {msg}{RESET}")


# ── Seed helpers ───────────────────────────────────────────────────────────────

TEST_EMAIL = f"dash_test_{int(time.time())}@example.com"

def _seed_data() -> str:
    """
    Insert one Customer, one RevenueCase (PENDING), one RevenueCase (RECOVERED),
    one Intervention, one AuditLog, and one RecoveryMetric.

    Returns the UUID string of the PENDING case for later lookup tests.
    """
    with sync_session() as session:
        # Customer
        customer = Customer(
            name="Dashboard Test User",
            email=TEST_EMAIL,
            phone="+919000000001",
        )
        session.add(customer)
        session.flush()

        # PENDING case
        pending_case = RevenueCase(
            customer_id=customer.id,
            razorpay_payment_id=f"pay_dash_{int(time.time())}",
            razorpay_order_id=f"ord_dash_{int(time.time())}",
            amount=1499.0,
            currency="INR",
            status="PENDING",
            risk_level="HIGH",
            failure_reason="Insufficient funds",
        )
        session.add(pending_case)
        session.flush()

        # RECOVERED case
        recovered_case = RevenueCase(
            customer_id=customer.id,
            amount=999.0,
            currency="INR",
            status="RECOVERED",
            risk_level="LOW",
        )
        session.add(recovered_case)
        session.flush()

        # Intervention for pending case
        intervention = Intervention(
            case_id=pending_case.id,
            channel="EMAIL",
            status="SENT",
            message_content="Dear customer, your payment failed. Please retry.",
            sent_at=datetime.now(timezone.utc),
        )
        session.add(intervention)

        # AuditLog for pending case
        audit_log = AuditLog(
            case_id=pending_case.id,
            event_type="CASE_CREATED",
            actor="SYSTEM",
            payload={"source": "dashboard_test", "amount": 1499.0},
            timestamp=datetime.now(timezone.utc),
        )
        session.add(audit_log)

        # RecoveryMetric row — upsert on unique date
        stmt = (
            pg_insert(RecoveryMetric)
            .values(
                id=uuid.uuid4(),
                date=date.today(),
                total_at_risk=1499.0,
                total_recovered=999.0,
                successful_recoveries=1,
                failed_recoveries=0,
            )
            .on_conflict_do_update(
                index_elements=["date"],
                set_={
                    "total_at_risk": 1499.0,
                    "total_recovered": 999.0,
                    "successful_recoveries": 1,
                    "failed_recoveries": 0,
                },
            )
        )
        session.execute(stmt)

        pending_case_id = str(pending_case.id)

    return pending_case_id


# ── TestClient ─────────────────────────────────────────────────────────────────

client = TestClient(app, raise_server_exceptions=True)


# ── Test functions ─────────────────────────────────────────────────────────────

def test_metrics_summary(errors: list[str]) -> None:
    """GET /api/metrics/summary — assert JSON structure and non-negative values."""
    print(f"\n{BOLD}[1/4] GET /api/metrics/summary{RESET}")
    resp = client.get("/api/metrics/summary")

    if resp.status_code == 200:
        _ok(f"HTTP 200 OK")
    else:
        _fail(f"HTTP {resp.status_code}: {resp.text}")
        errors.append("metrics/summary: non-200 status")
        return

    data = resp.json()
    required_keys = {
        "total_at_risk_amount",
        "total_recovered_amount",
        "recovery_rate_pct",
        "active_cases_count",
        "recovered_cases_count",
    }
    missing = required_keys - set(data.keys())
    if missing:
        _fail(f"Missing keys: {missing}")
        errors.append(f"metrics/summary: missing keys {missing}")
    else:
        _ok(f"All required keys present")

    if isinstance(data.get("recovery_rate_pct"), (int, float)):
        rate = data["recovery_rate_pct"]
        if 0.0 <= rate <= 100.0:
            _ok(f"recovery_rate_pct={rate} (valid 0–100 range)")
        else:
            _fail(f"recovery_rate_pct={rate} out of 0–100 range")
            errors.append("metrics/summary: recovery_rate_pct out of range")
    else:
        _fail("recovery_rate_pct is not a number")
        errors.append("metrics/summary: recovery_rate_pct type error")

    _info(f"Payload: {data}")


def test_list_cases(errors: list[str]) -> None:
    """GET /api/cases — assert non-empty paginated list with required fields."""
    print(f"\n{BOLD}[2/4] GET /api/cases{RESET}")
    resp = client.get("/api/cases")

    if resp.status_code == 200:
        _ok("HTTP 200 OK")
    else:
        _fail(f"HTTP {resp.status_code}: {resp.text}")
        errors.append("cases: non-200 status")
        return

    data = resp.json()
    for key in ("total", "limit", "offset", "items"):
        if key not in data:
            _fail(f"Missing top-level key: {key!r}")
            errors.append(f"cases: missing key {key!r}")

    items = data.get("items", [])
    if items:
        _ok(f"Returned {len(items)} case(s) (total={data.get('total')})")
    else:
        _fail("items list is empty — expected at least one seeded case")
        errors.append("cases: empty items list")
        return

    # Validate first item fields
    first = items[0]
    for field in ("id", "amount", "currency", "status", "risk_level", "created_at"):
        if field not in first:
            _fail(f"Case item missing field: {field!r}")
            errors.append(f"cases: item missing field {field!r}")
        else:
            _ok(f"Field {field!r} present: {first[field]!r}")

    # Filter by status
    resp_filtered = client.get("/api/cases?status=PENDING")
    if resp_filtered.status_code == 200:
        filtered_data = resp_filtered.json()
        _ok(f"Status filter works: {filtered_data.get('total')} PENDING case(s)")
    else:
        _fail(f"Status filter returned {resp_filtered.status_code}")
        errors.append("cases: status filter failed")


def test_case_detail(case_id: str, errors: list[str]) -> None:
    """GET /api/cases/{case_id} — assert joined customer and audit_logs."""
    print(f"\n{BOLD}[3/4] GET /api/cases/{case_id}{RESET}")
    resp = client.get(f"/api/cases/{case_id}")

    if resp.status_code == 200:
        _ok("HTTP 200 OK")
    else:
        _fail(f"HTTP {resp.status_code}: {resp.text}")
        errors.append(f"cases/{case_id}: non-200 status")
        return

    data = resp.json()

    # UUID round-trip
    if data.get("id") == case_id:
        _ok(f"id matches: {data['id']}")
    else:
        _fail(f"id mismatch: got {data.get('id')!r}")
        errors.append("case detail: id mismatch")

    # Customer
    customer = data.get("customer")
    if customer:
        _ok(f"customer joined: email={customer.get('email')!r}")
    else:
        _fail("customer is null — eager load failed")
        errors.append("case detail: customer not loaded")

    # Interventions list
    interventions = data.get("interventions", [])
    if interventions:
        _ok(f"interventions loaded: {len(interventions)} record(s)")
        first_iv = interventions[0]
        if "message_payload" in first_iv:
            _ok(f"message_payload field present: {first_iv['message_payload']!r}")
        else:
            _fail("message_payload missing in intervention")
            errors.append("case detail: intervention missing message_payload")
    else:
        _fail("interventions list is empty — expected 1 seeded record")
        errors.append("case detail: no interventions loaded")

    # Audit logs
    audit_logs = data.get("audit_logs", [])
    if audit_logs:
        _ok(f"audit_logs loaded: {len(audit_logs)} record(s)")
        first_al = audit_logs[0]
        for field in ("event", "actor", "created_at"):
            if field in first_al:
                _ok(f"AuditLog field {field!r}: {first_al[field]!r}")
            else:
                _fail(f"AuditLog missing field: {field!r}")
                errors.append(f"case detail: audit_log missing {field!r}")
    else:
        _fail("audit_logs list is empty — expected 1 seeded record")
        errors.append("case detail: no audit_logs loaded")

    # 404 for unknown UUID
    fake_id = str(uuid.uuid4())
    resp404 = client.get(f"/api/cases/{fake_id}")
    if resp404.status_code == 404:
        _ok("404 returned for unknown case_id")
    else:
        _fail(f"Expected 404 for unknown id, got {resp404.status_code}")
        errors.append("case detail: missing 404 for unknown id")


def test_list_interventions(errors: list[str]) -> None:
    """GET /api/interventions — assert list with expected fields."""
    print(f"\n{BOLD}[4/4] GET /api/interventions{RESET}")
    resp = client.get("/api/interventions")

    if resp.status_code == 200:
        _ok("HTTP 200 OK")
    else:
        _fail(f"HTTP {resp.status_code}: {resp.text}")
        errors.append("interventions: non-200 status")
        return

    data = resp.json()
    if not isinstance(data, list):
        _fail("Expected JSON array")
        errors.append("interventions: response is not a list")
        return

    if data:
        _ok(f"Returned {len(data)} intervention(s)")
        first = data[0]
        for field in ("id", "channel", "status", "message_payload"):
            if field in first:
                _ok(f"Field {field!r} present")
            else:
                _fail(f"Missing field: {field!r}")
                errors.append(f"interventions: missing field {field!r}")
    else:
        _fail("Interventions list is empty — expected at least 1 seeded record")
        errors.append("interventions: empty list")


# ── Summary ────────────────────────────────────────────────────────────────────

def _summary(errors: list[str]) -> None:
    print(f"\n{BOLD}{_SEP}{RESET}")
    if not errors:
        print(f"{GREEN}{BOLD}  ALL ASSERTIONS PASSED -- Dashboard API is operational [OK]{RESET}")
        print(f"{BOLD}{_SEP}{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}  FAILURES ({len(errors)}):{RESET}")
        for e in errors:
            print(f"    {RED}* {e}{RESET}")
        print(f"{BOLD}{_SEP}{RESET}\n")
        sys.exit(1)


# ── Main ───────────────────────────────────────────────────────────────────────

def run_tests() -> None:
    print(f"\n{BOLD}{_SEP}{RESET}")
    print(f"{BOLD}  AI Revenue Recovery -- Dashboard API Integration Tests{RESET}")
    print(f"{BOLD}{_SEP}{RESET}")

    errors: list[str] = []

    # Seed dummy data once
    print(f"\n{BOLD}[SETUP] Seeding dummy database records…{RESET}")
    try:
        case_id = _seed_data()
        _ok(f"Seeded PENDING case: {case_id}")
    except Exception as exc:
        _fail(f"DB seeding failed: {exc}")
        errors.append(f"setup: db seed failed — {exc}")
        _summary(errors)
        return

    # Run all endpoint tests
    test_metrics_summary(errors)
    test_list_cases(errors)
    test_case_detail(case_id, errors)
    test_list_interventions(errors)

    _summary(errors)


if __name__ == "__main__":
    run_tests()
