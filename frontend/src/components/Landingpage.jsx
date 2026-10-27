import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { seedDemoPatient } from "../services/api";

export default function LandingPage({ onSeedDemo }) {
  const navigate = useNavigate();
  const [loadingDemo, setLoadingDemo] = useState(false);
  const [demoStatus, setDemoStatus] = useState(null);

  const handleQuickLaunchDemo = async () => {
    setLoadingDemo(true);
    setDemoStatus(null);
    try {
      const res = await seedDemoPatient();
      if (res && res.patient_id) {
        setDemoStatus("Patient Eleanor Vance initialized successfully. Redirecting to recovery portal...");
        if (onSeedDemo) onSeedDemo();
        setTimeout(() => {
          navigate("/patient", { state: { patientId: res.patient_id } });
        }, 600);
      }
    } catch (err) {
      setDemoStatus("Note: Using local fallback patient.");
      navigate("/patient");
    } finally {
      setLoadingDemo(false);
    }
  };

  const clinicalPortals = [
    {
      title: "Nurse Station",
      path: "/nurse",
      icon: "local_hospital",
      badge: "Admission & Ingestion",
      badgeColor: "badge-teal",
      headline: "Post-Discharge Patient Admission",
      description: "Upload discharge summary PDFs. Autonomous extraction extracts medication routines, dietary restrictions, warning thresholds, and builds patient-specific vector knowledge bases.",
      features: ["PDF RAG Knowledge Base Ingestion", "Automated Daily Routine Generation", "Twilio Automated SMS Reminders"],
      cta: "Open Nurse Station",
    },
    {
      title: "Doctor Portal",
      path: "/doctor",
      icon: "medical_services",
      badge: "Triage & Telemetry",
      badgeColor: "badge-amber",
      headline: "Physician Clinical Dashboard",
      description: "Real-time alert prioritization engine. Surfaces only actionable escalations (risk score ≥ 40) with patient history, telemetry trends, and ESP32 biometric deviations.",
      features: ["Priority Risk Alert Stream", "ESP32 Pulse & SpO2 Real-Time Graph", "One-Click Resolution & Emergency Escalation"],
      cta: "Launch Doctor Portal",
    },
    {
      title: "Patient Recovery",
      path: "/patient",
      icon: "personal_injury",
      badge: "Autonomous Triage",
      badgeColor: "badge-blue",
      headline: "AI Recovery Companion & Chat",
      description: "24/7 empathetic conversational AI companion grounded in patient discharge instructions. Supports voice triage, wound photo analysis, and daily medication completion.",
      features: ["Multimodal Voice & Text Check-Ins", "Wound Infection Vision Analysis", "Interactive Daily Routine Checklist"],
      cta: "Open Recovery Room",
    },
  ];

  const agentArchitecture = [
    {
      role: "Intake & Knowledge Extraction",
      agent: "Discharge Ingestion Agent",
      tech: "LangChain + Gemini Flash",
      desc: "Parses complex clinical discharge PDFs into structured JSON profiles (medications, timings, emergency contacts, warning signs) and builds ChromaDB vector embeddings.",
    },
    {
      role: "Continuous Biosensing",
      agent: "IoT Telemetry Agent",
      tech: "ESP32 · MAX30102 · WebSockets",
      desc: "Captures photoplethysmogram (PPG) vitals (Heart Rate & Blood Oxygen SpO2) and 3-axis accelerometer fall detection, streaming to live clinical dashboards.",
    },
    {
      role: "Clinical Decision Support",
      agent: "Multimodal Triage Agent",
      tech: "Gemini Vision + Deepgram STT",
      desc: "Evaluates patient symptoms, audio cadence, and wound photos against clinical protocols. Computes a dynamic risk score (0-100) and recommends deterministic actions.",
    },
    {
      role: "Closed-Loop Escalation",
      agent: "Twilio Telephony Dispatcher",
      tech: "Twilio Voice + SMS",
      desc: "Sends scheduled medication prompts and initiates priority emergency physician calls and caregiver SMS notifications when critical thresholds are breached.",
    },
  ];

  return (
    <div className="w-full pb-20">
      {/* ── HERO COMMAND CENTER ── */}
      <section className="relative overflow-hidden border-b border-[var(--border)] bg-[var(--bg-surface)] py-14 px-4 sm:px-8">
        <div className="max-w-7xl mx-auto">
          {/* Status badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-[var(--accent-dim)] border border-[var(--accent)] text-xs font-semibold text-[var(--accent)] mb-6">
            <span className="material-icons-round text-sm">verified_user</span>
            <span>Autonomous Post-Discharge Clinical Triage & Telemetry Platform</span>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 items-center">
            <div className="lg:col-span-7">
              <h1 className="font-display text-3xl sm:text-4xl lg:text-5xl font-black text-[var(--text-1)] tracking-tight leading-[1.15] mb-5">
                Autonomous Clinical Post-Discharge Triage & Patient Monitoring
              </h1>
              <p className="text-base sm:text-lg text-[var(--text-2)] leading-relaxed mb-8 max-w-2xl">
                An open, agentic clinical intelligence system that transforms discharge summaries into personalized recovery roadmaps, tracks real-time wearable telemetry, and delivers closed-loop escalation for post-op safety.
              </p>

              {/* Action buttons */}
              <div className="flex flex-wrap items-center gap-4">
                <button
                  onClick={handleQuickLaunchDemo}
                  disabled={loadingDemo}
                  className="btn-primary text-base py-3 px-6 shadow-lg flex items-center gap-2"
                >
                  <span className="material-icons-round text-xl">play_circle_filled</span>
                  <span>{loadingDemo ? "Loading Patient..." : "1-Click Launch Demo Patient"}</span>
                </button>

                <Link
                  to="/nurse"
                  className="btn-secondary text-base py-3 px-6 flex items-center gap-2"
                >
                  <span className="material-icons-round text-xl">upload_file</span>
                  <span>Admit via Discharge PDF</span>
                </Link>
              </div>

              {demoStatus && (
                <div className="mt-4 p-3 rounded-lg bg-[var(--accent-dim)] border border-[var(--accent)] text-xs font-medium text-[var(--accent)] flex items-center gap-2">
                  <span className="material-icons-round text-sm">check_circle</span>
                  <span>{demoStatus}</span>
                </div>
              )}
            </div>

            {/* Quick System Telemetry Card */}
            <div className="lg:col-span-5">
              <div className="clinical-card p-6 border-2 border-[var(--border)] shadow-xl bg-[var(--bg-elevated)]">
                <div className="flex items-center justify-between pb-4 border-b border-[var(--border)] mb-5">
                  <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-lg bg-[var(--accent-dim)] border border-[var(--accent)] flex items-center justify-center">
                      <span className="material-icons-round text-base" style={{ color: "var(--accent)" }}>
                        sensors
                      </span>
                    </div>
                    <span className="font-display font-bold text-sm text-[var(--text-1)]">
                      System Operational Status
                    </span>
                  </div>
                  <span className="badge-clinical badge-green">LIVE ONLINE</span>
                </div>

                <div className="space-y-3.5">
                  <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)]">
                    <div className="flex items-center gap-2.5">
                      <span className="material-icons-round text-lg text-[var(--accent)]">memory</span>
                      <span className="text-xs font-semibold text-[var(--text-1)]">FastAPI Backend & Agents</span>
                    </div>
                    <span className="text-xs font-mono font-bold text-[var(--green)]">Port 8000 · Healthy</span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)]">
                    <div className="flex items-center gap-2.5">
                      <span className="material-icons-round text-lg text-[var(--blue)]">storage</span>
                      <span className="text-xs font-semibold text-[var(--text-1)]">MongoDB Medical Datastore</span>
                    </div>
                    <span className="text-xs font-mono font-bold text-[var(--green)]">Connected · 27017</span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)]">
                    <div className="flex items-center gap-2.5">
                      <span className="material-icons-round text-lg text-[var(--purple)]">psychology</span>
                      <span className="text-xs font-semibold text-[var(--text-1)]">Gemini Clinical Reasoning</span>
                    </div>
                    <span className="text-xs font-mono font-bold text-[var(--accent)]">Active Model</span>
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--bg-surface)] border border-[var(--border)]">
                    <div className="flex items-center gap-2.5">
                      <span className="material-icons-round text-lg text-[var(--amber)]">watch</span>
                      <span className="text-xs font-semibold text-[var(--text-1)]">ESP32 Wearable Telemetry</span>
                    </div>
                    <span className="text-xs font-mono font-bold text-[var(--text-2)]">WS Ready</span>
                  </div>
                </div>

                <div className="mt-5 pt-4 border-t border-[var(--border)] flex items-center justify-between text-xs text-[var(--text-3)]">
                  <span>Simulated Patient: Eleanor Vance</span>
                  <span className="font-semibold text-[var(--text-1)]">CABG Post-Op Day 4</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CLINICAL PORTALS DIRECT LAUNCHPAD ── */}
      <section className="py-14 px-4 sm:px-8 max-w-7xl mx-auto">
        <div className="mb-10 text-center sm:text-left">
          <div className="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-[var(--accent)] uppercase tracking-wider mb-2">
            <span className="material-icons-round text-sm">hub</span>
            <span>Clinical Workstations</span>
          </div>
          <h2 className="font-display text-2xl sm:text-3xl font-black text-[var(--text-1)]">
            Direct Access to Hospital Portals
          </h2>
          <p className="text-sm sm:text-base text-[var(--text-2)] mt-1.5 max-w-2xl">
            Choose a workstation to review patient status, ingest new records, or interact with recovery agents.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {clinicalPortals.map((portal) => (
            <div
              key={portal.title}
              className="clinical-card p-6 flex flex-col justify-between border-2 border-[var(--border)] hover:border-[var(--accent)] transition-all hover:-translate-y-1"
            >
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div
                    className="w-12 h-12 rounded-xl flex items-center justify-center border"
                    style={{
                      backgroundColor: "var(--accent-dim)",
                      borderColor: "var(--accent)",
                      color: "var(--accent)",
                    }}
                  >
                    <span className="material-icons-round text-2xl">{portal.icon}</span>
                  </div>
                  <span className={`badge-clinical ${portal.badgeColor}`}>
                    {portal.badge}
                  </span>
                </div>

                <h3 className="font-display text-xl font-bold text-[var(--text-1)] mb-1">
                  {portal.title}
                </h3>
                <h4 className="text-xs font-semibold text-[var(--accent)] uppercase tracking-wider mb-3 font-mono">
                  {portal.headline}
                </h4>
                <p className="text-sm text-[var(--text-2)] leading-relaxed mb-5">
                  {portal.description}
                </p>

                <div className="space-y-2 mb-6">
                  {portal.features.map((feat) => (
                    <div key={feat} className="flex items-center gap-2 text-xs font-medium text-[var(--text-1)]">
                      <span className="material-icons-round text-sm text-[var(--green)]">check</span>
                      <span>{feat}</span>
                    </div>
                  ))}
                </div>
              </div>

              <Link
                to={portal.path}
                className="btn-primary w-full text-center text-sm py-2.5 flex items-center justify-center gap-2"
              >
                <span>{portal.cta}</span>
                <span className="material-icons-round text-base">arrow_forward</span>
              </Link>
            </div>
          ))}
        </div>
      </section>

      {/* ── AGENTIC SYSTEM ARCHITECTURE ── */}
      <section className="py-14 px-4 sm:px-8 bg-[var(--bg-elevated)] border-y border-[var(--border)]">
        <div className="max-w-7xl mx-auto">
          <div className="mb-10 text-center sm:text-left">
            <div className="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-[var(--purple)] uppercase tracking-wider mb-2">
              <span className="material-icons-round text-sm">account_tree</span>
              <span>System Pipeline</span>
            </div>
            <h2 className="font-display text-2xl sm:text-3xl font-black text-[var(--text-1)]">
              Autonomous Clinical Agent Architecture
            </h2>
            <p className="text-sm sm:text-base text-[var(--text-2)] mt-1.5 max-w-2xl">
              How our multimodal agents collaborate to prevent hospital readmissions without alert fatigue.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
            {agentArchitecture.map((item, index) => (
              <div
                key={item.agent}
                className="clinical-card p-5 bg-[var(--bg-surface)] border border-[var(--border)] relative flex flex-col justify-between"
              >
                <div>
                  <div className="text-xs font-mono font-bold text-[var(--text-3)] mb-2">
                    PHASE 0{index + 1}
                  </div>
                  <h3 className="font-display font-bold text-base text-[var(--text-1)] mb-1">
                    {item.agent}
                  </h3>
                  <div className="text-xs font-semibold text-[var(--accent)] mb-3">
                    {item.tech}
                  </div>
                  <p className="text-xs text-[var(--text-2)] leading-relaxed">
                    {item.desc}
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-[var(--border)] text-[11px] font-semibold text-[var(--text-3)] uppercase tracking-wider">
                  {item.role}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── QUICK EVALUATION FOOTER BAR ── */}
      <section className="py-10 px-4 sm:px-8 max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
        <div>
          <h4 className="font-display font-bold text-base text-[var(--text-1)]">
            Ready to test live triage and wearable biosensing?
          </h4>
          <p className="text-xs text-[var(--text-2)]">
            Zero setup required. Click the button to inspect Eleanor Vance's care plan, vitals, and physician alert queue.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={handleQuickLaunchDemo}
            disabled={loadingDemo}
            className="btn-primary text-sm py-2 px-4 flex items-center gap-1.5"
          >
            <span className="material-icons-round text-base">bolt</span>
            <span>{loadingDemo ? 'Loading...' : 'Launch Eleanor Vance'}</span>
          </button>
          <Link to="/doctor" className="btn-secondary text-sm py-2 px-4">
            View Alerts
          </Link>
        </div>
      </section>
    </div>
  );
}