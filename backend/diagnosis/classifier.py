"""
Main Diagnosis Entry Point (Rules -> ML Model fallback).
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Any, Optional

from backend.diagnosis.rules import apply_rules

_MODEL_PIPELINE = None


def get_model_path() -> str:
    """Returns absolute path to trained classifier artifact."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "models", "classifier.joblib")


def load_classifier():
    """
    Loads or retrieves cached ML classifier pipeline.
    Trains model if model file does not exist.
    """
    global _MODEL_PIPELINE
    if _MODEL_PIPELINE is not None:
        return _MODEL_PIPELINE

    # Lazy-import heavy ML modules only when model loading is required
    import joblib
    from backend.diagnosis.train import train_model

    model_path = get_model_path()
    if not os.path.exists(model_path):
        print(f"Model file not found at {model_path}. Training new model...")
        _MODEL_PIPELINE = train_model(save_path=model_path)
    else:
        try:
            _MODEL_PIPELINE = joblib.load(model_path)
        except Exception as exc:
            print(f"Failed to load classifier model from {model_path} ({exc}). Retraining model with current scikit-learn version...")
            _MODEL_PIPELINE = train_model(save_path=model_path)
    
    return _MODEL_PIPELINE


def diagnose_failure(
    error_code: Optional[str] = "",
    error_description: Optional[str] = "",
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Diagnoses root cause of a payment failure using deterministic rules first,
    falling back to ML classifier model if no rule matches.

    Args:
        error_code: Gateway error code string
        error_description: Human readable error description
        context: Context dictionary containing features (hour_of_day, amount, retry_count, payment_method, bank_code)

    Returns:
        dict: {"root_cause": str, "confidence": float, "source": "RULE_ENGINE" | "ML_MODEL"}
    """
    if context is None:
        context = {}

    # 1. Rule-based evaluation (zero external ML library dependencies)
    rule_result = apply_rules(error_code, error_description)
    if rule_result is not None:
        return rule_result

    # 2. ML Classifier Fallback (lazy-loads pandas, numpy, and model pipeline on demand)
    import numpy as np
    import pandas as pd

    pipeline = load_classifier()

    # Extract features from context with safe defaults
    now = datetime.now()
    hour_of_day = context.get("hour_of_day", now.hour)
    amount = context.get("amount", 1000.0)
    retry_count = context.get("retry_count", 0)
    payment_method = context.get("payment_method", "upi")
    bank_code = context.get("bank_code", "OTHER")

    feature_df = pd.DataFrame([{
        "hour_of_day": int(hour_of_day) if hour_of_day is not None else now.hour,
        "amount": float(amount) if amount is not None else 1000.0,
        "retry_count": int(retry_count) if retry_count is not None else 0,
        "payment_method": str(payment_method) if payment_method else "upi",
        "bank_code": str(bank_code) if bank_code else "OTHER",
    }])

    probs = pipeline.predict_proba(feature_df)[0]
    max_idx = int(np.argmax(probs))
    predicted_cause = str(pipeline.classes_[max_idx])
    confidence = float(probs[max_idx])

    return {
        "root_cause": predicted_cause,
        "confidence": round(confidence, 4),
        "source": "ML_MODEL"
    }
