"""
app/auth.py — CareLoop Authentication & Authorization

- Multi-role login: Patient, Caregiver, Doctor, Nurse
- Passwords hashed with bcrypt
- JWT issued with PyJWT (HS256, 8-hour validity)
- Strict role checking via require_role(*roles)
- Enforces record-level authorization: patient_id is extracted solely
  from the verified JWT payload.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import bcrypt
import jwt
from fastapi import Header, HTTPException, Depends
from .db import get_conn

SECRET = os.getenv("JWT_SECRET", "careloop-super-secure-jwt-secret-key-32chars")
ALGORITHM = "HS256"


def verify_login(email: str, password: str) -> Optional[Dict[str, Any]]:
    """
    Look up user account in user_accounts by email and verify password hash.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT account_id, email, password_hash, account_role, patient_id, caregiver_id, staff_id
               FROM user_accounts WHERE email = %s""",
            (email.strip().lower(),),
        )
        row = cur.fetchone()

    if not row:
        return None
    try:
        if not bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode("utf-8")):
            return None
    except Exception:
        return None

    return row


def make_token(acct: Dict[str, Any]) -> str:
    """
    Generate an 8-hour JWT token containing role and identity bindings.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(acct["account_id"]),
        "account_id": acct["account_id"],
        "email": acct["email"],
        "role": acct["account_role"],
        "patient_id": acct["patient_id"],
        "caregiver_id": acct["caregiver_id"],
        "staff_id": acct["staff_id"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=8)).timestamp()),
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Dependency to decode and validate the Bearer JWT token from Authorization header.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")

    token = authorization.strip()
    if token.startswith("Bearer "):
        token = token[7:].strip()

    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory enforcing that the authenticated user
    possesses one of the specified roles.
    """
    def dep(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
        user_role = user.get("role")
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Role '{user_role}' is not allowed to access this resource",
            )
        return user

    return dep
