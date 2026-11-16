"""
backend/app/agents/phrase_bank_service.py — Doctor-Approved Phrase Bank (Phase 2 Task 3)

Rule:
- Conversational phrases come from an approved bank (English & Hindi) per situation.
- Praise is strictly for actions (e.g. "You finished your check-in"), never health praise.
- Rotational selection prevents repetitive robotic speech.
- Reading grade level <= 7.0 for patient readability.
"""

from typing import Dict, Any, List, Optional
import random
from backend.app.db import get_conn


DEFAULT_PHRASES: List[Dict[str, Any]] = [
    # ── Greetings (8) ──
    {"category": "greeting", "text_en": "Good morning. Ready for today's check-in?", "text_hi": "शुभ प्रभात। क्या आप आज के चेक-इन के लिए तैयार हैं?", "reading_grade_level": 5.0},
    {"category": "greeting", "text_en": "Hello! How are you feeling today?", "text_hi": "नमस्ते! आज आप कैसा महसूस कर रहे हैं?", "reading_grade_level": 4.5},
    {"category": "greeting", "text_en": "Welcome back. Let's do your daily recovery check-in.", "text_hi": "स्वागत है। आइए आपका दैनिक रिकवरी चेक-इन पूरा करें।", "reading_grade_level": 5.5},
    {"category": "greeting", "text_en": "Good day. It takes about 30 seconds to share how you're doing.", "text_hi": "नमस्ते। आज का चेक-इन करने में केवल 30 सेकंड लगेंगे।", "reading_grade_level": 5.2},
    {"category": "greeting", "text_en": "Hello. I am here to help with your routine today.", "text_hi": "नमस्ते। आज की दिनचर्या में मैं आपकी मदद के लिए उपस्थित हूँ।", "reading_grade_level": 5.0},
    {"category": "greeting", "text_en": "Good evening. Let's record your recovery updates for the day.", "text_hi": "शुभ संध्या। आइए आज की रिकवरी प्रगति दर्ज करें।", "reading_grade_level": 6.0},
    {"category": "greeting", "text_en": "Hello! Ready to take a moment for your care check-in?", "text_hi": "नमस्ते! क्या आप अपने दैनिक चेक-इन के लिए तैयार हैं?", "reading_grade_level": 5.0},
    {"category": "greeting", "text_en": "Welcome. Let's walk through today's health questions together.", "text_hi": "स्वागत है। आइए मिलकर आज के स्वास्थ्य प्रश्नों को पूरा करें।", "reading_grade_level": 6.0},

    # ── Acknowledgements (10) ──
    {"category": "acknowledgement", "text_en": "Thank you for telling me.", "text_hi": "बताने के लिए धन्यवाद।", "reading_grade_level": 4.0},
    {"category": "acknowledgement", "text_en": "I've noted that down.", "text_hi": "मैंने यह दर्ज कर लिया है।", "reading_grade_level": 4.5},
    {"category": "acknowledgement", "text_en": "Understood. Moving to the next question.", "text_hi": "समझ गया। अब अगले प्रश्न पर चलते हैं।", "reading_grade_level": 5.0},
    {"category": "acknowledgement", "text_en": "Got it. Thank you for answering.", "text_hi": "नोट कर लिया गया है। उत्तर देने के लिए धन्यवाद।", "reading_grade_level": 4.0},
    {"category": "acknowledgement", "text_en": "Thank you. Your care team values this detail.", "text_hi": "धन्यवाद। आपकी देखभाल टीम के लिए यह जानकारी महत्वपूर्ण है।", "reading_grade_level": 6.0},
    {"category": "acknowledgement", "text_en": "Recorded clearly. Let's continue.", "text_hi": "सफलतापूर्वक दर्ज किया गया। आइए आगे बढ़ें।", "reading_grade_level": 5.2},
    {"category": "acknowledgement", "text_en": "Thank you for sharing your symptom status.", "text_hi": "लक्षणों की स्थिति साझा करने के लिए धन्यवाद।", "reading_grade_level": 6.0},
    {"category": "acknowledgement", "text_en": "Noted. Keeping your team informed.", "text_hi": "दर्ज कर लिया गया है। आपकी टीम को सूचित रखा जाएगा।", "reading_grade_level": 5.5},
    {"category": "acknowledgement", "text_en": "Thank you. This helps us track your routine.", "text_hi": "धन्यवाद। इससे आपकी दिनचर्या पर नज़र रखने में मदद मिलती है।", "reading_grade_level": 5.5},
    {"category": "acknowledgement", "text_en": "Understood clearly. Thank you.", "text_hi": "स्पष्ट रूप से समझ लिया गया। धन्यवाद।", "reading_grade_level": 4.5},

    # ── Closings & Summaries (8) ──
    {"category": "closing", "text_en": "Here is what I will send to your care team:", "text_hi": "यहाँ वह जानकारी है जो आपकी देखभाल टीम को भेजी जाएगी:", "reading_grade_level": 5.0},
    {"category": "closing", "text_en": "Check-in completed. Your answers have been recorded.", "text_hi": "चेक-इन पूरा हो गया। आपके उत्तर दर्ज कर लिए गए हैं।", "reading_grade_level": 5.5},
    {"category": "closing", "text_en": "All set for today. Your care team can see your update.", "text_hi": "आज के लिए सब पूरा हो गया। आपकी देखभाल टीम आपका अपडेट देख सकती है।", "reading_grade_level": 5.0},
    {"category": "closing", "text_en": "Thank you. Your daily routine report has been submitted.", "text_hi": "धन्यवाद। आपकी दैनिक दिनचर्या रिपोर्ट जमा कर दी गई है।", "reading_grade_level": 6.0},
    {"category": "closing", "text_en": "Your recovery facts have been shared with Nurse Priya.", "text_hi": "आपकी रिकवरी से जुड़े तथ्य नर्स प्रिया के साथ साझा कर दिए गए हैं।", "reading_grade_level": 5.8},
    {"category": "closing", "text_en": "Today's check-in is finished. Have a restful recovery today.", "text_hi": "आज का चेक-इन समाप्त हुआ। आपका दिन आरामदायक और स्वस्थ रहे।", "reading_grade_level": 5.5},
    {"category": "closing", "text_en": "Submitted successfully. Your team will review if needed.", "text_hi": "सफलतापूर्वक सबमिट किया गया। आवश्यकता पड़ने पर आपकी टीम समीक्षा करेगी।", "reading_grade_level": 6.2},
    {"category": "closing", "text_en": "Thank you for completing your daily check-in on time.", "text_hi": "समय पर अपना दैनिक चेक-इन पूरा करने के लिए धन्यवाद।", "reading_grade_level": 6.0},

    # ── Action Encouragement (No Health Praise) (8) ──
    {"category": "encouragement", "text_en": "You finished your daily check-in.", "text_hi": "आपने अपना दैनिक चेक-इन पूरा कर लिया है।", "reading_grade_level": 4.0},
    {"category": "encouragement", "text_en": "You have taken all scheduled morning doses.", "text_hi": "आपने सुबह की सभी निर्धारित दवाएं ले ली हैं।", "reading_grade_level": 5.0},
    {"category": "encouragement", "text_en": "You logged your symptom status today.", "text_hi": "आज आपने अपने लक्षणों की स्थिति दर्ज की।", "reading_grade_level": 5.0},
    {"category": "encouragement", "text_en": "You marked your walking routine as completed.", "text_hi": "आपने अपनी टहलने की दिनचर्या पूरी के रूप में चिह्नित की।", "reading_grade_level": 5.5},
    {"category": "encouragement", "text_en": "You kept up with your recovery plan today.", "text_hi": "आज आपने अपने रिकवरी प्लान का पालन किया।", "reading_grade_level": 5.2},
    {"category": "encouragement", "text_en": "You confirmed your afternoon medication.", "text_hi": "आपने अपनी दोपहर की दवा की पुष्टि की।", "reading_grade_level": 5.5},
    {"category": "encouragement", "text_en": "You completed both check-ins this week.", "text_hi": "आपने इस सप्ताह दोनों चेक-इन पूरे किए।", "reading_grade_level": 5.0},
    {"category": "encouragement", "text_en": "You answered all recovery questions for today.", "text_hi": "आपने आज के सभी रिकवरी प्रश्नों के उत्तर दिए।", "reading_grade_level": 5.2},

    # ── Emergency Guidance (6) ──
    {"category": "emergency", "text_en": "Immediate Safety Alert: A triage nurse has been alerted right now.", "text_hi": "आपातकालीन सुरक्षा सूचना: एक ट्राइएज नर्स को तुरंत सूचित किया गया है।", "reading_grade_level": 6.5},
    {"category": "emergency", "text_en": "Please sit down and rest. If symptoms worsen, call 112 immediately.", "text_hi": "कृपया आराम से बैठें। यदि लक्षण बढ़ें, तो तुरंत 112 पर कॉल करें।", "reading_grade_level": 5.5},
    {"category": "emergency", "text_en": "Your safety is our priority. An urgent nurse call request was created.", "text_hi": "आपकी सुरक्षा हमारी प्राथमिकता है। नर्स कॉल का तत्काल अनुरोध बनाया गया है।", "reading_grade_level": 6.5},
    {"category": "emergency", "text_en": "Keep your phone near you. Your care team is reviewing this alert.", "text_hi": "अपना फोन अपने पास रखें। आपकी देखभाल टीम इस अलर्ट की समीक्षा कर रही है।", "reading_grade_level": 5.0},
    {"category": "emergency", "text_en": "Do not wait if you feel severe pain or trouble breathing: call 112.", "text_hi": "यदि तेज दर्द या सांस लेने में तकलीफ हो तो प्रतीक्षा न करें: 112 डायल करें।", "reading_grade_level": 5.5},
    {"category": "emergency", "text_en": "Emergency safety protocol activated. Routine questions are paused.", "text_hi": "आपातकालीन सुरक्षा प्रोटोकॉल सक्रिय। सामान्य प्रश्न रोक दिए गए हैं।", "reading_grade_level": 6.5},
]


class PhraseBankService:
    @classmethod
    def seed_initial_phrases(cls):
        """Seeds the 40 doctor-approved phrases if table is empty."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM phrase_bank")
            row = cur.fetchone()
            if row and row["cnt"] > 0:
                return row["cnt"]

            for p in DEFAULT_PHRASES:
                cur.execute(
                    """INSERT INTO phrase_bank
                       (category, text_en, text_hi, reading_grade_level, status, approved_by_staff_id, is_active)
                       VALUES (%s, %s, %s, %s, 'Approved', 1, TRUE)""",
                    (p["category"], p["text_en"], p["text_hi"], p.get("reading_grade_level", 5.5))
                )
            conn.commit()
            return len(DEFAULT_PHRASES)

    @classmethod
    def get_rotated_phrase(cls, category: str, language: str = "en", turn_seed: Optional[int] = None) -> str:
        """Selects a doctor-approved phrase rotated deterministically or randomly within the category."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT text_en, text_hi FROM phrase_bank
                   WHERE category = %s AND status = 'Approved' AND is_active = TRUE
                   ORDER BY phrase_id ASC""",
                (category,)
            )
            rows = cur.fetchall()

        if not rows:
            # Fallback to in-memory defaults
            matching = [p for p in DEFAULT_PHRASES if p["category"] == category]
            if not matching:
                return "Thank you." if language == "en" else "धन्यवाद।"
            idx = (turn_seed % len(matching)) if turn_seed is not None else random.randint(0, len(matching) - 1)
            p = matching[idx]
            return p["text_hi"] if language == "hi" else p["text_en"]

        idx = (turn_seed % len(rows)) if turn_seed is not None else random.randint(0, len(rows) - 1)
        chosen = rows[idx]
        return chosen["text_hi"] if language == "hi" else chosen["text_en"]

    @classmethod
    def list_phrases_for_doctor(cls) -> List[Dict[str, Any]]:
        """Returns all phrase bank rows for Doctor review / Approvals tab."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT phrase_id, category, text_en, text_hi, reading_grade_level, status, approved_by_staff_id, is_active, created_at
                   FROM phrase_bank
                   ORDER BY category ASC, phrase_id ASC"""
            )
            return cur.fetchall()

    @classmethod
    def update_phrase_status(cls, phrase_id: int, status: str, doctor_staff_id: int) -> bool:
        """Doctor approves or disables a phrase in the bank."""
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """UPDATE phrase_bank
                   SET status = %s, approved_by_staff_id = %s
                   WHERE phrase_id = %s""",
                (status, doctor_staff_id, phrase_id)
            )
            conn.commit()
            return cur.rowcount > 0

    @classmethod
    def get_approved_phrases(cls, category: Optional[str] = None, language: str = "en") -> List[Dict[str, Any]]:
        """Fetch all approved phrases for a given category and language."""
        with get_conn() as conn, conn.cursor() as cur:
            query = "SELECT phrase_id, category, text_en, text_hi, reading_grade_level, status FROM phrase_bank WHERE status = 'Approved'"
            params = []
            if category:
                query += " AND category = %s"
                params.append(category)
            query += " ORDER BY phrase_id ASC"
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            for r in rows:
                r["phrase_text"] = r["text_hi"] if language == "hi" else r["text_en"]
            return rows

    @classmethod
    def get_random_approved(cls, category: str, language: str) -> str:
        """Fetch a rotated approved phrase for category and language."""
        return cls.get_rotated_phrase(category=category, language=language)
