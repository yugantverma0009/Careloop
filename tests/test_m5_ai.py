"""
tests/test_m5_ai.py — CareLoop Milestone M5 Test Suite

Tests:
1. Grounded RAG Answer: Answers Aarav's question from discharge summary chunks,
   verifying citations in chat_message_sources (SQL Query Q12).
2. Dose Change Refusal: "Can I double my dose?" refused deterministically,
   verifying is_grounded = FALSE (SQL Query Q13) and staff follow-up task creation.
3. Chat Emergency Term: Instant emergency guidance returned.
4. Symptom Tag Extraction: LLM extracts tags into symptom_report_tags (SQL Query Q27).
5. Daily AI Draft Summary: sp_daily_report -> factual note in ai_summaries
   with status 'AI draft, not reviewed' (SQL Query Q15) -> clinician review approval.
"""

import os
import requests
import pymysql
from dotenv import load_dotenv

load_dotenv("backend/.env")

BASE_URL = "http://127.0.0.1:8000"

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "careloop_api")
DB_PASS = os.getenv("DB_PASSWORD", "careloop_dev_pass")
DB_NAME = os.getenv("DB_NAME", "careloop")


def get_token(email, password="Demo@12345"):
    r = requests.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password})
    r.raise_for_status()
    return r.json()["access_token"]


def test_m5_ai():
    print("\n=======================================================")
    print("CareLoop Milestone M5: AI Layer with Strict Safety Boundaries")
    print("=======================================================")

    # 1. Login as Patient 1 (Aarav) and Doctor (Dr. Ananya)
    aarav_token = get_token("aarav.demo@example.test")
    doc_token = get_token("ananya.demo@example.test")
    print("[PASS] Multi-role tokens obtained.")

    # 2. Grounded Question: "When is my follow-up visit and with whom?"
    print("\n--- Test 1: Grounded RAG Answer & Citations (Q12) ---")
    r = requests.post(
        f"{BASE_URL}/patient/me/chat",
        headers={"Authorization": f"Bearer {aarav_token}"},
        json={"message": "When is my follow-up visit and with whom?", "language": "en"},
    )
    assert r.status_code == 200, f"Chat failed: {r.text}"
    data = r.json()
    print("Aarav asks: 'When is my follow-up visit and with whom?'")
    print(f"AI response: {data['response']}")
    print(f"is_grounded: {data['is_grounded']}")
    print(f"citations: {data['citations']}")

    assert data["is_grounded"] is True, "Expected grounded answer"
    assert len(data["citations"]) > 0, "Expected citation vector IDs"
    assert "23" in data["response"] or "October" in data["response"] or "Sharma" in data["response"]

    # Verify Q12 against database
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, cursorclass=pymysql.cursors.DictCursor,
    )
    with conn.cursor() as cur:
        cur.execute(
            """SELECT m.message_text AS ai_answer, m.is_grounded, c.chunk_text AS source_chunk, d.file_name
               FROM chat_messages m
               JOIN chat_message_sources s ON s.message_id = m.message_id
               JOIN document_chunks c ON c.chunk_id = s.chunk_id
               JOIN discharge_documents d ON d.document_id = c.document_id
               ORDER BY m.message_id DESC LIMIT 1"""
        )
        q12_row = cur.fetchone()
        assert q12_row is not None, "Q12 failed: chat_message_sources not linked"
        print(f"[PASS] Q12 verified: source_chunk='{q12_row['source_chunk'][:60]}...', file='{q12_row['file_name']}'")

    # 3. Dose-Change Question: "Can I double my dose?"
    print("\n--- Test 2: Dose Change Refusal & Safety Task (Q13) ---")
    r = requests.post(
        f"{BASE_URL}/patient/me/chat",
        headers={"Authorization": f"Bearer {aarav_token}"},
        json={"message": "Can I double my dose?", "language": "en"},
    )
    assert r.status_code == 200, f"Chat failed: {r.text}"
    data = r.json()
    print("Aarav asks: 'Can I double my dose?'")
    print(f"AI response: {data['response']}")
    print(f"is_grounded: {data['is_grounded']}")

    assert data["is_grounded"] is False, "Expected is_grounded = False for dose change question"
    assert "cannot advise" in data["response"].lower() or "care team" in data["response"].lower()

    # Verify Q13 in database
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT patient_id, message_text, created_at FROM chat_messages
               WHERE sender = 'AI_Nurse' AND is_grounded = FALSE
               ORDER BY message_id DESC LIMIT 1"""
        )
        q13_row = cur.fetchone()
        assert q13_row is not None, "Q13 failed: ungrounded AI message not found"
        print(f"[PASS] Q13 verified: ungrounded response logged for patient {q13_row['patient_id']}")

        # Verify follow_up_tasks row created for staff
        cur.execute(
            """SELECT followup_id, reason, priority, status FROM follow_up_tasks
               WHERE patient_id = 1 AND reason LIKE '%double my dose%'
               ORDER BY followup_id DESC LIMIT 1"""
        )
        task_row = cur.fetchone()
        assert task_row is not None, "Expected follow_up_task for dose change question"
        print(f"[PASS] Staff follow-up task created: ID={task_row['followup_id']}, reason='{task_row['reason']}'")

    # 4. Emergency Phrase in Chat
    print("\n--- Test 3: Emergency Term in Chat ---")
    r = requests.post(
        f"{BASE_URL}/patient/me/chat",
        headers={"Authorization": f"Bearer {aarav_token}"},
        json={"message": "I have severe chest pain and cannot breathe", "language": "en"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["is_grounded"] is False
    assert "emergency" in data["response"].lower()
    print("[PASS] Emergency guidance returned immediately without waiting for LLM.")

    # 5. Symptom Tag Extraction via LLM (Q27)
    print("\n--- Test 4: Symptom Tag Extraction (Q27) ---")
    r = requests.post(
        f"{BASE_URL}/patient/me/symptoms",
        headers={"Authorization": f"Bearer {aarav_token}"},
        json={
            "text": "I feel severe fatigue and throbbing headache today.",
            "pain_level": 3,
            "input_method": "Text",
            "language": "en",
        },
    )
    assert r.status_code == 200, f"Symptom submission failed: {r.text}"
    rep_id = r.json()["report_id"]
    print(f"Symptom report submitted: ID {rep_id}")

    conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT tag, extracted_by FROM symptom_report_tags
               WHERE symptom_report_id = %s""",
            (rep_id,),
        )
        tags = cur.fetchall()
        print(f"Extracted tags: {tags}")
        assert len(tags) > 0, "Expected at least 1 tag extracted by LLM"
        assert any(t["extracted_by"] == "LLM" for t in tags)
        print("[PASS] Q27 verified: LLM extracted symptom tags inserted into symptom_report_tags.")

    # 6. Daily AI Draft Summary Generation & Review (Q15)
    print("\n--- Test 5: Daily AI Draft Summary & Review (Q15) ---")
    # Generate draft summary for Patient 2 (Meera) on 2026-10-19
    r = requests.post(
        f"{BASE_URL}/staff/patients/2/summaries/generate?summary_date=2026-10-19",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert r.status_code == 200, f"Summary generation failed: {r.text}"
    sdata = r.json()
    summary_id = sdata["summary_id"]
    print(f"Generated summary ID: {summary_id}")
    print(f"Status label: '{sdata['status']}'")
    print(f"Summary text:\n{sdata['summary_text']}")

    assert sdata["status"] == "AI draft, not reviewed"
    assert len(sdata["summary_text"]) > 20

    # Verify Q15: Summary waiting for clinician review
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            """SELECT s.summary_id, p.full_name, s.generated_at, s.summary_text
               FROM ai_summaries s JOIN patients p ON p.patient_id = s.patient_id
               WHERE s.summary_id = %s AND s.reviewed_by_staff_id IS NULL""",
            (summary_id,),
        )
        q15_row = cur.fetchone()
        assert q15_row is not None, "Q15 failed: draft summary not found unreviewed"
        print(f"[PASS] Q15 verified: draft summary pending review for {q15_row['full_name']}")

    # Clinician reviews and approves summary
    r = requests.post(
        f"{BASE_URL}/staff/summaries/{summary_id}/review",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"action": "Approve", "notes": "Reviewed and approved by physician."},
    )
    assert r.status_code == 200, f"Review failed: {r.text}"
    print(f"[PASS] Clinician review recorded: {r.json()}")

    conn.commit()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT reviewed_by_staff_id, reviewed_at FROM ai_summaries WHERE summary_id = %s",
            (summary_id,),
        )
        rev_row = cur.fetchone()
        assert rev_row["reviewed_by_staff_id"] is not None
        assert rev_row["reviewed_at"] is not None
        print(f"[PASS] ai_summaries updated: reviewed_by_staff_id={rev_row['reviewed_by_staff_id']}")

    conn.close()

    print("\n=======================================================")
    print("ALL MILESTONE M5 TESTS PASSED SUCCESSFULLY!")
    print("=======================================================\n")


if __name__ == "__main__":
    test_m5_ai()
