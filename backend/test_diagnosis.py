"""
Standalone verification script for Diagnosis & Classification Engine.
"""
import sys
import os

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.diagnosis.classifier import diagnose_failure

def test_rule_based_diagnosis():
    print("--- Test 1: Rule-based Match ---")
    error_code = "BAD_REQUEST_PAYMENT_INSUFFICIENT_BALANCE"
    error_desc = "Customer account balance is insufficient"
    context = {}

    result = diagnose_failure(error_code, error_desc, context)
    print("Input Code:", error_code)
    print("Result:", result)

    assert result["source"] == "RULE_ENGINE", f"Expected RULE_ENGINE, got {result['source']}"
    assert result["root_cause"] == "INSUFFICIENT_FUNDS", f"Expected INSUFFICIENT_FUNDS, got {result['root_cause']}"
    assert result["confidence"] == 1.0, f"Expected confidence 1.0, got {result['confidence']}"
    print("PASSED: Rule-based diagnosis test passed.\n")


def test_ml_fallback_diagnosis():
    print("--- Test 2: ML Fallback Match ---")
    error_code = "UNKNOWN_GATEWAY_ERROR_999"
    error_desc = "An ambiguous gateway failure occurred"
    context = {
        "hour_of_day": 20,
        "amount": 12000.0,
        "retry_count": 3,
        "payment_method": "upi",
        "bank_code": "SBI"
    }

    result = diagnose_failure(error_code, error_desc, context)
    print("Input Code:", error_code)
    print("Context:", context)
    print("Result:", result)

    assert result["source"] == "ML_MODEL", f"Expected ML_MODEL, got {result['source']}"
    assert "root_cause" in result and result["root_cause"] is not None
    assert 0.0 <= result["confidence"] <= 1.0
    print("PASSED: ML fallback diagnosis test passed.\n")

if __name__ == "__main__":
    print("Running Diagnosis Engine Verification Suite...\n")
    test_rule_based_diagnosis()
    test_ml_fallback_diagnosis()
    print("All Diagnosis Engine tests completed successfully!")
