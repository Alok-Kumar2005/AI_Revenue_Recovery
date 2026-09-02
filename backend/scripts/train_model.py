"""
backend/scripts/train_model.py
──────────────────────────────
Standalone script to retrain and re-export the ML diagnosis classifier model
using the current environment's scikit-learn version.
"""
import os
import sys

# Add project root directory to python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from backend.diagnosis.train import train_model

def main():
    print("Retraining diagnosis model with current scikit-learn package...")
    pipeline = train_model()
    print("Model retraining and export completed successfully.")

if __name__ == "__main__":
    main()
