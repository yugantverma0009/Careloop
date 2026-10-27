# CareLoop: Detailed Start Guide
### How to go from the SQL file to a working hackathon prototype

**Companion files:** `careloop_mysql_v2_detailed.sql` (database), `careloop_hackathon_dbms_project.md` (proposal and pitch)
**Rule that guides every decision:** *The LLM talks. Rules decide. Humans act.*

> **Honest status of this guide.** The SQL and code below are a starter skeleton written carefully but **not executed** in my environment. Treat every snippet as a first draft: run it, read the error, fix it. Library APIs (Twilio, Chroma, Google GenAI, SparkFun MAX3010x) change, so check each library's current docs when something does not match. All data is synthetic. This is a prototype, not a medical device.

---

## 1. What you will have at the end of each milestone

| Milestone | You can demo | Proof (run this) |
|---|---|---|
| **M0** Database | Schema, seed data, triggers fire | SQL Q19 counts, Q2 triage board, Q6 trigger |
| **M1** Backend + login | Role-based API, Swagger page | `http://localhost:8000/docs` |
| **M2** Device data | Simulator (then ESP32) posting readings, flags appear | Q3, Q5, Q6 |
| **M3** Patient flows | Doses, symptom check-in, emergency path | Q8, Q4 |
| **M4** Escalation | Ladder with consent, acknowledge flow, audit log | Q9, Q10, Q11 |
| **M5** AI layer | Cited RAG answers, safe refusal, tags, draft summary | Q12, Q13, Q27 |
| **M6** Polish | Hindi labels, dashboard, rehearsed demo | Demo script in the proposal |

Do them **in order**. If time runs out after M4 you still have a complete, impressive project.

---

## 2. Tools to install

| Tool | Version | Used for |
|---|---|---|
| MySQL Server + Workbench | 8.0.16 or newer | Database |
| Python | 3.10+ | Backend, agents, simulator |
| Node.js | 18+ (only if you build React) | Frontend |
| Arduino IDE or PlatformIO | latest | ESP32 firmware |
| Git + VS Code | any | Code |
| Twilio account (trial) | - | SMS (optional until M4) |
| LLM API key (e.g. Google AI Studio) | - | Chat, tags, summaries (M5) |

---

## 3. Recommended repository layout

```
careloop/
├── database/
│   └── careloop_mysql_v2_detailed.sql
├── backend/
│   ├── .env                  # never commit
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # FastAPI app + routes
│       ├── db.py             # connection helper
│       ├── auth.py           # login, JWT, role checks
│       ├── safety.py         # emergency keywords, refusal patterns
│       ├── escalation.py     # ladder logic + SMS
│       ├── rag.py            # chunking, Chroma, grounded answers
│       ├── llm.py            # single wrapper around the LLM API
│       └── scheduler.py      # periodic jobs
├── device/
│   ├── simulator.py          # fake device (use this first)
│   └── esp32_careloop/esp32_careloop.ino
├── frontend/                 # React or plain HTML pages
├── scripts/
│   ├── set_demo_passwords.py
│   └── index_document.py
└── docs/                     # ER diagram, screenshots, report
```

Add a `.gitignore` with `.env`, `.venv/`, `chroma/`, `__pycache__/`. **Never** commit API keys or Wi-Fi passwords.

---

## 4. Milestone M0: Database

1. Open MySQL Workbench, connect as a user that can create databases.
2. Open `careloop_mysql_v2_detailed.sql`, read the header, run the **entire** script (lightning icon, not the single-statement icon).
3. Run **Q19**. Expected: `25 tables, 7 views, 8 procedures, 3 triggers, 2 events`.
4. Run Q1-Q5, then Q6 (watch the trigger create a flag), Q7 (impossible value becomes Invalid), Q8 (emergency report creates an Urgent flag).
5. Re-run the whole script any time to reset data.

### 4.1 What every table is for (data dictionary)

| Table | Purpose | Written by | Read by |
|---|---|---|---|
| `care_staff` | Doctors and nurses | Admin | Everyone (names on dashboards) |
| `patients` | Patient profile, language, consent status | Admin / onboarding | All flows |
| `caregivers` | Family contacts with explicit consent flag | Patient / admin | Escalation agent |
| `user_accounts` | Logins; a CHECK ensures exactly one identity per role | Admin | Auth |
| `discharge_records` | Discharge date, condition summary, follow-up due | Doctor | Chat, dashboard |
| `discharge_documents` | Uploaded discharge files and indexing status | Backend | RAG |
| `document_chunks` | Text chunks used for citations (vectors live in Chroma) | Indexing script | RAG, chat |
| `medicines` | Medicine catalogue (fictional in demo) | Admin | Prescriptions |
| `prescriptions` | Which medicine, which patient, date range | Doctor | Dose generation |
| `prescription_times` | One row per daily dose time | Doctor | `sp_generate_daily_doses` |
| `medication_logs` | One row per dose event and its status | Procedure / patient | Reminder agent, adherence view |
| `devices` | Registered devices and last heartbeat | Admin / trigger | Device status view |
| `sensor_readings` | Heart rate / SpO₂ with quality status | Device endpoint | Rules, charts |
| `symptom_reports` | Patient check-ins, pain, language, emergency hit | Patient | Triggers, dashboard |
| `symptom_report_tags` | Structured tags and who produced them | Check-in agent | Search |
| `chat_messages` | Patient and AI-nurse messages, grounded or not | Chat endpoint | Audit |
| `chat_message_sources` | Which chunks supported which answer | RAG | Citations |
| `alert_rules` | Clinician-approved limits per patient | Doctor | Rule engine |
| `flags` | A reason for a human to look, with severity and status | Triggers / procedures | Triage board |
| `escalations` | Ladder steps taken for each flag | Escalation agent | Dashboard, audit |
| `follow_up_tasks` | Work items created when a flag is acknowledged | `sp_acknowledge_flag` | Nurses |
| `appointments` | Scheduled follow-ups | Staff | Patient app |
| `ai_summaries` | AI draft summaries awaiting review | Summary agent | Doctor |
| `risk_snapshots` | Explainable priority score history | Procedure | Triage board |
| `audit_log` | Every autonomous or human action | Backend / procedures | Review |

### 4.2 Where each business rule is enforced

| Rule | Enforced in |
|---|---|
| Pain score is 0-10 | DB CHECK |
| A reading can only be stored for the device's owner | DB composite FK |
| A retried device upload creates no duplicate | DB UNIQUE |
| Impossible sensor values are stored as Invalid, never flagged clinically | DB trigger |
| Reading above/below approved limit creates one open flag with a reason | DB trigger |
| Emergency keyword creates an Urgent flag | Backend detects, DB trigger flags |
| Caregiver contacted only with consent | Escalation code + DB column |
| A patient can read only their own data | **Backend** (never trust an id from the URL) |
| Acknowledging is atomic | DB procedure (transaction) |
| AI never creates flags or changes doses | **Backend design** (LLM output is text only) |

---

## 5. Milestone M1: Backend setup

```bash
cd careloop/backend
python -m venv .venv
# Windows: .venv\Scripts\activate      Mac/Linux: source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pymysql python-dotenv pyjwt bcrypt apscheduler \
            twilio chromadb pypdf google-genai requests
pip freeze > requirements.txt
```

Create `backend/.env` (example values only):

```
DB_HOST=localhost
DB_PORT=3306
DB_USER=careloop_api
DB_PASSWORD=change_this
DB_NAME=careloop
JWT_SECRET=use-a-long-random-string
DEVICE_API_KEY=demo-device-key-change-me
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=
SMS_ENABLED=false
LLM_API_KEY=
LLM_MODEL=check-current-model-name-in-provider-docs
CHROMA_PATH=./chroma
```

Create the DB user (run in Workbench):

```sql
CREATE USER 'careloop_api'@'localhost' IDENTIFIED BY 'change_this';
GRANT SELECT, INSERT, UPDATE, EXECUTE ON careloop.* TO 'careloop_api'@'localhost';
```

Set the time zone once and use it everywhere (the prototype uses IST):
`SET GLOBAL time_zone = '+05:30';` (or configure in `my.ini`). Mixed time zones are the most common source of "my flag fired at the wrong time" bugs.

### 5.1 `db.py`

```python
import os
import pymysql
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv()

@contextmanager
def get_conn():
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "careloop"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("SET time_zone = '+05:30'")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### 5.2 `auth.py`: login, JWT, roles

```python
import os, bcrypt, jwt
from datetime import datetime, timedelta, timezone
from fastapi import Header, HTTPException, Depends
from .db import get_conn

SECRET = os.getenv("JWT_SECRET", "dev-only")

def verify_login(email: str, password: str):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM user_accounts WHERE email=%s", (email,))
        row = cur.fetchone()
    if not row or not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return None
    return row

def make_token(acct: dict) -> str:
    payload = {
        "sub": acct["account_id"],
        "role": acct["account_role"],
        "patient_id": acct["patient_id"],
        "caregiver_id": acct["caregiver_id"],
        "staff_id": acct["staff_id"],
        "exp": datetime.now(timezone.utc) + timedelta(hours=8),
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def current_user(authorization: str = Header(...)):
    try:
        return jwt.decode(authorization.removeprefix("Bearer "), SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

def require_role(*roles):
    def dep(user=Depends(current_user)):
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Not allowed for this role")
        return user
    return dep
```

The seed accounts hold a placeholder hash. Set real demo passwords with `scripts/set_demo_passwords.py`:

```python
import bcrypt, pymysql, os
from dotenv import load_dotenv
load_dotenv("../backend/.env")
conn = pymysql.connect(host=os.getenv("DB_HOST"), user="root", password=input("root password: "), database="careloop")
h = bcrypt.hashpw(b"Demo@12345", bcrypt.gensalt()).decode()
with conn.cursor() as cur:
    cur.execute("UPDATE user_accounts SET password_hash=%s", (h,))
conn.commit()
print("Demo accounts now use the password Demo@12345 (demo only!)")
```

---

## 6. Milestone M2: Device data (simulator first, ESP32 second)

### 6.1 Ingestion endpoint (idempotent)

```python
# main.py (excerpt)
import os, pymysql
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field
from .db import get_conn
from .auth import verify_login, make_token, require_role

app = FastAPI(title="CareLoop API")
IST = ZoneInfo("Asia/Kolkata")

class ReadingIn(BaseModel):
    device_id: str
    measurement_type: str = Field(pattern="^(Heart_Rate|SpO2)$")
    value: float
    unit: str
    measured_at: int                 # epoch seconds (UTC) from the device
    quality: str = Field(pattern="^(Good|Questionable|Simulated)$")

@app.post("/device/readings")
def ingest(r: ReadingIn, x_device_key: str = Header(...)):
    if x_device_key != os.getenv("DEVICE_API_KEY"):          # demo only; use per-device hashed keys later
        raise HTTPException(status_code=401, detail="Bad device key")
    when = datetime.fromtimestamp(r.measured_at, tz=IST).replace(tzinfo=None)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT patient_id FROM devices WHERE device_id=%s", (r.device_id,))
        dev = cur.fetchone()
        if not dev:
            raise HTTPException(status_code=404, detail="Unknown device")
        try:
            cur.execute(
                """INSERT INTO sensor_readings
                   (patient_id, device_id, measurement_type, measurement_value, unit, measured_at, quality_status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (dev["patient_id"], r.device_id, r.measurement_type, r.value, r.unit, when, r.quality),
            )
        except pymysql.err.IntegrityError as e:
            if e.args[0] == 1062:                              # duplicate key: retried upload
                return {"status": "duplicate_ignored"}
            raise
    return {"status": "stored"}      # triggers have already created any flag
```

Because the database triggers do the rule checks, the endpoint stays tiny and the logic is visible in SQL, which suits a DBMS submission.

### 6.2 Simulator `device/simulator.py`

```python
import time, random, argparse, requests

p = argparse.ArgumentParser()
p.add_argument("--api", default="http://localhost:8000")
p.add_argument("--device", default="ESP32-DEMO-02")
p.add_argument("--key", default="demo-device-key-change-me")
p.add_argument("--interval", type=int, default=10)
p.add_argument("--low-spo2", action="store_true", help="send an SpO2 below the demo limit")
a = p.parse_args()

while True:
    now = int(time.time())
    hr = random.randint(72, 92)
    spo2 = random.randint(89, 91) if a.low_spo2 else random.randint(95, 98)
    for mtype, val, unit in (("Heart_Rate", hr, "bpm"), ("SpO2", spo2, "%")):
        body = {"device_id": a.device, "measurement_type": mtype, "value": val,
                "unit": unit, "measured_at": now, "quality": "Simulated"}
        r = requests.post(f"{a.api}/device/readings", json=body, headers={"X-Device-Key": a.key}, timeout=10)
        print(mtype, val, r.status_code, r.text)
    time.sleep(a.interval)
```

Run `python simulator.py --low-spo2` during the demo to show the flag appear live. Missing data demo: just stop the script and show the `v_device_status` view.

### 6.3 ESP32 firmware (starter, heart rate first)

Libraries (Library Manager): **SparkFun MAX3010x Pulse and Proximity Sensor Library**. Wiring on many ESP32 dev boards: SDA to GPIO 21, SCL to GPIO 22, GND to GND, power as your module's documentation says. Verify for your exact board.

```cpp
#include <Wire.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include "MAX30105.h"
#include "heartRate.h"

const char* WIFI_SSID = "YOUR_WIFI";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* API_URL   = "http://192.168.1.10:8000/device/readings"; // your laptop's LAN IP
const char* DEVICE_ID = "ESP32-DEMO-01";
const char* DEVICE_KEY = "demo-device-key-change-me";

MAX30105 sensor;
float bpmAvg = 0; long lastBeat = 0; byte beats = 0;
unsigned long lastSend = 0;

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  if (!sensor.begin(Wire, I2C_SPEED_FAST)) { Serial.println("Sensor not found"); while (1); }
  sensor.setup();                         // default LED settings
  sensor.setPulseAmplitudeRed(0x0A);
  sensor.setPulseAmplitudeGreen(0);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  configTime(0, 0, "pool.ntp.org");       // device sends UTC epoch seconds; the server converts to IST
}

void sendReading(float bpm, const char* quality) {
  if (WiFi.status() != WL_CONNECTED) return;
  time_t now; time(&now);
  if (now < 1700000000) return;           // time not synced yet: do not send bad timestamps
  HTTPClient http;
  http.begin(API_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-Device-Key", DEVICE_KEY);
  String body = String("{\"device_id\":\"") + DEVICE_ID +
                "\",\"measurement_type\":\"Heart_Rate\",\"value\":" + String(bpm, 1) +
                ",\"unit\":\"bpm\",\"measured_at\":" + String((long)now) +
                ",\"quality\":\"" + quality + "\"}";
  int code = http.POST(body);
  Serial.printf("POST %d\n", code);
  http.end();
}

void loop() {
  long ir = sensor.getIR();
  bool finger = ir > 50000;               // typical threshold; tune for your module
  if (finger && checkForBeat(ir)) {
    long delta = millis() - lastBeat; lastBeat = millis();
    float bpm = 60.0 / (delta / 1000.0);
    if (bpm > 20 && bpm < 255) {
      bpmAvg = (beats == 0) ? bpm : (bpmAvg * 0.8f + bpm * 0.2f);
      if (beats < 255) beats++;
    }
  }
  if (millis() - lastSend > 60000) {      // one reading per minute
    lastSend = millis();
    if (finger && beats >= 5) sendReading(bpmAvg, "Good");
    else                      sendReading(0, "Questionable"); // optional: or skip sending when no finger
  }
}
```

Notes: for SpO₂, adapt the SparkFun `spo2_algorithm` example only **after** heart rate works, and keep its quality as `Questionable` unless you can compare against a reference device. Optical readings are sensitive to motion, pressure, ambient light and skin contact. Never call them clinical. Sending a `0` BPM "Questionable" reading would be flagged by nobody (rules ignore Questionable), but you may prefer to skip sending it.

---

## 7. Milestone M3: Patient flows

### 7.1 Doses

- Run `CALL sp_generate_daily_doses(CURDATE())` (or enable the scheduler, section 9).
- `GET /patient/me/doses`: dose events for today, filtered by the **patient id inside the JWT**:

```python
@app.get("/patient/me/doses")
def my_doses(user=Depends(require_role("Patient"))):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""SELECT ml.medication_log_id, m.medicine_name, ml.scheduled_for, ml.status
                       FROM medication_logs ml
                       JOIN prescriptions pr ON pr.prescription_id = ml.prescription_id
                       JOIN medicines m ON m.medicine_id = pr.medicine_id
                       WHERE pr.patient_id=%s AND ml.scheduled_for >= CURDATE()
                         AND ml.scheduled_for < CURDATE() + INTERVAL 1 DAY
                       ORDER BY ml.scheduled_for""", (user["patient_id"],))
        return cur.fetchall()
```

- `POST /patient/me/doses/{id}/confirm` with `{"status": "Taken_Confirmed" | "Skipped"}`: update only if the dose belongs to this patient (join through prescriptions), set `recorded_at=NOW()`, `recorded_by='Patient'`, and write an `audit_log` row.

### 7.2 Symptom check-in with the emergency layer (`safety.py`)

```python
EMERGENCY_TERMS = [
    # English (starter list only; a clinician must review and extend it)
    "chest pain", "can't breathe", "cannot breathe", "difficulty breathing", "short of breath",
    "unconscious", "fainted", "heavy bleeding", "seizure", "stroke",
    # Hindi
    "सीने में दर्द", "सांस नहीं", "सांस लेने में तकलीफ", "बेहोश", "बहुत खून",
]

EMERGENCY_GUIDANCE = {
    "en": "This may be an emergency. Call your local emergency number now or go to the nearest emergency department. Your care team has been alerted.",
    "hi": "यह आपातकालीन स्थिति हो सकती है। अभी अपने स्थानीय आपातकालीन नंबर पर कॉल करें या नज़दीकी अस्पताल के आपातकालीन विभाग जाएँ। आपकी केयर टीम को सूचित कर दिया गया है।",
}

def has_emergency_term(text: str) -> bool:
    t = text.lower()
    return any(term in t for term in EMERGENCY_TERMS)

DOSE_CHANGE_PATTERNS = ["double dose", "skip my medicine", "stop taking", "increase the dose",
                        "extra tablet", "दवा बंद", "दोगुनी खुराक"]

def is_dose_change_question(text: str) -> bool:
    t = text.lower()
    return any(p in t for p in DOSE_CHANGE_PATTERNS)
```

Endpoint logic:

```python
@app.post("/patient/me/symptoms")
def report_symptom(body: SymptomIn, user=Depends(require_role("Patient"))):
    emergency = has_emergency_term(body.text)
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO symptom_reports
            (patient_id, symptom_text, pain_level, input_method, language, emergency_keyword_hit)
            VALUES (%s,%s,%s,%s,%s,%s)""",
            (user["patient_id"], body.text, body.pain_level, body.input_method, body.language, emergency))
        # the AFTER INSERT trigger creates the Urgent flag and any pain-rule flag
    # tag extraction runs in the background and must never block the response
    return {"emergency": emergency,
            "guidance": EMERGENCY_GUIDANCE[body.language] if emergency else None}
```

The emergency path never waits for the LLM and never tells the patient to "wait for a call".

---

## 8. Milestone M4: Escalation agent (`escalation.py`)

Ladder definitions (minutes after the flag was created; demo values, to be set by clinicians):

```python
LADDER_REVIEW_SOON = [(1, "Patient_Prompt", "App", 0),
                      (2, "Caregiver_SMS", "SMS", 20),
                      (3, "Nurse_Alert", "Dashboard", 40),
                      (4, "Doctor_Alert", "Dashboard", 90)]
LADDER_URGENT      = [(1, "Patient_Prompt", "App", 0),
                      (2, "Nurse_Alert", "Dashboard", 0),
                      (3, "Doctor_Alert", "Dashboard", 0),
                      (4, "Caregiver_SMS", "SMS", 10)]
```

Core loop (runs every minute from the scheduler):

```python
import os
from datetime import datetime
from .db import get_conn

def send_sms(to: str, body: str) -> str:
    if os.getenv("SMS_ENABLED", "false").lower() != "true":
        return "Sent"                                  # demo mode: logged only
    try:
        from twilio.rest import Client
        Client(os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN")).messages.create(
            to=to, from_=os.getenv("TWILIO_FROM_NUMBER"), body=body)
        return "Sent"
    except Exception:
        return "Failed"                                # a failure must never stop the ladder

def run_escalations():
    now = datetime.now()
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM flags WHERE status='Open'")
        for f in cur.fetchall():
            ladder = LADDER_URGENT if f["severity"] == "Urgent_Review" else LADDER_REVIEW_SOON
            minutes = (now - f["created_at"]).total_seconds() / 60
            for step_no, step_type, channel, offset in ladder:
                if minutes < offset:
                    continue
                cur.execute("SELECT 1 FROM escalations WHERE flag_id=%s AND step_no=%s",
                            (f["flag_id"], step_no))
                if cur.fetchone():
                    continue
                status, note = "Sent", None
                if step_type == "Caregiver_SMS":
                    cur.execute("""SELECT phone FROM caregivers
                                   WHERE patient_id=%s AND consent_granted=TRUE
                                   ORDER BY is_primary DESC LIMIT 1""", (f["patient_id"],))
                    cg = cur.fetchone()
                    if not cg:
                        status, note = "Skipped_No_Consent", "No caregiver with recorded consent"
                    else:
                        status = send_sms(cg["phone"], "CareLoop: the care team is checking on a recent update. Please contact the patient.")
                cur.execute("""INSERT IGNORE INTO escalations
                               (flag_id, step_no, step_type, channel, delivery_status, notes)
                               VALUES (%s,%s,%s,%s,%s,%s)""",
                            (f["flag_id"], step_no, step_type, channel, status, note))
                cur.execute("""INSERT INTO audit_log (actor_type, actor_id, action, entity_type, entity_id, details)
                               VALUES ('Agent','escalation_agent','ESCALATION_STEP','flag',%s,
                                       JSON_OBJECT('step',%s,'status',%s))""",
                            (f["flag_id"], step_type, status))
```

Keep SMS text **free of medical details** (the message above reveals nothing about the condition). Acknowledging a flag (`sp_acknowledge_flag`) changes its status away from `Open`, so the loop stops escalating it automatically.

Acknowledge endpoint:

```python
@app.post("/staff/flags/{flag_id}/acknowledge")
def acknowledge(flag_id: int, note: str = "", user=Depends(require_role("Doctor", "Nurse"))):
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.callproc("sp_acknowledge_flag", (flag_id, user["staff_id"], note))
        except pymysql.err.OperationalError as e:
            raise HTTPException(status_code=409, detail="Flag not found or already acknowledged")
    return {"status": "acknowledged"}
```

(Check the exact exception class your PyMySQL version raises for `SIGNAL SQLSTATE '45000'`; print `type(e)` once and adjust.)

---

## 9. Scheduler (`scheduler.py`)

You can use MySQL events (in the SQL file, disabled by default) **or** the backend scheduler. For clarity in a demo, use the backend:

```python
from apscheduler.schedulers.background import BackgroundScheduler
from .db import get_conn
from .escalation import run_escalations

def rule_cycle():
    with get_conn() as conn, conn.cursor() as cur:
        cur.callproc("sp_generate_daily_doses", (datetime.now().date(),))
        cur.callproc("sp_mark_overdue_doses_missed", (datetime.now(), 60))
        cur.callproc("sp_evaluate_missed_dose_rules", (datetime.now(),))
        cur.callproc("sp_evaluate_no_data_rules", (datetime.now(),))
        cur.callproc("sp_compute_all_risk_snapshots", (datetime.now(),))

def start():
    s = BackgroundScheduler()
    s.add_job(rule_cycle, "interval", minutes=5)
    s.add_job(run_escalations, "interval", minutes=1)
    s.start()
```

Call `start()` from FastAPI's startup event. During the live demo, trigger these manually (or lower the intervals) so you do not wait.

---

## 10. Milestone M5: AI layer

### 10.1 `llm.py`: one wrapper only

```python
import os
from google import genai

_client = genai.Client(api_key=os.getenv("LLM_API_KEY"))

def generate(system: str, user: str) -> str:
    resp = _client.models.generate_content(
        model=os.getenv("LLM_MODEL"),
        contents=f"{system}\n\n{user}",
    )
    return resp.text
```

Every other module calls `generate()`. If you change provider, only this file changes. Model names change often; copy the current name from your provider's documentation into `.env`.

### 10.2 Indexing a discharge document (`scripts/index_document.py`)

```python
import sys, pypdf, chromadb, pymysql, os
from dotenv import load_dotenv
load_dotenv("../backend/.env")

discharge_id, pdf_path = int(sys.argv[1]), sys.argv[2]
text = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(pdf_path).pages)

def chunk(t, size=500, overlap=80):
    out, i = [], 0
    while i < len(t):
        out.append(t[i:i + size]); i += size - overlap
    return out

chunks = [c.strip() for c in chunk(text) if c.strip()]
conn = pymysql.connect(host=os.getenv("DB_HOST"), user=os.getenv("DB_USER"), password=os.getenv("DB_PASSWORD"),
                       database="careloop", charset="utf8mb4")
col = chromadb.PersistentClient(path=os.getenv("CHROMA_PATH", "./chroma")).get_or_create_collection(f"discharge_{discharge_id}")
with conn.cursor() as cur:
    cur.execute("INSERT INTO discharge_documents (discharge_id, file_name, indexing_status, vector_collection) VALUES (%s,%s,'Pending',%s)",
                (discharge_id, os.path.basename(pdf_path), f"discharge_{discharge_id}"))
    doc_id = cur.lastrowid
    for i, c in enumerate(chunks):
        vid = f"{doc_id}-{i}"
        cur.execute("INSERT INTO document_chunks (document_id, chunk_index, chunk_text, vector_id) VALUES (%s,%s,%s,%s)", (doc_id, i, c, vid))
        col.add(ids=[vid], documents=[c])
    cur.execute("UPDATE discharge_documents SET indexing_status='Indexed' WHERE document_id=%s", (doc_id,))
conn.commit()
print("Indexed", len(chunks), "chunks")
```

Use **synthetic** PDFs only. Chroma's default embedding model is English-oriented and is downloaded on first use (needs internet). For Hindi questions, translate the question to English with the LLM before retrieval, or pick a multilingual embedding model and say so in your limitations.

### 10.3 Grounded answer with refusal (`rag.py`)

```python
from .llm import generate
from .safety import is_dose_change_question, has_emergency_term, EMERGENCY_GUIDANCE

SYSTEM = ("You are a post-discharge assistant. Answer ONLY from the CONTEXT. "
          "If the context does not contain the answer, reply exactly: NOT_IN_DOCUMENTS. "
          "Never diagnose, never advise changing, stopping or doubling any medicine, "
          "and never reassure about symptoms. Reply in the language of the question. Be brief.")

def answer(patient_id, question, lang, col, conn):
    if has_emergency_term(question):
        return EMERGENCY_GUIDANCE[lang], False, []
    if is_dose_change_question(question):
        return ("I cannot advise on changing doses. Please contact your care team. I have asked them to get in touch with you.", False, [])
    res = col.query(query_texts=[question], n_results=3)
    docs, ids = res["documents"][0], res["ids"][0]
    if not docs:
        return ("I could not find this in your discharge documents. I have asked your care team to reply.", False, [])
    out = generate(SYSTEM, "CONTEXT:\n" + "\n---\n".join(docs) + f"\n\nQUESTION: {question}")
    if "NOT_IN_DOCUMENTS" in out:
        return ("I could not find this in your discharge documents. I have asked your care team to reply.", False, [])
    return out, True, ids          # ids -> chat_message_sources via document_chunks.vector_id
```

After answering: insert the patient message and the AI message into `chat_messages` (`is_grounded` TRUE/FALSE), insert source rows by looking up `chunk_id` from `document_chunks.vector_id`, and for every ungrounded answer create a `follow_up_tasks` row so staff really do reply (otherwise "I asked your care team" would be untrue).

### 10.4 Tags and daily draft summary

- **Tags:** after a symptom report is saved, ask the LLM for 1-3 short tags as JSON, validate them (lowercase words, max 40 chars), insert with `extracted_by='LLM'`. If the LLM fails, skip silently; tags are a convenience, not a safety feature.
- **Summary:** build a plain-text fact sheet from `sp_daily_report` output, ask the LLM to rewrite it as a short factual note ("do not add advice, do not interpret"), and store it in `ai_summaries` with `model_name`. It stays unreviewed until a clinician reviews it. Show the label **"AI draft, not reviewed"** on screen.

---

## 11. Frontend plan (keep it small)

| Page | Role | Content | Main API |
|---|---|---|---|
| Login | All | Email + password | `POST /auth/login` |
| Home | Patient | Today's doses (Taken/Skipped), latest readings, device status, follow-up date, emergency banner | `/patient/me/doses`, `/patient/me/status` |
| Check-in | Patient | Text box, pain slider, language, optional mic (browser speech recognition) | `/patient/me/symptoms` |
| Chat | Patient | Messages, citation chips | `/patient/me/chat` |
| Triage | Nurse/Doctor | `v_triage_board` rows, severity colour, reason text, Acknowledge | `/staff/triage`, acknowledge |
| Patient detail | Nurse/Doctor | `v_patient_timeline`, charts, adherence, device status | `/staff/patients/{id}/timeline` |
| Summaries | Doctor | Unreviewed drafts with Mark reviewed | `/staff/summaries/pending` |

Show **the reason** next to every flag, show quality labels on readings, and show "Missing data" (never a blank or a zero). If React is too heavy, plain HTML pages with `fetch()` are completely acceptable for a hackathon.

---

## 12. Day-by-day plan with acceptance checks

| Day | Tasks | Done when |
|---|---|---|
| 1 | M0 database, M1 backend, login for the 3 roles, Swagger works | Login returns a token; Q19 correct |
| 2 | M2 ingestion + simulator; flags visible through `/staff/triage`; ESP32 sends one real reading | Simulator low SpO₂ creates exactly one flag |
| 3 | M3 doses, check-in, emergency path, patient home page | Emergency phrase shows guidance and Urgent flag |
| 4 | M4 scheduler, escalation ladder, acknowledge, triage page | Caregiver step shows `Skipped_No_Consent` for Kabir; acknowledge creates a task |
| 5 | M5 RAG with citations/refusal, tags, summary, Hindi labels, rehearsal | Q12 and Q13 give the expected rows |

**3-day version:** days 1-3 plus the escalation ladder with SMS logging only. Put chat and summaries under "future scope".
**Team of 4:** (1) database + backend rules, (2) device + simulator, (3) frontend, (4) AI layer + demo/report.
**Solo:** simulator first, ESP32 last, skip Twilio until everything else works.

---

## 13. Testing checklist (tick each)

- [ ] Whole SQL script runs without error; Q19 shows 25 / 7 / 8 / 3 / 2.
- [ ] Re-sending the same device reading returns `duplicate_ignored`.
- [ ] A reading of 400 bpm is stored as `Invalid` and creates no flag.
- [ ] One low-SpO₂ reading creates exactly one open flag with the reason text.
- [ ] A second low reading does not create a duplicate while the first flag is open.
- [ ] Stopping the simulator leads to "Missing data" in `v_device_status` and a flag after the rule time.
- [ ] Emergency phrase (English and Hindi) shows guidance and creates an Urgent flag.
- [ ] Kabir's caregiver step is logged `Skipped_No_Consent`; Meera's is `Sent` (or logged).
- [ ] Acknowledging twice returns an error and changes nothing.
- [ ] Patient A cannot fetch patient B's data (try changing ids in the URL).
- [ ] "Can I double my dose?" is refused and creates a staff task.
- [ ] An LLM failure or SMS failure is logged and the system keeps working.

---

## 14. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Procedure/trigger creation fails with a syntax error near `$$` | Ran statements one by one. Run the full script so `DELIMITER` works, or use the `mysql` CLI: `mysql -u root -p < file.sql` |
| `CHECK constraint` ignored or syntax error | MySQL older than 8.0.16. Upgrade |
| `ER_CHECK_CONSTRAINT_CLAUSE_USING_FK_REFERENTIAL_ACTION_COLUMN` | A CHECK uses a column that also has `ON DELETE CASCADE/SET NULL`. Remove one of them |
| `Error 1055 ... ONLY_FULL_GROUP_BY` | Add all non-aggregated selected columns to `GROUP BY` |
| Events never run | `SET GLOBAL event_scheduler = ON;` and `ALTER EVENT ... ENABLE;` |
| Flags at "wrong" times | Time zone mismatch. Use IST everywhere (section 5) |
| Duplicate flags | Rule engine ran while an earlier flag was already Resolved/Dismissed. Expected; the dedupe only covers Open/Acknowledged |
| Device cannot reach the API | Use your laptop's LAN IP, same Wi-Fi, firewall allows port 8000, run `uvicorn app.main:app --host 0.0.0.0` |
| ESP32 timestamp 1970 | NTP not synced yet; the sketch skips sending until time is valid |
| Chroma downloads a model on first run | Normal; needs internet once |
| Hindi retrieval is poor | English-oriented embeddings. Translate the query first or use a multilingual embedding model |

Run the API with: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` (from the `backend` folder).

---

## 15. Security and safety checklist before any demo

- Synthetic data only; remove real names, phone numbers and Wi-Fi passwords from screenshots and repos.
- `.env` and keys never committed; rotate any key that leaks.
- JWT secret is long and random; passwords hashed with bcrypt.
- The API filters every patient request by the id **inside the token**.
- Database account has no DELETE or DDL rights.
- LLM text never creates flags, changes prescriptions or diagnoses.
- Missing/questionable/invalid readings are labelled, never shown as "normal".
- You can state clearly: *prototype, synthetic data, thresholds are demo values, not clinically validated.*

---

## 16. After the hackathon (if you continue)

Per-device hashed keys using `devices.api_key_hash`, staff-to-patient assignment filtering, wound-photo upload for clinician viewing, BLE through the phone, WhatsApp, more languages, usability testing with real clinicians, security and privacy review, and clinical validation before any real-world use.
