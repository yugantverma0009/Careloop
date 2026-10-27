"""
app/db.py — CareLoop Database Helper

Raw SQL access via PyMySQL (no ORM).
Enforces session time_zone = '+05:30' (IST) and DictCursor.
Provides transactional commit/rollback via contextmanager.
"""

import os
from contextlib import contextmanager
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()


@contextmanager
def get_conn():
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "careloop_api"),
        password=os.getenv("DB_PASSWORD", "careloop_dev_pass"),
        database=os.getenv("DB_NAME", "careloop"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SET time_zone = '+05:30'")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
