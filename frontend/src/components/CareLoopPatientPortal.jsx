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
import ThemeToggle from './ThemeToggle';
import {
  IconLogo,
  IconPill,
  IconHeartPulse,
  IconActivity,
  IconAlertTriangle,
  IconSparkles,
  IconSend,
  IconCheck,
  IconLogOut,
  IconShieldCheck,
  IconSearch,
} from './Icons';

export default function CareLoopPatientPortal({ user }) {
  const [lang, setLang] = useState('en');
  const [loading, setLoading] = useState(true);
  const [statusData, setStatusData] = useState(null);
  const [doses, setDoses] = useState([]);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Active navigation sidebar tab: 'recovery', 'prescriptions', 'telemetry', 'checkin', 'chat'
  const [activeNav, setActiveNav] = useState('recovery');

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

  const handleExportSummary = () => {
    const summaryText = `CARELOOP RECOVERY SUMMARY
Patient: ${user?.name || 'Aarav Patel'}
Role: ${user?.role || 'Patient'}
Generated: ${new Date().toLocaleString()}

-- WEARABLE READINGS --
Pulse: ${heartRateValue} bpm
Oxygen level (SpO2): ${spo2Value}%
Prescribed Daily Doses: ${doses.length}
Doses confirmed: ${adherencePct}% (${takenCount} of ${doses.length} completed)

-- YOUR MEDICINES --
${doses.map((d) => `• ${d.medicine_name}: ${d.dose_instructions || 'Take as instructed'} [Status: ${d.status}]`).join('\n')}

-- ATTENTION NEEDED --
Safeguard Flags Active: ${hasUrgentFlag ? '1 (Care team review requested)' : '0 (Stable)'}

Readings are checked for impossible values. They are not a medical diagnosis.
`;
    const blob = new Blob([summaryText], { type: 'text/plain;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `careloop_recovery_summary_${user?.name?.toLowerCase().replace(/\s+/g, '_') || 'patient'}.txt`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleConfirmDose = async (logId, status) => {
    try {
      await confirmMyDose(logId, status);
      await loadAll();
    } catch (err) {
      alert(`Could not update medicine: ${err.message}`);
    }
  };

  const handleSymptomSubmit = async (e) => {
    e.preventDefault();
    if (!symptomText.trim()) return;

    try {
      setLoading(true);
      const res = await submitSymptomCheckin(symptomText, painLevel);
      setSymptomSuccess(
        lang === 'hi'
          ? 'आपकी स्थिति दर्ज कर ली गई है। आपकी केयर टीम इसे देख सकती है।'
          : 'Check-in recorded. Your care team can see your update.'
      );
      if (res && (res.guidance || res.immediate_guidance)) {
        setSymptomGuidance(res.guidance || res.immediate_guidance);
      }
      setSymptomText('');
      setTimeout(() => setSymptomSuccess(''), 6000);
      await loadAll();
    } catch (err) {
      alert(`Check-in failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim() || chatLoading) return;

    const userText = chatInput.trim();
    setChatInput('');
    setChatMessages((prev) => [
      ...prev,
      { role: 'user', content: userText, timestamp: new Date().toISOString() },
    ]);
    setChatLoading(true);

    try {
      const res = await sendChatMessage(userText, lang);
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: res.reply || res.message,
          grounded: true,
          forwarded_to_staff: res.forwarded_to_staff,
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content:
            lang === 'hi'
              ? 'कनेक्ट करने में समस्या हुई। कृपया पुनः प्रयास करें या केयर टीम को कॉल करें।'
              : "I couldn't connect right now. Please try again or call your care team.",
          grounded: false,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const hrReading = statusData?.readings?.find((r) => r.measurement_type?.toLowerCase().includes('heart') || r.measurement_type?.toLowerCase().includes('pulse'));
  const heartRateValue = hrReading && hrReading.quality_status !== 'Invalid' ? Math.round(hrReading.measurement_value) : (statusData?.latest_vitals?.heart_rate ?? 72);

  const spo2Reading = statusData?.readings?.find((r) => r.measurement_type?.toLowerCase().includes('spo2') || r.measurement_type?.toLowerCase().includes('oxygen'));
  const spo2Value = spo2Reading && spo2Reading.quality_status !== 'Invalid' ? Math.round(spo2Reading.measurement_value) : (statusData?.latest_vitals?.spo2 ?? 98);

  const hasUrgentFlag = statusData?.active_flags?.some(
    (f) => f.severity === 'Urgent_Review' || f.severity === 'Immediate_Review'
  );

  const takenCount = doses.filter((d) => d.status === 'Taken' || d.status === 'Taken_Confirmed').length;
  const adherencePct = doses.length > 0 ? Math.round((takenCount / doses.length) * 100) : 100;

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        background: 'var(--bg-base, #f8fafc)',
        color: 'var(--text-primary, #0f172a)',
        fontFamily: "'Plus Jakarta Sans', sans-serif",
      }}
    >
      {/* 1. LEFT VERTICAL SIDEBAR (BhoomiSetu Style: 240px Wide) */}
      <aside
        style={{
          width: '240px',
          background: 'var(--sidebar-bg, #ffffff)',
          borderRight: '1px solid var(--sidebar-border, #e2e8f0)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          height: '100vh',
          flexShrink: 0,
          zIndex: 40,
        }}
      >
        <div>
          {/* Brand Logo Header */}
          <div
            style={{
              padding: '20px 22px 18px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
            }}
          >
            <IconLogo size={34} />
            <div>
              <div
                style={{
                  fontSize: '17px',
                  fontWeight: 800,
                  letterSpacing: '-0.02em',
                  color: 'var(--text-primary, #0f172a)',
                }}
              >
                Care<span style={{ color: '#0d9488' }}>Loop</span>
              </div>
              <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>
                Recovery portal
              </div>
            </div>
          </div>

          {/* Navigation Groups */}
          <div style={{ padding: '20px 14px' }}>
            <div
              style={{
                fontSize: '10px',
                fontWeight: 800,
                color: '#94a3b8',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                padding: '0 10px',
                marginBottom: '10px',
              }}
            >
              MY CARE
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '22px' }}>
              {[
                { id: 'recovery', label: 'Overview', Icon: IconActivity },
                { id: 'prescriptions', label: 'Medicines', Icon: IconPill, badge: doses.length },
                { id: 'checkin', label: 'Daily check-in', Icon: IconShieldCheck },
              ].map((item) => {
                const isActive = activeNav === item.id;
                const ItemIcon = item.Icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveNav(item.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      width: '100%',
                      padding: '9px 12px',
                      borderRadius: '8px',
                      border: 'none',
                      background: isActive ? '#eff6ff' : 'transparent',
                      color: isActive ? '#0284c7' : 'var(--text-secondary, #475569)',
                      fontWeight: isActive ? 700 : 500,
                      fontSize: '13px',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <ItemIcon width={16} height={16} />
                      <span>{item.label}</span>
                    </div>
                    {item.badge !== undefined && (
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 7px',
                          borderRadius: '12px',
                          background: isActive ? '#0284c7' : '#e2e8f0',
                          color: isActive ? '#ffffff' : '#475569',
                        }}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            <div
              style={{
                fontSize: '10px',
                fontWeight: 800,
                color: '#94a3b8',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                padding: '0 10px',
                marginBottom: '10px',
              }}
            >
              ASK
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              {[
                { id: 'chat', label: 'Ask my discharge papers', Icon: IconSparkles },
              ].map((item) => {
                const isActive = activeNav === item.id;
                const ItemIcon = item.Icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveNav(item.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                      width: '100%',
                      padding: '9px 12px',
                      borderRadius: '8px',
                      border: 'none',
                      background: isActive ? '#eff6ff' : 'transparent',
                      color: isActive ? '#0284c7' : 'var(--text-secondary, #475569)',
                      fontWeight: isActive ? 700 : 500,
                      fontSize: '13px',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <ItemIcon width={16} height={16} />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Sidebar Footer Controls */}
        <div
          style={{
            padding: '16px 14px',
            borderTop: '1px solid var(--sidebar-border, #e2e8f0)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 6px' }}>
            <span style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 600 }}>Theme</span>
            <ThemeToggle />
          </div>

          <button
            type="button"
            onClick={logout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 10px',
              borderRadius: '8px',
              border: 'none',
              background: 'transparent',
              color: 'var(--text-secondary, #475569)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <IconLogOut width={14} height={14} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* 2. MAIN APPLICATION CONTENT AREA */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top Breadcrumb & Search Header */}
        <header
          style={{
            height: '64px',
            background: 'var(--header-bg, #ffffff)',
            borderBottom: '1px solid var(--header-border, #e2e8f0)',
            padding: '0 32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            position: 'sticky',
            top: 0,
            zIndex: 30,
          }}
        >
          <div>
            <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 800, letterSpacing: '0.06em' }}>
              CARELOOP
            </div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
              My recovery
            </div>
          </div>

          {/* Centered Search Bar matching BhoomiSetu */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'var(--bg-base, #f8fafc)',
              border: '1px solid var(--border-strong, #cbd5e1)',
              borderRadius: '8px',
              padding: '6px 14px',
              width: '360px',
              gap: '8px',
            }}
          >
            <IconSearch width={14} height={14} style={{ color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="Search medicines, notes..."
              style={{
                border: 'none',
                background: 'transparent',
                width: '100%',
                fontSize: '12px',
                color: 'var(--text-primary, #0f172a)',
              }}
            />
            <span
              style={{
                fontSize: '10px',
                fontWeight: 700,
                color: '#94a3b8',
                background: 'var(--border-subtle, #e2e8f0)',
                padding: '2px 5px',
                borderRadius: '4px',
              }}
            >
              Ctrl+K
            </span>
          </div>

          {/* Right User & Role Switcher */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <div
              style={{
                background: 'var(--bg-base, #f8fafc)',
                borderRadius: '6px',
                padding: '2px',
                display: 'flex',
                border: '1px solid var(--border-subtle, #e2e8f0)',
              }}
            >
              <button
                type="button"
                onClick={() => setLang('en')}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: 'none',
                  background: lang === 'en' ? '#0d9488' : 'transparent',
                  color: lang === 'en' ? '#ffffff' : '#64748b',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                EN
              </button>
              <button
                type="button"
                onClick={() => setLang('hi')}
                style={{
                  padding: '3px 8px',
                  borderRadius: '4px',
                  border: 'none',
                  background: lang === 'hi' ? '#0d9488' : 'transparent',
                  color: lang === 'hi' ? '#ffffff' : '#64748b',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                HI
              </button>
            </div>

            <SwitchDemoWorkspace currentUser={user} />

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: '#0f172a',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: 800,
                }}
              >
                AP
              </div>
              <div style={{ textAlign: 'left', lineHeight: 1.2 }}>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                  Aarav Patel
                </div>
                <div style={{ fontSize: '10px', color: '#94a3b8' }}>Post-CABG Day 3</div>
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Main Container */}
        <main style={{ padding: '32px 36px', maxWidth: '1400px', width: '100%', margin: '0 auto' }}>
          {/* Main Title Section */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              marginBottom: '26px',
            }}
          >
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '11px',
                  fontWeight: 800,
                  color: '#0284c7',
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  marginBottom: '6px',
                }}
              >
                <IconShieldCheck width={14} height={14} />
                <span>RECOVERY OVERVIEW</span>
              </div>
              <h1
                style={{
                  fontSize: '26px',
                  fontWeight: 800,
                  color: 'var(--text-primary, #0f172a)',
                  letterSpacing: '-0.025em',
                  marginBottom: '4px',
                }}
              >
                How your recovery is going
              </h1>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', margin: 0 }}>
                Check your daily medicines, watch readings, and updates from your care team.
              </p>
            </div>

            <button
              type="button"
              onClick={handleExportSummary}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                borderRadius: '8px',
                border: '1px solid var(--border-strong, #cbd5e1)',
                background: 'var(--bg-surface, #ffffff)',
                color: 'var(--text-primary, #0f172a)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                boxShadow: 'var(--shadow-subtle)',
              }}
            >
              <span>Download my summary</span>
            </button>
          </div>

          {/* Emergency Alert Banner if present */}
          {(hasUrgentFlag || symptomGuidance) && (
            <div
              style={{
                background: '#fef2f2',
                border: '1px solid #dc2626',
                borderRadius: '12px',
                padding: '16px 20px',
                marginBottom: '24px',
                display: 'flex',
                alignItems: 'center',
                gap: '14px',
              }}
            >
              <div
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  background: '#dc2626',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <IconAlertTriangle width={20} height={20} />
              </div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 800, color: '#991b1b' }}>
                  Your care team has been told
                </div>
                <div style={{ fontSize: '13px', color: '#b91c1c', marginTop: '2px' }}>
                  {symptomGuidance ||
                    'A nurse or doctor will look at your latest update. If you have chest pain or severe trouble breathing, call 112 now.'}
                </div>
              </div>
            </div>
          )}

          {/* TAB: RECOVERY OVERVIEW OR PRESCRIPTIONS */}
          {(activeNav === 'recovery' || activeNav === 'prescriptions') && (
            <>
              {/* 3. FOUR KPI STAT CARDS (BhoomiSetu Style with Icon Boxes) */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '18px',
                  marginBottom: '24px',
                }}
              >
                {/* Card 1: Scheduled Medications */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#eff6ff',
                      border: '1px solid #bfdbfe',
                      color: '#1d4ed8',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconPill width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Medicines today
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {doses.length}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    Planned for today
                  </div>
                </div>

                {/* Card 2: Heart Rate Telemetry */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#fff7ed',
                      border: '1px solid #fed7aa',
                      color: '#c2410c',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconHeartPulse width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Pulse
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {heartRateValue}{' '}
                    <span style={{ fontSize: '14px', fontWeight: 500, color: '#64748b' }}>bpm</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    Last reading from your watch
                  </div>
                </div>

                {/* Card 3: Blood Oxygen (SpO2) */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#faf5ff',
                      border: '1px solid #e9d5ff',
                      color: '#7e22ce',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconShieldCheck width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Oxygen level (SpO2)
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {spo2Value}%
                  </div>
                  <span className="status-pill status-pill-green" style={{ fontSize: '10px', padding: '1px 8px' }}>
                    Latest reading
                  </span>
                </div>

                {/* Card 4: Adherence Rate */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#f0fdf4',
                      border: '1px solid #bbf7d0',
                      color: '#15803d',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconCheck width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Doses confirmed
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {adherencePct}%
                  </div>
                  <span className="status-pill status-pill-green" style={{ fontSize: '10px', padding: '1px 8px' }}>
                    {takenCount} of {doses.length} confirmed
                  </span>
                </div>
              </div>

              {/* 4. TWO-COLUMN: PROGRESS METERS & SAFEGUARD ATTENTION */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.8fr 1fr',
                  gap: '18px',
                  marginBottom: '24px',
                }}
              >
                {/* Left: Medication Regimen Progress Bars */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '22px 24px',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
                    Today's medicines
                  </div>
                  <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '20px' }}>
                    Mark each dose Taken or Skipped. Your care team can see your answers.
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {doses.map((dose) => {
                      const isTaken = dose.status === 'Taken' || dose.status === 'Taken_Confirmed';
                      return (
                        <div key={dose.medication_log_id}>
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              marginBottom: '6px',
                            }}
                          >
                            <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                              {dose.medicine_name} {dose.dose_instructions ? <span style={{ color: '#0284c7', fontSize: '11px', fontWeight: 500 }}>({dose.dose_instructions})</span> : null}
                            </span>
                            <span
                              style={{
                                fontSize: '11px',
                                fontWeight: 700,
                                color: isTaken ? '#059669' : '#94a3b8',
                              }}
                            >
                              {isTaken ? '100%' : '0%'}
                            </span>
                          </div>
                          <div
                            style={{
                              height: '6px',
                              background: 'var(--bg-base, #f1f5f9)',
                              borderRadius: '3px',
                              overflow: 'hidden',
                            }}
                          >
                            <div
                              style={{
                                height: '100%',
                                width: isTaken ? '100%' : '0%',
                                background: '#0d9488',
                                borderRadius: '3px',
                                transition: 'width 0.4s ease',
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Right: Safeguard Attention Card */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '22px 24px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
                      Needs a look
                    </div>
                    <div style={{ fontSize: '12px', color: '#94a3b8', marginBottom: '18px' }}>
                      Readings that need a care team check
                    </div>

                    <div
                      style={{
                        fontSize: '44px',
                        fontWeight: 800,
                        color: hasUrgentFlag ? '#dc2626' : '#0d9488',
                        lineHeight: 1,
                        marginBottom: '8px',
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {hasUrgentFlag ? '1' : '0'}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', lineHeight: 1.5 }}>
                      {hasUrgentFlag
                        ? 'A reading is waiting for your care team to review.'
                        : 'All readings look normal today.'}
                    </div>
                  </div>

                  <div>
                    <button
                      type="button"
                      onClick={() => setActiveNav('checkin')}
                      style={{
                        width: '100%',
                        padding: '9px 14px',
                        borderRadius: '8px',
                        border: '1px solid var(--border-strong, #cbd5e1)',
                        background: 'var(--bg-base, #f8fafc)',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        marginTop: '16px',
                      }}
                    >
                      Tell us how you feel today
                    </button>
                    <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '8px', textAlign: 'center' }}>
                      Readings are checked for impossible values. They are not a medical diagnosis.
                    </div>
                  </div>
                </div>
              </div>

              {/* 5. AFFECTED PATIENT REGISTER TABLE */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '22px 24px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '18px',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                      Your medicines
                    </div>
                    <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                      Your planned doses for today
                    </div>
                  </div>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          MEDICINE
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          WHEN
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          HOW TO TAKE
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          STATUS
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', textAlign: 'right' }}>
                          ACTION
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {doses.map((d) => (
                        <tr
                          key={d.medication_log_id}
                          style={{
                            borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
                            transition: 'background 0.15s ease',
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-card-hover, #f8fafc)')}
                          onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                        >
                          <td style={{ padding: '12px', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                            {d.medicine_name}
                          </td>
                          <td style={{ padding: '12px', fontSize: '12px', color: '#64748b', fontFamily: "'JetBrains Mono', monospace" }}>
                            {d.scheduled_for?.slice(11, 16) || 'Today, 09:00'}
                          </td>
                          <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                            {d.dose_instructions || d.dosage || 'Prescribed oral dose with water'}
                          </td>
                          <td style={{ padding: '12px' }}>
                            {d.status === 'Taken' || d.status === 'Taken_Confirmed' ? (
                              <span className="status-pill status-pill-green">Taken</span>
                            ) : d.status === 'Skipped' ? (
                              <span className="status-pill status-pill-amber">Skipped</span>
                            ) : (
                              <span className="status-pill status-pill-blue">Planned</span>
                            )}
                          </td>
                          <td style={{ padding: '12px', textAlign: 'right' }}>
                            {d.status !== 'Taken' && d.status !== 'Taken_Confirmed' ? (
                              <button
                                type="button"
                                onClick={() => handleConfirmDose(d.medication_log_id, 'Taken_Confirmed')}
                                style={{
                                  padding: '5px 12px',
                                  borderRadius: '6px',
                                  border: 'none',
                                  background: '#0f172a',
                                  color: '#ffffff',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                }}
                              >
                                Mark Taken
                              </button>
                            ) : (
                              <span style={{ fontSize: '11px', color: '#059669', fontWeight: 600 }}>
                                Confirmed
                              </span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* TAB: SYMPTOM CHECK-IN */}
          {activeNav === 'checkin' && (
            <div
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '12px',
                padding: '28px',
                maxWidth: '680px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                <IconShieldCheck width={20} height={20} style={{ color: '#0d9488' }} />
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0 }}>
                  Daily health check-in
                </h2>
              </div>
              <p style={{ fontSize: '13px', color: '#64748b', marginBottom: '20px' }}>
                Tell us how you are feeling and if you notice anything unusual.
              </p>

              {symptomSuccess && (
                <div
                  style={{
                    background: '#f0fdf4',
                    color: '#166534',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 600,
                    marginBottom: '16px',
                    border: '1px solid #bbf7d0',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <IconCheck width={14} height={14} />
                  <span>{symptomSuccess}</span>
                </div>
              )}

              <form onSubmit={handleSymptomSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                    <span>Pain level (0 to 10)</span>
                    <span style={{ color: painLevel > 6 ? '#dc2626' : painLevel > 3 ? '#d97706' : '#059669', fontWeight: 800 }}>
                      {painLevel} / 10
                    </span>
                  </div>
                  <input
                    type="range"
                    min="0"
                    max="10"
                    value={painLevel}
                    onChange={(e) => setPainLevel(parseInt(e.target.value, 10))}
                    style={{ width: '100%', accentColor: '#0d9488' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                    Describe how you feel right now
                  </label>
                  <textarea
                    rows="4"
                    value={symptomText}
                    onChange={(e) => setSymptomText(e.target.value)}
                    placeholder="e.g. A little tired after walking, no chest pain..."
                    style={{
                      width: '100%',
                      padding: '12px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-strong, #cbd5e1)',
                      fontSize: '13px',
                    }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={loading || !symptomText.trim()}
                  style={{
                    padding: '10px 18px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#0f172a',
                    color: '#ffffff',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: !symptomText.trim() ? 'not-allowed' : 'pointer',
                    opacity: !symptomText.trim() ? 0.6 : 1,
                  }}
                >
                  Send check-in
                </button>
              </form>
            </div>
          )}

          {/* TAB: GROUNDED RAG ASSISTANT */}
          {activeNav === 'chat' && (
            <div
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '12px',
                padding: '24px',
                height: '560px',
                display: 'flex',
                flexDirection: 'column',
                maxWidth: '820px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  paddingBottom: '14px',
                  borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                  marginBottom: '16px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <IconSparkles width={20} height={20} style={{ color: '#0d9488' }} />
                  <div>
                    <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0 }}>
                      Discharge recovery assistant
                    </h2>
                    <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                      Answers are taken directly from your discharge papers
                    </div>
                  </div>
                </div>
                <span className="status-pill status-pill-blue">Discharge papers only</span>
              </div>

              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  paddingRight: '6px',
                }}
              >
                {chatMessages.length === 0 ? (
                  <div style={{ margin: 'auto', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                    Ask about your medicines, wound care, or doctor visits.
                  </div>
                ) : (
                  chatMessages.map((msg, i) => {
                    const isUser = msg.role === 'user' || msg.sender === 'patient';
                    return (
                      <div
                        key={i}
                        style={{
                          alignSelf: isUser ? 'flex-end' : 'flex-start',
                          maxWidth: '80%',
                          padding: '10px 14px',
                          borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                          background: isUser ? '#0f172a' : 'var(--bg-base, #f1f5f9)',
                          color: isUser ? '#ffffff' : 'var(--text-primary, #0f172a)',
                          fontSize: '13px',
                          lineHeight: 1.5,
                        }}
                      >
                        {msg.content || msg.message_text || msg.text}
                      </div>
                    );
                  })
                )}
                {chatLoading && (
                  <div style={{ fontSize: '12px', color: '#94a3b8', padding: '6px' }}>
                    Checking your discharge papers...
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <form
                onSubmit={handleSendMessage}
                style={{
                  display: 'flex',
                  gap: '10px',
                  paddingTop: '14px',
                  borderTop: '1px solid var(--border-subtle, #e2e8f0)',
                  marginTop: '12px',
                }}
              >
                <input
                  type="text"
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  placeholder="Ask about your medicines or discharge instructions..."
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    fontSize: '13px',
                  }}
                />
                <button
                  type="submit"
                  disabled={chatLoading || !chatInput.trim()}
                  style={{
                    padding: '0 18px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#0f172a',
                    color: '#ffffff',
                    cursor: !chatInput.trim() ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <IconSend width={15} height={15} />
                </button>
              </form>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
