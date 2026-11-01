"""
backend/app/permissions.py — CareLoop Role and Permission Model

Implements the single role contract documented in PROJECT_GUIDE.md Section 9:
- Strict role checking dependencies: require_doctor, require_nurse, require_staff, require_patient, require_family
- Immediate family consent enforcement (caregivers.consent_granted)
- Flag resolution authority policy:
    * Routine and Review_Soon: Nurse and Doctor can resolve.
    * Urgent_Review and Immediate: Only Doctor can resolve, requiring a mandatory clinical note.
    * Nurse escalates urgent items to Doctor via escalate-doctor.
"""

from typing import Dict, Any, Optional, Tuple
from fastapi import Depends, HTTPException
from .auth import current_user
from .db import get_conn


# ── Role-Specific Dependencies ───────────────────────────────────────────────

def require_doctor(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Requires role 'Doctor'."""
    role = user.get("role") or user.get("account_role")
    if role != "Doctor":
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Doctor role required. User role '{role}' is not authorized.",
        )
    return user


def require_nurse(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Requires role 'Nurse'."""
    role = user.get("role") or user.get("account_role")
    if role != "Nurse":
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Nurse role required. User role '{role}' is not authorized.",
        )
    return user


def require_staff(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """Requires role 'Doctor' or 'Nurse'."""
    role = user.get("role") or user.get("account_role")
    if role not in ("Doctor", "Nurse"):
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Clinical staff role required. User role '{role}' is not authorized.",
        )
    return user


def require_patient(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """
    Requires role 'Patient'.
    Extracts and validates patient_id directly from the verified token.
    Caregivers calling patient endpoints are explicitly rejected with 403.
    """
    role = user.get("role") or user.get("account_role")
    if role != "Patient":
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Patient role required. User role '{role}' cannot access patient endpoints.",
        )
    if not user.get("patient_id"):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: No patient identity bound to this token.",
        )
    return user


def require_family(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    """
    Requires role 'Caregiver' (Family Helper).
    Strictly verifies in real time that the linked patient has granted consent (caregivers.consent_granted = 1).
    If consent is revoked or absent, immediately returns 403.
    Injects verified patient_id into user dict.
    """
    role = user.get("role") or user.get("account_role")
    if role != "Caregiver":
        raise HTTPException(
            status_code=403,
            detail=f"Forbidden: Family Helper (Caregiver) role required. User role '{role}' is not authorized.",
        )

    caregiver_id = user.get("caregiver_id")
    if not caregiver_id:
        raise HTTPException(
            status_code=403,
            detail="Forbidden: No caregiver identity bound to this token.",
        )

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT caregiver_id, patient_id, full_name, relationship, consent_granted
               FROM caregivers WHERE caregiver_id = %s""",
            (caregiver_id,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Caregiver profile not found.")

    if not row.get("consent_granted"):
        raise HTTPException(
            status_code=403,
            detail="Aarav has turned sharing off. Sharing turned off by patient. Family access is disabled until patient grants consent.",
        )

    # Attach verified patient_id to the user context
    user["patient_id"] = row["patient_id"]
    user["caregiver_info"] = row
    return user


# ── Flag Resolution Authority Policy ─────────────────────────────────────────

FLAG_AUTHORITY_POLICY = {
    "nurse_allowed_severities": {"Info", "Review_Soon", "Routine"},
    "doctor_allowed_severities": {"Info", "Review_Soon", "Routine", "Urgent_Review", "Immediate"},
    "urgent_severities": {"Urgent_Review", "Immediate"},
    "min_urgent_note_length": 5,
}


def can_resolve_flag(
    role: str,
    severity: str,
    resolution_note: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Evaluates whether the given role is authorized to resolve a flag with the given severity.
    Returns (allowed: bool, reason: str).
    """
    norm_sev = "Urgent_Review" if severity in ("Urgent_Review", "Immediate") else severity
    norm_role = role.capitalize() if role else ""

    if norm_sev in FLAG_AUTHORITY_POLICY["urgent_severities"]:
        if norm_role != "Doctor":
            return False, "Nurse cannot resolve urgent or immediate flags. Please escalate to doctor."
        note_clean = (resolution_note or "").strip()
        if len(note_clean) < FLAG_AUTHORITY_POLICY["min_urgent_note_length"]:
            return False, "A clinical note of at least 5 characters is required to resolve an urgent/immediate flag."
        return True, "Authorized"

    # Routine / Review_Soon
    if norm_role in ("Doctor", "Nurse"):
        return True, "Authorized"

    return False, f"Role '{role}' is not authorized to resolve clinical flags."

