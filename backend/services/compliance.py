"""
backend/services/compliance.py
─────────────────────────────
Compliance service wrapper re-exporting compliance checks from agent logic.
"""
from backend.agent.compliance import check_compliance

__all__ = ["check_compliance"]
