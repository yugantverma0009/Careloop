"""
tests/test_m1_auth.py

Test Milestone M1:
- /health endpoint
- Login for all 4 roles (Patient, Caregiver, Doctor, Nurse)
- Rejection of invalid passwords
- Role-based route enforcement (Patient routes reject Doctor/Nurse tokens with 403)
- Verification that patient_id is strictly extracted from the JWT token and isolated
"""

import pytest
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "healthy"
    assert data["database"] == "careloop"
    assert "+05:30" in data["session_timezone"]
    print("✅ Health check passed: Connected to CareLoop MySQL with IST timezone")


def test_login_all_roles():
    roles_and_emails = [
        ("Patient", "aarav.demo@example.test", "Aarav Patel", 1),
        ("Caregiver", "caregiver1.demo@example.test", "Aarav's Caregiver", None),
        ("Doctor", "ananya.demo@example.test", "Dr. Ananya Sharma", None),
        ("Nurse", "priya.demo@example.test", "Priya Nair", None),
    ]

    tokens = {}
    for role, email, expected_name, expected_pid in roles_and_emails:
        res = client.post("/auth/login", json={"email": email, "password": "Demo@12345"})
        assert res.status_code == 200, f"Login failed for {email}: {res.text}"
        data = res.json()
        assert data["role"] == role
        assert data["name"] == expected_name
        assert "access_token" in data
        if expected_pid:
            assert data["patient_id"] == expected_pid
        tokens[role] = data["access_token"]
        print(f"✅ Login success for {role} ({email}) -> Token received, bound to {expected_name}")

    return tokens


@pytest.fixture
def tokens():
    return test_login_all_roles()


def test_invalid_login():
    res = client.post("/auth/login", json={"email": "aarav.demo@example.test", "password": "BadPassword"})
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("✅ Invalid password correctly rejected with HTTP 401")


def test_role_enforcement_and_isolation(tokens):
    patient_headers = {"Authorization": f"Bearer {tokens['Patient']}"}
    doctor_headers = {"Authorization": f"Bearer {tokens['Doctor']}"}
    nurse_headers = {"Authorization": f"Bearer {tokens['Nurse']}"}
    caregiver_headers = {"Authorization": f"Bearer {tokens['Caregiver']}"}

    # 1. Patient profile succeeds with Patient token
    res = client.get("/patient/me/profile", headers=patient_headers)
    assert res.status_code == 200, res.text
    patient_data = res.json()
    assert patient_data["profile"]["patient_id"] == 1
    assert patient_data["profile"]["full_name"] == "Aarav Patel"
    print("✅ Patient profile successfully retrieved using JWT claims (Patient ID=1)")

    # 2. Patient profile is FORBIDDEN for Doctor and Nurse tokens (HTTP 403)
    res_doc = client.get("/patient/me/profile", headers=doctor_headers)
    assert res_doc.status_code == 403, f"Doctor should get 403, got {res_doc.status_code}"
    print("✅ Doctor token correctly blocked from /patient/me/profile with HTTP 403")

    res_nurse = client.get("/patient/me/profile", headers=nurse_headers)
    assert res_nurse.status_code == 403, f"Nurse should get 403, got {res_nurse.status_code}"
    print("✅ Nurse token correctly blocked from /patient/me/profile with HTTP 403")

    # 3. Staff profile works for Doctor and Nurse, but blocked for Patient
    res_staff = client.get("/staff/me/profile", headers=doctor_headers)
    assert res_staff.status_code == 200, res_staff.text
    assert res_staff.json()["full_name"] == "Dr. Ananya Sharma"
    print("✅ Doctor staff profile successfully retrieved")

    res_staff_nurse = client.get("/staff/me/profile", headers=nurse_headers)
    assert res_staff_nurse.status_code == 200, res_staff_nurse.text
    assert res_staff_nurse.json()["full_name"] == "Priya Nair"
    print("✅ Nurse staff profile successfully retrieved")

    res_pat_on_staff = client.get("/staff/me/profile", headers=patient_headers)
    assert res_pat_on_staff.status_code == 403
    print("✅ Patient token correctly blocked from /staff/me/profile with HTTP 403")

    # 4. Caregiver profile works for Caregiver, blocked for Patient
    res_cg = client.get("/caregiver/me/profile", headers=caregiver_headers)
    assert res_cg.status_code == 200, res_cg.text
    assert res_cg.json()["full_name"] == "Aarav's Caregiver"
    print("✅ Caregiver profile successfully retrieved")

    res_pat_on_cg = client.get("/caregiver/me/profile", headers=patient_headers)
    assert res_pat_on_cg.status_code == 403
    print("✅ Patient token correctly blocked from /caregiver/me/profile with HTTP 403")


if __name__ == "__main__":
    test_health()
    tokens = test_login_all_roles()
    test_invalid_login()
    test_role_enforcement_and_isolation(tokens)
    print("\n🎉 ALL MILESTONE M1 AUTH & SECURITY TESTS PASSED!")
