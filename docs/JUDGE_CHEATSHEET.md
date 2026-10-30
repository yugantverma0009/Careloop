# CareLoop Judge Cheat-Sheet

## 1. 30-Second Elevator Pitch
> "CareLoop is a post-discharge recovery system that closes the loop between patients, family helpers, nurses and doctors.
> Instead of giving conversational AI authority over clinical alerts, CareLoop separates communication from decisions:
> **The LLM talks. Rules decide. Humans act.**
> Clinician-approved deterministic rules detect health risks; the patient and family receive calm, grounded guidance with consent; the triage nurse works a prioritized queue; and the attending doctor retains sole authority to approve summaries, change safety limits, and sign off on care decisions."

---

## 2. Four One-Liners (Memorize These)
- **Doctor (Dr. Ananya Sharma):** *"The doctor decides, approves and exports."*
- **Nurse (Priya Nair):** *"The nurse calls, logs, rechecks and escalates."*
- **Patient (Aarav Patel):** *"The patient acts, checks in and asks their papers."*
- **Family Helper (Neha Patel):** *"The family helper supports, is informed with consent, and calls 112 if needed."*

---

## 3. Demo Sequence & Timings (6:30 Total)

| Timestamp | Screen / Role | Key Click / Action | Core Takeaway |
|---|---|---|---|
| **0:00** | Landing Page | Four role cards, database stats (5 patients, 2 staff, 3 flags) | Genuinely different roles; zero exaggerated claims |
| **0:30** | Patient (Aarav) | Taps Taken; sends check-in; queries appointment & tests dose refusal | Patient acts; AI strictly grounded; refuses medical changes |
| **2:00** | Presenter | Trigger simulator: SpO₂ drops to 91% | Telemetry event ingested from wearable watch |
| **2:15** | Patient | Banner appears: "Your care team has been told. Call 112 if you have chest pain." | Patient reassured without panic or clinical jargon |
| **2:30** | Family (Neha) | "What you may need to do" card updates; taps "I helped Aarav take it" | Family notified with consent; useful helper task |
| **3:15** | Nurse (Priya) | My Call List shows Aarav at top; logs phone call; clicks "Ask doctor" | Nurse works prioritized queue & escalates urgent cases |
| **4:15** | Doctor (Dr. Sharma) | Needs My Decision shows Aarav; reviews ladder; resolves; approves AI summary | Attending physician makes decisions; AI is only a draft |
| **5:30** | Audit Log | Views chronologic trace of reading, flag, SMS, call, and resolution | Full regulatory auditability |
| **6:00** | Consent Gating | Patient turns Sharing OFF; Family portal immediately locks | Consent is real, dynamic, and enforced |
| **6:30** | Close | "The LLM talks. Rules decide. Humans act." | Guiding principle |

---

## 4. Real Numbers on Screen (Know Your Data)
- **Cohort Size:** Exactly **5** monitored patients (`Aarav Patel`, `Meera Rao`, `Rajesh Kumar`, `Kabir Mehta`, `Sunita Sharma`).
- **Care Staff:** Exactly **2** (`Dr. Ananya Sharma` [Attending Physician], `Priya Nair` [Lead Nurse]).
- **Baseline Open Flags:** Exactly **3**
  - *Meera Rao:* Silent Device (No Data > 6h) — Review Soon
  - *Rajesh Kumar:* Emergency Ingestion (Severe pain 8/10 + chest pain) — Immediate
  - *Sunita Sharma:* Missed Doses (2 unconfirmed doses) — Review Soon
- **Headline Pulse Rate:** **74 bpm (Good)** for Aarav (an impossible 450 bpm reading is filtered out as invalid).
- **Aarav SpO₂ Rule Limit:** Approved threshold is **< 94.0%** (set and approved by Dr. Sharma on 28 Oct).
- **Post-Discharge Day Numbers:** Aarav (Day 3), Meera (Day 6), Rajesh (Day 5), Kabir (Day 9), Sunita (Day 4).

---

## 5. Say and Do Not Say Guidelines

### ✅ SAY:
- *"Prototype with synthetic sample data."*
- *"Rules raise flags; the AI explains and drafts."*
- *"The nurse can resolve routine flags; urgent flags require the doctor."*
- *"Every action is recorded in a tamper-evident audit log."*
- *"The family only sees what the patient explicitly allowed."*
- *"Limits are approved by the attending physician."*

### ❌ DO NOT SAY:
- *"prevents readmissions"*
- *"clinically validated"*
- *"100% accurate"*
- *"AI detects problems / AI diagnosed"*
- *"hardware-verified"*
- *"stable"* / *"normal"* / *"optimal"*
- Do not read out arbitrary thresholds as absolute clinical truth.

---

## 6. Likely Judge Questions & Crisp Answers

**Q: Why four roles instead of a single shared dashboard?**  
*A: Patients need simple actions to follow their discharge instructions; families need reassurance and small helper tasks with consent; nurses work a fast, prioritized call queue; and doctors need high-level decisions and approvals. Giving everyone the same screen creates confusion and privacy violations.*

**Q: Does the AI make medical decisions or diagnose patients?**  
*A: Never. Medical rules are evaluated in deterministic code and SQL triggers. The LLM only answers questions from the patient's own discharge papers with clickable source citations, and writes draft summaries that a doctor must inspect and approve.*

**Q: What if the wearable watch sends a glitch or wrong number?**  
*A: Signal plausibility checks filter out impossible physiological numbers (such as 450 bpm) as invalid before rules evaluate them. Missing readings are flagged explicitly as 'No Data' rather than assumed to be safe.*

**Q: What happens if a patient doesn't respond or nobody answers the phone?**  
*A: CareLoop features an automated 4-tier escalation ladder: Patient Prompt → Caregiver SMS (consent-gated) → Nurse Alert → Doctor Alert. Each step has a target timer and logs delivery status.*

**Q: How is patient privacy protected?**  
*A: We enforce strict role-based access control. The family helper cannot see doctor notes, symptom free-text, or chat transcripts. If the patient flips their sharing toggle off, family access is revoked immediately.*

**Q: How would this scale to a real hospital?**  
*A: The architecture separates stateless frontends, role-based APIs, and standard FHIR R4 exports. Hospital EHR integration can ingest discharge summaries and export signed clinical notes via standard FHIR bundles.*

**Q: What are the current limitations?**  
*A: This is an academic research prototype evaluated with synthetic data and simulated watches. It is not cleared as a medical device and would require clinical trials and regulatory review prior to clinical deployment.*

