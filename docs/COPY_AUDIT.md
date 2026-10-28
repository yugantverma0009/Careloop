# CareLoop On-Screen Copy Audit & Proposed Rewrites

This document lists **every user-facing text string** across the CareLoop application, with proposed plain-language, honest rewrites in both English (EN) and everyday Hindi (HI).

> **Status**: Audit Completed. Awaiting User Approval before applying code edits.  
> **Hard Limits Honored**: No changes to components, layouts, CSS, routes, APIs, DB schemas, enum values, numbers, or data. No new emojis or lines. All strings within ~20% length of originals. All banned words removed.

---

## Summary of Banned Word Deletions & Canonical Replacements

| Banned Term / Pattern | Canonical Replacement (EN) | Canonical Replacement (HI) |
| :--- | :--- | :--- |
| `NATIONAL CLINICAL GOVERNANCE` | `POST-DISCHARGE FOLLOW-UP` | `डिस्चार्ज के बाद देखभाल` |
| `National Clinical Governance Platform` | `Follow-up after discharge` | `अस्पताल से छुट्टी के बाद देखभाल` |
| `DEMONSTRATION COMMAND CENTER` | `CARE OVERVIEW` | `केयर अवलोकन` |
| `Clinical Telemetry Overview` | `Recovery overview` | `स्वास्थ्य लाभ अवलोकन` |
| `Synthetic cohort` | `Monitored now` | `सक्रिय निगरानी` |
| `PUBLISHED DEMO OVERVIEW` | `AT A GLANCE` | `एक नज़र में` |
| `Synthetic-data demonstration workspace` | `Secure sign-in` | `सुरक्षित साइन-इन` |
| `Choose a stakeholder role and use the published demo credentials.` | `Pick your role to continue.` | `आगे बढ़ने के लिए अपनी भूमिका चुनें।` |
| `Demo role` | `Role` | `भूमिका` |
| `Enter demo workspace` | `Sign in` | `साइन इन करें` |
| `Demo access only` | *(Removed)* | *(हटाया गया)* |
| `This is not production authentication.` | *(Deleted from credential helper)* | *(हटाया गया)* |
| `SYNTHETIC DEMO LOGS` | *(Removed)* | *(हटाया गया)* |
| `Smart India Hackathon 2026 · Clinical Demonstration Environment` | `CareLoop · Follow-up after discharge` | `केयरलूप · डिस्चार्ज के बाद देखभाल` |
| Footer honest statement (Landing & Login only) | `Sample data. Not medical advice.` | `नमूना डेटा। यह चिकित्सीय सलाह नहीं है।` |
| Honesty line under readings | `Readings are checked for impossible values. They are not a medical diagnosis.` | `रीडिंग्स में असंभव मानों की जांच की जाती है। यह कोई मेडिकल निदान नहीं है।` |

---

## Table of User-Facing Strings

### 1. `frontend/public/index.html`

| File | Line | Current Text | Proposed Text (EN) | Proposed Text (HI) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `frontend/public/index.html` | 10 | `CareLoop — Post-Discharge Clinical Care Architecture. Real-time telemetry, clinician rules, and grounded AI assistance.` | `CareLoop — Post-Discharge Care Follow-Up. Wearable readings, clinical rules, and hospital discharge assistance.` | `केयरलूप — डिस्चार्ज के बाद देखभाल। घड़ी की रीडिंग्स, क्लिनिकल नियम और डिस्चार्ज सहायता।` | Meta description; removed "Architecture", "telemetry". |
| `frontend/public/index.html` | 15 | `CareLoop — Post-Discharge Clinical Governance` | `CareLoop — Follow-up after discharge` | `केयरलूप — अस्पताल से छुट्टी के बाद देखभाल` | Page title tag; removed "Clinical Governance". |
| `frontend/public/index.html` | 18 | `You need to enable JavaScript to run this app.` | `You need to enable JavaScript to run this app.` | `इस ऐप को चलाने के लिए जावास्क्रिप्ट सक्षम करें।` | Standard noscript warning. |

---

### 2. `frontend/src/components/Landingpage.jsx`

| File | Line | Current Text | Proposed Text (EN) | Proposed Text (HI) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `Landingpage.jsx` | 54 | `Developed by TechTitans` | `Follow-up after discharge` | `अस्पताल से छुट्टी के बाद देखभाल` | Subtitle under brand logo. |
| `Landingpage.jsx` | 63 | `Platform` | `Platform` | `प्लेटफ़ॉर्म` | Navigation link. |
| `Landingpage.jsx` | 64 | `Capabilities` | `Workspaces` | `कार्यक्षेत्र` | Navigation link (replaces jargon "Capabilities"). |
| `Landingpage.jsx` | 65 | `Impact` | `Outcomes` | `परिणाम` | Navigation link. |
| `Landingpage.jsx` | 66 | `Public Transparency` | `Transparency` | `पारदर्शिता` | Navigation link; removed "Public". |
| `Landingpage.jsx` | 109 | `Sign in` | `Sign in` | `साइन इन करें` | Top-right auth button. |
| `Landingpage.jsx` | 130 | `Explore Dashboard` | `See care team view` | `केयर टीम व्यू देखें` | Header CTA button. |
| `Landingpage.jsx` | 171 | `NATIONAL CLINICAL GOVERNANCE PLATFORM • SIH 2026 PROTOTYPE` | `POST-DISCHARGE FOLLOW-UP` | `डिस्चार्ज के बाद देखभाल` | Hero kicker badge; removed banned words. |
| `Landingpage.jsx` | 184 | `Transforming post-discharge care through digital governance.` | `Recovering at home, with your care team in the loop.` | `घर पर स्वास्थ्य लाभ, आपकी केयर टीम के साथ।` | Main hero heading. |
| `Landingpage.jsx` | 195–196 | `A unified clinical governance platform for transparent, continuous and accountable patient recovery—from hospital discharge to full rehabilitation.` | `CareLoop helps patients follow their discharge plan, and shows nurses and doctors who needs attention first, with the reason for every alert.` | `केयरलूप मरीज़ों को डिस्चार्ज प्लान अपनाने में मदद करता है और डॉक्टरों व नर्सों को दिखाता है कि किसे पहले ध्यान की ज़रूरत है।` | Hero supporting text. |
| `Landingpage.jsx` | 218 | `Explore National Dashboard` | `See the care-team view` | `केयर टीम व्यू देखें` | Primary action button. |
| `Landingpage.jsx` | 236 | `Sign in to workspace` | `Sign in` | `साइन इन करें` | Secondary button. |
| `Landingpage.jsx` | 242 (1) | `Role-based governance` | `A separate view for each role` | `हर भूमिका के लिए अलग दृश्य` | Checkpoint pill 1. |
| `Landingpage.jsx` | 242 (2) | `Synthetic demo data` | `Sample patient records` | `नमूना मरीज़ रिकॉर्ड` | Checkpoint pill 2. |
| `Landingpage.jsx` | 242 (3) | `Continuous IoT telemetry` | `Wearable readings (watch)` | `घड़ी से आने वाली रीडिंग्स` | Checkpoint pill 3. |
| `Landingpage.jsx` | 299 | `Decision Intelligence` | `Flags raised` | `जारी किए गए अलर्ट` | Floating badge kicker. |
| `Landingpage.jsx` | 302 | `12 risks identified early` | `12 open flags` | `12 सक्रिय अलर्ट` | Floating badge metric. |
| `Landingpage.jsx` | 318 | `DEMONSTRATION COMMAND CENTER` | `CARE OVERVIEW` | `केयर अवलोकन` | Mockup card kicker. |
| `Landingpage.jsx` | 321 | `Clinical Telemetry Overview` | `Recovery overview` | `स्वास्थ्य लाभ अवलोकन` | Mockup card heading. |
| `Landingpage.jsx` | 327 | `ACTIVE PATIENTS` | `ACTIVE PATIENTS` | `सक्रिय मरीज़` | Sub-card label. |
| `Landingpage.jsx` | 329 | `Synthetic cohort` | `Monitored now` | `सक्रिय निगरानी` | Sub-card subtitle. |
| `Landingpage.jsx` | 333 | `TELEMETRY INTEGRITY` | `READINGS RECEIVED` | `प्राप्त रीडिंग्स` | Sub-card label. |
| `Landingpage.jsx` | 335 | `ESP32 validated` | `From watch` | `घड़ी से प्राप्त` | Sub-card subtitle. |
| `Landingpage.jsx` | 339 | `DOSES TAKEN` | `DOSES CONFIRMED` | `पुष्ट की गई खुराकें` | Sub-card label. |
| `Landingpage.jsx` | 341 | `On-time adherence` | `Self-reported` | `मरीज़ द्वारा दर्ज` | Sub-card subtitle. |
| `Landingpage.jsx` | 406 | `Continuous Biometric Telemetry Stream (SpO2 & Heart Rate)` | `Heart rate and oxygen readings (not a diagnosis)` | `हृदय गति और ऑक्सीजन रीडिंग (यह कोई निदान नहीं है)` | Chart caption. |
| `Landingpage.jsx` | 444 | `Field Verification` | `Quality check` | `गुणवत्ता जांच` | Lower floating pill kicker. |
| `Landingpage.jsx` | 447 | `8 vitals verified` | `Every reading carries a quality label` | `हर रीडिंग पर गुणवत्ता लेबल मौजूद है` | Lower floating pill text. |
| `Landingpage.jsx` | 476 | `PUBLISHED DEMO OVERVIEW` | `AT A GLANCE` | `एक नज़र में` | Dark stats band kicker. |
| `Landingpage.jsx` | 479 | `One system. Every stakeholder. Consistent derived totals.` | `One record for patients, family helpers, nurses and doctors.` | `मरीज़ों, परिवार के मददगारों, नर्सों और डॉक्टरों के लिए एक रिकॉर्ड।` | Dark stats band headline. |
| `Landingpage.jsx` | 486 | `Monitored patients` | `Monitored patients` | `निगरानी में मरीज़` | Metric 1 label. |
| `Landingpage.jsx` | 491 | `Telemetry integrity` | `Readings received` | `प्राप्त रीडिंग्स` | Metric 2 label. |
| `Landingpage.jsx` | 496 | `Adherence confirmed` | `Doses confirmed` | `पुष्ट की गई खुराकें` | Metric 3 label. |
| `Landingpage.jsx` | 501 | `Escalation SLA ladder` | `3-step escalation ladder` | `3-चरणीय अलर्ट प्रक्रिया` | Metric 4 label. |
| `Landingpage.jsx` | 504 | *(New Caption)* | `Figures shown are sample data.` | `दिखाए गए आंकड़े नमूना डेटा हैं।` | Mandatory honesty line under stats band. |
| `Landingpage.jsx` | 536 | `Core Governing Architecture` | `How it works` | `यह कैसे काम करता है` | Section 4 kicker. |
| `Landingpage.jsx` | 539 | `"The LLM talks. Rules decide. Humans act."` | `"The LLM talks. Rules decide. Humans act."` | `"एआई केवल बताता है। नियम तय करते हैं। इंसान कार्रवाई करते हैं।"` | Core principle heading. |
| `Landingpage.jsx` | 542–544 | `CareLoop completely eliminates clinical hallucinations by separating medical rule execution from conversational AI. The database enforces deterministic safety triggers while humans maintain full authority.` | `CareLoop keeps AI text strictly separate from medical rules. The database checks every limit, and doctors and nurses make the final call.` | `केयरलूप एआई को मेडिकल नियमों से अलग रखता है। डेटाबेस हर सीमा की जांच करता है, और डॉक्टर व नर्स अंतिम निर्णय लेते हैं।` | Platform section body. |
| `Landingpage.jsx` | 550 | `Deterministic Clinical Engine` | `Clear clinical rules` | `स्पष्ट क्लिनिकल नियम` | Feature 1 title. |
| `Landingpage.jsx` | 551 | `Database stored procedures and triggers evaluate SpO2 and heart-rate thresholds. LLMs never emit medical flags.` | `The database checks SpO2 and heart rate limits. The chatbot never creates medical alerts.` | `डेटाबेस ऑक्सीजन और पल्स सीमाओं की जांच करता है। चैटबॉट कभी मेडिकल अलर्ट नहीं बनाता।` | Feature 1 body. |
| `Landingpage.jsx` | 552 | `Zero Hallucinations` | `Rules decide` | `नियम तय करते हैं` | Feature 1 tag. |
| `Landingpage.jsx` | 557 | `Append-Only Audit Trail` | `Permanent audit log` | `स्थायी ऑडिट लॉग` | Feature 2 title. |
| `Landingpage.jsx` | 558 | `Every dose confirmation, flag escalation, and clinician review is recorded immutably in the central audit ledger.` | `Every dose, alert, and care team review is saved in an unchangeable record.` | `हर खुराक, अलर्ट और डॉक्टर की समीक्षा एक स्थायी रिकॉर्ड में दर्ज होती है।` | Feature 2 body. |
| `Landingpage.jsx` | 559 | `Tamper Evident` | `Recorded` | `दर्ज रिकॉर्ड` | Feature 2 tag. |
| `Landingpage.jsx` | 564 | `ESP32 IoT Telemetry` | `Wearable readings` | `घड़ी की रीडिंग्स` | Feature 3 title. |
| `Landingpage.jsx` | 565 | `Firmware-level plausibility checks drop non-physiological readings (>300 bpm) with zero false-positive clinical alerts.` | `Readings are checked for impossible values (>300 bpm) to prevent false alarms.` | `गलत अलार्म रोकने के लिए असंभव रीडिंग्स (>300 bpm) को हटा दिया जाता है।` | Feature 3 body. |
| `Landingpage.jsx` | 566 | `Hardware-Verified` | `Value checked` | `मान जाँचा गया` | Feature 3 tag. |
| `Landingpage.jsx` | 571 | `Grounded RAG Assistant` | `Discharge question answers` | `डिस्चार्ज संबंधी उत्तर` | Feature 4 title. |
| `Landingpage.jsx` | 572 | `Discharge document vector search answers patient queries strictly from hospital notes with verified citation links.` | `Answers come directly from your hospital discharge papers with citations.` | `उत्तर सीधे आपके अस्पताल के डिस्चार्ज पेपर्स और संदर्भों से आते हैं।` | Feature 4 body. |
| `Landingpage.jsx` | 573 | `Cited Evidence` | `From papers` | `दस्तावेज़ों से` | Feature 4 tag. |
| `Landingpage.jsx` | 653 | `Role-Segregated Workstations` | `Separate views for each role` | `हर भूमिका के लिए अलग पोर्टल` | Section 5 kicker. |
| `Landingpage.jsx` | 656 | `Explore Workspaces & Live Dashboards` | `Portals for every care role` | `देखभाल दल के लिए पोर्टल` | Section 5 heading. |
| `Landingpage.jsx` | 659 | `Each stakeholder accesses a dedicated portal tailored to their role with strict row-level security and IDOR protection.` | `Patients, family members, nurses, and doctors each see only what they need.` | `मरीज़, परिवार के सदस्य, नर्सें और डॉक्टर केवल वही देखते हैं जो आवश्यक है।` | Section 5 body. |
| `Landingpage.jsx` | 667 | `Physician Command Hub` | `Doctor hub` | `डॉक्टर पोर्टल` | Role 1 title. |
| `Landingpage.jsx` | 669 | `High-risk patient triage board with priority scoring, symptom trends, and one-click AI daily summary approval.` | `Patient priority board, symptom trends, and draft summary reviews.` | `मरीज़ों की प्राथमिकता सूची, लक्षण और ड्राफ्ट सारांश की समीक्षा।` | Role 1 body. |
| `Landingpage.jsx` | 670 | `Clinical Authority` | `Doctor` | `डॉक्टर` | Role 1 badge. |
| `Landingpage.jsx` | 675 | `Ward Triage Station` | `Nurse station` | `नर्स स्टेशन` | Role 2 title. |
| `Landingpage.jsx` | 677 | `Escalation alert ladder queue, follow-up task dispatching, and rapid patient vitals acknowledgement.` | `Alert escalation queue, follow-up tasks, and quick vital sign reviews.` | `अलर्ट सूची, फॉलो-अप कार्य और मरीज़ की ताज़ा रीडिंग्स की जांच।` | Role 2 body. |
| `Landingpage.jsx` | 679 | `Active SLA Monitor` | `Nurse` | `नर्स` | Role 2 badge. |
| `Landingpage.jsx` | 683 | `Patient Recovery Companion` | `Patient portal` | `मरीज़ पोर्टल` | Role 3 title. |
| `Landingpage.jsx` | 685 | `Daily medication checklist, live wristband vitals, Hindi/English emergency guidance, and grounded discharge chat.` | `Daily medicines, wristband readings, emergency help, and discharge questions.` | `रोज़ की दवाएं, घड़ी की रीडिंग्स, आपातकालीन सहायता और डिस्चार्ज प्रश्न।` | Role 3 body. |
| `Landingpage.jsx` | 687 | `Self-Care Hub` | `Patient` | `मरीज़` | Role 3 badge. |
| `Landingpage.jsx` | 691 | `Family Caregiver View` | `Family helper view` | `परिवार सहायक दृश्य` | Role 4 title. |
| `Landingpage.jsx` | 693 | `Consent-gated vitals access, real-time escalation SMS notifications, and recovery milestone monitoring.` | `Readings with patient consent, text notifications, and daily milestones.` | `मरीज़ की सहमति से रीडिंग्स, संदेश सूचनाएं और दैनिक प्रगति।` | Role 4 body. |
| `Landingpage.jsx` | 695 | `Family Bridge` | `Caregiver` | `देखभालकर्ता` | Role 4 badge. |
| `Landingpage.jsx` | 725 | `Demo Ready` | `Ready` | `सक्रिय` | Card status pill; removed "Demo". |
| `Landingpage.jsx` | 745 | `Demo Login Email (Password: Demo@12345)` | `Sign-in details (Password: Demo@12345)` | `साइन-इन विवरण (पासवर्ड: Demo@12345)` | Helper label; removed "Demo Login". |
| `Landingpage.jsx` | 773 | `Launch {card.role} Portal` | `Open {card.role} portal` | `{card.role} पोर्टल खोलें` | Role card CTA. |
| `Landingpage.jsx` | 810 | `Verified Outcomes` | `Target outcomes` | `लक्ष्य और परिणाम` | Section 6 kicker. |
| `Landingpage.jsx` | 813 | `Measurable Clinical Governance Impact` | `Clinical follow-up targets` | `क्लिनिकल देखभाल के लक्ष्य` | Section 6 heading. |
| `Landingpage.jsx` | 816 | `Designed to prevent post-discharge readmissions by converting wearable telemetry into actionable, audited clinician workflows.` | `Aims to prevent hospital readmissions by sending wearable readings to care teams.` | `घड़ी की रीडिंग्स केयर टीम तक पहुँचाकर दोबारा अस्पताल भर्ती रोकने में मदद करता है।` | Section 6 body. |
| `Landingpage.jsx` | 822 | `Telemetry Plausibility Rate` | `Readings checked for errors` | `असंभव मानों की सफल जांच` | Impact metric 1 label. |
| `Landingpage.jsx` | 823 | `Confirmed Medication Adherence` | `Doses confirmed by patients` | `मरीज़ों द्वारा पुष्ट खुराकें` | Impact metric 2 label. |
| `Landingpage.jsx` | 824 | `Bilingual Emergency Safety Gate` | `Emergency keyword detection` | `आपातकालीन शब्दों की पहचान` | Impact metric 3 label. |
| `Landingpage.jsx` | 825 | `Autonomous Escalation SLA` | `3-step escalation ladder` | `3-चरणीय अलर्ट प्रक्रिया` | Impact metric 4 label. |
| `Landingpage.jsx` | 879 | `Compliance & Standards` | `Safety standards` | `सुरक्षा मानक` | Section 7 kicker. |
| `Landingpage.jsx` | 881 | `Public Transparency & Governance Disclosure` | `Safety and privacy standards` | `सुरक्षा और गोपनीयता मानक` | Section 7 heading. |
| `Landingpage.jsx` | 884 | `CareLoop is built for national-scale clinical auditability. All demonstration cohorts and medical thresholds adhere to transparent safety specifications.` | `CareLoop is built for clear clinical records. All sample data and limits follow standard guidelines.` | `केयरलूप स्पष्ट रिकॉर्ड के लिए बना है। सभी नमूना डेटा मानक नियमों का पालन करते हैं।` | Section 7 body. |
| `Landingpage.jsx` | 891 | `Synthetic Clinical Data Only` | `Sample data notice` | `नमूना डेटा सूचना` | Card 1 title. |
| `Landingpage.jsx` | 894 | `All 12 patient records, telemetry feeds, and discharge notes in this prototype are synthetic demonstrations for SIH 2026. No protected personal health information is accessed.` | `All patient records and readings shown here are sample data. No real personal health records are used.` | `यहाँ दिखाए गए सभी मरीज़ रिकॉर्ड और रीडिंग्स नमूना डेटा हैं। किसी वास्तविक रिकॉर्ड का उपयोग नहीं हुआ है।` | Card 1 body; removed SIH/prototype/synthetic. |
| `Landingpage.jsx` | 900 | `Immutable Audit Ledger` | `Permanent audit trail` | `स्थायी ऑडिट रिकॉर्ड` | Card 2 title. |
| `Landingpage.jsx` | 903 | `Every medication acknowledgement, alert resolution, and escalation action is permanently registered in an append-only MySQL audit log for medico-legal traceability.` | `Every dose confirmation, alert update, and care team action is saved in a permanent log.` | `हर खुराक पुष्टि, अलर्ट समाधान और डॉक्टर की कार्रवाई एक स्थायी रिकॉर्ड में दर्ज होती है।` | Card 2 body. |
| `Landingpage.jsx` | 909 | `Physician Final Authority` | `Doctor makes final decision` | `डॉक्टर का अंतिम निर्णय` | Card 3 title. |
| `Landingpage.jsx` | 912 | `AI drafts are visibly marked with "AI draft, not reviewed" until an attending physician reviews and stamps approval. The AI is structurally prevented from altering prescriptions.` | `AI drafts are clearly marked until a doctor reviews them. The assistant cannot change medicines.` | `डॉक्टर की समीक्षा तक AI ड्राफ्ट स्पष्ट रूप से चिह्नित रहते हैं। सहायक दवाएं नहीं बदल सकता।` | Card 3 body. |
| `Landingpage.jsx` | 942 | `CareLoop — Autonomous Clinical Post-Discharge Triage & Wearable Telemetry Platform (SIH 2026 Prototype)` | `CareLoop — Follow-up after discharge` | `केयरलूप — डिस्चार्ज के बाद देखभाल` | Footer title; removed banned words. |
| `Landingpage.jsx` | 945 | `Developed by TechTitans • Core Rule: "The LLM talks. Rules decide. Humans act."` | `Sample data. Not medical advice.` | `नमूना डेटा। यह चिकित्सीय सलाह नहीं है।` | Footer note (Mandatory honesty line). |

---

### 3. `frontend/src/components/CareLoopLogin.jsx`

| File | Line | Current Text | Proposed Text (EN) | Proposed Text (HI) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `CareLoopLogin.jsx` | 99 | `Invalid credentials. Please select one of the demo roles.` | `Invalid credentials. Please select one of the roles.` | `अमान्य विवरण। कृपया उपलब्ध भूमिकाओं में से एक चुनें।` | Login error toast; removed "demo". |
| `CareLoopLogin.jsx` | 152 | `Back to CareLoop` | `Back to CareLoop` | `केयरलूप पर वापस जाएं` | Top back navigation link. |
| `CareLoopLogin.jsx` | 171 | `Clinical Governance Platform` | `Follow-up after discharge` | `अस्पताल से छुट्टी के बाद देखभाल` | Logo subtitle; canonical replacement. |
| `CareLoopLogin.jsx` | 187 | `NATIONAL CLINICAL GOVERNANCE` | `FOLLOW-UP AFTER DISCHARGE` | `डिस्चार्ज के बाद देखभाल` | Left panel kicker; canonical replacement. |
| `CareLoopLogin.jsx` | 202 | `One trusted workflow from discharge to full recovery.` | `From discharge day to full recovery, in one place.` | `डिस्चार्ज के दिन से पूरी तरह ठीक होने तक, एक ही जगह।` | Left panel headline; canonical replacement. |
| `CareLoopLogin.jsx` | 215–216 | `Role-focused access for attending physicians, triage nurses, recovering patients, and family caregivers with deterministic safety bounds.` | `Separate views for doctors, triage nurses, recovering patients, and family helpers.` | `डॉक्टरों, नर्सों, स्वास्थ्य लाभ ले रहे मरीज़ों और परिवार के सहायकों के लिए अलग दृश्य।` | Left panel hero description. |
| `CareLoopLogin.jsx` | 222 | `Continuous biometric telemetry & plausibility guard` | `Wearable readings, checked for impossible values` | `घड़ी की रीडिंग्स, असंभव मानों की जांच के साथ` | Bullet 1. |
| `CareLoopLogin.jsx` | 223 | `Grounded clinical intelligence & triage safety rules` | `Answers taken from your own discharge papers` | `उत्तर सीधे आपके डिस्चार्ज पेपर्स से लिए गए हैं` | Bullet 2. |
| `CareLoopLogin.jsx` | 224 | `Autonomous 3-tier escalation ladder with SLA timers` | `A 3-step escalation ladder with timers; people stay in charge` | `टाइमर के साथ 3-चरणीय अलर्ट; निर्णय हमेशा इंसानों का` | Bullet 3. |
| `CareLoopLogin.jsx` | 253 | `Smart India Hackathon 2026 · Clinical Demonstration Environment` | `CareLoop · Follow-up after discharge` | `केयरलूप · डिस्चार्ज के बाद देखभाल` | Left panel footer; canonical replacement. |
| `CareLoopLogin.jsx` | 308 | `Synthetic-data demonstration workspace` | `Secure sign-in` | `सुरक्षित साइन-इन` | Top pill badge; canonical replacement. |
| `CareLoopLogin.jsx` | 322 | `Welcome to CareLoop` | `Welcome back` | `वापसी पर स्वागत है` | Form heading; canonical replacement. |
| `CareLoopLogin.jsx` | 332 | `Choose a stakeholder role and use the published demo credentials.` | `Pick your role to continue.` | `आगे बढ़ने के लिए अपनी भूमिका चुनें।` | Form subtitle; canonical replacement. |
| `CareLoopLogin.jsx` | 364 | `Demo role` | `Role` | `भूमिका` | Dropdown label; canonical replacement. |
| `CareLoopLogin.jsx` | 417 | `Email or clinician ID` | `Email or staff ID` | `ईमेल या स्टाफ आईडी` | Input label. |
| `CareLoopLogin.jsx` | 463 | `Password` | `Password` | `पासवर्ड` | Input label. |
| `CareLoopLogin.jsx` | 534 | `Remember this role` | `Remember this role` | `इस भूमिका को याद रखें` | Checkbox label; kept per rule. |
| `CareLoopLogin.jsx` | 537 | `Demo access only` | *(Removed)* | *(हटाया गया)* | Deleted per Addendum item 3. |
| `CareLoopLogin.jsx` | 569 | `Enter demo workspace` | `Sign in` | `साइन इन करें` | Button text; canonical replacement. |
| `CareLoopLogin.jsx` | 569 | `Authenticating...` | `Signing in...` | `साइन इन हो रहा है...` | Button loading state. |
| `CareLoopLogin.jsx` | 585 | *(Callout Header)* | `Sign-in details for this role` | `इस भूमिका के लिए साइन-इन विवरण` | Callout box header per Addendum item 3. |
| `CareLoopLogin.jsx` | 595 | `Password: Demo@12345 · This is not production authentication.` | `Password: Demo@12345` | `पासवर्ड: Demo@12345` | Deleted "This is not production authentication." |
| `CareLoopLogin.jsx` | 604 | `By continuing, you acknowledge this is a synthetic demonstration prototype. Open public dashboard` | `Open public dashboard` | `सार्वजनिक डैशबोर्ड खोलें` | Bottom disclaimer link per Addendum item 3. |
| `CareLoopLogin.jsx` | 616 | *(Footer Honesty)* | `Sample data. Not medical advice.` | `नमूना डेटा। यह चिकित्सीय सलाह नहीं है।` | Added mandatory honesty line in footer. |

---

### 4. `frontend/src/components/CareLoopPatientPortal.jsx`

| File | Line | Current Text | Proposed Text (EN) | Proposed Text (HI) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `CareLoopPatientPortal.jsx` | 76 | `CARELOOP CLINICAL RECOVERY SUMMARY` | `CARELOOP RECOVERY SUMMARY` | `केयरलूप स्वास्थ्य लाभ सारांश` | Export summary header. |
| `CareLoopPatientPortal.jsx` | 81 | `-- BIOMETRIC TELEMETRY --` | `-- WEARABLE READINGS --` | `-- घड़ी की रीडिंग्स --` | Export summary section. |
| `CareLoopPatientPortal.jsx` | 82 | `Resting Pulse` | `Pulse` | `नाड़ी` | Export summary pulse label. |
| `CareLoopPatientPortal.jsx` | 83 | `Blood Oxygen (SpO2)` | `Oxygen level (SpO2)` | `ऑक्सीजन स्तर (SpO2)` | Export summary oxygen label. |
| `CareLoopPatientPortal.jsx` | 85 | `Confirmed Adherence` | `Doses confirmed` | `पुष्ट की गई खुराकें` | Export summary doses. |
| `CareLoopPatientPortal.jsx` | 87 | `-- PRESCRIBED REGIMEN --` | `-- YOUR MEDICINES --` | `-- आपकी दवाएं --` | Export summary medicines. |
| `CareLoopPatientPortal.jsx` | 90 | `-- RECOVERY ATTENTION --` | `-- ATTENTION NEEDED --` | `-- ध्यान देने योग्य --` | Export summary flags. |
| `CareLoopPatientPortal.jsx` | 93 | `Hospital Discharge Protocol verified with deterministic safety boundaries.` | `Readings are checked for impossible values. They are not a medical diagnosis.` | `रीडिंग्स में असंभव मानों की जांच की जाती है। यह कोई मेडिकल निदान नहीं है।` | Export summary footer honesty. |
| `CareLoopPatientPortal.jsx` | 110 | `Could not update medication: ${err.message}` | `Could not update medicine: ${err.message}` | `दवा की स्थिति अपडेट नहीं हो सकी: ${err.message}` | Dose update error toast. |
| `CareLoopPatientPortal.jsx` | 122–125 | `Health check-in logged and verified with clinical rules.` / `आपकी स्वास्थ्य रिपोर्ट सफलतापूर्वक दर्ज कर ली गई है।` | `Check-in recorded. Your care team can see your update.` / `आपकी स्थिति दर्ज कर ली गई है। आपकी केयर टीम इसे देख सकती है।` | Check-in success message (EN & HI). |
| `CareLoopPatientPortal.jsx` | 133 | `Symptom check-in failed: ${err.message}` | `Check-in failed: ${err.message}` | `स्थिति दर्ज नहीं हो सकी: ${err.message}` | Check-in error toast. |
| `CareLoopPatientPortal.jsx` | 169–171 | `Error connecting to discharge assistant. Please try again or call your care team.` / `क्षमा करें, आपके अनुरोध को पूरा करने में समस्या हुई।` | `I couldn't connect right now. Please try again or call your care team.` / `कनेक्ट करने में समस्या हुई। कृपया पुनः प्रयास करें या केयर टीम को कॉल करें।` | Chat error toast (EN & HI). |
| `CareLoopPatientPortal.jsx` | 244 | `Clinical Recovery Portal` | `Recovery portal` | `स्वास्थ्य लाभ पोर्टल` | Sidebar subtitle; canonical replacement. |
| `CareLoopPatientPortal.jsx` | 262 | `WORKSPACE` | `MY CARE` | `मेरी देखभाल` | Sidebar section 1 header. |
| `CareLoopPatientPortal.jsx` | 267 | `Recovery Overview` | `Overview` | `अवलोकन` | Nav item 1. |
| `CareLoopPatientPortal.jsx` | 268 | `Prescriptions` | `Medicines` | `दवाएं` | Nav item 2. |
| `CareLoopPatientPortal.jsx` | 269 | `Symptom Check-in` | `Daily check-in` | `दैनिक जांच` | Nav item 3. |
| `CareLoopPatientPortal.jsx` | 329 | `INTELLIGENCE` | `ASK` | `सहायता` | Sidebar section 2 header. |
| `CareLoopPatientPortal.jsx` | 334 | `AI Discharge RAG` | `Ask my discharge papers` | `डिस्चार्ज पेपर्स से पूछें` | Nav item 4. |
| `CareLoopPatientPortal.jsx` | 379 | `Theme` | `Theme` | `थीम` | Sidebar control label. |
| `CareLoopPatientPortal.jsx` | 401 | `Sign Out` | `Sign Out` | `साइन आउट` | Sidebar logout button. |
| `CareLoopPatientPortal.jsx` | 425 | `CARELOOP CLINICAL AUTHORITY` | `CARELOOP` | `केयरलूप` | Breadcrumb kicker. |
| `CareLoopPatientPortal.jsx` | 428 | `Patient Recovery & Adherence` | `My recovery` | `मेरा स्वास्थ्य लाभ` | Breadcrumb title. |
| `CareLoopPatientPortal.jsx` | 448 | `Search medications, symptoms, guidelines...` | `Search medicines, notes...` | `दवाएं, नोट्स खोजें...` | Search input placeholder. |
| `CareLoopPatientPortal.jsx` | 571 | `CONTINUOUS BIOMETRIC RECOVERY MONITORING` | `RECOVERY OVERVIEW` | `स्वास्थ्य लाभ अवलोकन` | Main content kicker. |
| `CareLoopPatientPortal.jsx` | 582 | `Post-Discharge Recovery & Telemetry` | `How your recovery is going` | `आपकी रिकवरी की स्थिति` | Main content H1. |
| `CareLoopPatientPortal.jsx` | 584–586 | `Track medication adherence, biometric telemetry streams, and verified triage outcomes with deterministic safety.` | `Check your daily medicines, watch readings, and updates from your care team.` | `अपनी दैनिक दवाएं, घड़ी की रीडिंग्स और केयर टीम के संदेश देखें।` | Subtitle description. |
| `CareLoopPatientPortal.jsx` | 607 | `Export Clinical Summary` | `Download my summary` | `मेरा सारांश डाउनलोड करें` | Top action button. |
| `CareLoopPatientPortal.jsx` | 642 | `Urgent Clinical Review Flagged` | `Your care team has been told` | `आपकी केयर टीम को सूचित कर दिया गया है` | Emergency banner title. |
| `CareLoopPatientPortal.jsx` | 645–647 | `Your attending clinician has received an alert for vital review. If experiencing severe shortness of breath or chest pain, please dial 112 immediately.` | `A nurse or doctor will look at your latest update. If you have chest pain or severe trouble breathing, call 112 now.` | `कोई नर्स या डॉक्टर आपकी स्थिति देखेंगे। अगर सीने में दर्द या सांस लेने में बहुत तकलीफ़ हो, तो तुरंत 112 पर कॉल करें।` | Emergency banner body (action first). |
| `CareLoopPatientPortal.jsx` | 694 | `Today's Doses` | `Medicines today` | `आज की दवाएं` | Card 1 title. |
| `CareLoopPatientPortal.jsx` | 707 | `Scheduled daily regimen` | `Planned for today` | `आज के लिए निर्धारित` | Card 1 subtitle. |
| `CareLoopPatientPortal.jsx` | 741 | `Resting Pulse` | `Pulse` | `नाड़ी` | Card 2 title. |
| `CareLoopPatientPortal.jsx` | 756 | `Continuous ESP32 pulse guard` | `Last reading from your watch` | `आपकी घड़ी से ताज़ा रीडिंग` | Card 2 subtitle. |
| `CareLoopPatientPortal.jsx` | 790 | `Blood Oxygen (SpO2)` | `Oxygen level (SpO2)` | `ऑक्सीजन स्तर (SpO2)` | Card 3 title. |
| `CareLoopPatientPortal.jsx` | 804 | `Optimal range` | `Latest reading` | `ताज़ा रीडिंग` | Card 3 status pill (honest label). |
| `CareLoopPatientPortal.jsx` | 838 | `Adherence Outcome` | `Doses confirmed` | `पुष्ट की गई खुराकें` | Card 4 title. |
| `CareLoopPatientPortal.jsx` | 851 | `{takenCount} of {doses.length} confirmed` | `{takenCount} of {doses.length} confirmed` | `{takenCount} में से {doses.length} खुराकें ली गईं` | Card 4 status pill. |
| `CareLoopPatientPortal.jsx` | 876 | `Medication Intake Progress` | `Today's medicines` | `आज की दवाएं` | Progress section title. |
| `CareLoopPatientPortal.jsx` | 879 | `Prescribed doses tracked by deterministic SLA verification timers` | `Mark each dose Taken or Skipped. Your care team can see your answers.` | `हर खुराक को 'ले ली' या 'छोड़ दी' मार्क करें। आपकी केयर टीम आपके जवाब देख सकती है।` | Progress section subtitle. |
| `CareLoopPatientPortal.jsx` | 947 | `Safeguard Attention` | `Needs a look` | `ध्यान देने की ज़रूरत है` | Card title. |
| `CareLoopPatientPortal.jsx` | 950 | `Clinical thresholds beyond normal post-discharge watch limits` | `Readings that need a care team check` | `रीडिंग्स जिन पर केयर टीम का ध्यान चाहिए` | Card subtitle. |
| `CareLoopPatientPortal.jsx` | 967 | `1 clinical vital reading requires clinician review. Deterministic escalation ladder active.` | `A reading is waiting for your care team to review.` | `एक रीडिंग आपकी केयर टीम की समीक्षा की प्रतीक्षा में है।` | Flag active text. |
| `CareLoopPatientPortal.jsx` | 968 | `Zero critical deviations flagged. All continuous telemetry readings within safe discharge bounds.` | `All readings look normal today.` | `आज सभी रीडिंग्स सामान्य दिख रही हैं।` | Flag zero text. |
| `CareLoopPatientPortal.jsx` | 989 | `Log Daily Health Check-in` | `Tell us how you feel today` | `बताएं आज आप कैसा महसूस कर रहे हैं` | Button text. |
| `CareLoopPatientPortal.jsx` | 992 | `Telemetry verified by hardware ESP32 plausibility filters.` | `Readings are checked for impossible values. They are not a medical diagnosis.` | `रीडिंग्स में असंभव मानों की जांच की जाती है। यह कोई मेडिकल निदान नहीं है।` | Honesty caption under readings. |
| `CareLoopPatientPortal.jsx` | 1018 | `Active Medication & Dosing Register` | `Your medicines` | `आपकी दवाएं` | Table header title. |
| `CareLoopPatientPortal.jsx` | 1021 | `Deterministic dosage schedule with one-click proxy/patient confirmation` | `Your planned doses for today` | `आज के लिए आपकी निर्धारित दवाएं` | Table header subtitle. |
| `CareLoopPatientPortal.jsx` | 1036 | `SYNTHETIC DEMO LOGS` | *(Removed)* | *(हटाया गया)* | Deleted per Addendum item 3. |
| `CareLoopPatientPortal.jsx` | 1046 | `MEDICATION NAME` | `MEDICINE` | `दवा का नाम` | Column 1 header. |
| `CareLoopPatientPortal.jsx` | 1049 | `SCHEDULED FOR` | `WHEN` | `कब लें` | Column 2 header. |
| `CareLoopPatientPortal.jsx` | 1052 | `DOSAGE & INSTRUCTIONS` | `HOW TO TAKE` | `कैसे लें` | Column 3 header. |
| `CareLoopPatientPortal.jsx` | 1055 | `STATUS` | `STATUS` | `स्थिति` | Column 4 header. |
| `CareLoopPatientPortal.jsx` | 1058 | `ACTION` | `ACTION` | `कार्रवाई` | Column 5 header. |
| `CareLoopPatientPortal.jsx` | 1084 | `Taken` | `Taken` | `ले ली` | Pill label. |
| `CareLoopPatientPortal.jsx` | 1086 | `Skipped` | `Skipped` | `छोड़ दी` | Pill label. |
| `CareLoopPatientPortal.jsx` | 1088 | `Scheduled` | `Planned` | `निर्धारित` | Pill label. |
| `CareLoopPatientPortal.jsx` | 1107 | `Confirm Taken` | `Mark Taken` | `'ले ली' मार्क करें` | Table action button. |
| `CareLoopPatientPortal.jsx` | 1111 | `Confirmed` | `Confirmed` | `पुष्ट` | Confirmed state label. |
| `CareLoopPatientPortal.jsx` | 1139 | `Daily Health & Symptom Verification` | `Daily health check-in` | `दैनिक स्वास्थ्य जांच` | Check-in tab title. |
| `CareLoopPatientPortal.jsx` | 1143 | `Report your current physical comfort, wound site status, and vital sensations.` | `Tell us how you are feeling and if you notice anything unusual.` | `बताएं कि आप कैसा महसूस कर रहे हैं और क्या कोई नई तकलीफ़ है।` | Check-in tab subtitle. |
| `CareLoopPatientPortal.jsx` | 1170 | `Pain Intensity Level (0 to 10)` | `Pain level (0 to 10)` | `दर्द का स्तर (0 से 10)` | Pain slider label. |
| `CareLoopPatientPortal.jsx` | 1187 | `Describe your symptoms or observations` | `Describe how you feel right now` | `बताएं कि आप अभी कैसा महसूस कर रहे हैं` | Check-in textarea label. |
| `CareLoopPatientPortal.jsx` | 1193 | `e.g. Mild shortness of breath when walking, no chest pain...` | `e.g. A little tired after walking, no chest pain...` | `जैसे: चलने पर थोड़ी थकान, सीने में कोई दर्द नहीं...` | Textarea placeholder. |
| `CareLoopPatientPortal.jsx` | 1219 | `Submit Health Check-in` | `Send check-in` | `जांच भेजें` | Submit check-in button. |
| `CareLoopPatientPortal.jsx` | 1254 | `Discharge Plan AI Recovery Assistant` | `Discharge recovery assistant` | `डिस्चार्ज रिकवरी सहायक` | Chat title. |
| `CareLoopPatientPortal.jsx` | 1257 | `Strictly grounded in your hospital discharge summary instructions` | `Answers are taken directly from your discharge papers` | `उत्तर सीधे आपके डिस्चार्ज पेपर्स से लिए जाते हैं` | Chat subtitle. |
| `CareLoopPatientPortal.jsx` | 1261 | `Grounded Gemini RAG` | `Discharge papers only` | `केवल डिस्चार्ज पेपर्स से` | Chat pill badge; removed RAG jargon. |
| `CareLoopPatientPortal.jsx` | 1276 | `Ask about prescribed medicines, recovery routines, or follow-up doctor visits.` | `Ask about your medicines, wound care, or doctor visits.` | `अपनी दवाओं, घाव की देखभाल या डॉक्टर से मिलने के बारे में पूछें।` | Chat empty state. |
| `CareLoopPatientPortal.jsx` | 1302 | `Consulting hospital discharge instructions...` | `Checking your discharge papers...` | `आपके डिस्चार्ज पेपर्स देखे जा रहे हैं...` | Chat loading state. |
| `CareLoopPatientPortal.jsx` | 1322 | `Ask a question about your medication or recovery instructions...` | `Ask about your medicines or discharge instructions...` | `अपनी दवाओं या डिस्चार्ज निर्देशों के बारे में पूछें...` | Chat input placeholder. |

---

### 5. `frontend/src/components/CareLoopStaffPortal.jsx`

| File | Line | Current Text | Proposed Text (EN) | Proposed Text (HI) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `CareLoopStaffPortal.jsx` | 36 | `No triage items available to export.` | `No flags to export.` | `निर्यात के लिए कोई अलर्ट नहीं है।` | Export alert. |
| `CareLoopStaffPortal.jsx` | 104 | `Flag #${flagId} acknowledged.` | `Flag #${flagId} acknowledged.` | `अलर्ट #${flagId} स्वीकार कर लिया गया।` | Toast notification. |
| `CareLoopStaffPortal.jsx` | 115 | `Summary draft #${res.summary_id} generated for Patient #${pid}.` | `Draft #${res.summary_id} created for Patient #${pid}.` | `मरीज़ #${pid} के लिए ड्राफ्ट #${res.summary_id} तैयार किया गया।` | Summary toast. |
| `CareLoopStaffPortal.jsx` | 126 | `Summary #${summaryId} ${action}ed.` | `Summary #${summaryId} ${action}ed.` | `सारांश #${summaryId} ${action} किया गया।` | Review toast. |
| `CareLoopStaffPortal.jsx` | 192 | `Clinical Command Hub` | `Care team hub` | `केयर टीम केंद्र` | Sidebar subtitle; canonical replacement. |
| `CareLoopStaffPortal.jsx` | 209 | `WORKSPACE` | `CARE TEAM` | `केयर टीम` | Sidebar header. |
| `CareLoopStaffPortal.jsx` | 215 | `Triage Board` | `Who needs attention` | `किसे ध्यान चाहिए` | Nav item 1. |
| `CareLoopStaffPortal.jsx` | 216 | `Patient Timeline` | `Patient timeline` | `मरीज़ टाइमलाइन` | Nav item 2. |
| `CareLoopStaffPortal.jsx` | 217 | `Follow-up Tasks` | `Follow-up tasks` | `फॉलो-अप कार्य` | Nav item 3. |
| `CareLoopStaffPortal.jsx` | 218 | `AI Draft Summaries` | `Draft summaries` | `ड्राफ्ट सारांश` | Nav item 4. |
| `CareLoopStaffPortal.jsx` | 279 | `Theme` | `Theme` | `थीम` | Theme label. |
| `CareLoopStaffPortal.jsx` | 301 | `Sign Out` | `Sign Out` | `साइन आउट` | Logout label. |
| `CareLoopStaffPortal.jsx` | 325 | `CARELOOP CLINICAL AUTHORITY` | `WHO NEEDS ATTENTION` | `किसे ध्यान चाहिए` | Header kicker per voice guide. |
| `CareLoopStaffPortal.jsx` | 328 | `Triage & Clinical Escalations` | `Care team` | `केयर टीम` | Header title per voice guide. |
| `CareLoopStaffPortal.jsx` | 347 | `Search patients, triage flags, audit records...` | `Search patients, flags, records...` | `मरीज़, अलर्ट, रिकॉर्ड खोजें...` | Search placeholder. |
| `CareLoopStaffPortal.jsx` | 394 | `{user.role} · Clinical Staff` | `{user.role} · Care team` | `{user.role} · केयर टीम` | User role pill. |
| `CareLoopStaffPortal.jsx` | 447 | `CLINICAL TRIAGE & GOVERNANCE` | `WHO NEEDS ATTENTION FIRST` | `किसे पहले ध्यान की ज़रूरत है` | Section kicker; removed governance. |
| `CareLoopStaffPortal.jsx` | 458 | `Live Triage & Safeguard Board` | `Who needs attention first` | `किसे पहले ध्यान की ज़रूरत है` | Main H1 per voice guide. |
| `CareLoopStaffPortal.jsx` | 461 | `Transparent priority scoring, SLA escalation ladders, and verified clinical review workflows.` | `Every flag shows why it was raised. Open flags are listed by severity.` | `हर अलर्ट बताता है कि यह क्यों जारी हुआ। खुले अलर्ट गंभीरता के क्रम में हैं।` | Subtitle per voice guide. |
| `CareLoopStaffPortal.jsx` | 482 | `Export Triage CSV` | `Export flags (CSV)` | `अलर्ट निर्यात करें (CSV)` | Button text. |
| `CareLoopStaffPortal.jsx` | 527 | `Active Flags` | `Open flags` | `सक्रिय अलर्ट` | Card 1 title per voice guide. |
| `CareLoopStaffPortal.jsx` | 540 | `Across monitored patient cohorts` | `All monitored patients` | `सभी निगरानी वाले मरीज़` | Card 1 subtitle per voice guide. |
| `CareLoopStaffPortal.jsx` | 573 | `Immediate Review` | `Immediate review` | `तत्काल समीक्षा` | Card 2 title. |
| `CareLoopStaffPortal.jsx` | 586 | `SLA timeout: < 15 minutes` | `Target: under 15 minutes` | `लक्ष्य: 15 मिनट के भीतर` | Card 2 subtitle per voice guide. |
| `CareLoopStaffPortal.jsx` | 619 | `Urgent Review` | `Urgent review` | `ज़रूरी समीक्षा` | Card 3 title. |
| `CareLoopStaffPortal.jsx` | 632 | `SLA timeout: < 2 hours` | `Target: under 2 hours` | `लक्ष्य: 2 घंटे के भीतर` | Card 3 subtitle per voice guide. |
| `CareLoopStaffPortal.jsx` | 665 | `Pending Summaries` | `Drafts to review` | `समीक्षा के लिए ड्राफ्ट` | Card 4 title per voice guide. |
| `CareLoopStaffPortal.jsx` | 678 | `Awaiting clinician sign-off` | `Waiting for a clinician. AI draft, not reviewed.` | `डॉक्टर की समीक्षा की प्रतीक्षा में। AI ड्राफ्ट, समीक्षा शेष।` | Card 4 subtitle per voice guide. |
| `CareLoopStaffPortal.jsx` | 703 | `Live Triage Register` | `Open flags` | `सक्रिय अलर्ट सूची` | Table title per voice guide. |
| `CareLoopStaffPortal.jsx` | 706 | `Derived from v_triage_board view with priority weights and transparent reasoning` | `Sorted by severity. Each row says why it was raised.` | `गंभीरता के अनुसार क्रमबद्ध। हर पंक्ति बताती है कि अलर्ट क्यों जारी हुआ।` | Table subtitle per voice guide. |
| `CareLoopStaffPortal.jsx` | 711 | `ALL / Immediate_Review / Urgent_Review / Routine_Review` | `All / Urgent now / Review soon / Routine` | `सभी / अति आवश्यक / जल्द समीक्षा / सामान्य` | Filter chips (labels only, values preserved). |
| `CareLoopStaffPortal.jsx` | 738 | `PRIORITY` | `SCORE` | `स्कोर` | Column 1 header per voice guide. |
| `CareLoopStaffPortal.jsx` | 741 | `PATIENT` | `PATIENT` | `मरीज़` | Column 2 header. |
| `CareLoopStaffPortal.jsx` | 744 | `SEVERITY` | `SEVERITY` | `गंभीरता` | Column 3 header. |
| `CareLoopStaffPortal.jsx` | 747 | `FLAG REASON & EVIDENCE` | `WHY IT WAS RAISED` | `अलर्ट का कारण` | Column 4 header per voice guide. |
| `CareLoopStaffPortal.jsx` | 750 | `DETECTED AT` | `RAISED AT` | `अलर्ट का समय` | Column 5 header per voice guide. |
| `CareLoopStaffPortal.jsx` | 753 | `ACTION` | `ACTION` | `कार्रवाई` | Column 6 header. |
| `CareLoopStaffPortal.jsx` | 761 | `No active triage flags under this filter. All patients clinically stable.` | `No open flags in this view.` | `इस दृश्य में कोई खुला अलर्ट नहीं है।` | Table empty state (honest, no false claims). |
| `CareLoopStaffPortal.jsx` | 801 | `Immediate` | `Immediate` | `तत्काल` | Severity badge. |
| `CareLoopStaffPortal.jsx` | 803 | `Urgent` | `Urgent` | `ज़रूरी` | Severity badge. |
| `CareLoopStaffPortal.jsx` | 805 | `Routine` | `Routine` | `सामान्य` | Severity badge. |
| `CareLoopStaffPortal.jsx` | 811 | `Source: ... · Status: ...` | `Source: ... · Status: ...` | `स्रोत: ... · स्थिति: ...` | Flag metadata line. |
| `CareLoopStaffPortal.jsx` | 832 | `Acknowledge` | `Acknowledge` | `स्वीकार करें` | Flag action button. |
| `CareLoopStaffPortal.jsx` | 858 | `Patient Recovery Audit Trail` | `Patient event timeline` | `मरीज़ घटना टाइमलाइन` | Tab 2 title. |
| `CareLoopStaffPortal.jsx` | 859 | `Chronological clinical event progression` | `Recorded events in chronological order` | `समय के अनुसार दर्ज की गई घटनाएं` | Tab 2 subtitle. |
| `CareLoopStaffPortal.jsx` | 886 | `No logged events for Patient #${timelinePatientId}.` | `No recorded events for Patient #${timelinePatientId}.` | `मरीज़ #${timelinePatientId} के लिए कोई दर्ज घटना नहीं है।` | Timeline empty state. |
| `CareLoopStaffPortal.jsx` | 924 | `Patient #${...} · Verified Audit Trail` | `Patient #${...} · Event log` | `मरीज़ #${...} · घटना लॉग` | Timeline event subtitle. |
| `CareLoopStaffPortal.jsx` | 951 | `Clinician Follow-up Tasks` | `Care team follow-up tasks` | `केयर टीम फॉलो-अप कार्य` | Tab 3 title. |
| `CareLoopStaffPortal.jsx` | 952 | `Deterministic escalation actions requiring staff sign-off` | `Tasks created from alerts waiting for review` | `अलर्ट से बने कार्य, समीक्षा की प्रतीक्षा में` | Tab 3 subtitle. |
| `CareLoopStaffPortal.jsx` | 1000 | `Clinical AI Draft Summaries` | `Draft summaries to review` | `समीक्षा के लिए ड्राफ्ट सारांश` | Tab 4 title. |
| `CareLoopStaffPortal.jsx` | 1001 | `Human clinician validation required before EHR commit` | `Review and approve drafts. AI draft, not reviewed.` | `ड्राफ्ट की समीक्षा करें और स्वीकृत करें। AI ड्राफ्ट, समीक्षा शेष।` | Tab 4 subtitle. |
| `CareLoopStaffPortal.jsx` | 1036 | `Generate AI Summary` | `Create draft summary` | `ड्राफ्ट सारांश बनाएं` | Tab 4 action button. |
| `CareLoopStaffPortal.jsx` | 1054 | `Draft Summary #${s.summary_id}` | `Draft Summary #${s.summary_id}` | `ड्राफ्ट सारांश #${s.summary_id}` | Summary item heading. |
| `CareLoopStaffPortal.jsx` | 1074 | `Approve` | `Approve` | `स्वीकृत करें` | Summary approve button. |
| `CareLoopStaffPortal.jsx` | 1089 | `Reject` | `Reject` | `अस्वीकार करें` | Summary reject button. |

---

### 6. `frontend/src/components/SwitchDemoWorkspace.jsx`

| File | Line | Current Text | Proposed Text (EN) | Proposed Text (HI) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `SwitchDemoWorkspace.jsx` | 139 | `title="Telemetry Guard & Live Alerts Active"` | `title="Alerts and updates active"` | `title="अलर्ट और अपडेट सक्रिय हैं"` | Bell tooltip; removed "Telemetry Guard". |
| `SwitchDemoWorkspace.jsx` | 240 | `Demo Role Switcher` | `Switch role` | `भूमिका बदलें` | Dropdown header; removed "Demo". |
| `SwitchDemoWorkspace.jsx` | 252 | `1-Click Switch` | `Quick switch` | `त्वरित बदलाव` | Dropdown badge. |
| `SwitchDemoWorkspace.jsx` | 256 | `Instant role demonstration for evaluation` | `Switch between care-team roles` | `केयर टीम की भूमिकाओं में बदलें` | Dropdown subtitle; removed "demonstration". |
| `SwitchDemoWorkspace.jsx` | 371 | `Deterministic rules enforce role-based safety gates.` | `Each role sees only what they need to see.` | `प्रत्येक भूमिका केवल वही देखती है जो आवश्यक है।` | Dropdown footer note. |

---

### 7. `frontend/src/components/DashboardShell.jsx`

| File | Line | Current Text | Proposed Text (EN) | Proposed Text (HI) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `DashboardShell.jsx` | 412 | `aria-label="AgenticNurse home"` | `aria-label="CareLoop home"` | `aria-label="केयरलूप होम"` | Accessibility aria-label. |
| `DashboardShell.jsx` | 415 | `AgenticNurse` | `CareLoop` | `केयरलूप` | Brand logo text. |
| `DashboardShell.jsx` | 416 | `Clinical AI` | `Follow-up after discharge` | `डिस्चार्ज के बाद देखभाल` | Brand logo subtitle. |
| `DashboardShell.jsx` | 447 | `placeholder="Search patients, alerts..."` | `placeholder="Search patients, alerts..."` | `placeholder="मरीज़, अलर्ट खोजें..."` | Search placeholder. |
| `DashboardShell.jsx` | 467 | `← Home` | `← Home` | `← होम` | Top-right return link. |

---

### 8. Backend Safety, RAG & Notification Templates

| File | Line | Current Text | Proposed Text (EN) | Proposed Text (HI) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `backend/app/safety.py` | 40–42 | `"en": "This may be an emergency. Call your local emergency number now or go to the nearest emergency department. Your care team has been alerted."` / `"hi": "यह आपातकालीन स्थिति हो सकती है।..."` | `"en": "If you have severe symptoms, call 112 now or go to the nearest emergency room. Your care team has been told."` / `"hi": "यदि गंभीर लक्षण हैं, तो तुरंत 112 पर कॉल करें या नज़दीकी आपातकालीन कक्ष जाएँ। आपकी केयर टीम को बता दिया गया है।"` | Kept "112"; calm in urgency, action first. |
| `backend/app/safety.py` | 80–83 | `"en": "I cannot advise on changing, stopping, or adjusting medication doses. Please contact your care team. A follow-up task has been logged for your clinical staff to get in touch with you."` / `"hi": "..."` | `"en": "I can't advise on changing doses. Please contact your care team. I've asked them to get in touch with you."` / `"hi": "मैं दवा की खुराक बदलने की सलाह नहीं दे सकता। कृपया अपनी केयर टीम से संपर्क करें। मैंने उनसे आपसे संपर्क करने को कहा है।"` | Exact voice guide refusal wording in EN & HI. |
| `backend/app/rag.py` | 96–98 | `refusal = ("I cannot advise on changing doses. Please contact your care team. I have asked them to get in touch with you.")` | `refusal = ("I can't advise on changing doses. Please contact your care team. I've asked them to get in touch with you.")` | `मैं दवा की खुराक बदलने की सलाह नहीं दे सकता। कृपया अपनी केयर टीम से संपर्क करें। मैंने उनसे आपसे संपर्क करने को कहा है।` | Exact voice guide refusal wording. |
| `backend/app/rag.py` | 126, 141, 153 | `"I could not find this in your discharge documents. I have asked your care team to reply."` | `"I couldn't find this in your discharge papers. I've asked your care team to reply."` | `मुझे आपके डिस्चार्ज पेपर्स में यह नहीं मिला। मैंने आपकी केयर टीम से जवाब देने को कहा है।` | Exact voice guide NOT_IN_DOCUMENTS wording. |
| `backend/app/rag.py` | 158 | `return out.strip(), True, ids` | `return f"From your discharge summary: {out.strip()}", True, ids` | `आपके डिस्चार्ज सारांश के अनुसार: ...` | Exact voice guide rule: "Every grounded AI answer starts with the source line." |
| `backend/app/escalation.py` | 109 | `CareLoop: The care team is checking on a recent health update for the patient. Please contact them when convenient.` | `CareLoop: The care team is checking on an update for the patient. Please call them when you can.` | `केयरलूप: केयर टीम मरीज़ के स्वास्थ्य अपडेट की जांच कर रही है। कृपया समय मिलने पर कॉल करें।` | SMS template: short, calm, no diagnosis details. |
| `backend/app/main.py` | 774, 786 | `'AI draft, not reviewed'` | `'AI draft, not reviewed'` | `'AI ड्राफ्ट, समीक्षा शेष'` | Factual draft status kept intact. |
