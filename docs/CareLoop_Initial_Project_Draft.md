# CareLoop: Project Initial Draft & Technical Proposal
**Autonomous Clinical Post-Discharge Triage, Wearable Telemetry & Grounded AI Platform**

---

## 1. Group Members’ Names

| S.No. | Student / Member Name | Roll Number / Student ID | Department / Specialisation | Primary Project Role |
|:---:|:---|:---|:---|:---|
| **1** | **Yugant Verma** *(Team Lead)* | *[Insert Roll Number]* | Computer Science & Engineering | System Architecture, IoT Firmware & RAG Pipeline |
| **2** | *[Insert Member 2 Name]* | *[Insert Roll Number]* | Computer Science & Engineering | Front-End Development & UI/UX Design |
| **3** | *[Insert Member 3 Name]* | *[Insert Roll Number]* | Computer Science & Engineering | Database Engineering (MySQL), Views & Stored Procedures |
| **4** | *[Insert Member 4 Name]* | *[Insert Roll Number]* | Electronics / Computer Engineering | IoT Hardware Prototyping, Sensor Calibration & Testing |

*Project Mentor / Guide:* *[Insert Professor / Supervisor Name]*  
*Institution / University:* *[Insert University / College Name]*  
*Academic Year / Semester:* 2026 / *[Insert Semester]*

---

## 2. Project Title

> ### **CareLoop: An Agentic Post-Discharge Patient Triage, Wearable IoT Telemetry, and Verifiable Grounded Retrieval System**

*Short Title / Acronym:* **CareLoop (AI Post-Discharge Care Platform)**  
*Core Governing Paradigm:* **"The LLM talks. Rules decide. Humans act."**

---

## 3. Aim and Objectives of the Project

### 3.1 Aim
To bridge the critical and vulnerable post-operative recovery gap (Days 1–30 following hospital discharge) by building an autonomous, safety-governed, agentic healthcare monitoring platform. The system continuously ingests wearable physiological telemetry, enforces deterministic clinical safety rules, executes an autonomous multi-step escalation ladder, and delivers verifiable, document-grounded AI guidance to recovering patients and hospital care teams.

### 3.2 Objectives
1. **Wearable Physiological Telemetry Ingestion (IoT)**:
   * Construct a wearable smartwatch unit based on the ESP32 microcontroller and MAX30102 PPG sensor to capture real-time Heart Rate (BPM) and Blood Oxygen Saturation ($\text{SpO}_2$).
   * Transmit encrypted biometric readings over Wi-Fi to a centralized ingestion pipeline with NTP time synchronization and signal quality indicators.
2. **Deterministic Clinical Safety Rule Engine**:
   * Implement automated database triggers and stored procedures in MySQL 8.0 that immediately evaluate incoming telemetry against doctor-approved patient thresholds (e.g., Tachycardia $> 110\text{ BPM}$, Bradycardia $< 50\text{ BPM}$, Hypoxemia $< 90\%\text{ SpO}_2$, or missed critical doses).
   * Guarantee zero reliance on probabilistic LLMs for medical alerts, ensuring 100% auditable and explainable flags.
3. **Verifiable Hybrid RAG Clinical Assistant**:
   * Build a bilingual (English & Hindi) conversational assistant for patients grounded strictly in their individualized hospital discharge summaries.
   * Employ hybrid search combining dense vector embeddings (ChromaDB) and sparse keyword retrieval (MySQL full-text) with Reciprocal Rank Fusion (RRF), deterministic zero-LLM emergency fast-paths, numeric hallucination guards, and exact document citations.
4. **Autonomous Consent-Aware Escalation Ladder**:
   * Engineer a 4-tier progressive notification workflow (`Patient` $\rightarrow$ `Caregiver` $\rightarrow$ `Primary Nurse` $\rightarrow$ `Attending Doctor`) that escalates unacknowledged clinical flags or severe telemetry breaches while respecting patient privacy and caregiver consent.
5. **Dual-Portal Web Application**:
   * Develop an empathetic, accessible **Patient Recovery Portal** featuring medication schedules, calendar sync (Google Calendar), daily symptom surveys, and discharge paper Q&A.
   * Develop a high-throughput **Clinical Staff Triage Dashboard** with explainable priority scores, real-time vitals graphs, automated shift handoff generators (SBAR format), and clinical task queues.

---

## 4. Proposed Front-End Design and Dashboard (Layout)

The user interface is architected into two distinct, responsive portals tailored for two distinct personas: **The Recovering Patient / Caregiver** and **The Hospital Clinical Care Team**.

### 4.1 Patient Recovery Portal Layout (`/patient`)
Designed with high legibility, soft clinical tones, bi-directional theme switching, and bilingual toggles (English & Hindi) to reduce cognitive load on recovering patients.

```
+----------------------------------------------------------------------------------------------------+
|  [Logo] CareLoop Recovery    [Search Bar]           [EN | HI]  [Bell (Audio)]  [User: Aarav Patel] |
+-----------------------+----------------------------------------------------------------------------+
|  MY CARE              |  EMERGENCY BANNER: Call 112 if chest pain or severe breathlessness occurs   |
|  * Overview           +------------------------------------+---------------------------------------+
|  * Medicines (Badge)  |  TODAY'S VITALS                    |  UPCOMING DOCTOR VISITS               |
|  * My Calendar        |  Heart Rate: 76 bpm [Normal]       |  Post-Op Checkup - Dr. Ananya Sharma  |
|  * Daily Check-in     |  SpO2:       98%    [Good]         |  Date: 23 Oct 2026 at 10:30 AM        |
|                       |  Last Sync:  2 mins ago (IoT Watch)|  [+ Add to Google Calendar] [Download]|
|  ASK                  +------------------------------------+---------------------------------------+
|  * Ask Discharge      |  TODAY'S MEDICATIONS SCHEDULE                                              |
|    Papers             |  - 08:00 AM: Atorvastatin 40mg  [Taken Confirmed]                          |
|                       |  - 02:00 PM: Metoprolol 25mg    [Confirm Taken] [Skip / Report]            |
|  THEME                |  - 08:00 PM: Aspirin 75mg       [Scheduled]                                |
|  [Light / Dark Mode]  +----------------------------------------------------------------------------+
|  [Sign Out]           |  DISCHARGE RECOVERY ASSISTANT (RAG Chatbot)                                |
|                       |  "From your discharge summary: Follow-up visit is scheduled for Oct 23."   |
|                       |  Sources: [Discharge summary . General p.1]  [Ask Care Team Button]        |
|                       |  [Type your recovery question here...                               ] [Send]|
+-----------------------+----------------------------------------------------------------------------+
```

### 4.2 Clinical Staff Triage Dashboard Layout (`/staff`)
Designed for high-stress hospital environments: high information density, explainable priority queues, color-coded triage badges, and shift handoff tooling.

```
+----------------------------------------------------------------------------------------------------+
| [Logo] CareLoop CLINICAL DASHBOARD    [Dept: Cardiology v]    [Search Patients]   [Dr. Ananya Sharma]|
+-----------------------+----------------------------------------------------+-----------------------+
| PRIORITISED PATIENTS  | PATIENT CLINICAL DOSSIER: Aarav Sharma (Day 3 Post)| CLINICAL ACTIONS      |
| [Critical / Action /  | Status: Red Alert | Priority Score: 92/100         | [Task Queue (3 Active)]|
|  Stable Filters]      +----------------------------------------------------+ - Task #101: Review   |
|                       | LIVE WEARABLE TELEMETRY (ESP32-DEMO-01)            |   tachycardia alert   |
| 1. Aarav Sharma [!]   | [==== Heart Rate Graph (24 hr) ====] Last: 114 bpm |   [Mark In Progress]  |
|    Score: 92 (Tachy)  | [==== SpO2 Oxygen Trend =======]     Last: 97%     | - Task #102: Refill   |
| 2. Priya Nair [Warn]  | Contact Quality: Good | Battery: 88% | Sync: Live  |   Metoprolol check    |
|    Score: 68 (Missed) +----------------------------------------------------+-----------------------+
| 3. Rajesh Kumar [OK]  | ACTIVE CLINICAL FLAGS & TRIGGER RULES              | SHIFT HANDOFF (SBAR)  |
|    Score: 24 (Stable) | * Rule #4 Triggered: Sustained Tachycardia (>110)  | [Generate SBAR Draft] |
| 4. Sunita Devi [OK]   | * Reason: HR recorded at 114 bpm for > 15 minutes  | [Approve & Hand Off]  |
|    Score: 12 (Stable) | * Escalation Level: Level 3 (Primary Nurse Notified|-----------------------+
|                       +----------------------------------------------------+ CLINICAL AI SUMMARY  |
|                       | AUDIT LOG & INTERACTION TIMELINE                   | [Generate AI Summary] |
|                       | - 14:10: Telemetry reading ingested (114 bpm)      | [Doctor Sign-off]     |
|                       | - 14:11: Automatic Level 1 SMS sent to Patient     |                       |
+-----------------------+----------------------------------------------------+-----------------------+
```

---

## 5. Front-End Tools and Technologies

| Technology / Tool | Version / Specification | Purpose in Project |
|:---|:---|:---|
| **React.js** | 18.2+ | Component-driven Single Page Application (SPA) architecture for dynamic, reactive state management. |
| **JavaScript (ES6+) / JSX** | Modern Standard | Core application logic, asynchronous data fetching, and component templating. |
| **Vanilla CSS3 & Custom Design Tokens** | CSS3 Custom Properties | Fully customized clinical design system with zero bloated third-party CSS dependencies; includes theme tokens, accessible contrast ratios, and responsive CSS Grid / Flexbox layouts. |
| **Lucide React** | Latest | Clean, accessible clinical vector iconography (Heart, Activity, Calendar, ShieldCheck, AlertTriangle). |
| **HTML5 Web Audio API** | Native Browser API | Plays soothing auditory chimes for dose confirmations and distinct alert tones for critical clinical updates. |
| **Chrome DevTools / Lighthouse** | Latest | Continuous auditing for WCAG 2.1 AA accessibility, sub-millisecond layout shifts (CLS), and mobile responsiveness. |

---

## 6. Back-End Tools and Technologies

| Technology / Tool | Version / Specification | Purpose in Project |
|:---|:---|:---|
| **Python** | 3.12+ | Primary server-side programming language chosen for strong asynchronous runtime and native AI/data science libraries. |
| **FastAPI** | 0.115+ | High-performance ASGI REST framework providing native Pydantic validation, asynchronous route concurrency, and automatic OpenAPI documentation. |
| **Uvicorn** | Standard ASGI | Ultra-fast ASGI web server handling HTTP/1.1 and WebSocket connections. |
| **MySQL Database** | 8.0.16+ (InnoDB) | The single authoritative source of truth. Contains **25 relational tables**, **7 views**, **8 stored procedures**, **3 triggers**, and **2 scheduled events** enforcing relational integrity, audit trails, and deterministic alert rules. |
| **PyMySQL / DB Pooling** | Latest | Thread-safe database connectivity and pooled cursor execution. |
| **ChromaDB** | 0.5+ | Local, self-hosted vector database storing dense embeddings of hospital discharge documents for semantic similarity retrieval. |
| **Google Gemini API** | `gemini-3.5-flash-lite` | Large Language Model used strictly for contextual text synthesis, natural language explanations, and bilingual (Hindi/English) phrasing. |
| **Pytest & Starlette TestClient** | Latest | Comprehensive test harness executing **99 automated unit and integration tests** across authentication, IoT ingestion, clinical rules, and AI guardrails. |

---

## 7. Front-End and Back-End Connectivity Tools and Technologies

```
  +------------------+         HTTP POST / GET (JSON)        +-------------------+
  |   React Client   | <===================================> |   FastAPI Server  |
  | (Port 3000/3001) |     Bearer JWT (HS256 Auth Token)     |    (Port 8000)    |
  +------------------+                                       +-------------------+
                                                                 ||         ||
                                               SQL Triggers / SP ||         || Embeddings
                                                                 \/         \/
                                                          +-----------+ +-----------+
                                                          | MySQL 8.0 | | ChromaDB  |
                                                          +-----------+ +-----------+
```

| Connectivity Layer | Tool / Protocol | Technical Implementation Details |
|:---|:---|:---|
| **API Architecture** | **RESTful JSON API** | Clean decoupled architecture communicating via standard HTTP verbs (`GET`, `POST`, `PUT`, `DELETE`) with strict Pydantic payload validation. |
| **Client HTTP Transport** | **Fetch API / Axios Client** | Centralized client module (`frontend/src/services/api.js`) featuring dynamic host resolution (`http://${window.location.hostname}:8000`) to guarantee seamless connectivity across `localhost` and LAN environments. |
| **Authentication & RBAC** | **JWT (JSON Web Tokens)** | Cryptographically signed HS256 tokens carrying user identity and role claims (`Patient`, `Caregiver`, `Doctor`, `Nurse`). Includes IDOR protection enforcing patient data isolation. |
| **Cross-Origin Handling** | **FastAPI CORS Middleware** | Configured `CORSMiddleware` supporting dynamic origin resolution, pre-flight checks, and authorization header propagation (`Authorization: Bearer <token>`). |
| **Third-Party Calendar Sync** | **Google Calendar Web API & .ics Engine** | Dynamic appointment synchronizer generating direct Google Calendar deep-links (`https://calendar.google.com/calendar/render?action=TEMPLATE...`) and downloadable `.ics` iCalendar calendar event payloads. |
| **IoT Device Authentication** | **HTTP Header Authentication** | Custom authorization header (`X-Device-Key`) verified against pre-shared cryptographically hashed device credentials before telemetry is permitted into the database. |

---

## 8. IoT Devices Used as Input Sources

The CareLoop physical layer captures live physiological telemetry from recovering patients in home environments via a dedicated wearable prototype.

```
   +--------------------+     I2C Bus (SDA=21, SCL=22)     +--------------------+
   |  MAX30102 PPG      | -------------------------------> |   ESP32 DevKit V1  |
   |  (Heart Rate/SpO2) |                                  |  (Dual-Core 2.4GHz)|
   +--------------------+                                  +--------------------+
   +--------------------+     I2C Bus (SDA=21, SCL=22)               ||
   |  SSD1306 OLED      | <------------------------------------------+| Wi-Fi 802.11b/g/n
   |  (128x64 Display)  |                                            \/ (HTTP POST)
   +--------------------+                                  +--------------------+
                                                           | CareLoop Backend   |
                                                           | (/device/readings) |
                                                           +--------------------+
```

### 8.1 Hardware Specifications

| Component | Hardware Model | Interface / Pinout | Clinical & Operational Purpose |
|:---|:---|:---|:---|
| **Microcontroller Unit (MCU)** | **ESP32 DevKit V1 (ESP-WROOM-32)** | 32-bit LX6 dual-core, Micro-USB, 2.4 GHz Wi-Fi | Ingests raw biometric signals, calculates rolling heart rates, renders local OLED statistics, and executes encrypted HTTP uploads. |
| **Optical Pulse Oximeter & Heart Rate Sensor** | **Maxim Integrated MAX30102 / MAX30100** | $\text{I}^2\text{C}$ (`SDA: GPIO 21`, `SCL: GPIO 22`) | Utilizes dual Red (660nm) and Infrared (880nm) LEDs with low-noise photodetectors to measure heart rate and peripheral oxygen saturation ($\text{SpO}_2$) via photoplethysmography (PPG). |
| **On-Board Visual Display** | **0.96-inch OLED (SSD1306)** | $\text{I}^2\text{C}$ (`Address: 0x3C`, `SDA: 21`, `SCL: 22`) | Provides immediate visual feedback to the patient on the wrist: displays **`AI NURSE WATCH`**, active **`BPM`**, and skin contact status (`OK` vs `No Finger`). |
| **Power Management** | **3.7V LiPo (500mAh) + TP4056 / Micro-USB** | Regulated 3.3V DC Rail | Powers the wearable unit untethered for multi-hour monitoring with battery protection circuitry. |
| **Wearable Enclosure & Strap** | **20mm/22mm Silicone Strap + Insulated Cradle** | Wrist Mount | Secures the optical sensor flush against the radial artery while isolating board pins from skin conductivity. |

### 8.2 Firmware Transmission Protocol & Ingestion Contract
The firmware ([device/esp32_careloop/esp32_careloop.ino](file:///Users/yugantverma/Desktop/CareLoop/device/esp32_careloop/esp32_careloop.ino)) implements an autonomous sampling and transmission cycle:
1. **NTP Epoch Time Synchronization**: Upon boot, the device connects to Wi-Fi and queries `pool.ntp.org` to ensure all sensor readings carry valid UTC timestamps.
2. **Contact Quality Gate**: If infrared reflectivity is below baseline (`sensor.getIR() < 50000`), the device flags the reading quality as `"Questionable"` or `"No Finger"`, avoiding false bradycardia alerts caused by loose contact.
3. **Payload Structure**: Every 60 seconds (or immediately on clinical deviation), an HTTP POST is transmitted to `/device/readings`:
   ```json
   {
     "device_id": "ESP32-DEMO-01",
     "measurement_type": "Heart_Rate",
     "value": 78.5,
     "unit": "bpm",
     "measured_at": 1730198000,
     "quality": "Good"
   }
   ```
4. **Database Trigger Execution**: MySQL evaluates the reading against the patient's alert thresholds. If heart rate exceeds the safe ceiling, the trigger automatically raises a severity flag in `clinical_flags` and schedules escalation.

---

### 9. Summary & Compliance Checklist

* [x] **Group Members' Names**: Listed with academic roles, roll number fields, and mentor details.
* [x] **Project Title**: Official title with guiding clinical paradigm (*"The LLM talks. Rules decide. Humans act."*).
* [x] **Aim & Objectives**: Explicit aim with 5 measurable, engineering-focused technical objectives.
* [x] **Proposed Front-End Layout**: Comprehensive ASCII wireframes for both the Patient Portal and Clinical Dashboard.
* [x] **Front-End Tools & Technologies**: React 18, Custom CSS3 design tokens, Lucide icons, HTML5 Web Audio.
* [x] **Back-End Tools & Technologies**: Python 3.12, FastAPI, MySQL 8.0 (triggers & stored procedures), ChromaDB, Gemini LLM.
* [x] **Connectivity Technologies**: REST APIs, dynamic origin routing, JWT HS256 RBAC, Google Calendar API.
* [x] **IoT Devices & Input Sources**: Detailed breakdown of ESP32, MAX30102 PPG sensor, SSD1306 OLED display, wiring pinouts, and transmission contracts.
