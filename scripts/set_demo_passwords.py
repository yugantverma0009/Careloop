"""
scripts/set_demo_passwords.py

Sets real bcrypt password hashes for all seed user accounts in user_accounts.
Password set for all accounts: Demo@12345
"""

import os
import bcrypt
import pymysql
from dotenv import load_dotenv

# Load backend/.env
env_path = os.path.join(os.path.dirname(__file__), "..", "backend", ".env")
load_dotenv(env_path)

db_host = os.getenv("DB_HOST", "localhost")
db_port = int(os.getenv("DB_PORT", "3306"))
db_user = os.getenv("DB_USER", "careloop_api")
db_password = os.getenv("DB_PASSWORD", "careloop_dev_pass")
db_name = os.getenv("DB_NAME", "careloop")

demo_password = b"Demo@12345"
password_hash = bcrypt.hashpw(demo_password, bcrypt.gensalt()).decode("utf-8")

print(f"Connecting to MySQL ({db_host}:{db_port}) as {db_user}...")
conn = pymysql.connect(
    host=db_host,
    port=db_port,
    user=db_user,
    password=db_password,
    database=db_name,
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
    autocommit=False,
)

try:
    with conn.cursor() as cur:
        cur.execute("UPDATE user_accounts SET password_hash=%s", (password_hash,))
        affected = cur.rowcount
    conn.commit()
    print(f"✅ Success: Updated {affected} demo accounts with password 'Demo@12345'")
except Exception as e:
    conn.rollback()
    print(f"❌ Error updating passwords: {e}")
    raise
finally:
    conn.close()
