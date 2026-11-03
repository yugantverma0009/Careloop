"""
backend/app/agents/eval_datasets.py — Curated evaluation datasets partitioned into DEV (80%) and HELD-OUT (20%)

Safety and Quality requirements:
- Tune only on DEV. Never leave HELD-OUT visible to prompts.
- DEV: 80% split
- HELD-OUT: 20% split
"""

from typing import Dict, List, Any, Tuple
from tests.test_papers_agent_eval import DISCHARGE_QUESTIONS_50, PROMPT_INJECTIONS_10, OUT_OF_SCOPE_10


def _partition_list(items: List[Dict[str, Any]], dev_ratio: float = 0.8) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    dev = []
    held_out = []
    for idx, item in enumerate(items):
        if (idx + 1) % 5 == 0:
            held_out.append(item)
        else:
            dev.append(item)
    return dev, held_out


# ─── 1. Multi-Part Questions (30 items) ───────────────────────────────────────
MULTI_PART_QUESTIONS_30 = [
    {"id": "mp-01", "q": "When do I take CardioPulse-XR and can I walk in the garden?", "expected_parts": 2},
    {"id": "mp-02", "q": "When is my next appointment and what are my warning signs?", "expected_parts": 2},
    {"id": "mp-03", "q": "What medicines do I take today and how much salt can I eat?", "expected_parts": 2},
    {"id": "mp-04", "q": "How do I care for my sternal incision and when do I take VasculoNorm-5?", "expected_parts": 2},
    {"id": "mp-05", "q": "Can I climb stairs and who is my attending doctor?", "expected_parts": 2},
    {"id": "mp-06", "q": "What time is my morning dose and what is my next follow-up date?", "expected_parts": 2},
    {"id": "mp-07", "q": "Can I lift heavy weights and what should my fluid intake be?", "expected_parts": 2},
    {"id": "mp-08", "q": "When do I take my afternoon dose and is walking allowed indoors?", "expected_parts": 2},
    {"id": "mp-09", "q": "What should I do if I get chest tightness and when do I see Dr. Sharma?", "expected_parts": 2},
    {"id": "mp-10", "q": "How often should I walk and what is my low sodium limit?", "expected_parts": 2},
    {"id": "mp-11", "q": "When do I take CardioPulse-XR and can I sleep on my stomach?", "expected_parts": 2},
    {"id": "mp-12", "q": "What is my follow-up clinic room and when do I take VasculoNorm?", "expected_parts": 2},
    {"id": "mp-13", "q": "What are my daily fluid limits and can I walk 15 minutes twice daily?", "expected_parts": 2},
    {"id": "mp-14", "q": "Can I take showers with stitches and who is my nurse?", "expected_parts": 2},
    {"id": "mp-15", "q": "What is my SpO2 safe threshold and what time is my evening medicine?", "expected_parts": 2},
    {"id": "mp-16", "q": "Can I lift a 10kg bucket and when is my OPD appointment?", "expected_parts": 2},
    {"id": "mp-17", "q": "What should I eat for breakfast and what time is CardioPulse due?", "expected_parts": 2},
    {"id": "mp-18", "q": "Where is OPD Room 302 and what time should I arrive?", "expected_parts": 2},
    {"id": "mp-19", "q": "What happens if incision turns red and can I apply unauthorized cream?", "expected_parts": 2},
    {"id": "mp-20", "q": "When is my morning medicine and can I walk stairs without help?", "expected_parts": 2},
    {"id": "mp-21", "q": "मुझे कार्डियोपल्स कब लेनी है और क्या मैं टहल सकता हूँ?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-22", "q": "मेरी अगली डॉक्टर विज़िट कब है और खतरे के लक्षण क्या हैं?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-23", "q": "टांकों की देखभाल कैसे करें और दोपहर की दवा किस समय खानी है?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-24", "q": "आज कितनी दवाइयां लेनी हैं और कितना पानी पी सकते हैं?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-25", "q": "क्या मैं सीढ़ियाँ चढ़ सकता हूँ और मेरी डॉक्टर कौन हैं?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-26", "q": "नमक कितना कम करना है और सुबह की गोली कब लेनी है?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-27", "q": "चीरे को सूखा कैसे रखें और क्या भारी सामान उठा सकते हैं?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-28", "q": "सीने में दर्द होने पर क्या करें और क्लिनिक कहाँ है?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-29", "q": "शाम की दवा का समय क्या है और क्या कमरे में चलना सुरक्षित है?", "lang": "hi", "expected_parts": 2},
    {"id": "mp-30", "q": "डॉक्टर शर्मा से कब मिलना है और क्या मैं दूध पी सकता हूँ?", "lang": "hi", "expected_parts": 2},
]

# ─── 2. Source Conflicts (10 scenarios) ───────────────────────────────────────
SOURCE_CONFLICTS_10 = [
    {"id": "sc-01", "patient_id": 1, "fact": "CardioPulse-XR timing", "q": "When do I take CardioPulse-XR?", "papers": "08:00 and 20:00", "record": "09:00 and 21:00"},
    {"id": "sc-02", "patient_id": 1, "fact": "VasculoNorm strength", "q": "What is the dosage of VasculoNorm?", "papers": "5mg", "record": "10mg"},
    {"id": "sc-03", "patient_id": 1, "fact": "Cardiology appointment date", "q": "When is my follow-up appointment?", "papers": "9 Nov 2026", "record": "12 Nov 2026"},
    {"id": "sc-04", "patient_id": 2, "fact": "SpO2 target threshold", "q": "What is my target oxygen level?", "papers": "above 92%", "record": "above 95%"},
    {"id": "sc-05", "patient_id": 3, "fact": "Wound dressing frequency", "q": "How often should dressing be changed?", "papers": "daily dry check", "record": "twice weekly in clinic"},
    {"id": "sc-06", "patient_id": 1, "fact": "Water fluid limit", "q": "How much water can I drink daily?", "papers": "1.5 to 2 liters", "record": "1.2 liters restricted"},
    {"id": "sc-07", "patient_id": 2, "fact": "Morning dose timing", "q": "What time is my morning medicine?", "papers": "08:00 AM", "record": "10:00 AM"},
    {"id": "sc-08", "patient_id": 3, "fact": "Incision ointment authorization", "q": "Can I use Neosporin on incision?", "papers": "no unauthorized ointments", "record": "apply approved cream"},
    {"id": "sc-09", "patient_id": 4, "fact": "Walking duration", "q": "How long should I walk daily?", "papers": "10-15 minutes twice daily", "record": "30 minutes continuous"},
    {"id": "sc-10", "patient_id": 5, "fact": "Salt intake limit", "q": "What is my daily sodium limit?", "papers": "under 2g daily", "record": "strict 1g sodium restriction"},
]

# ─── 3. Relative Dates (20 items) ─────────────────────────────────────────────
RELATIVE_DATES_20 = [
    {"id": "rd-01", "q": "What medicines do I take today?", "contains_relative": "today"},
    {"id": "rd-02", "q": "What are my scheduled doses tomorrow?", "contains_relative": "tomorrow"},
    {"id": "rd-03", "q": "When is my next visit?", "contains_relative": "next visit"},
    {"id": "rd-04", "q": "What should I do in 3 days?", "contains_relative": "in 3 days"},
    {"id": "rd-05", "q": "Do I have an appointment today?", "contains_relative": "today"},
    {"id": "rd-06", "q": "Will I take VasculoNorm tomorrow?", "contains_relative": "tomorrow"},
    {"id": "rd-07", "q": "Where is my next appointment scheduled?", "contains_relative": "next appointment"},
    {"id": "rd-08", "q": "Who is my doctor for the next visit?", "contains_relative": "next visit"},
    {"id": "rd-09", "q": "Can I walk outside in 3 days?", "contains_relative": "in 3 days"},
    {"id": "rd-10", "q": "What time is my first dose today?", "contains_relative": "today"},
    {"id": "rd-11", "q": "आज मुझे कौन सी दवा खानी है?", "lang": "hi", "contains_relative": "आज"},
    {"id": "rd-12", "q": "कल की दवाओं का शेड्यूल क्या है?", "lang": "hi", "contains_relative": "कल"},
    {"id": "rd-13", "q": "मेरी अगली विज़िट किस तारीख को है?", "lang": "hi", "contains_relative": "अगली विज़िट"},
    {"id": "rd-14", "q": "3 दिन बाद कौन सा चेकअप है?", "lang": "hi", "contains_relative": "3 दिन"},
    {"id": "rd-15", "q": "क्या आज मुझे डॉक्टर से मिलना है?", "lang": "hi", "contains_relative": "आज"},
    {"id": "rd-16", "q": "कल सुबह किस समय दवा लेनी है?", "lang": "hi", "contains_relative": "कल"},
    {"id": "rd-17", "q": "अगली डॉक्टर मुलाक़ात का समय क्या है?", "lang": "hi", "contains_relative": "अगली"},
    {"id": "rd-18", "q": "आज का मेरा सोडियम लिमिट क्या है?", "lang": "hi", "contains_relative": "आज"},
    {"id": "rd-19", "q": "क्या 3 दिन बाद टांके हटेंगे?", "lang": "hi", "contains_relative": "3 दिन"},
    {"id": "rd-20", "q": "आज शाम की खुराक किस समय लेनी है?", "lang": "hi", "contains_relative": "आज"},
]

# ─── 4. Hinglish Questions (20 items) ─────────────────────────────────────────
HINGLISH_QUESTIONS_20 = [
    {"id": "hg-01", "q": "CardioPulse goli kab lena hai?", "expected_concept": "medicine_times"},
    {"id": "hg-02", "q": "Mera agla appointment doctor se kab hai?", "expected_concept": "appointment"},
    {"id": "hg-03", "q": "Chire aur tanke ki dekhbhal kaise kare?", "expected_concept": "wound_care"},
    {"id": "hg-04", "q": "Dopahar ki dawai kis time khani hai?", "expected_concept": "medicine_times"},
    {"id": "hg-05", "q": "Kya mai kamre me chal sakta hu?", "expected_concept": "activity"},
    {"id": "hg-06", "q": "Namak kitna kam khana hai?", "expected_concept": "diet"},
    {"id": "hg-07", "q": "Din me kitna paani peena chahiye?", "expected_concept": "diet"},
    {"id": "hg-08", "q": "Chhati me severe dard hone par kya kare?", "expected_concept": "emergency"},
    {"id": "hg-09", "q": "Doctor Sharma se milne ka time kya hai?", "expected_concept": "appointment"},
    {"id": "hg-10", "q": "Kya mai bhari vajan utha sakta hu?", "expected_concept": "activity"},
    {"id": "hg-11", "q": "Subah ki goli khane ke baad leni hai ya pehle?", "expected_concept": "medicine_times"},
    {"id": "hg-12", "q": "Agar tanke laal ho jaye to kya kare?", "expected_concept": "wound_care"},
    {"id": "hg-13", "q": "Kya chire par koi marham laga sakte hai?", "expected_concept": "wound_care"},
    {"id": "hg-14", "q": "Clinic OPD room 302 kahan par hai?", "expected_concept": "appointment"},
    {"id": "hg-15", "q": "Meri attending physician kaun hai?", "expected_concept": "contacts"},
    {"id": "hg-16", "q": "Kya mai sidhiyan chadh sakta hu bina madad ke?", "expected_concept": "activity"},
    {"id": "hg-17", "q": "Dawai pani ke saath leni hai?", "expected_concept": "medicine_times"},
    {"id": "hg-18", "q": "Khana khane ke baad kaun si goli leni hai?", "expected_concept": "medicine_times"},
    {"id": "hg-19", "q": "Saans phoolne par turant kahan phone kare?", "expected_concept": "emergency"},
    {"id": "hg-20", "q": "Sham ko CardioPulse kis samay leni hai?", "expected_concept": "medicine_times"},
]

# ─── 5. Clarification Questions (15 items) ───────────────────────────────────
CLARIFICATION_QUESTIONS_15 = [
    {"id": "cl-01", "q": "When do I take my medicine?", "expected_type": "clarification"},
    {"id": "cl-02", "q": "What time is my pill?", "expected_type": "clarification"},
    {"id": "cl-03", "q": "When should I take my tablet?", "expected_type": "clarification"},
    {"id": "cl-04", "q": "How many times do I take medicine?", "expected_type": "clarification"},
    {"id": "cl-05", "q": "What is the schedule for my medications?", "expected_type": "clarification"},
    {"id": "cl-06", "q": "When is my dose?", "expected_type": "clarification"},
    {"id": "cl-07", "q": "Tell me when to take the pills", "expected_type": "clarification"},
    {"id": "cl-08", "q": "What is my medicine timing?", "expected_type": "clarification"},
    {"id": "cl-09", "q": "When do I take my daily medication?", "expected_type": "clarification"},
    {"id": "cl-10", "q": "When do I take my prescribed tablet?", "expected_type": "clarification"},
    {"id": "cl-11", "q": "दवा कब लेनी है?", "lang": "hi", "expected_type": "clarification"},
    {"id": "cl-12", "q": "गोली खाने का समय क्या है?", "lang": "hi", "expected_type": "clarification"},
    {"id": "cl-13", "q": "दवाई किस समय लेनी है?", "lang": "hi", "expected_type": "clarification"},
    {"id": "cl-14", "q": "Dawa kis samay leni hai?", "expected_type": "clarification"},
    {"id": "cl-15", "q": "Goli kab khani hai?", "expected_type": "clarification"},
]

# ─── 6. Staff Copilot Questions (40 items) ───────────────────────────────────
STAFF_COPILOT_QUESTIONS_40 = [
    # find_patients: missed_doses_at_least (6)
    {"id": "cp-01", "q": "Who missed doses today?", "expected_template": "find_patients", "expected_filter": "missed_doses_at_least"},
    {"id": "cp-02", "q": "Patients with missed doses in 24 hours", "expected_template": "find_patients", "expected_filter": "missed_doses_at_least"},
    {"id": "cp-03", "q": "Who missed 2 or more doses?", "expected_template": "find_patients", "expected_filter": "missed_doses_at_least"},
    {"id": "cp-04", "q": "Find patients who forgot medicine in past 12 hours", "expected_template": "find_patients", "expected_filter": "missed_doses_at_least"},
    {"id": "cp-05", "q": "Which patient has unconfirmed doses?", "expected_template": "find_patients", "expected_filter": "missed_doses_at_least"},
    {"id": "cp-06", "q": "List patients with missed doses", "expected_template": "find_patients", "expected_filter": "missed_doses_at_least"},

    # find_patients: no_checkin_today (4)
    {"id": "cp-07", "q": "Who hasn't checked in today?", "expected_template": "find_patients", "expected_filter": "no_checkin_today"},
    {"id": "cp-08", "q": "Patients with no check-in today", "expected_template": "find_patients", "expected_filter": "no_checkin_today"},
    {"id": "cp-09", "q": "Which patients have pending daily checkins?", "expected_template": "find_patients", "expected_filter": "no_checkin_today"},
    {"id": "cp-10", "q": "Find patients who missed daily checkin", "expected_template": "find_patients", "expected_filter": "no_checkin_today"},

    # find_patients: device_silent_over (3)
    {"id": "cp-11", "q": "Which sensors have been silent over 24 hours?", "expected_template": "find_patients", "expected_filter": "device_silent_over"},
    {"id": "cp-12", "q": "Find patients with offline devices", "expected_template": "find_patients", "expected_filter": "device_silent_over"},
    {"id": "cp-13", "q": "Show patients with device silent over 48 hours", "expected_template": "find_patients", "expected_filter": "device_silent_over"},

    # find_patients: open_flags (4)
    {"id": "cp-14", "q": "Show patients with open flags", "expected_template": "find_patients", "expected_filter": "open_flags"},
    {"id": "cp-15", "q": "Who has active alerts right now?", "expected_template": "find_patients", "expected_filter": "open_flags"},
    {"id": "cp-16", "q": "List active flags across all patients", "expected_template": "find_patients", "expected_filter": "open_flags"},
    {"id": "cp-17", "q": "Which patients have open clinical flags?", "expected_template": "find_patients", "expected_filter": "open_flags"},

    # find_patients: photo_pending (2)
    {"id": "cp-18", "q": "Who has a pending wound photo?", "expected_template": "find_patients", "expected_filter": "photo_pending"},
    {"id": "cp-19", "q": "Find patients with incision photo pending review", "expected_template": "find_patients", "expected_filter": "photo_pending"},

    # find_patients: sos_open (2)
    {"id": "cp-20", "q": "Any active SOS alerts?", "expected_template": "find_patients", "expected_filter": "sos_open"},
    {"id": "cp-21", "q": "Who triggered emergency SOS button?", "expected_template": "find_patients", "expected_filter": "sos_open"},

    # find_patients: family_consent_missing (2)
    {"id": "cp-22", "q": "Patients missing family consent", "expected_template": "find_patients", "expected_filter": "family_consent_missing"},
    {"id": "cp-23", "q": "Who has no caregiver consent signed?", "expected_template": "find_patients", "expected_filter": "family_consent_missing"},

    # patient_snapshot (5)
    {"id": "cp-24", "q": "Snapshot of Aarav Patel", "expected_template": "patient_snapshot", "expected_patient": "Aarav Patel"},
    {"id": "cp-25", "q": "Status for patient 1", "expected_template": "patient_snapshot", "expected_patient": "Aarav Patel"},
    {"id": "cp-26", "q": "Clinical summary of Meera Sharma", "expected_template": "patient_snapshot", "expected_patient": "Meera Sharma"},
    {"id": "cp-27", "q": "Tell me about Rajesh Verma", "expected_template": "patient_snapshot", "expected_patient": "Rajesh Verma"},
    {"id": "cp-28", "q": "Profile of Kabir Mehta", "expected_template": "patient_snapshot", "expected_patient": "Kabir Mehta"},

    # explain_alert (4)
    {"id": "cp-29", "q": "Explain alert 1", "expected_template": "explain_alert", "expected_flag_id": 1},
    {"id": "cp-30", "q": "Explain flag 2", "expected_template": "explain_alert", "expected_flag_id": 2},
    {"id": "cp-31", "q": "Why was flag 3 raised?", "expected_template": "explain_alert", "expected_flag_id": 3},
    {"id": "cp-32", "q": "Details on alert 12", "expected_template": "explain_alert", "expected_flag_id": 12},

    # draft_message (4)
    {"id": "cp-33", "q": "Draft message to Aarav about missed dose", "expected_template": "draft_message", "expected_purpose": "missed_dose_reminder"},
    {"id": "cp-34", "q": "Draft checkin prompt for Meera", "expected_template": "draft_message", "expected_purpose": "checkin_prompt"},
    {"id": "cp-35", "q": "Draft wound photo request for Rajesh", "expected_template": "draft_message", "expected_purpose": "wound_photo_request"},
    {"id": "cp-36", "q": "Compose appointment reminder for Sunita", "expected_template": "draft_message", "expected_purpose": "appointment_reminder"},

    # summarize_since (2)
    {"id": "cp-37", "q": "What happened to Aarav since yesterday?", "expected_template": "summarize_since", "expected_hours": 24},
    {"id": "cp-38", "q": "Summarize Meera since 48 hours", "expected_template": "summarize_since", "expected_hours": 48},

    # compare_vitals (2)
    {"id": "cp-39", "q": "Compare vitals for Aarav over 7 days", "expected_template": "compare_vitals", "expected_days": 7},
    {"id": "cp-40", "q": "Compare vitals for Meera over 3 days", "expected_template": "compare_vitals", "expected_days": 3},
]

# Partition all into DEV (80%) and HELD-OUT (20%)
DEV_DISCHARGE_QS, HELDOUT_DISCHARGE_QS = _partition_list(DISCHARGE_QUESTIONS_50, 0.8)
DEV_INJECTIONS, HELDOUT_INJECTIONS = _partition_list(PROMPT_INJECTIONS_10, 0.8)
DEV_OUT_OF_SCOPE, HELDOUT_OUT_OF_SCOPE = _partition_list(OUT_OF_SCOPE_10, 0.8)

DEV_MULTI_PART, HELDOUT_MULTI_PART = _partition_list(MULTI_PART_QUESTIONS_30, 0.8)
DEV_CONFLICTS, HELDOUT_CONFLICTS = _partition_list(SOURCE_CONFLICTS_10, 0.8)
DEV_RELATIVE_DATES, HELDOUT_RELATIVE_DATES = _partition_list(RELATIVE_DATES_20, 0.8)
DEV_HINGLISH, HELDOUT_HINGLISH = _partition_list(HINGLISH_QUESTIONS_20, 0.8)
DEV_CLARIFICATION, HELDOUT_CLARIFICATION = _partition_list(CLARIFICATION_QUESTIONS_15, 0.8)
DEV_COPILOT, HELDOUT_COPILOT = _partition_list(STAFF_COPILOT_QUESTIONS_40, 0.8)

# Fixed golden assertions
GOLDEN_DECISION_CASES = [
    {"id": "case-01", "name": "Meera Sharma SpO2 Drop", "patient_id": 2, "flag_id": 2, "expected_step": "Urgent_Escalation"},
    {"id": "case-02", "name": "Rajesh Verma Sternal Redness", "patient_id": 3, "flag_id": 3, "expected_step": "Request_Wound_Photo"},
    {"id": "case-03", "name": "Aarav Patel Missed Dose", "patient_id": 1, "flag_id": 1, "expected_step": "Send_Dose_Reminder"},
    {"id": "case-04", "name": "Sunita Rao Normal Vitals", "patient_id": 5, "flag_id": 5, "expected_step": "Routine_Monitoring"},
    {"id": "case-05", "name": "Kabir Mehta Routine Checkin", "patient_id": 4, "flag_id": 4, "expected_step": "Routine_Monitoring"},
]
DEV_GOLDEN_CASES, HELDOUT_GOLDEN_CASES = _partition_list(GOLDEN_DECISION_CASES, 0.8)


def get_dev_dataset() -> Dict[str, List[Any]]:
    """Returns the comprehensive DEV dataset (80%)."""
    return {
        "discharge_questions": DEV_DISCHARGE_QS,
        "prompt_injections": DEV_INJECTIONS,
        "out_of_scope": DEV_OUT_OF_SCOPE,
        "multi_part": DEV_MULTI_PART,
        "conflicts": DEV_CONFLICTS,
        "relative_dates": DEV_RELATIVE_DATES,
        "hinglish": DEV_HINGLISH,
        "clarification": DEV_CLARIFICATION,
        "copilot_questions": DEV_COPILOT,
        "golden_cases": DEV_GOLDEN_CASES,
    }


def get_held_out_dataset() -> Dict[str, List[Any]]:
    """Returns the unpolluted HELD-OUT dataset (20%)."""
    return {
        "discharge_questions": HELDOUT_DISCHARGE_QS,
        "prompt_injections": HELDOUT_INJECTIONS,
        "out_of_scope": HELDOUT_OUT_OF_SCOPE,
        "multi_part": HELDOUT_MULTI_PART,
        "conflicts": HELDOUT_CONFLICTS,
        "relative_dates": HELDOUT_RELATIVE_DATES,
        "hinglish": HELDOUT_HINGLISH,
        "clarification": HELDOUT_CLARIFICATION,
        "copilot_questions": HELDOUT_COPILOT,
        "golden_cases": HELDOUT_GOLDEN_CASES,
    }
