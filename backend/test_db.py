"""
backend/test_db.py
──────────────────
Standalone verification script: connects to Neon PostgreSQL and runs
a lightweight SELECT 1 to confirm connectivity, SSL handshake, and
connection latency.

Usage (from project root):
    python -m backend.test_db
    # or
    python backend/test_db.py
"""

import sys
import time

# Ensure project root is on the path when run as a plain script
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from backend.config import settings
from backend.database import sync_engine


def main() -> None:
    print("=" * 60)
    print("  AI Revenue Recovery -- Neon DB Connection Test")
    print("=" * 60)

    # Mask credentials in the displayed URL
    display_url = settings.DATABASE_URL
    try:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(display_url)
        masked = parsed._replace(
            netloc=f"{parsed.username}:***@{parsed.hostname}"
            + (f":{parsed.port}" if parsed.port else "")
        )
        display_url = urlunparse(masked)
    except Exception:
        display_url = "<url parsing error>"

    print(f"\n  Target : {display_url}")
    print("  Query  : SELECT 1\n")

    start = time.perf_counter()
    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text("SELECT 1 AS ping"))
            row = result.fetchone()
        elapsed_ms = (time.perf_counter() - start) * 1000

        if row and row[0] == 1:
            print(f"  [OK]  Connection successful!  Latency: {elapsed_ms:.1f} ms")
        else:
            print(f"  [FAIL]  Unexpected result: {row}")
            sys.exit(1)

    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"  [FAIL]  Connection FAILED after {elapsed_ms:.1f} ms")
        print(f"      Error: {exc}")
        sys.exit(1)

    print("=" * 60)


if __name__ == "__main__":
    main()
