# CareLoop Care Team Portal — 5-Minute Doctor Demo Script

This script provides a concise, high-impact clinical demonstration of the CareLoop Doctor & Nurse Portal, designed to be executed in under 5 minutes by an attending physician or clinical product specialist.

---

## 🎯 Demo Objectives
1. Demonstrate deterministic clinical safety ("The LLM talks. Rules decide. Humans act").
2. Showcase the prioritized, deduplicated clinical worklist and SLA management.
3. Walk through deep chart review, telemetry quality verification, and medication adherence.
4. Demonstrate AI summary review grounded in deterministic fact sheets (with zero judgment words).
5. Highlight governance, rule threshold history, FHIR R4 interoperability, and operational insights.

---

## ⏱️ Timeline & Script Steps

### Minute 0:00 – 0:45 | Login & Triage Worklist
- **Action**: Open [http://localhost:3000](http://localhost:3000). On the landing screen, click the **"Doctor Demo (Dr. Ananya Sharma)"** quick-login button.
- **Talking Points**:
  > *"Welcome to CareLoop's Care Team Portal. Notice the top banner: identity verification is unambiguous. We are logged in as Dr. Ananya Sharma, Cardiology Attending.*
  > 
  > *Our default landing view is the Prioritized Worklist. Unlike raw alert logs that create alarm fatigue, CareLoop groups alerts per patient into 4 distinct clinical tiers: Immediate, Urgent, Review soon, and Routine.*
  > 
  > *Notice Aarav Patel at the top. The red Immediate chip indicates a critical SpO2 drop below 88%. The SLA badge displays in real time how long this alert has been open. CareLoop guarantees that acknowledging an alert requires a named clinician, preventing alerts from falling through the cracks."*

---

### Minute 0:45 – 1:45 | Flag Investigation & Action Drawer
- **Action**: Click on Aarav Patel's row to open the Flag Detail Drawer.
- **Talking Points**:
  > *"When we open the flag drawer, we see full clinical provenance. The exact rule trigger is displayed with its mathematical criteria: `SpO2 < 88% for >= 2 consecutive readings`.*
  > 
  > *Beneath the trigger, the Autonomous Escalation Ladder shows who was contacted: first a patient prompt, then a caregiver alert, and now an escalated nurse notification.*
  > 
  > *Here, I can click 'Acknowledge' to take clinical ownership, or click 'Resolve' or 'Dismiss'. When dismissing, the system mandates a clinical reason code — such as 'Sensor artifact' or 'Patient ambulating' — ensuring accountability and eliminating unexplained dismissals."*

---

### Minute 1:45 – 2:45 | Patient Chart, Telemetry & Adherence Grid
- **Action**: Click the **"Open Full Patient Chart"** button (or press `Ctrl+K`, type `Aarav`, and hit Enter).
- **Talking Points**:
  > *"In the Patient Chart, notice the Patient Overview banner: Patient Code, ABHA Health ID, Age, Day 3 post-CABG, and attending physician are all visible.*
  > 
  > *Looking at the Vital Signs Timeline, telemetry readings are never just raw numbers. Each reading carries a signal quality badge — Good, Degraded, or Invalid — and shows whether it crossed the clinician-defined rule threshold.*
  > 
  > *In the Medication Adherence section, past doses show real confirmation timestamps and skip reasons, while upcoming doses are explicitly labeled as 'Scheduled' rather than 'Missed', avoiding misleading compliance statistics."*

---

### Minute 2:45 – 3:45 | Deterministic Summaries & Shift Handoff
- **Action**: Navigate to the **"Clinical Summaries"** tab, select Aarav Patel's pending summary, then switch to the **"Shift Handoff (I-PASS)"** tab.
- **Talking Points**:
  > *"Here in Clinical Summaries, we see our LLM safety architecture in action. The draft summary is generated strictly from a deterministic fact sheet of sensor events and medication logs.*
  > 
  > *Per clinical safety protocol, the LLM is prohibited from using speculative judgment words like 'stable' or 'normal'. As an attending doctor, I can inspect the exact source data, edit the draft, and officially approve or reject it.*
  > 
  > *In the Shift Handoff tab, we follow the structured I-PASS protocol: Illness severity tier, Patient summary, Action list with assigned task owners, and Situation contingency plans — ensuring zero communication gaps during shift transitions."*

---

### Minute 3:45 – 4:45 | Pathway Templates, FHIR R4 & Operational Insights
- **Action**: Return to Patient Chart $\to$ **"Rules"** subtab. Click **"Apply Pathway Template"**, open the modal, then close and navigate to **"Insights"** tab.
- **Talking Points**:
  > *"In the Rules tab, we provide standard clinical templates like Post-Cardiac Surgery and DKA Recovery. But notice: default thresholds ship completely BLANK. Doctors must explicitly enter numeric thresholds before applying a template — the system makes zero medical assumptions.*
  > 
  > *Every threshold change is saved to an immutable audit history with author and timestamp.*
  > 
  > *At the top of the chart, one click on 'Export FHIR R4 Bundle' generates a complete, validated HL7 FHIR R4 collection bundle with LOINC codes for EHR interoperability.*
  > 
  > *Finally, our Operational Insights dashboard tracks 9 non-outcome metrics: median acknowledgment latency, SLA adherence, and device connectivity uptime — without making unbacked prognostic claims."*

---

### Minute 4:45 – 5:00 | Summary & Conclusion
- **Talking Points**:
  > *"To summarize: CareLoop gives clinical teams an accountable, auditable, and lightning-fast portal where rules decide, deterministic data grounds all text, and clinicians remain firmly in control."*
