# CareLoop Patient Portal — 5-Minute Demonstration Script

This walkthrough script demonstrates all features of the upgraded CareLoop Patient Portal (`/patient`) to clinicians, stakeholders, and product evaluators.

**Target Duration**: 5 minutes  
**Demo Account**: Aarav Patel (`aarav.demo@example.test` / `Demo@12345`)  
**Portal URL**: `http://localhost:3000/patient`

---

## Demo Timeline Overview

| Minute | Stage / Feature | What to Show |
|---|---|---|
| **0:00 - 1:00** | **Login & Recovery Overview** | Status banner, realistic dose schedule, 1-tap "Mark Taken", 5-min Undo toast, Skip sheet with reason. |
| **1:00 - 2:00** | **Calendar & Plan Checklist** | Month grid, daily dose breakdown, doctor follow-up appointment, 1-tap `.ics` calendar sync download. |
| **2:00 - 3:00** | **Daily Check-in (under 30s)** | Pain 0-10 slider, multi-select symptom & location chips, trend comparison, optional voice recording, live care team confirmation. |
| **3:00 - 4:15** | **Grounded RAG Assistant** | Starter chips, question about discharge paper warning signs, Grounded Source Pill chip, Source Inspection Drawer, dose modification refusal with "Ask My Care Team" escalation, thumbs up/down feedback. |
| **4:15 - 5:00** | **Safety, Language & Dark Mode** | Emergency keyword bypass ("chest pain" / "सांस लेने में तकलीफ") showing instant 112 calling alert without waiting for LLM; toggle Hindi (`हिंदी`) and Dark Mode. |

---

## Detailed Step-by-Step Walkthrough

### Step 1: Login & Recovery Overview (Minute 0:00 - 1:00)
1. **Navigate to**: `http://localhost:3000/login`
2. **Enter Credentials**:
   - Email: `aarav.demo@example.test`
   - Password: `Demo@12345`
   - Click **Sign In**.
3. **Point out Overview Screen**:
   - **Header**: Shows *"Recovery portal · Day 13 after discharge"*.
   - **Banner**: Reflects real patient care status (e.g. *"Waiting for care team review"* or *"Care team acknowledged"*). Emphasize that there is **no permanent red alarm banner**.
   - **Schedule Section**: Morning dose (`CardioPulse-XR`) is marked as **Taken** with green badge.
4. **Demonstrate 1-Tap "Mark Taken"**:
   - On the afternoon dose (`VasculoNorm-5`), click the green **"Mark Taken"** button.
   - Observe the immediate status transition to **Taken**.
5. **Demonstrate 5-Minute Undo**:
   - A dark floating toast appears at the bottom-right: *"Marked VasculoNorm-5 as taken. Undo (5 min)"*.
   - Click **Undo**. Observe the dose immediately reverts back to pending without page reload.
6. **Demonstrate Skip Reason Sheet**:
   - Click **"Skip"** on the dose card.
   - Modal drawer opens asking *"Why are you skipping this dose?"*.
   - Select *"Felt unwell / Nauseous"* and click **Confirm Skip**.
   - Notice the dose status becomes **Skipped** with amber badge.

---

### Step 2: Calendar & Care Plan Checklist (Minute 1:00 - 2:00)
1. In the sidebar, click **"My calendar"**.
2. **Month Grid**:
   - Point out days with completed doses (green dots), skipped doses (amber dots), and appointments (blue calendar icons).
3. **Day Drawer**:
   - Click on today's date (or any date with an appointment).
   - The right panel updates with the complete day breakdown: prescribed doses, scheduled appointments, and check-in history.
4. **1-Tap .ics Download**:
   - Under the upcoming visit with *Dr. Ananya Sharma* on November 4, click **"Add visit to calendar (.ics)"**.
   - Show that a standard RFC 5545 `.ics` file downloads immediately, ready to import into Apple Calendar, Google Calendar, or Outlook with exact UTC times.

---

### Step 3: Daily Check-in in Under 30 Seconds (Minute 2:00 - 3:00)
1. In the sidebar, click **"Daily check-in"**.
2. **Pain Scale (0 - 10)**:
   - Tap **4** on the 0-10 numeric scale.
3. **Structured Chips**:
   - Under symptoms, tap **"Dizziness"** and **"Swelling"**.
   - Under location, tap **"Surgical site"**.
4. **Trend Comparison**:
   - Under *"Compared with yesterday"*, tap **"Better"**.
5. **Multi-Modal Input (Voice or Text)**:
   - Point to the microphone button: explain that patients can speak in English or Hindi, or type directly into the notes field.
6. **Submit**:
   - Click **"Send to my care team"**.
   - The submission finishes within 1 second.
   - Screen displays factual green confirmation: *"Sent. Your care team can see this."*
   - Scroll down to show the **14-day history chart**, showing prior pain scores and symptom timelines.

---

### Step 4: Grounded RAG Assistant & Safety Engine (Minute 3:00 - 4:15)
1. In the sidebar, click **"Ask my discharge papers"**.
2. **Starter Prompt Chips**:
   - Notice the 4 starter chips on the empty state.
   - Click the starter chip: *"What warning signs should I watch for?"*.
3. **Grounded Answer & Citations**:
   - Assistant answers with bulleted warning signs strictly from Aarav's hospital discharge summary.
   - Below the message bubble, point out the **Grounded Source Pill**: `📄 Discharge summary · Warning signs · p.2`.
4. **Source Inspection Drawer**:
   - Click the source pill.
   - The **Source Record Passage** drawer slides in, showing the verbatim text excerpt from the document, page number, section title, and hospital badge.
   - Press **Escape** on the keyboard to close the drawer.
5. **Safety: Dose Modification Refusal**:
   - Type in the chat input: *"Can I double my dose of CardioPulse today?"*
   - Assistant immediately refuses: *"I cannot advise you to change your medicine dosage. Please consult your doctor or care team."*
   - Point out the **"👨‍⚕️ Ask My Care Team"** escalation button that appears automatically under the refusal.
   - Click **"Ask My Care Team"**. It confirms with *"✓ Request Sent"*, and a clinical follow-up task is logged in the backend.
6. **Feedback Thumbs**:
   - Click the **Thumbs Up** (👍) icon on any answer to submit 1-tap feedback.

---

### Step 5: Emergency Bypass, Hindi & Dark Mode (Minute 4:15 - 5:00)
1. **Deterministic Emergency Bypass**:
   - Type in the chat input: *"I have severe chest pain and shortness of breath"*.
   - **Crucial Safety Note**: Show that **no LLM is called**. The emergency detector triggers instantly with a red emergency notice and a clickable **📞 Call 112 Emergency** button.
2. **Hindi Language Support**:
   - Click **हिंदी** in the top navigation bar.
   - Observe the entire interface cleanly re-renders in natural everyday Hindi:
     - *"रिकवरी अवलोकन"*, *"अगली दवा"*, *"ले ली"*, *"छोड़ें"*, *"मेरा कैलेंडर"*, *"दैनिक चेक-इन"*.
   - Type a question in Hindi: *"मेरी अगली विज़िट कब है?"*
   - Assistant replies in Hindi with the exact appointment date and doctor name from the care plan database.
3. **Dark Mode**:
   - Click the moon icon (**🌙**) in the top header.
   - Observe the rich dark theme (`--navy-deep: #070d18`, `--bg-surface: #111a2c`) preserving all WCAG AA contrast ratios.

---

## End of Demo Summary
- **Style Lock**: 100% maintained; Landing and Login pages remain pixel-identical.
- **Safety**: 100% deterministic emergency bypass; zero ungrounded numeric inventions; dose change refusal with clinician follow-up task creation.
- **Accessibility**: Keyboard navigable (Tab, Esc), ARIA live regions, 44px tap targets, WCAG AA compliant in light and dark mode.
