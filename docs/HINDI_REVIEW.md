# CareLoop Patient Portal — Hindi Copy Review

This document provides a comprehensive review of all user-facing strings translated into Hindi across the CareLoop Patient Portal (`/patient`). It satisfies **Brief Section 10.2** and is structured for review by a native Hindi speaker prior to deployment.

---

## 1. Core Vocabulary & Section 10.2 Key Strings

| Translation Key | English Copy | Hindi Copy | Context / Placement | Reviewer Notes |
|---|---|---|---|---|
| `next_medicine` | Next medicine | अगली दवा | Overview Banner & Header | Plain, everyday Hindi |
| `taken` | Taken | ले ली | Dose Pill, Action Button, Summary | Short, active verb |
| `skip` | Skip | छोड़ें | Dose Action Button, Modal Title | Natural imperative form |
| `undo` | Undo | वापस करें | Floating Toast Action | Clear reversible action |
| `due_now` | Due now | अभी लेनी है | Dose Status Badge (within 60m) | High urgency indicator |
| `in_hours` | In {n} hr | {n} घंटे में | Dose Relative Timing Pill | Relative schedule |
| `not_confirmed` | Not confirmed | पुष्टि नहीं हुई | Dose Status Badge (past scheduled) | Distinct from "Skipped" |
| `upcoming` | Upcoming | आने वाली | Scheduled dose later today | Neutral forward-looking |
| `took_late` | I took it | मैंने ले ली | Dose Action for past unconfirmed | 1-tap confirmation |
| `morning` | Morning | सुबह | Regimen Slot Header | Standard daily phase |
| `afternoon` | Afternoon | दोपहर | Regimen Slot Header | Standard daily phase |
| `evening` | Evening | शाम | Regimen Slot Header | Standard daily phase |
| `night` | Night | रात | Regimen Slot Header | Standard daily phase |
| `n_of_m_taken` | {n} of {m} taken | {m} में से {n} ली | Daily Dose Progress Counter | Natural Hindi phrasing |
| `my_calendar` | My calendar | मेरा कैलेंडर | Navigation Tab & Page Header | Simple personal possessive |
| `add_to_calendar` | Add to my calendar | अपने कैलेंडर में जोड़ें | .ics Download Button | Direct call-to-action |
| `pain_question` | How bad is the pain? | दर्द कितना है? | Check-in Step 1 Header | Grade 6 reading level |
| `no_pain` | No pain | दर्द नहीं | Pain Scale Slider (0) | Simple baseline |
| `worst_pain` | Worst pain | बहुत ज़्यादा दर्द | Pain Scale Slider (10) | Empathetic anchor |
| `where_hurts` | Where does it hurt? | दर्द कहाँ है? | Check-in Step 3 Header | Direct symptom prompt |
| `vs_yesterday` | Compared with yesterday | कल की तुलना में | Check-in Trend Header | Standard comparative phrase |
| `better` | Better | बेहतर | Trend Chip (Improving) | Clean everyday term |
| `same` | Same | वैसा ही | Trend Chip (Stable) | Colloquial neutral term |
| `worse` | Worse | ज़्यादा | Trend Chip (Deteriorating) | Clinically actionable |
| `send_checkin` | Send to my care team | केयर टीम को भेजें | Check-in Primary Submit | Accountable target |
| `sent_ok` | Sent. Your care team can see this. | भेज दिया गया। आपकी केयर टीम इसे देख सकती है। | Post-submission Card | Reassuring confirmation |
| `ask_care_team` | Ask my care team | केयर टीम से पूछें | Assistant Escalation Button | Human-in-the-loop action |
| `from_papers` | From your discharge papers | आपके डिस्चार्ज पेपर से | Grounded Source Badge | Trust and provenance |
| `not_found` | I couldn't find this in your discharge papers. | यह आपके डिस्चार्ज पेपर में नहीं मिला। | Assistant Refusal Fallback | Honest, non-hallucinatory |

---

## 2. Navigation & Shell

| English | Hindi | Component / Location |
|---|---|---|
| Recovery portal | रिकवरी पोर्टल | Brand Subtitle (Sidebar) |
| MY CARE | मेरी देखभाल | Sidebar Section Header |
| Overview | अवलोकन | Sidebar Tab Item |
| Medicines | दवाइयाँ | Sidebar Tab Item |
| My calendar | मेरा कैलेंडर | Sidebar Tab Item |
| Daily check-in | दैनिक चेक-इन | Sidebar Tab Item |
| ASK | सहायता | Sidebar Section Header |
| Ask my discharge papers | डिस्चार्ज पेपर्स से पूछें | Sidebar Assistant Tab |
| Sign Out | साइन आउट | Sidebar Footer Action |
| Search medicines, schedule... | दवाइयाँ खोजें... | Top Navigation Search Bar |
| Care Reminders | केयर रिमाइंडर | Top Nav Bell Drawer |
| All clear! No pending reminders. | सब ठीक है! कोई लंबित रिमाइंडर नहीं है। | Reminders Empty State |

---

## 3. Overview & Doses (`/patient`)

| English | Hindi | Component / Location |
|---|---|---|
| RECOVERY OVERVIEW | रिकवरी अवलोकन | Page Banner Badge |
| Day {n} after discharge | डिस्चार्ज के बाद दिन {n} | Page Banner Subtitle |
| Hi {name} | नमस्ते {name} | Hero Greeting |
| Take {medicine} scheduled for {time} | {time} पर निर्धारित {medicine} लें | Urgent Dose Prompt |
| View medicines | दवाइयाँ देखें | Banner Action Button |
| Your care team has been told | आपकी केयर टीम को सूचित कर दिया गया है | Urgent Banner Escalation |
| Waiting for care team review | समीक्षा प्रतीक्षित | Review Soon Banner |
| Care team acknowledged | केयर टीम द्वारा देखा गया | Seen Banner State |
| Today's Medicines | आज की दवाइयाँ | Dose Section Header |
| Mark Taken | ले ली | 1-Tap Action Button |
| Skip | छोड़ें | Skip Sheet Trigger |
| Undo (5 min) | वापस करें (Undo) | Floating Action Toast |
| Why are you skipping this dose? | यह दवा क्यों छोड़ रहे हैं? | Skip Sheet Drawer Title |
| Felt unwell / Nauseous | तबियत ठीक नहीं लगी / जी मिचलाना | Skip Reason 1 |
| Ran out of medicine | दवा समाप्त हो गई है | Skip Reason 2 |
| Forgot or missed time window | भूल गए या समय निकल गया | Skip Reason 3 |
| Worried about side effects | साइड इफेक्ट्स की चिंता है | Skip Reason 4 |
| Other reason | अन्य कारण | Skip Reason 5 |

---

## 4. Calendar & Plan Checklist

| English | Hindi | Component / Location |
|---|---|---|
| Month | महीना | Calendar Month Selector |
| PRESCRIBED DOSES | निर्धारित दवाइयाँ | Day Drawer Doses Section |
| APPOINTMENTS | अपॉइंटमेंट्स | Day Drawer Appointments |
| CHECK-IN & SYMPTOMS | दैनिक चेक-इन और दर्द | Day Drawer Symptoms |
| Add visit to calendar (.ics) | अपॉइंटमेंट कैलेंडर में जोड़ें (.ics) | Appointment Action |
| Post-discharge follow-up | डिस्चार्ज के बाद फॉलो-अप | Appointment Type |
| No appointments scheduled for this day | इस दिन के लिए कोई अपॉइंटमेंट निर्धारित नहीं है | Empty State |
| No check-in recorded for this day | इस दिन कोई चेक-इन दर्ज नहीं किया गया | Empty State |

---

## 5. Daily Check-in (`checkin`)

| English | Hindi | Component / Location |
|---|---|---|
| How bad is the pain today? | आज दर्द कितना है? | Pain Scale Question |
| Tap your symptoms | लक्षण चुनें | Step 2 Header |
| Swelling | सूजन | Symptom Chip |
| Redness | लालिमा | Symptom Chip |
| Dizziness | चक्कर आना | Symptom Chip |
| Feverish | बुखार जैसा | Symptom Chip |
| Nausea | जी मिचलाना | Symptom Chip |
| Short of breath | सांस फूलना | Symptom Chip |
| Where is the symptom located? | लक्षण कहाँ महसूस हो रहा है? | Location Step Header |
| Chest | छाती | Location Chip |
| Surgical site | ऑपरेशन की जगह | Location Chip |
| Left arm | बायाँ हाथ | Location Chip |
| Right leg | दायाँ पैर | Location Chip |
| Abdomen | पेट | Location Chip |
| General / Whole body | पूरा शरीर | Location Chip |
| Start voice input | बोलकर दर्ज करें | Voice STT Trigger |
| Listening... Speak in Hindi or English | सुन रहे हैं... हिंदी या अंग्रेज़ी में बोलें | Voice Recording Active |
| Emergency Notice - Call 112 Immediately | आपातकालीन सूचना - तुरंत 112 पर कॉल करें | Emergency Alert Banner |
| Sent. Your care team can see this. | भेज दिया गया। आपकी केयर टीम इसे देख सकती है। | Success Confirmation |

---

## 6. Grounded RAG Assistant (`chat`)

| English | Hindi | Component / Location |
|---|---|---|
| Answers are strictly grounded in your hospital discharge papers & care plan | उत्तर सीधे आपके डिस्चार्ज पेपर्स और केयर प्लान से प्रमाणित हैं | Assistant Header Subtitle |
| Grounded records | प्रमाणित स्रोत | Assistant Trust Badge |
| New chat | नया संवाद | Session Reset Button |
| When is my next visit? | मेरी अगली विज़िट कब है? | Starter Prompt Chip 1 |
| What medicines do I take today? | मुझे आज कौन सी दवाइयाँ लेनी हैं? | Starter Prompt Chip 2 |
| What warning signs should I watch for? | मुझे किन चेतावनी संकेतों का ध्यान रखना चाहिए? | Starter Prompt Chip 3 |
| Until when do I take my medicines? | मुझे कब तक दवाइयाँ लेनी हैं? | Starter Prompt Chip 4 |
| Ask my discharge papers... | अपने डिस्चार्ज पेपर्स से पूछें... | Input Placeholder |
| Sources: | स्रोत: | Grounded Pill Header |
| Source record passage | स्रोत रिकॉर्ड विवरण | Source Modal Title |
| This answer was verified directly against this record | यह उत्तर आपके प्रमाणित मेडिकल रिकॉर्ड से सत्यापित है | Source Modal Subtitle |
| Would you like a clinician to review this request? | क्या आप चाहते हैं कि डॉक्टर या नर्स आपसे संपर्क करें? | Refusal Prompt |
| Ask My Care Team | केयर टीम से पूछें | Escalation Button |
| Request Sent | अनुरोध भेज दिया गया | Sent Confirmation State |
| Was this answer helpful? | क्या यह उत्तर मददगार था? | Feedback Label |
