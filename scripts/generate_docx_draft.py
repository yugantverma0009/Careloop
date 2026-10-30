"""
CareLoop Initial Project Draft DOCX Generator
Generates a simplified, professional academic project proposal in Word (.docx) format.
"""
import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_shading(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_padding(cell, top=120, bottom=120, left=180, right=180):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def create_draft_docx(output_path):
    doc = Document()

    # Page Margins (1 inch all around)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    PRIMARY_COLOR = RGBColor(15, 118, 110)    # Deep Teal (#0F766E)
    DARK_TEXT = RGBColor(30, 41, 59)          # Slate-800 (#1E293B)
    MUTED_TEXT = RGBColor(100, 116, 139)      # Slate-500 (#64748B)

    # Base Styles
    normal_style = doc.styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = DARK_TEXT

    # Document Header / Badge
    p_badge = doc.add_paragraph()
    p_badge.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_badge = p_badge.add_run("PROJECT PROPOSAL & INITIAL TECHNICAL DRAFT")
    run_badge.font.size = Pt(10)
    run_badge.font.bold = True
    run_badge.font.color.rgb = PRIMARY_COLOR

    # Main Title
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_title = p_title.add_run("CareLoop: Post-Discharge Patient Triage & Wearable Telemetry System")
    run_title.font.size = Pt(20)
    run_title.font.bold = True
    run_title.font.color.rgb = PRIMARY_COLOR

    # Subtitle
    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_sub = p_sub.add_run("IoT Wearable Vitals Monitoring • Rule-Based Clinical Safety • Grounded AI Recovery Assistant")
    run_sub.font.size = Pt(11)
    run_sub.font.italic = True
    run_sub.font.color.rgb = MUTED_TEXT

    doc.add_paragraph().paragraph_format.space_after = Pt(12)

    def add_section_heading(num_str, title_str):
        h = doc.add_paragraph()
        h.paragraph_format.space_before = Pt(16)
        h.paragraph_format.space_after = Pt(6)
        run_num = h.add_run(f"{num_str}. ")
        run_num.font.bold = True
        run_num.font.size = Pt(14)
        run_num.font.color.rgb = PRIMARY_COLOR

        run_txt = h.add_run(title_str)
        run_txt.font.bold = True
        run_txt.font.size = Pt(14)
        run_txt.font.color.rgb = PRIMARY_COLOR
        return h

    # -------------------------------------------------------------
    # 1. GROUP MEMBERS' NAMES
    # -------------------------------------------------------------
    add_section_heading("1", "Group Members' Names")

    t1 = doc.add_table(rows=5, cols=4)
    t1.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers1 = ["S.No.", "Student Name", "Roll Number / ID", "Project Role"]
    col_widths1 = [Inches(0.6), Inches(2.2), Inches(1.8), Inches(2.4)]

    for c_idx, h_text in enumerate(headers1):
        cell = t1.cell(0, c_idx)
        cell.width = col_widths1[c_idx]
        set_cell_shading(cell, "0F766E")
        set_cell_padding(cell, 140, 140, 140, 140)
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h_text)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(10)

    rows1_data = [
        ("1", "Yugant Verma (Lead)", "[Insert Roll No.]", "IoT Telemetry, Backend API & RAG Pipeline"),
        ("2", "[Member 2 Name]", "[Insert Roll No.]", "Frontend Development & Patient Portal UI"),
        ("3", "[Member 3 Name]", "[Insert Roll No.]", "MySQL Database Design & Clinical Rule Engine"),
        ("4", "[Member 4 Name]", "[Insert Roll No.]", "Hardware Assembly, Sensor Testing & Documentation")
    ]

    for r_idx, row_vals in enumerate(rows1_data, start=1):
        bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_vals):
            cell = t1.cell(r_idx, c_idx)
            cell.width = col_widths1[c_idx]
            set_cell_shading(cell, bg)
            set_cell_padding(cell, 100, 100, 140, 140)
            p = cell.paragraphs[0]
            if c_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(val)
            r.font.size = Pt(10)
            if c_idx == 1 and "Yugant" in val:
                r.font.bold = True

    p_meta = doc.add_paragraph()
    p_meta.paragraph_format.space_before = Pt(8)
    p_meta.paragraph_format.space_after = Pt(12)
    r_guide = p_meta.add_run("Project Guide / Supervisor: ")
    r_guide.font.bold = True
    p_meta.add_run("[Insert Guide / Professor Name]\n")
    r_dept = p_meta.add_run("Department & Institution: ")
    r_dept.font.bold = True
    p_meta.add_run("Computer Science & Engineering, [Insert College/University Name]")

    # -------------------------------------------------------------
    # 2. PROJECT TITLE
    # -------------------------------------------------------------
    add_section_heading("2", "Project Title")

    p2 = doc.add_paragraph()
    p2.paragraph_format.space_after = Pt(8)
    r2_title = p2.add_run("CareLoop: An Agentic Post-Discharge Patient Triage, Wearable Telemetry & Grounded AI Assistant System")
    r2_title.font.bold = True
    r2_title.font.size = Pt(12)

    p2_desc = doc.add_paragraph(
        "A safety-first healthcare platform engineered to protect recovering patients in the vulnerable days "
        "following hospital discharge. The system pairs wearable physiological telemetry with doctor-approved "
        "rules and verified AI-powered discharge instruction retrieval."
    )
    p2_desc.paragraph_format.space_after = Pt(8)

    p2_quote = doc.add_paragraph()
    p2_quote.paragraph_format.left_indent = Inches(0.4)
    r_q = p2_quote.add_run("Core Design Principle: \"The LLM talks. Rules decide. Humans act.\"\n")
    r_q.font.bold = True
    r_q.font.color.rgb = PRIMARY_COLOR
    p2_quote.add_run(
        "Artificial Intelligence never diagnoses or alters prescriptions. Deterministic clinician-approved "
        "rules flag health risks, while verified humans (nurses and doctors) make medical decisions."
    )

    # -------------------------------------------------------------
    # 3. AIM AND OBJECTIVES OF THE PROJECT
    # -------------------------------------------------------------
    add_section_heading("3", "Aim and Objectives")

    p3_aim = doc.add_paragraph()
    r3_aim = p3_aim.add_run("Aim: ")
    r3_aim.font.bold = True
    p3_aim.add_run(
        "To significantly reduce post-operative complications and hospital readmissions by providing recovering "
        "patients with continuous IoT biometric monitoring, automated clinical escalation, and reliable, "
        "document-grounded answers to their recovery questions."
    )
    p3_aim.paragraph_format.space_after = Pt(8)

    doc.add_paragraph("Key Objectives:").runs[0].font.bold = True

    objectives = [
        ("Real-time Biometric Tracking (IoT)", "Continuously measure heart rate and blood oxygen levels via a lightweight wearable watch and transmit them securely over Wi-Fi."),
        ("Deterministic Clinical Safety Engine", "Automatically evaluate live telemetry and medication logs against doctor-set thresholds using MySQL database triggers, raising instant alerts for severe heart rate abnormalities."),
        ("Document-Grounded RAG Assistant", "Provide patients with a bilingual (English & Hindi) conversational assistant that answers recovery questions strictly from their hospital discharge papers, complete with verifiable page citations."),
        ("4-Tier Escalation Ladder", "Automatically notify Patient -> Family Caregiver -> Primary Nurse -> Doctor when critical alerts or unconfirmed high-risk medications are detected."),
        ("Dual-Role Web Portals", "Deliver an easy-to-use Patient Recovery Portal (medications, schedule, calendar sync) and a streamlined Clinical Triage Dashboard for hospital doctors and nurses.")
    ]

    for title, desc in objectives:
        p_obj = doc.add_paragraph(style='List Bullet')
        p_obj.paragraph_format.space_after = Pt(4)
        r_t = p_obj.add_run(f"{title}: ")
        r_t.font.bold = True
        p_obj.add_run(desc)

    # -------------------------------------------------------------
    # 4. PROPOSED FRONT-END DESIGN AND DASHBOARD (LAYOUT)
    # -------------------------------------------------------------
    add_section_heading("4", "Proposed Front-End Design and Dashboard Layout")

    doc.add_paragraph(
        "The web interface is split into two responsive, role-tailored dashboards to keep clinical data "
        "and patient recovery tasks cleanly separated:"
    )

    p_p_title = doc.add_paragraph()
    r_pt = p_p_title.add_run("A. Patient Recovery Portal (/patient)")
    r_pt.font.bold = True
    r_pt.font.color.rgb = PRIMARY_COLOR

    p_p_pts = [
        "Header Bar: Displays patient name, recovery day count, bilingual switch (English / Hindi), gentle audio chime notifications, and dark/light theme toggle.",
        "Today's Vitals Cards: Real-time heart rate and oxygen level cards linked directly to the ESP32 watch, showing sync status and health indicators.",
        "Medication Schedule: Chronological daily schedule with 1-click confirmation chips ('Confirm Taken' or 'Skip with Note').",
        "Appointments & Calendar Sync: Displays next hospital follow-up visits with a direct 'Add to Google Calendar' link and downloadable .ics calendar files.",
        "Discharge Paper Q&A (RAG): Clean chat interface allowing patients to ask questions about diet, activity, wound care, or medications with clickable source citations."
    ]
    for pt in p_p_pts:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        p.add_run(pt)

    p_s_title = doc.add_paragraph()
    p_s_title.paragraph_format.space_before = Pt(6)
    r_st = p_s_title.add_run("B. Clinical Care Team Dashboard (/staff)")
    r_st.font.bold = True
    r_st.font.color.rgb = PRIMARY_COLOR

    p_s_pts = [
        "Prioritised Triage Queue: Patients ranked automatically by a clinical risk score (0-100) based on abnormal vitals, missed doses, and active flags.",
        "Patient Dossier & Telemetry Graphs: Visual 24-hour vital trends, active clinical rule breaches, and recent medication adherence history.",
        "Clinical Task Queue: Actionable checklist for attending nurses (e.g. 'Review Tachycardia Alert', 'Confirm Medication Refill').",
        "Automated Shift Handoff Tool: One-click generator creating structured SBAR (Situation, Background, Assessment, Recommendation) handover notes."
    ]
    for pt in p_s_pts:
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_after = Pt(3)
        p.add_run(pt)

    # -------------------------------------------------------------
    # 5. FRONT-END TOOLS AND TECHNOLOGIES
    # -------------------------------------------------------------
    add_section_heading("5", "Front-End Tools and Technologies")

    t5 = doc.add_table(rows=6, cols=3)
    t5.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers5 = ["Technology", "Version / Spec", "Usage & Role in Project"]
    col_widths5 = [Inches(1.8), Inches(1.5), Inches(3.7)]

    for c_idx, h_text in enumerate(headers5):
        cell = t5.cell(0, c_idx)
        cell.width = col_widths5[c_idx]
        set_cell_shading(cell, "0F766E")
        set_cell_padding(cell, 120, 120, 140, 140)
        p = cell.paragraphs[0]
        r = p.add_run(h_text)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(10)

    rows5_data = [
        ("React.js", "v18.2+", "Component-based Single Page Application (SPA) framework for dynamic state."),
        ("JavaScript (ES6+) & JSX", "Modern Standard", "Core client logic, asynchronous REST API calls, and component templating."),
        ("Vanilla CSS3 & Design System", "Custom CSS Variables", "Hand-crafted clinical styling, responsive CSS Grid / Flexbox, dark/light themes."),
        ("Lucide React", "Latest", "Clean, lightweight medical and operational icons (Heart, Activity, Calendar, Shield)."),
        ("HTML5 Web Audio API", "Browser Native", "Gentle auditory chimes for dose confirmations and emergency alerts.")
    ]

    for r_idx, row_vals in enumerate(rows5_data, start=1):
        bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_vals):
            cell = t5.cell(r_idx, c_idx)
            cell.width = col_widths5[c_idx]
            set_cell_shading(cell, bg)
            set_cell_padding(cell, 90, 90, 120, 120)
            p = cell.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(9.5)
            if c_idx == 0:
                r.font.bold = True

    # -------------------------------------------------------------
    # 6. BACK-END TOOLS AND TECHNOLOGIES
    # -------------------------------------------------------------
    add_section_heading("6", "Back-End Tools and Technologies")

    t6 = doc.add_table(rows=7, cols=3)
    t6.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers6 = ["Technology", "Version / Spec", "Usage & Role in Project"]
    col_widths6 = [Inches(1.8), Inches(1.5), Inches(3.7)]

    for c_idx, h_text in enumerate(headers6):
        cell = t6.cell(0, c_idx)
        cell.width = col_widths6[c_idx]
        set_cell_shading(cell, "0F766E")
        set_cell_padding(cell, 120, 120, 140, 140)
        p = cell.paragraphs[0]
        r = p.add_run(h_text)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(10)

    rows6_data = [
        ("Python", "v3.12+", "High-performance server runtime for asynchronous backend logic and AI pipelines."),
        ("FastAPI", "v0.115+", "ASGI REST API framework with native Pydantic validation and automatic OpenAPI docs."),
        ("Uvicorn", "Latest", "Lightning-fast ASGI web server handling HTTP requests and concurrent connections."),
        ("MySQL Database", "v8.0.16+ (InnoDB)", "Authoritative storage: 25 relational tables, 7 views, 8 stored procedures, 3 triggers."),
        ("ChromaDB", "v0.5+", "Local vector database storing dense embeddings of hospital discharge documents."),
        ("Google Gemini API", "gemini-3.5-flash-lite", "Large Language Model used strictly for contextual text synthesis and Hindi phrasing.")
    ]

    for r_idx, row_vals in enumerate(rows6_data, start=1):
        bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_vals):
            cell = t6.cell(r_idx, c_idx)
            cell.width = col_widths6[c_idx]
            set_cell_shading(cell, bg)
            set_cell_padding(cell, 90, 90, 120, 120)
            p = cell.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(9.5)
            if c_idx == 0:
                r.font.bold = True

    # -------------------------------------------------------------
    # 7. FRONT-END AND BACK-END CONNECTIVITY
    # -------------------------------------------------------------
    add_section_heading("7", "Front-End and Back-End Connectivity")

    doc.add_paragraph(
        "Communication between the React client, FastAPI server, and IoT devices is structured "
        "around lightweight, secure, and industry-standard protocols:"
    )

    conn_items = [
        ("RESTful JSON API", "All client actions (fetching vitals, confirming doses, submitting check-ins) use standard HTTP GET, POST, and PUT requests with structured JSON payloads."),
        ("Dynamic API Endpoint Resolution", "The frontend automatically binds to window.location.hostname:8000, ensuring flawless communication whether running on localhost, mobile emulators, or local network hospital devices."),
        ("JWT Authentication (HS256)", "Secure token-based login with 8-hour sessions and strict Role-Based Access Control (Patient, Caregiver, Doctor, Nurse) to prevent unauthorized patient data access."),
        ("FastAPI CORS Middleware", "Permits secure cross-origin requests while restricting origins and validating authorized headers."),
        ("Google Calendar & .ics Engine", "Connects appointment schedules directly with external calendars via Google Calendar Web URLs and standardized .ics calendar files."),
        ("IoT Device Header Authentication", "Wearable watches authenticate via a pre-shared X-Device-Key HTTP header, preventing spoofed sensor telemetry.")
    ]

    for tech, desc in conn_items:
        p_c = doc.add_paragraph(style='List Bullet')
        p_c.paragraph_format.space_after = Pt(4)
        r_ct = p_c.add_run(f"{tech}: ")
        r_ct.font.bold = True
        p_c.add_run(desc)

    # -------------------------------------------------------------
    # 8. IOT DEVICES USED AS INPUT SOURCES
    # -------------------------------------------------------------
    add_section_heading("8", "IoT Devices Used as Input Sources")

    doc.add_paragraph(
        "The CareLoop physical layer consists of a dedicated wearable smartwatch prototype developed "
        "and programmed specifically for real-time post-discharge recovery monitoring:"
    )

    t8 = doc.add_table(rows=6, cols=3)
    t8.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers8 = ["Hardware Module", "Model / Spec", "Clinical Function & Pin Connection"]
    col_widths8 = [Inches(1.8), Inches(1.6), Inches(3.6)]

    for c_idx, h_text in enumerate(headers8):
        cell = t8.cell(0, c_idx)
        cell.width = col_widths8[c_idx]
        set_cell_shading(cell, "0F766E")
        set_cell_padding(cell, 120, 120, 140, 140)
        p = cell.paragraphs[0]
        r = p.add_run(h_text)
        r.font.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)
        r.font.size = Pt(10)

    rows8_data = [
        ("Microcontroller", "ESP32 DevKit V1 (30-pin)", "32-bit dual-core MCU with built-in Wi-Fi. Ingests raw PPG sensor data and handles NTP time sync."),
        ("Pulse & SpO2 Sensor", "MAX30102 / MAX30100", "Optical PPG sensor with Red & IR LEDs. Connected via I2C bus (SDA: GPIO 21, SCL: GPIO 22)."),
        ("On-Board Display", "0.96\" OLED (SSD1306)", "128x64 display showing 'AI NURSE WATCH', live BPM, and contact status. Shares I2C bus (0x3C)."),
        ("Watch Chassis & Strap", "20mm Silicone Strap", "Comfortable wrist strap with insulated backing plate securing sensors against the wrist."),
        ("Power Source", "Micro-USB / 3.7V LiPo", "Powers the device continuously (5V USB or 3.7V 500mAh LiPo with TP4056 charging board).")
    ]

    for r_idx, row_vals in enumerate(rows8_data, start=1):
        bg = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
        for c_idx, val in enumerate(row_vals):
            cell = t8.cell(r_idx, c_idx)
            cell.width = col_widths8[c_idx]
            set_cell_shading(cell, bg)
            set_cell_padding(cell, 90, 90, 120, 120)
            p = cell.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(9.5)
            if c_idx == 0:
                r.font.bold = True

    # Embed watch image if available
    watch_img_path = "/Users/yugantverma/.gemini/antigravity-ide/brain/ddde650f-ad3c-45eb-b3d6-95fc995a205d/.user_uploaded/media_1793266715269.jpg"
    if os.path.exists(watch_img_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(12)
        p_img.paragraph_format.space_after = Pt(4)
        run_img = p_img.add_run()
        run_img.add_picture(watch_img_path, width=Inches(3.8))

        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_after = Pt(12)
        r_cap = p_cap.add_run("Figure 1: CareLoop Physical IoT Wearable Telemetry Watch Prototype (ESP32 + MAX30102 + OLED)")
        r_cap.font.italic = True
        r_cap.font.size = Pt(9.5)
        r_cap.font.color.rgb = MUTED_TEXT

    p_flow = doc.add_paragraph()
    r_flow = p_flow.add_run("IoT Telemetry Data Flow:\n")
    r_flow.font.bold = True
    p_flow.add_run(
        "1. MAX30102 measures blood volume pulses at the patient's wrist.\n"
        "2. ESP32 checks contact quality: if finger/wrist contact is verified (ir > 50000), it computes rolling BPM and displays 'OK' on the OLED screen.\n"
        "3. Every 60 seconds, the ESP32 issues an authenticated HTTP POST with JSON payload to /device/readings on the FastAPI server.\n"
        "4. MySQL triggers instantly evaluate the BPM against doctor-approved thresholds (e.g., Tachycardia > 110 BPM), immediately raising alerts on the hospital dashboard."
    )

    doc.save(output_path)
    print(f"✅ Generated DOCX file successfully at: {output_path}")

if __name__ == "__main__":
    out_file = "/Users/yugantverma/Desktop/CareLoop/CareLoop_Initial_Project_Draft.docx"
    create_draft_docx(out_file)
