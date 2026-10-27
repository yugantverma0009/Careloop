import React, { useState, useEffect, useRef } from 'react';
import {
  getMyStatus,
  getMyDoses,
  confirmMyDose,
  submitSymptomCheckin,
  sendChatMessage,
  getChatHistory,
  logout,
} from '../services/api';
import SwitchDemoWorkspace from './SwitchDemoWorkspace';

export default function CareLoopPatientPortal({ user }) {
  const [lang, setLang] = useState('en');
  const [loading, setLoading] = useState(true);
  const [statusData, setStatusData] = useState(null);
  const [doses, setDoses] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Symptom check-in state
  const [symptomText, setSymptomText] = useState('');
  const [painLevel, setPainLevel] = useState(2);
  const [symptomGuidance, setSymptomGuidance] = useState(null);
  const [symptomSuccess, setSymptomSuccess] = useState('');

  const chatEndRef = useRef(null);

  const loadAll = async () => {
    try {
      setLoading(true);
      const [st, ds, ch] = await Promise.all([
        getMyStatus().catch(() => null),
        getMyDoses().catch(() => []),
        getChatHistory().catch(() => []),
      ]);
      setStatusData(st);
      setDoses(ds || []);
      setChatMessages(ch || []);
    } catch (err) {
      console.error('Error loading patient data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, 10000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const handleConfirmDose = async (logId, status) => {
    try {
      await confirmMyDose(logId, status);
      await loadAll();
    } catch (err) {
      alert(`Error updating dose: ${err.message}`);
    }
  };

  const handleSubmitSymptom = async (e) => {
    e.preventDefault();
    setSymptomGuidance(null);
    setSymptomSuccess('');
    try {
      const res = await submitSymptomCheckin(symptomText, painLevel, 'Text', lang);
      if (res.emergency && res.guidance) {
        setSymptomGuidance(res.guidance);
      } else {
        setSymptomSuccess(lang === 'hi' ? 'लक्षण सफलतापूर्वक दर्ज कर दिए गए हैं।' : 'Symptoms recorded successfully.');
      }
      setSymptomText('');
      await loadAll();
    } catch (err) {
      alert(`Error submitting symptoms: ${err.message}`);
    }
  };

  const handleSendChat = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;
    const msg = chatInput.trim();
    setChatInput('');
    setChatLoading(true);

    // Optimistic patient message
    const tempMsg = {
      message_id: Date.now(),
      sender: 'Patient',
      message_text: msg,
      created_at: new Date().toISOString(),
    };
    setChatMessages((prev) => [...prev, tempMsg]);

    try {
      const res = await sendChatMessage(msg, lang);
      const aiMsg = {
        message_id: Date.now() + 1,
        sender: 'AI_Nurse',
        message_text: res.response,
        is_grounded: res.is_grounded,
        citations: res.citations,
        created_at: new Date().toISOString(),
      };
      setChatMessages((prev) => [...prev, aiMsg]);
    } catch (err) {
      alert(`Chat error: ${err.message}`);
    } finally {
      setChatLoading(false);
    }
  };

  const t = {
    en: {
      appName: 'CareLoop Patient Recovery',
      welcome: 'Welcome,',
      logout: 'Sign Out',
      emergencyAlert: 'Active Emergency Alert',
      emergencyAdvice: 'Your clinical team has flagged an urgent review. If experiencing severe symptoms, please dial 112 immediately.',
      medications: "Today's Prescribed Medications",
      noMeds: 'No medications scheduled for today.',
      taken: 'Confirm Taken',
      skip: 'Skip Dose',
      vitals: 'Latest Physiological Telemetry',
      deviceStatus: 'Device Connectivity',
      connected: 'Connected & Syncing',
      missingData: 'Missing data (Offline)',
      nextAppt: 'Next Clinical Follow-up',
      noAppt: 'No upcoming appointments scheduled.',
      checkin: 'Daily Health & Symptom Check-in',
      painSlider: 'Pain Intensity Score (0 to 10):',
      describeSymptoms: 'Describe any symptoms or feelings...',
      submitCheckin: 'Submit Check-in',
      dischargeAssistant: 'Discharge Plan AI Assistant',
      chatPlaceholder: 'Ask about your medicines, instructions, or follow-up...',
      send: 'Send',
      groundedBadge: 'Grounded in Discharge Plan',
      forwardedBadge: 'Forwarded to Care Team',
    },
    hi: {
      appName: 'केयरलूप रिकवरी पोर्टल',
      welcome: 'नमस्ते,',
      logout: 'लॉग आउट',
      emergencyAlert: 'आपातकालीन सूचना',
      emergencyAdvice: 'आपकी क्लीनिकल टीम ने तत्काल समीक्षा का अलर्ट दिया है। यदि गंभीर लक्षण हों, तो कृपया तुरंत 112 पर कॉल करें।',
      medications: 'आज की निर्धारित दवाइयां',
      noMeds: 'आज के लिए कोई दवा निर्धारित नहीं है।',
      taken: 'दवा ले ली',
      skip: 'दवा छोड़ी',
      vitals: 'नवीनतम शारीरिक रीडिंग',
      deviceStatus: 'डिवाइस कनेक्टिविटी',
      connected: 'कनेक्टेड और सक्रिय',
      missingData: 'डेटा अनुपलब्ध (ऑफलाइन)',
      nextAppt: 'अगली डॉक्टर मुलाकात',
      noAppt: 'कोई आगामी अपॉइंटमेंट निर्धारित नहीं है।',
      checkin: 'दैनिक स्वास्थ्य और लक्षण रिपोर्ट',
      painSlider: 'दर्द का स्तर (0 से 10):',
      describeSymptoms: 'अपने लक्षण या स्वास्थ्य स्थिति बताएं...',
      submitCheckin: 'रिपोर्ट दर्ज करें',
      dischargeAssistant: 'डिस्चार्ज योजना AI सहायक',
      chatPlaceholder: 'अपनी दवा, निर्देशों या फॉलो-अप के बारे में पूछें...',
      send: 'भेजें',
      groundedBadge: 'डिस्चार्ज सारांश से प्रमाणित',
      forwardedBadge: 'केयर टीम को भेजा गया',
    },
  }[lang];

  const hasUrgentFlag = statusData?.active_flags?.some((f) => f.severity === 'Urgent_Review');

  return (
    <div style={{
      minHeight: '100vh',
      background: '#0b132b',
      color: '#f8fafc',
      fontFamily: "'Inter', sans-serif",
      paddingBottom: '40px',
    }}>
      {/* Top Navbar */}
      <header style={{
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid #1e293b',
        padding: '16px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <img
            src="/careloop_logo.jpg"
            alt="CareLoop"
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              objectFit: 'cover',
              boxShadow: '0 4px 14px rgba(14, 165, 233, 0.35)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
            }}
          />
          <div>
            <div style={{ fontWeight: 800, fontSize: '18px', color: '#f8fafc', letterSpacing: '-0.02em' }}>
              Care<span style={{ color: '#2dd4bf' }}>Loop</span>
            </div>
            <div style={{ fontSize: '11px', color: '#94a3b8' }}>{t.appName}</div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Language Switcher */}
          <div style={{
            background: '#1e293b',
            borderRadius: '8px',
            padding: '3px',
            display: 'flex',
            border: '1px solid #334155',
          }}>
            <button
              onClick={() => setLang('en')}
              style={{
                padding: '5px 10px',
                borderRadius: '6px',
                border: 'none',
                background: lang === 'en' ? '#0d9488' : 'transparent',
                color: '#fff',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              English
            </button>
            <button
              onClick={() => setLang('hi')}
              style={{
                padding: '5px 10px',
                borderRadius: '6px',
                border: 'none',
                background: lang === 'hi' ? '#0d9488' : 'transparent',
                color: '#fff',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              हिंदी
            </button>
          </div>

          {/* Switch Demo Workspace Component */}
          <SwitchDemoWorkspace currentUser={user} />

          <button
            onClick={logout}
            title={t.logout}
            style={{
              padding: '7px 12px',
              borderRadius: '8px',
              border: '1px solid #475569',
              background: '#1e293b',
              color: '#94a3b8',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
          >
            <span>🚪</span> {t.logout}
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main style={{ maxWidth: '1200px', margin: '24px auto', padding: '0 20px' }}>
        {loading && !statusData && (
          <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8', fontSize: '13px' }}>
            Syncing telemetry and medications...
          </div>
        )}

        {/* Emergency Alert Banner */}
        {(hasUrgentFlag || symptomGuidance) && (
          <div style={{
            background: 'linear-gradient(135deg, rgba(239, 68, 68, 0.25), rgba(185, 28, 28, 0.35))',
            border: '2px solid #ef4444',
            borderRadius: '14px',
            padding: '18px 22px',
            marginBottom: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '16px',
            boxShadow: '0 10px 25px rgba(239, 68, 68, 0.2)',
          }}>
            <div style={{ fontSize: '32px' }}>🚨</div>
            <div>
              <h3 style={{ margin: '0 0 4px 0', fontSize: '16px', fontWeight: 800, color: '#fca5a5' }}>
                {t.emergencyAlert}
              </h3>
              <p style={{ margin: 0, fontSize: '14px', color: '#fee2e2' }}>
                {symptomGuidance || t.emergencyAdvice}
              </p>
            </div>
          </div>
        )}

        {/* Dashboard Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))', gap: '24px' }}>
          {/* Left Column: Medications & Vitals */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
            {/* Medications Card */}
            <div style={{
              background: '#1e293b',
              borderRadius: '16px',
              padding: '22px',
              border: '1px solid #334155',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                <h2 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: '#f8fafc' }}>
                  💊 {t.medications}
                </h2>
                <span style={{ fontSize: '11px', background: '#0f172a', padding: '4px 8px', borderRadius: '6px', color: '#94a3b8' }}>
                  {doses.length} scheduled
                </span>
              </div>

              {doses.length === 0 ? (
                <div style={{ color: '#94a3b8', fontSize: '13px', padding: '16px 0' }}>{t.noMeds}</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {doses.map((d) => (
                    <div
                      key={d.medication_log_id}
                      style={{
                        background: '#0f172a',
                        border: '1px solid #334155',
                        borderRadius: '12px',
                        padding: '14px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '14px', color: '#f1f5f9' }}>
                          {d.medicine_name} <span style={{ color: '#38bdf8', fontSize: '12px' }}>({d.dosage})</span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                          Scheduled: {d.scheduled_for?.slice(11, 16) || 'Today'} • {d.instructions || 'With water'}
                        </div>
                        <div style={{ marginTop: '4px' }}>
                          <span style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '2px 8px',
                            borderRadius: '4px',
                            background: d.status === 'Taken_Confirmed' ? '#065f46' : d.status === 'Skipped' ? '#991b1b' : '#374151',
                            color: d.status === 'Taken_Confirmed' ? '#34d399' : d.status === 'Skipped' ? '#f87171' : '#d1d5db',
                          }}>
                            {d.status}
                          </span>
                        </div>
                      </div>

                      {d.status === 'Unconfirmed' && (
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            onClick={() => handleConfirmDose(d.medication_log_id, 'Taken_Confirmed')}
                            style={{
                              padding: '8px 12px',
                              borderRadius: '8px',
                              border: 'none',
                              background: '#0d9488',
                              color: '#fff',
                              fontSize: '12px',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            ✓ {t.taken}
                          </button>
                          <button
                            onClick={() => handleConfirmDose(d.medication_log_id, 'Skipped')}
                            style={{
                              padding: '8px 12px',
                              borderRadius: '8px',
                              border: '1px solid #475569',
                              background: '#1e293b',
                              color: '#cbd5e1',
                              fontSize: '12px',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            {t.skip}
                          </button>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Vitals & Connectivity */}
            <div style={{
              background: '#1e293b',
              borderRadius: '16px',
              padding: '22px',
              border: '1px solid #334155',
            }}>
              <h2 style={{ fontSize: '17px', fontWeight: 700, margin: '0 0 16px 0', color: '#f8fafc' }}>
                📊 {t.vitals}
              </h2>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '18px' }}>
                {statusData?.latest_readings?.length > 0 ? (
                  statusData.latest_readings.map((r, i) => (
                    <div
                      key={i}
                      style={{
                        background: '#0f172a',
                        border: '1px solid #334155',
                        borderRadius: '12px',
                        padding: '14px',
                      }}
                    >
                      <div style={{ fontSize: '12px', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        {r.measurement_type}
                      </div>
                      <div style={{ fontSize: '24px', fontWeight: 800, color: '#f8fafc', margin: '4px 0' }}>
                        {r.measurement_value}{' '}
                        <span style={{ fontSize: '13px', fontWeight: 500, color: '#94a3b8' }}>{r.unit}</span>
                      </div>
                      <span style={{
                        fontSize: '10px',
                        padding: '2px 6px',
                        borderRadius: '4px',
                        fontWeight: 700,
                        background: r.quality_status === 'Good' ? '#065f46' : r.quality_status === 'Simulated' ? '#1e3a8a' : '#7f1d1d',
                        color: r.quality_status === 'Good' ? '#34d399' : r.quality_status === 'Simulated' ? '#93c5fd' : '#fca5a5',
                      }}>
                        {r.quality_status}
                      </span>
                    </div>
                  ))
                ) : (
                  <div style={{ gridColumn: 'span 2', color: '#f59e0b', fontSize: '13px', background: '#0f172a', padding: '14px', borderRadius: '8px' }}>
                    ⚠️ {t.missingData}
                  </div>
                )}
              </div>

              {/* Device Status */}
              <div style={{ background: '#0f172a', borderRadius: '10px', padding: '12px 14px', border: '1px solid #334155' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                  {t.deviceStatus}
                </div>
                {statusData?.devices?.length > 0 ? (
                  statusData.devices.map((d, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '13px' }}>
                      <span>{d.device_type} ({d.device_id})</span>
                      <span style={{
                        color: d.connectivity_status === 'Connected' ? '#34d399' : '#f87171',
                        fontWeight: 700,
                        fontSize: '12px',
                      }}>
                        {d.connectivity_status === 'Connected' ? `● ${t.connected}` : `○ ${t.missingData}`}
                      </span>
                    </div>
                  ))
                ) : (
                  <div style={{ color: '#f87171', fontSize: '12px', fontWeight: 600 }}>
                    ○ {t.missingData}
                  </div>
                )}
              </div>

              {/* Next Appointment */}
              <div style={{ marginTop: '14px', background: '#0f172a', borderRadius: '10px', padding: '12px 14px', border: '1px solid #334155' }}>
                <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                  🗓️ {t.nextAppt}
                </div>
                {statusData?.next_appointment ? (
                  <div style={{ fontSize: '13px', color: '#f1f5f9' }}>
                    <strong>{statusData.next_appointment.doctor_name}</strong> •{' '}
                    {new Date(statusData.next_appointment.appointment_date).toLocaleDateString()}
                  </div>
                ) : (
                  <div style={{ fontSize: '12px', color: '#64748b' }}>{t.noAppt}</div>
                )}
              </div>
            </div>

            {/* Daily Symptom Check-in */}
            <div style={{
              background: '#1e293b',
              borderRadius: '16px',
              padding: '22px',
              border: '1px solid #334155',
            }}>
              <h2 style={{ fontSize: '17px', fontWeight: 700, margin: '0 0 16px 0', color: '#f8fafc' }}>
                📝 {t.checkin}
              </h2>

              {symptomSuccess && (
                <div style={{ background: '#065f46', color: '#34d399', padding: '10px 14px', borderRadius: '8px', fontSize: '13px', marginBottom: '14px' }}>
                  ✓ {symptomSuccess}
                </div>
              )}

              <form onSubmit={handleSubmitSymptom}>
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '13px', color: '#cbd5e1', marginBottom: '8px' }}>
                    {t.painSlider} <strong style={{ color: painLevel >= 7 ? '#f87171' : '#38bdf8', fontSize: '15px' }}>{painLevel} / 10</strong>
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    value={painLevel}
                    onChange={(e) => setPainLevel(e.target.value)}
                    style={{ width: '100%', accentColor: painLevel >= 7 ? '#ef4444' : '#0d9488' }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                    <span>0 (No Pain)</span>
                    <span>5 (Moderate)</span>
                    <span>10 (Severe)</span>
                  </div>
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <textarea
                    rows="3"
                    value={symptomText}
                    onChange={(e) => setSymptomText(e.target.value)}
                    placeholder={t.describeSymptoms}
                    required
                    style={{
                      width: '100%',
                      padding: '12px',
                      borderRadius: '10px',
                      background: '#0f172a',
                      border: '1px solid #334155',
                      color: '#f8fafc',
                      fontSize: '13px',
                      outline: 'none',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>

                <button
                  type="submit"
                  style={{
                    width: '100%',
                    padding: '11px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#0d9488',
                    color: '#fff',
                    fontWeight: 700,
                    fontSize: '13px',
                    cursor: 'pointer',
                  }}
                >
                  {t.submitCheckin}
                </button>
              </form>
            </div>
          </div>

          {/* Right Column: Grounded RAG Chat Assistant */}
          <div style={{
            background: '#1e293b',
            borderRadius: '16px',
            border: '1px solid #334155',
            display: 'flex',
            flexDirection: 'column',
            height: '780px',
            overflow: 'hidden',
          }}>
            {/* Chat Header */}
            <div style={{
              padding: '18px 22px',
              borderBottom: '1px solid #334155',
              background: '#0f172a',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}>
              <div>
                <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: '#f8fafc' }}>
                  💬 {t.dischargeAssistant}
                </h2>
                <p style={{ margin: '2px 0 0 0', fontSize: '11px', color: '#94a3b8' }}>
                  Grounded strictly in clinician discharge instructions
                </p>
              </div>
              <span style={{ fontSize: '11px', background: '#1e293b', padding: '4px 8px', borderRadius: '6px', color: '#2dd4bf', fontWeight: 600 }}>
                Safety-Guarded
              </span>
            </div>

            {/* Messages Thread */}
            <div style={{
              flex: 1,
              overflowY: 'auto',
              padding: '18px',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
            }}>
              {chatMessages.map((m, idx) => (
                <div
                  key={m.message_id || idx}
                  style={{
                    alignSelf: m.sender === 'Patient' ? 'flex-end' : 'flex-start',
                    maxWidth: '82%',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: m.sender === 'Patient' ? 'flex-end' : 'flex-start',
                  }}
                >
                  <div style={{
                    padding: '12px 16px',
                    borderRadius: '14px',
                    background: m.sender === 'Patient' ? '#0d9488' : '#0f172a',
                    color: '#f8fafc',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    border: m.sender === 'Patient' ? 'none' : '1px solid #334155',
                  }}>
                    {m.message_text}

                    {/* Citations if available */}
                    {m.citations?.length > 0 && (
                      <div style={{ marginTop: '8px', paddingTop: '6px', borderTop: '1px solid #1e293b', display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                        {m.citations.map((c, ci) => (
                          <span
                            key={ci}
                            style={{
                              fontSize: '10px',
                              background: '#1e293b',
                              color: '#38bdf8',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              border: '1px solid #334155',
                            }}
                          >
                            📄 doc-chunk: {c}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {m.sender === 'AI_Nurse' && (
                    <div style={{ marginTop: '4px', fontSize: '10px', color: m.is_grounded ? '#34d399' : '#fbbf24', fontWeight: 600 }}>
                      {m.is_grounded ? `✓ ${t.groundedBadge}` : `⚠️ ${t.forwardedBadge}`}
                    </div>
                  )}
                </div>
              ))}
              {chatLoading && (
                <div style={{ alignSelf: 'flex-start', background: '#0f172a', padding: '10px 14px', borderRadius: '12px', fontSize: '12px', color: '#94a3b8' }}>
                  Checking discharge summary...
                </div>
              )}
              <div ref={chatEndRef} />
            </div>

            {/* Chat Input */}
            <form onSubmit={handleSendChat} style={{ padding: '16px', background: '#0f172a', borderTop: '1px solid #334155', display: 'flex', gap: '10px' }}>
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder={t.chatPlaceholder}
                style={{
                  flex: 1,
                  padding: '11px 14px',
                  borderRadius: '10px',
                  background: '#1e293b',
                  border: '1px solid #334155',
                  color: '#f8fafc',
                  fontSize: '13px',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                disabled={chatLoading}
                style={{
                  padding: '11px 20px',
                  borderRadius: '10px',
                  border: 'none',
                  background: '#0d9488',
                  color: '#fff',
                  fontWeight: 700,
                  fontSize: '13px',
                  cursor: chatLoading ? 'not-allowed' : 'pointer',
                }}
              >
                {t.send}
              </button>
            </form>
          </div>
        </div>
      </main>
    </div>
  );
}
