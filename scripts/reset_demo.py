#!/usr/bin/env python3
"""
scripts/reset_demo.py

Phase 6 CLI helper to reset the demo database to the clean Section 4 baseline.
Execution time target: < 30 seconds (typically < 1s).
Output contract: "Reset complete: 5 patients, 3 open flags, 5 tasks"
"""

import sys
import os

# Auto re-exec with backend/env/bin/python if running under system python
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PYTHON = os.path.abspath(os.path.join(SCRIPT_DIR, "../backend/env/bin/python"))
if os.path.exists(VENV_PYTHON) and sys.executable != VENV_PYTHON:
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

import time

if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import pymysql
from dotenv import load_dotenv

env_path = os.path.abspath(os.path.join(SCRIPT_DIR, "../backend/.env"))
load_dotenv(env_path)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "careloop_api")
DB_PASSWORD = os.getenv("DB_PASSWORD", "careloop_dev_pass")
DB_NAME = os.getenv("DB_NAME", "careloop")


def main():
    start = time.time()
    try:
        import seed_demo
        seed_demo.main()
    except Exception as e:
        print(f"❌ Reset failed: {e}", file=sys.stderr)
        sys.exit(1)

    duration = time.time() - start

    # Query counts for validation
    conn = pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM patients")
            patients = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM flags WHERE status = 'Open'")
            open_flags = cur.fetchone()["total"]
            cur.execute("SELECT COUNT(*) AS total FROM follow_up_tasks WHERE status = 'Pending'")
            open_tasks = cur.fetchone()["total"]
    finally:
        conn.close()

    # Exact required output phrase
    print(f"Reset complete: {patients} patients, {open_flags} open flags, {open_tasks} tasks")
    if duration >= 30:
        print(f"⚠️ Warning: Reset took {duration:.2f}s (target < 30s)")


if __name__ == "__main__":
    main()
