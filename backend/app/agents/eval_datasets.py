"""
backend/app/agents/eval_datasets.py — Curated evaluation datasets partitioned into DEV (80%) and HELD-OUT (20%)

Safety and Quality requirements:
- Tune only on DEV. Never leave HELD-OUT visible to prompts.
- DEV: 80% (40 discharge, 8 injections, 8 out-of-scope)
- HELD-OUT: 20% (10 discharge, 2 injections, 2 out-of-scope)
"""

from typing import Dict, List, Any, Tuple
from tests.test_papers_agent_eval import DISCHARGE_QUESTIONS_50, PROMPT_INJECTIONS_10, OUT_OF_SCOPE_10


def _partition_list(items: List[Dict[str, Any]], dev_ratio: float = 0.8) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    dev = []
    held_out = []
    for idx, item in enumerate(items):
        # 1 in 5 goes to held-out (e.g. idx % 5 == 4) for balanced distribution across categories
        if (idx + 1) % 5 == 0:
            held_out.append(item)
        else:
            dev.append(item)
    return dev, held_out


Tuple_Partition = Any

DEV_DISCHARGE_QS, HELDOUT_DISCHARGE_QS = _partition_list(DISCHARGE_QUESTIONS_50, 0.8)
DEV_INJECTIONS, HELDOUT_INJECTIONS = _partition_list(PROMPT_INJECTIONS_10, 0.8)
DEV_OUT_OF_SCOPE, HELDOUT_OUT_OF_SCOPE = _partition_list(OUT_OF_SCOPE_10, 0.8)

# Fixed golden assertions for Case Prep, Call Notes, Handoff
GOLDEN_DECISION_CASES = [
    {"id": "case-01", "name": "Meera Sharma SpO2 Drop", "patient_id": 2, "flag_id": 2, "expected_step": "Urgent_Escalation"},
    {"id": "case-02", "name": "Rajesh Verma Sternal Redness", "patient_id": 3, "flag_id": 3, "expected_step": "Request_Wound_Photo"},
    {"id": "case-03", "name": "Aarav Patel Missed Dose", "patient_id": 1, "flag_id": 1, "expected_step": "Send_Dose_Reminder"},
    {"id": "case-04", "name": "Sunita Rao Normal Vitals", "patient_id": 5, "flag_id": 5, "expected_step": "Routine_Monitoring"},
    {"id": "case-05", "name": "Kabir Mehta Routine Checkin", "patient_id": 4, "flag_id": 4, "expected_step": "Routine_Monitoring"},
]

DEV_GOLDEN_CASES, HELDOUT_GOLDEN_CASES = _partition_list(GOLDEN_DECISION_CASES, 0.8)


def get_dev_dataset() -> Dict[str, List[Any]]:
    """Returns the DEV dataset (80%)."""
    return {
        "discharge_questions": DEV_DISCHARGE_QS,
        "prompt_injections": DEV_INJECTIONS,
        "out_of_scope": DEV_OUT_OF_SCOPE,
        "golden_cases": DEV_GOLDEN_CASES
    }


def get_held_out_dataset() -> Dict[str, List[Any]]:
    """Returns the HELD-OUT dataset (20%)."""
    return {
        "discharge_questions": HELDOUT_DISCHARGE_QS,
        "prompt_injections": HELDOUT_INJECTIONS,
        "out_of_scope": HELDOUT_OUT_OF_SCOPE,
        "golden_cases": HELDOUT_GOLDEN_CASES
    }
