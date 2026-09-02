"""
Synthetic dataset generator & Scikit-learn model training for payment failure diagnosis.
"""
from __future__ import annotations

import os
from typing import Any, Optional


def generate_synthetic_data(num_samples: int = 2000, random_state: int = 42):
    """
    Generates synthetic payment failure data with realistic distributions.
    Lazy-loads numpy and pandas.
    """
    import numpy as np
    import pandas as pd

    np.random.seed(random_state)
    
    payment_methods = ["upi", "card", "netbanking"]
    bank_codes = ["HDFC", "ICICI", "SBI", "AXIS", "OTHER"]
    labels = [
        "INSUFFICIENT_FUNDS",
        "NETWORK_TIMEOUT",
        "BANK_SERVER_DOWN",
        "AUTHENTICATION_FAILED",
        "EXPIRED_CARD",
    ]

    records = []
    
    # Generate balanced synthetic samples
    samples_per_label = num_samples // len(labels)
    
    for label in labels:
        for _ in range(samples_per_label):
            if label == "INSUFFICIENT_FUNDS":
                hour = int(np.random.randint(0, 24))
                amount = float(np.random.uniform(3000, 50000))
                retry_count = int(np.random.choice([1, 2, 3, 4]))
                pm = str(np.random.choice(payment_methods, p=[0.4, 0.4, 0.2]))
                bank = str(np.random.choice(bank_codes))
            elif label == "NETWORK_TIMEOUT":
                hour = int(np.random.choice([10, 11, 12, 18, 19, 20, 21, 22]))
                amount = float(np.random.uniform(100, 15000))
                retry_count = int(np.random.choice([2, 3, 4, 5]))
                pm = str(np.random.choice(["upi", "netbanking"], p=[0.7, 0.3]))
                bank = str(np.random.choice(bank_codes))
            elif label == "BANK_SERVER_DOWN":
                hour = int(np.random.choice([0, 1, 2, 3, 4, 13, 14]))
                amount = float(np.random.uniform(500, 20000))
                retry_count = int(np.random.choice([0, 1, 2]))
                pm = str(np.random.choice(["upi", "netbanking"], p=[0.6, 0.4]))
                bank = str(np.random.choice(["SBI", "ICICI", "HDFC"], p=[0.5, 0.3, 0.2]))
            elif label == "AUTHENTICATION_FAILED":
                hour = int(np.random.randint(0, 24))
                amount = float(np.random.uniform(200, 10000))
                retry_count = int(np.random.choice([0, 1]))
                pm = str(np.random.choice(["card", "upi"], p=[0.7, 0.3]))
                bank = str(np.random.choice(bank_codes))
            elif label == "EXPIRED_CARD":
                hour = int(np.random.randint(0, 24))
                amount = float(np.random.uniform(100, 25000))
                retry_count = int(np.random.choice([0, 1, 2]))
                pm = "card"
                bank = str(np.random.choice(bank_codes))
            else:
                hour = int(np.random.randint(0, 24))
                amount = float(np.random.uniform(100, 10000))
                retry_count = int(np.random.randint(0, 5))
                pm = str(np.random.choice(payment_methods))
                bank = str(np.random.choice(bank_codes))

            records.append({
                "hour_of_day": hour,
                "amount": amount,
                "retry_count": retry_count,
                "payment_method": pm,
                "bank_code": bank,
                "root_cause": label
            })

    df = pd.DataFrame(records)
    # Shuffle dataset
    df = df.sample(frac=1, random_state=random_state).reset_index(drop=True)
    return df


def train_model(save_path: Optional[str] = None) -> Any:
    """
    Trains RandomForestClassifier on synthetic payment failure dataset and saves model pipeline.
    Lazy-loads joblib and scikit-learn modules.
    """
    import joblib
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.compose import ColumnTransformer
    from sklearn.preprocessing import OneHotEncoder
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report

    if save_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        models_dir = os.path.join(base_dir, "models")
        os.makedirs(models_dir, exist_ok=True)
        save_path = os.path.join(models_dir, "classifier.joblib")
    else:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)

    print("Generating synthetic dataset (2,000 samples)...")
    df = generate_synthetic_data(num_samples=2000, random_state=42)

    X = df[["hour_of_day", "amount", "retry_count", "payment_method", "bank_code"]]
    y = df["root_cause"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    numeric_features = ["hour_of_day", "amount", "retry_count"]
    categorical_features = ["payment_method", "bank_code"]

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", "passthrough", numeric_features),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical_features),
        ]
    )

    pipeline = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", RandomForestClassifier(n_estimators=100, max_depth=12, random_state=42)),
        ]
    )

    print("Training RandomForestClassifier...")
    pipeline.fit(X_train, y_train)

    y_pred = pipeline.predict(X_test)
    print("Evaluation Results on Test Set:")
    print(classification_report(y_test, y_pred))

    joblib.dump(pipeline, save_path)
    print(f"Model successfully saved to {save_path}")

    return pipeline


if __name__ == "__main__":
    train_model()
