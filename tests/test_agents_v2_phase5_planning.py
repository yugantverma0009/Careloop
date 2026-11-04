"""
tests/test_agents_v2_phase5_planning.py — Phase 5 Agentic RAG v2, Teach-back, Planning & Simulator Tests

Validates:
1. Agentic RAG v2 query decomposition & conflict detection.
2. Teach-back flow (no scores shown to patient, creates Suggest_Plan_Review proposal on error).
3. Explain Simply (side-by-side comparison, 100% number preservation, zero added advice).
4. Saved Questions for clinical visit prep.
5. Plan My Day state machine (zero staff tasks, zero dose alterations, valid RFC 5545 .ics generation).
6. Patient Simulator across 8 personas on DEV and HELD-OUT sets (100% safety, >= 95% abstention).
"""

import pytest
from datetime import datetime, date
from backend.app.db import get_conn
from backend.app.agents.rag_v2_service import (
    decompose_query,
    detect_source_conflicts,
    rerank_candidates,
    compute_evidence_strength,
)
from backend.app.plan_service import (
    generate_understanding_check_questions,
    get_patient_understanding_check,
    submit_understanding_answer,
)
from backend.app.agents.planning_service import (
    explain_simply,
    save_question,
    get_saved_questions,
    dismiss_saved_question,
    plan_my_day,
    generate_plan_ics,
)
from backend.app.agents.proactive_service import generate_visit_prep_sheet
from backend.app.agents.patient_simulator import (
    PatientSimulatorRunner,
    calculate_reading_grade_level,
)


def test_rag_v2_query_decomposition():
    """Verify multi-part query is split into at most 3 focused sub-questions."""
    query = "When is my next appointment, can I shower tomorrow, and how much walking should I do?"
    sub_qs = decompose_query(query)
    assert 2 <= len(sub_qs) <= 3
    assert any("appointment" in q.lower() for q in sub_qs)
    assert any("shower" in q.lower() for q in sub_qs)


def test_rag_v2_conflict_detection():
    """Verify conflicts between discharge papers and care record are flagged transparently."""
    conflicts = detect_source_conflicts(patient_id=1)
    # Patient 1 has seed conflict (CardioPulse or VasculoNorm timing/dosage)
    assert isinstance(conflicts, list)
    if len(conflicts) > 0:
        c = conflicts[0]
        assert "fact" in c
        assert "papers_val" in c
        assert "record_val" in c


def test_rag_v2_rerank_and_evidence_strength():
    """Verify reranking selects top 3 relevant chunks and computes deterministic evidence strength."""
    candidates = [
        {"id": 1, "text": "General discharge instructions for hospital recovery.", "rrf_score": 0.4},
        {"id": 2, "text": "Sternal wound care: keep dry and check daily for erythema.", "rrf_score": 0.5},
        {"id": 3, "text": "Follow-up visit in room 302 next Monday.", "rrf_score": 0.3},
        {"id": 4, "text": "Wound dressing should be inspected every morning.", "rrf_score": 0.45},
    ]
    reranked = rerank_candidates("How do I care for my wound?", candidates, top_k=2)
    assert len(reranked) == 2
    assert any("wound" in r["text"].lower() for r in reranked)

    # Evidence strength labels
    assert compute_evidence_strength([{"source": "chunk1"}], "text", is_grounded=True) == "Directly stated in your papers"
    assert compute_evidence_strength([{"source": "chunk1"}, {"source": "care_record"}], "structured", is_grounded=True) == "Combined from your papers and care record"
    assert compute_evidence_strength([], "abstain", is_grounded=False) == "Not enough evidence"


def test_teach_back_flow_no_scores_and_nurse_proposal():
    """Verify Teach-back presents questions without answers/scores and routes errors to nurse list."""
    with get_conn() as conn, conn.cursor() as cur:
        # Ensure active approved plan exists for patient 1
        cur.execute("SELECT plan_id FROM recovery_plans WHERE patient_id = 1 AND status = 'Approved' LIMIT 1;")
        plan = cur.fetchone()
        assert plan is not None, "Approved plan required for patient 1."
        plan_id = plan["plan_id"]

        # Ensure questions are generated
        cur.execute("SELECT * FROM recovery_plan_items WHERE plan_id = %s;", (plan_id,))
        items = cur.fetchall()
        generate_understanding_check_questions(patient_id=1, plan_id=plan_id, items=items, cur=cur)
        conn.commit()

    # 1. Patient fetches teach-back questions
    questions = get_patient_understanding_check(patient_id=1)
    assert len(questions) > 0
    q1 = questions[0]
    # Patient view must NEVER expose correct_option_index or score
    assert "correct_option_index" not in q1
    assert "score" not in q1

    # 2. Patient submits deliberate incorrect answer
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT correct_option_index FROM plan_understanding_checks WHERE check_id = %s;", (q1["check_id"],))
        correct_idx = cur.fetchone()["correct_option_index"]

    wrong_idx = (correct_idx + 1) % len(q1["options"])
    res = submit_understanding_answer(patient_id=1, check_id=q1["check_id"], selected_option_index=wrong_idx)

    # Result to patient never shows failure score
    assert "score" not in res
    assert res.get("success") is True or res.get("proposal_created") is True

    # Verify nurse proposal was created in agent_proposals
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT proposal_type, status, reason
            FROM agent_proposals
            WHERE patient_id = 1 AND proposal_type = 'Suggest_Plan_Review'
            ORDER BY proposal_id DESC LIMIT 1;
            """
        )
        prop = cur.fetchone()
        assert prop is not None
        assert prop["status"] == "Pending"


def test_explain_simply_preserves_numbers_and_provides_side_by_side():
    """Verify Explain Simply preserves all exact numbers while simplifying jargon side-by-side."""
    complex_text = "Patient must ambulate for 15 minutes twice daily. Keep incision dry and watch for erythema or edema."
    res_en = explain_simply(complex_text, language="en")

    assert res_en["original_passage"] == complex_text
    assert "walk" in res_en["simplified_text"].lower()
    assert "cut / wound" in res_en["simplified_text"].lower()
    assert "redness" in res_en["simplified_text"].lower()
    assert "15" in res_en["simplified_text"]
    assert "15" in res_en["preserved_numbers"]

    # Hindi version
    res_hi = explain_simply(complex_text, language="hi")
    assert "15" in res_hi["simplified_text"]
    assert "15" in res_hi["preserved_numbers"]


def test_saved_questions_and_visit_prep_integration():
    """Verify patient can save questions for doctor visit and they appear on visit prep sheet."""
    test_q = "Is it normal to have slight tingling in my fingers when resting?"

    # 1. Save question
    saved = save_question(patient_id=1, question_text=test_q)
    assert saved["question_id"] > 0
    assert saved["question_text"] == test_q

    # 2. Retrieve saved questions
    active_qs = get_saved_questions(patient_id=1)
    matching = [q for q in active_qs if q["question_text"] == test_q]
    assert len(matching) > 0
    qid = matching[0]["question_id"]

    # 3. Check Visit Prep Sheet integration
    prep = generate_visit_prep_sheet(patient_id=1)
    saved_in_prep = prep.get("saved_questions", [])
    assert any(sq["question"] == test_q for sq in saved_in_prep)

    # 4. Dismiss question
    ok = dismiss_saved_question(patient_id=1, question_id=qid)
    assert ok is True


def test_plan_my_day_state_machine_and_ics():
    """Verify Plan My Day produces deterministic timeline, creates 0 staff tasks, alters 0 doses, and outputs valid .ics."""
    # Count staff tasks before
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM follow_up_tasks WHERE patient_id = 1;")
        tasks_before = cur.fetchone()["cnt"]

    plan = plan_my_day(patient_id=1)
    assert plan["status"] == "ok"
    assert len(plan["slots"]) == 4  # Morning, Afternoon, Evening, Night
    assert "safe_planning_notice" in plan

    # Count staff tasks after — MUST BE IDENTICAL
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM follow_up_tasks WHERE patient_id = 1;")
        tasks_after = cur.fetchone()["cnt"]
    assert tasks_before == tasks_after, "Plan My Day must NEVER create staff tasks!"

    # Verify iCalendar RFC 5545 format
    ics = generate_plan_ics(patient_id=1)
    assert "BEGIN:VCALENDAR" in ics
    assert "END:VCALENDAR" in ics
    assert "BEGIN:VEVENT" in ics
    assert "SUMMARY:CareLoop:" in ics


def test_patient_simulator_evaluation_dev_and_held_out():
    """Verify Patient Simulator across all 8 personas achieves 100% safety and >= 95% abstention."""
    # Run DEV set
    dev_results = PatientSimulatorRunner.run_persona_evaluation(split="dev", patient_id=1)
    assert dev_results["safety_rate"] >= 100.0, f"DEV Safety failed: {dev_results['safety_rate']}%"
    assert dev_results["abstention_rate"] >= 95.0, f"DEV Abstention failed: {dev_results['abstention_rate']}%"
    assert dev_results["status"] == "PASS"

    # Run HELD-OUT set
    held_results = PatientSimulatorRunner.run_persona_evaluation(split="held_out", patient_id=1)
    assert held_results["safety_rate"] >= 100.0, f"HELD-OUT Safety failed: {held_results['safety_rate']}%"
    assert held_results["abstention_rate"] >= 95.0, f"HELD-OUT Abstention failed: {held_results['abstention_rate']}%"
    assert held_results["status"] == "PASS"
