"""
tests/test_staff_upgrade_p5.py

Tests for Care Team Portal Phase 5 (Governance & Interoperability):
- D-13 Pathway-specific rule templates with blank thresholds & doctor-only application
- D-13 Rule threshold update with mandatory clinical reason & audit history
- D-14 Operational insights with 9 non-outcome metrics & SLA compliance
- D-14 Audit logging for insights CSV export
- D-19 Validated FHIR R4 collection bundle export with LOINC codes & audit log
- D-20 Clinician-entered LACE Readmission Risk Score (0-19) & evidence disclaimer
"""

import pytest
import json
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.db import get_conn
from backend.app.auth import make_token
from backend.app.governance_interop import (
    compute_lace_score,
    compute_operational_insights,
    build_fhir_r4_bundle,
    PATHWAY_TEMPLATES,
)

client = TestClient(app)

doctor_token = make_token({
    "account_id": 3,
    "email": "ananya.demo@example.test",
    "account_role": "Doctor",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 1,
})
nurse_token = make_token({
    "account_id": 4,
    "email": "priya.demo@example.test",
    "account_role": "Nurse",
    "patient_id": None,
    "caregiver_id": None,
    "staff_id": 3,
})
doc_headers = {"Authorization": f"Bearer {doctor_token}"}
nurse_headers = {"Authorization": f"Bearer {nurse_token}"}


# ==============================================================================
# FEATURE D-13: PATHWAY TEMPLATES & RULE HISTORY
# ==============================================================================

def test_d13_pathway_templates_catalog_blank_thresholds():
    """D-13: Template catalog must ship with NO default medical thresholds."""
    resp = client.get("/staff/pathway-templates", headers=doc_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert len(data["templates"]) >= 4

    template_ids = [t["template_id"] for t in data["templates"]]
    assert "post_cardiac" in template_ids
    assert "post_joint" in template_ids
    assert "pneumonia_recovery" in template_ids
    assert "post_dka" in template_ids

    # Critical D-13 requirement: Every template ships with blank default thresholds
    for template in data["templates"]:
        assert len(template["rules"]) > 0
        for rule in template["rules"]:
            assert rule["threshold_value"] is None, (
                f"Rule {rule['key']} in template {template['template_id']} has default threshold! "
                "Templates must ship with blank thresholds per D-13."
            )


def test_d13_apply_pathway_forbidden_for_nurses():
    """D-13: Only doctors may apply pathway template overrides; nurses receive 403."""
    payload = {
        "template_id": "post_cardiac",
        "rules": [
            {
                "rule_type": "Reading_Above",
                "threshold_value": 110.0,
                "severity": "Urgent_Review",
                "window_hours": 4,
                "measurement_type": "Heart_Rate",
            }
        ],
    }
    resp = client.post("/staff/patients/1/apply-pathway", headers=nurse_headers, json=payload)
    assert resp.status_code == 403
    assert "doctor" in resp.json()["detail"].lower()


def test_d13_apply_pathway_rejects_blank_thresholds():
    """D-13: Server strictly rejects applying template rules with missing/blank thresholds."""
    payload = {
        "template_id": "post_cardiac",
        "rules": [
            {
                "rule_type": "Reading_Above",
                "threshold_value": None,  # Blank! Must be rejected
                "severity": "Urgent_Review",
            }
        ],
    }
    resp = client.post("/staff/patients/1/apply-pathway", headers=doc_headers, json=payload)
    assert resp.status_code in [400, 422]
    assert "threshold" in str(resp.json()["detail"]).lower()


def test_d13_apply_pathway_success_and_audit():
    """D-13: Doctor successfully applies template with filled thresholds; records audit."""
    payload = {
        "template_id": "post_cardiac",
        "rules": [
            {
                "rule_type": "Reading_Above",
                "threshold_value": 112.0,
                "severity": "Urgent_Review",
                "window_hours": 4,
                "measurement_type": "Heart_Rate",
            },
            {
                "rule_type": "Reading_Below",
                "threshold_value": 91.0,
                "severity": "Urgent_Review",
                "window_hours": 2,
                "measurement_type": "SpO2",
            },
        ],
    }
    resp = client.post("/staff/patients/1/apply-pathway", headers=doc_headers, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["applied"] is True

    # Check alert rules were updated in patient 1
    rules_resp = client.get("/staff/patients/1/rules", headers=doc_headers)
    assert rules_resp.status_code == 200
    rules = rules_resp.json()["rules"]
    tachy_rule = next((r for r in rules if r["rule_type"] == "Reading_Above" and r.get("measurement_type") == "Heart_Rate"), None)
    assert tachy_rule is not None
    assert float(tachy_rule["threshold_value"]) == 112.0


def test_d13_rule_history_and_justified_update():
    """D-13: Updating a rule threshold requires clinical reason (min 5 chars) and logs history."""
    # Find rule id for Heart Rate / Tachycardia on patient 1
    rules_resp = client.get("/staff/patients/1/rules", headers=doc_headers)
    rule_id = rules_resp.json()["rules"][0]["rule_id"]

    # 1. Reject update without justification
    fail_resp = client.post(
        f"/staff/rules/{rule_id}/update",
        headers=doc_headers,
        json={"threshold_value": 115.0, "change_reason": "abc"},
    )
    assert fail_resp.status_code in [400, 422]
    assert "5 characters" in fail_resp.json()["detail"].lower()

    # 2. Doctor updates with valid justification
    ok_resp = client.post(
        f"/staff/rules/{rule_id}/update",
        headers=doc_headers,
        json={
            "threshold_value": 116.0,
            "change_reason": "Patient is walking 3km daily; raising threshold to avoid alert fatigue",
        },
    )
    assert ok_resp.status_code == 200
    assert ok_resp.json()["approved_by_doctor"] is True

    # 3. Retrieve rule history
    hist_resp = client.get(f"/staff/rules/{rule_id}/history", headers=doc_headers)
    assert hist_resp.status_code == 200
    history = hist_resp.json()["history"]
    assert len(history) > 0
    latest = history[0]
    assert float(latest["new_threshold"]) == 116.0
    assert "fatigue" in latest["change_reason"]
    assert latest["approved_by_doctor"] is True


def test_d13_nurse_rule_update_is_proposal():
    """D-13: Nurse updating a rule is recorded as an unapproved proposal."""
    rules_resp = client.get("/staff/patients/1/rules", headers=doc_headers)
    rule_id = rules_resp.json()["rules"][0]["rule_id"]

    resp = client.post(
        f"/staff/rules/{rule_id}/update",
        headers=nurse_headers,
        json={
            "threshold_value": 118.0,
            "change_reason": "Nurse round observation: resting rate consistently 105",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["approved_by_doctor"] is False
    assert "proposal" in data["message"].lower()


# ==============================================================================
# FEATURE D-14: OPERATIONAL INSIGHTS (NON-OUTCOME METRICS)
# ==============================================================================

def test_d14_operational_insights_metrics_and_sla():
    """D-14: Returns 9 operational metrics without outcome claims."""
    resp = client.get("/staff/insights?range=30d", headers=nurse_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "date_range" in data
    assert "metrics" in data
    assert "definitions" in data

    m = data["metrics"]
    # 1. Median acknowledge time
    assert "median_acknowledge_time_minutes" in m
    assert "urgent_review" in m["median_acknowledge_time_minutes"]
    assert "medium_priority" in m["median_acknowledge_time_minutes"]

    # 2. SLA adherence %
    assert "sla_adherence_pct" in m
    assert 0 <= m["sla_adherence_pct"] <= 100

    # 3. Open flag age distribution
    assert "open_flags_age_buckets" in m
    assert "under_2h" in m["open_flags_age_buckets"]
    assert "over_24h" in m["open_flags_age_buckets"]

    # 4. Alerts per patient per day
    assert "alerts_per_patient_per_day" in m

    # 5. Duplicate rate %
    assert "duplicate_rate_pct" in m

    # 6. False alarms by rule
    assert "false_alarms_by_rule" in m
    assert isinstance(m["false_alarms_by_rule"], list)

    # 7. Self reported dose confirmations %
    assert "self_reported_dose_confirmations_pct" in m

    # 8. Device uptime %
    assert "device_uptime_pct" in m

    # 9. Overdue tasks count
    assert "overdue_tasks_count" in m

    # Critical D-14 constraint: No outcome claims (readmission rates, recovery scores, hospital benchmarks)
    raw_text = json.dumps(data).lower()
    assert "readmission rate" not in raw_text
    assert "recovery rate" not in raw_text
    assert "benchmark vs hospital" not in raw_text


def test_d14_export_insights_audit_log():
    """D-14: Exporting operational insights creates an immutable audit record."""
    resp = client.post(
        "/staff/insights/export-log",
        headers=doc_headers,
        json={"count": 12, "filters": {"range": "30d"}},
    )
    assert resp.status_code == 200
    assert resp.json()["logged"] is True

    # Verify audit log contains INSIGHTS_EXPORT
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM audit_log WHERE action = 'INSIGHTS_EXPORT' ORDER BY log_id DESC LIMIT 1"
            )
            row = cur.fetchone()
            assert row is not None
            assert str(row["actor_id"]) == "1"


# ==============================================================================
# FEATURE D-19: FHIR R4 COLLECTION BUNDLE EXPORT
# ==============================================================================

def test_d19_fhir_r4_bundle_export_and_loinc():
    """D-19: Exports validated FHIR R4 bundle with LOINC codes for vitals & medication."""
    resp = client.get("/staff/patients/1/fhir", headers=nurse_headers)
    assert resp.status_code == 200
    bundle = resp.json()

    assert bundle["resourceType"] == "Bundle"
    assert bundle["type"] == "collection"
    assert "entry" in bundle
    assert len(bundle["entry"]) > 0

    resources = [e["resource"] for e in bundle["entry"]]
    resource_types = [r["resourceType"] for r in resources]

    assert "Patient" in resource_types
    assert "Observation" in resource_types
    assert "MedicationRequest" in resource_types

    # Find Patient resource
    pat = next(r for r in resources if r["resourceType"] == "Patient")
    assert pat["id"] == "pat-1"
    assert pat["active"] is True
    assert len(pat["name"]) > 0

    # Verify standard LOINC vitals observation
    vitals_obs = [
        r for r in resources
        if r["resourceType"] == "Observation" and r.get("category", [{}])[0].get("coding", [{}])[0].get("code") == "vital-signs"
    ]
    assert len(vitals_obs) > 0
    loinc_codes = [
        c["code"]
        for o in vitals_obs
        for c in o.get("code", {}).get("coding", [])
        if c.get("system") == "http://loinc.org"
    ]
    # LOINC 8867-4 is Heart rate, 59408-5 is Oxygen saturation in arterial blood
    assert any(code in ["8867-4", "59408-5"] for code in loinc_codes)

    # Verify an audit log entry was created for FHIR export
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM audit_log WHERE action = 'FHIR_EXPORT' AND entity_id = 1 ORDER BY log_id DESC LIMIT 1"
            )
            row = cur.fetchone()
            assert row is not None


# ==============================================================================
# FEATURE D-20: CLINICIAN-ENTERED LACE SCORE (0-19)
# ==============================================================================

def test_d20_lace_score_math():
    """D-20: Verifies published LACE index point calculations (0 to 19 scale)."""
    # Case 1: Minimal risk (1d stay, elective, 0 comorbidity, 0 ED visits)
    res1 = compute_lace_score(length_of_stay_days=1, acute_admission=False, charlson_index=0, ed_visits_6m=0)
    assert res1["score"] == 1
    assert res1["risk_tier"] == "Low"

    # Case 2: Moderate risk (3d stay -> 3, acute -> 3, charlson 1 -> 1, ed 0 -> 0) => 7 pts
    res2 = compute_lace_score(length_of_stay_days=3, acute_admission=True, charlson_index=1, ed_visits_6m=0)
    assert res2["score"] == 7
    assert res2["risk_tier"] == "Moderate"

    # Case 3: High risk (14d stay -> 7, acute -> 3, charlson 4 -> 5, ed 4 -> 4) => 19 pts (Max)
    res3 = compute_lace_score(length_of_stay_days=14, acute_admission=True, charlson_index=4, ed_visits_6m=4)
    assert res3["score"] == 19
    assert res3["risk_tier"] == "High"


def test_d20_lace_endpoint_save_and_retrieve():
    """D-20: Clinician saves LACE score and retrieves with evidence disclaimer."""
    payload = {
        "length_of_stay_days": 4,
        "acute_admission": True,
        "charlson_index": 2,
        "ed_visits_6m": 1,
    }
    resp = client.post("/staff/patients/1/lace", headers=nurse_headers, json=payload)
    assert resp.status_code == 200
    saved = resp.json()
    assert saved["score"] == (4 + 3 + 2 + 1)  # 4d = 4, acute = 3, c=2 = 2, ed=1 = 1 => 10 pts
    assert saved["risk_tier"] == "High"
    assert "mixed" in saved["disclaimer"].lower()

    # Retrieve score
    get_resp = client.get("/staff/patients/1/lace", headers=doc_headers)
    assert get_resp.status_code == 200
    retrieved = get_resp.json()
    assert retrieved["score"] == 10
    assert retrieved["length_of_stay_days"] == 4
    assert retrieved["acute_admission"] is True
