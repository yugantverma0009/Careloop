import React, { useState, useEffect, useRef } from 'react';
import {
  getPatientToday,
  markDoseTaken,
  skipDose,
  undoDose,
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
  IconCalendar,
  IconClock,
} from './Icons';

const SKIP_REASONS = [
  { id: 'felt_unwell', en: 'Felt unwell', hi: 'तबीयत ठीक नहीं थी' },
  { id: 'ran_out', en: 'Ran out', hi: 'दवा खत्म हो गई' },
  { id: 'forgot', en: 'Forgot', hi: 'भूल गए' },
  { id: 'side_effects', en: 'Had side effects', hi: 'साइड इफेक्ट्स हुए' },
  { id: 'other', en: 'Other', hi: 'अन्य कारण' },
];

export default function CareLoopPatientPortal({ user }) {
  const [lang, setLang] = useState('en');
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [todayData, setTodayData] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Active navigation sidebar tab: 'recovery', 'prescriptions', 'checkin', 'chat'
  const [activeNav, setActiveNav] = useState('recovery');

  // Skip Modal State
  const [skipModalDose, setSkipModalDose] = useState(null);
  const [selectedSkipReason, setSelectedSkipReason] = useState('felt_unwell');
  const [actionLoading, setActionLoading] = useState(false);

  // Undo Toast State
  const [undoToast, setUndoToast] = useState(null);

  // Symptom check-in state (retained from existing)
  const [symptomText, setSymptomText] = useState('');
  const [painLevel, setPainLevel] = useState(2);
  const [symptomGuidance, setSymptomGuidance] = useState(null);
  const [symptomSuccess, setSymptomSuccess] = useState('');

  const chatEndRef = useRef(null);

  // 1. Single Network Request for Patient Overview (Brief Sec 6.1, 8.1)
  const loadTodayData = async (silent = false) => {
    try {
      if (!silent) setLoading(true);
      setErrorMsg('');
      const [todayRes, chatRes] = await Promise.all([
        getPatientToday().catch((err) => {
          throw err;
        }),
        getChatHistory().catch(() => []),
      ]);
      setTodayData(todayRes);
      setChatMessages(chatRes || []);
    } catch (err) {
      console.error('Error loading patient today data', err);
      setErrorMsg(
        lang === 'hi'
          ? 'डेटा लोड करने में समस्या हुई। कृपया पुनः प्रयास करें।'
          : 'Could not load your recovery plan. Please try again.'
      );
    } finally {
      if (!silent) setLoading(false);
    }
  };

  useEffect(() => {
    loadTodayData();
    const interval = setInterval(() => loadTodayData(true), 10000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  // Handle One-Tap Taken (Brief Sec 6.2)
  const handleTakeDose = async (dose) => {
    if (actionLoading) return;
    setActionLoading(true);

    // Optimistic UI update
    const previousToday = todayData;
    setTodayData((prev) => {
      if (!prev) return prev;
      const updateList = (list) =>
        list.map((d) => (d.id === dose.id ? { ...d, status: 'Taken_Confirmed', pill_label: 'Taken', pill_color: 'green' } : d));
      return {
        ...prev,
        counts: {
          ...prev.counts,
          taken: prev.counts.taken + (dose.status === 'Taken_Confirmed' ? 0 : 1),
          pending: Math.max(0, prev.counts.pending - (dose.status === 'Unconfirmed' ? 1 : 0)),
        },
        doses: {
          morning: updateList(prev.doses.morning),
          afternoon: updateList(prev.doses.afternoon),
          evening: updateList(prev.doses.evening),
          night: updateList(prev.doses.night),
        },
        all_doses: updateList(prev.all_doses),
      };
    });

    try {
      await markDoseTaken(dose.id);
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setUndoToast({
        doseId: dose.id,
        medicine: dose.medicine,
        time: timeStr,
        action: 'taken',
      });
      await loadTodayData(true);
    } catch (err) {
      // Rollback on failure
      setTodayData(previousToday);
      alert(err.message || 'Could not update medicine');
    } finally {
      setActionLoading(false);
    }
  };

  // Open Skip Reason Sheet
  const handleOpenSkipModal = (dose) => {
    setSkipModalDose(dose);
    setSelectedSkipReason('felt_unwell');
  };

  // Confirm Skip Dose (Brief Sec 6.2)
  const handleConfirmSkip = async () => {
    if (!skipModalDose || actionLoading) return;
    setActionLoading(true);

    const doseId = skipModalDose.id;
    const previousToday = todayData;
    const reasonLabel = SKIP_REASONS.find((r) => r.id === selectedSkipReason)?.[lang] || selectedSkipReason;

    // Optimistic UI update
    setTodayData((prev) => {
      if (!prev) return prev;
      const updateList = (list) =>
        list.map((d) => (d.id === doseId ? { ...d, status: 'Skipped', pill_label: `Skipped: ${reasonLabel}`, pill_color: 'grey' } : d));
      return {
        ...prev,
        counts: {
          ...prev.counts,
          skipped: prev.counts.skipped + 1,
          pending: Math.max(0, prev.counts.pending - 1),
        },
        doses: {
          morning: updateList(prev.doses.morning),
          afternoon: updateList(prev.doses.afternoon),
          evening: updateList(prev.doses.evening),
          night: updateList(prev.doses.night),
        },
        all_doses: updateList(prev.all_doses),
      };
    });

    try {
      await skipDose(doseId, selectedSkipReason);
      setSkipModalDose(null);
      const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      setUndoToast({
        doseId: doseId,
        medicine: skipModalDose.medicine,
        time: timeStr,
        action: 'skipped',
      });
      await loadTodayData(true);
    } catch (err) {
      setTodayData(previousToday);
      alert(err.message || 'Could not record skipped dose');
    } finally {
      setActionLoading(false);
    }
  };

  // Handle Undo (within 5-minute safety window)
  const handleUndoDose = async (doseId) => {
    if (actionLoading) return;
    setActionLoading(true);
    try {
      await undoDose(doseId);
      setUndoToast(null);
      await loadTodayData(true);
    } catch (err) {
      alert(err.message || 'Could not undo action');
    } finally {
      setActionLoading(false);
    }
  };

  // Symptom Check-in submit
  const handleSymptomSubmit = async (e) => {
    e.preventDefault();
    if (!symptomText.trim()) return;

    try {
      setLoading(true);
      const res = await submitSymptomCheckin(symptomText, painLevel, 'Text', lang);
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
      await loadTodayData(true);
    } catch (err) {
      alert(`Check-in failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Chat message submit
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
          content: res.response || res.reply || res.message,
          grounded: res.is_grounded,
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

  // Derived telemetry metrics
  const hrReading = todayData?.readings?.find((r) => r.type?.toLowerCase().includes('heart') || r.type?.toLowerCase().includes('pulse'));
  const heartRateValue = hrReading?.value ?? 72;
  const hrQuality = hrReading?.quality ?? 'Valid';
  const hrTime = hrReading?.measured_time ?? '09:15 AM';

  const spo2Reading = todayData?.readings?.find((r) => r.type?.toLowerCase().includes('spo2') || r.type?.toLowerCase().includes('oxygen'));
  const spo2Value = spo2Reading?.value ?? 98;
  const spo2Quality = spo2Reading?.quality ?? 'Valid';
  const spo2Time = spo2Reading?.measured_time ?? '09:15 AM';

  // Sidebar badge: doses still to take today (pending + not_confirmed); hidden if 0 (Brief Sec 6.1)
  const remainingDosesCount = (todayData?.counts?.pending || 0) + (todayData?.counts?.not_confirmed || 0);

  // Grouped doses
  const morningDoses = todayData?.doses?.morning || [];
  const afternoonDoses = todayData?.doses?.afternoon || [];
  const eveningDoses = todayData?.doses?.evening || [];
  const nightDoses = todayData?.doses?.night || [];

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        background: 'var(--bg-base, #f8fafc)',
        color: 'var(--text-primary, #0f172a)',
        fontFamily: "var(--font-sans, 'Plus Jakarta Sans', sans-serif)",
      }}
    >
      {/* ─── 1. LEFT VERTICAL SIDEBAR (240px Fixed) ─── */}
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
                Care<span style={{ color: 'var(--accent-teal, #0d9488)' }}>Loop</span>
              </div>
              <div style={{ fontSize: '10px', color: 'var(--text-muted, #94a3b8)', fontWeight: 600 }}>
                {lang === 'hi' ? 'रिकवरी पोर्टल' : 'Recovery portal'}
              </div>
            </div>
          </div>

          {/* Navigation Groups */}
          <div style={{ padding: '20px 14px' }}>
            <div
              style={{
                fontSize: '10px',
                fontWeight: 800,
                color: 'var(--text-muted, #94a3b8)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                padding: '0 10px',
                marginBottom: '10px',
              }}
            >
              {lang === 'hi' ? 'मेरी देखभाल' : 'MY CARE'}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '22px' }}>
              {[
                { id: 'recovery', label: lang === 'hi' ? 'अवलोकन' : 'Overview', Icon: IconActivity },
                {
                  id: 'prescriptions',
                  label: lang === 'hi' ? 'दवाइयाँ' : 'Medicines',
                  Icon: IconPill,
                  badge: remainingDosesCount > 0 ? remainingDosesCount : undefined, // hidden at 0 (Brief Sec 6.1)
                },
                { id: 'checkin', label: lang === 'hi' ? 'दैनिक चेक-इन' : 'Daily check-in', Icon: IconShieldCheck },
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
                      background: isActive ? 'var(--accent-blue-soft, #eff6ff)' : 'transparent',
                      color: isActive ? 'var(--accent-blue, #0284c7)' : 'var(--text-secondary, #475569)',
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
                          background: isActive ? 'var(--accent-blue, #0284c7)' : 'var(--border-subtle, #e2e8f0)',
                          color: isActive ? '#ffffff' : 'var(--text-secondary, #475569)',
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
                color: 'var(--text-muted, #94a3b8)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                padding: '0 10px',
                marginBottom: '10px',
              }}
            >
              {lang === 'hi' ? 'सहायता' : 'ASK'}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
              {[
                {
                  id: 'chat',
                  label: lang === 'hi' ? 'डिस्चार्ज पेपर्स से पूछें' : 'Ask my discharge papers',
                  Icon: IconSparkles,
                },
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
                      background: isActive ? 'var(--accent-blue-soft, #eff6ff)' : 'transparent',
                      color: isActive ? 'var(--accent-blue, #0284c7)' : 'var(--text-secondary, #475569)',
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

        {/* Sidebar Footer */}
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
            <span style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)', fontWeight: 600 }}>Theme</span>
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
            <span>{lang === 'hi' ? 'साइन आउट' : 'Sign Out'}</span>
          </button>
        </div>
      </aside>

      {/* ─── 2. MAIN APPLICATION CONTENT AREA ─── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top Header Bar */}
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
            <div style={{ fontSize: '10px', color: 'var(--text-muted, #94a3b8)', fontWeight: 800, letterSpacing: '0.06em' }}>
              CARELOOP
            </div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
              {lang === 'hi' ? 'मेरी रिकवरी' : 'My recovery'}
            </div>
          </div>

          {/* Search Box */}
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
            <IconSearch width={14} height={14} style={{ color: 'var(--text-muted, #94a3b8)' }} />
            <input
              type="text"
              placeholder={lang === 'hi' ? 'दवाइयाँ खोजें...' : 'Search medicines, schedule...'}
              style={{
                border: 'none',
                background: 'transparent',
                width: '100%',
                fontSize: '12px',
                color: 'var(--text-primary, #0f172a)',
              }}
            />
          </div>

          {/* Right Controls */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            {/* Language Toggle */}
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
                  background: lang === 'en' ? 'var(--accent-teal, #0d9488)' : 'transparent',
                  color: lang === 'en' ? '#ffffff' : 'var(--text-muted, #64748b)',
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
                  background: lang === 'hi' ? 'var(--accent-teal, #0d9488)' : 'transparent',
                  color: lang === 'hi' ? '#ffffff' : 'var(--text-muted, #64748b)',
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
                  background: 'var(--navy-deep, #0b1528)',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: 800,
                }}
              >
                {todayData?.name?.slice(0, 2).toUpperCase() || 'AP'}
              </div>
              <div style={{ textAlign: 'left', lineHeight: 1.2 }}>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                  {todayData?.name || user?.name || 'Aarav Patel'}
                </div>
                <div style={{ fontSize: '10px', color: 'var(--text-muted, #94a3b8)' }}>
                  {lang === 'hi'
                    ? `डिस्चार्ज के बाद दिन ${todayData?.day_after_discharge || 1}`
                    : `Day ${todayData?.day_after_discharge || 1} after discharge`}
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* ─── 3. DASHBOARD MAIN CONTAINER ─── */}
        <main style={{ padding: '32px 36px', maxWidth: '1400px', width: '100%', margin: '0 auto' }}>
          {errorMsg && (
            <div
              style={{
                background: 'var(--alert-red-soft, #fef2f2)',
                border: '1px solid var(--alert-red, #dc2626)',
                borderRadius: '8px',
                padding: '12px 16px',
                marginBottom: '20px',
                color: 'var(--alert-red-text, #991b1b)',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <span>{errorMsg}</span>
              <button
                type="button"
                onClick={() => loadTodayData()}
                style={{
                  background: 'var(--alert-red, #dc2626)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '4px',
                  padding: '4px 10px',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {lang === 'hi' ? 'पुनः प्रयास करें' : 'Retry'}
              </button>
            </div>
          )}

          {/* Main Title Section with Factual Day Chip (Brief Sec 6.1) */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              marginBottom: '24px',
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
                  color: 'var(--accent-blue, #0284c7)',
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  marginBottom: '6px',
                }}
              >
                <IconShieldCheck width={14} height={14} />
                <span>
                  {lang === 'hi' ? 'रिकवरी अवलोकन' : 'RECOVERY OVERVIEW'} ·{' '}
                  {lang === 'hi'
                    ? `डिस्चार्ज के बाद दिन ${todayData?.day_after_discharge || 1}`
                    : `Day ${todayData?.day_after_discharge || 1} after discharge`}
                </span>
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
                {lang === 'hi' ? `नमस्ते ${todayData?.name || 'आरव'}` : `Hi ${todayData?.name || 'Aarav'}`}
              </h1>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', margin: 0 }}>
                {todayData?.formatted_date || 'Thursday, 29 October 2026'} ·{' '}
                {lang === 'hi'
                  ? 'अपनी दैनिक दवाइयाँ, स्मार्टवॉच रीडिंग और देखभाल योजना देखें।'
                  : 'Check your daily medicines, watch readings, and care team updates.'}
              </p>
            </div>
          </div>

          {/* ─── 4. STATUS BANNER (Driven by Real Flag States - Brief Sec 6.5) ─── */}
          {todayData?.banner?.state === 'urgent' && (
            <div
              style={{
                background: 'var(--alert-red-soft, #fef2f2)',
                border: '1px solid var(--alert-red, #dc2626)',
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
                  background: 'var(--alert-red, #dc2626)',
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
                <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--alert-red-text, #991b1b)' }}>
                  {lang === 'hi' ? 'आपकी केयर टीम को सूचित कर दिया गया है' : 'Your care team has been told'}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--alert-red-text, #991b1b)', marginTop: '2px' }}>
                  {lang === 'hi'
                    ? 'यदि आपको सीने में दर्द या सांस लेने में गंभीर तकलीफ हो, तो तुरंत 112 पर कॉल करें।'
                    : 'If you have chest pain or severe trouble breathing, call 112 now.'}
                </div>
              </div>
            </div>
          )}

          {todayData?.banner?.state === 'review' && (
            <div
              style={{
                background: 'var(--warning-amber-soft, #fffbeb)',
                border: '1px solid var(--warning-amber, #d97706)',
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
                  background: 'var(--warning-amber, #d97706)',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <IconClock width={20} height={20} />
              </div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--warning-amber-text, #92400e)' }}>
                  {lang === 'hi' ? 'समीक्षा प्रतीक्षित' : 'Waiting for care team review'}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--warning-amber-text, #92400e)', marginTop: '2px' }}>
                  {lang === 'hi'
                    ? 'आपकी केयर टीम के अवलोकन के लिए एक रीडिंग लंबित है।'
                    : 'A reading is waiting for your care team to review.'}
                </div>
              </div>
            </div>
          )}

          {todayData?.banner?.state === 'seen' && (
            <div
              style={{
                background: 'var(--success-green-soft, #f0fdf4)',
                border: '1px solid var(--success-green, #059669)',
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
                  background: 'var(--success-green, #059669)',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                <IconCheck width={20} height={20} />
              </div>
              <div>
                <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--success-green-text, #166534)' }}>
                  {lang === 'hi' ? 'केयर टीम द्वारा देखा गया' : 'Care team acknowledged'}
                </div>
                <div style={{ fontSize: '13px', color: 'var(--success-green-text, #166534)', marginTop: '2px' }}>
                  {lang === 'hi'
                    ? 'नर्स या डॉक्टर ने आपका नवीनतम स्वास्थ्य अपडेट देख लिया है।'
                    : 'A nurse or doctor has seen your update.'}
                </div>
              </div>
            </div>
          )}

          {/* ─── 5. UNDO FLOATING TOAST (Brief Sec 6.2) ─── */}
          {undoToast && (
            <div
              style={{
                position: 'fixed',
                bottom: '24px',
                right: '24px',
                background: 'var(--navy-deep, #0b1528)',
                color: '#ffffff',
                padding: '14px 20px',
                borderRadius: '10px',
                boxShadow: 'var(--shadow-float)',
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                zIndex: 100,
                border: '1px solid var(--border-strong, #334155)',
              }}
            >
              <div style={{ fontSize: '13px' }}>
                {undoToast.action === 'taken'
                  ? lang === 'hi'
                    ? `${undoToast.medicine} को ${undoToast.time} पर लिया गया चिन्हित किया गया।`
                    : `Marked ${undoToast.medicine} as taken at ${undoToast.time}.`
                  : lang === 'hi'
                  ? `${undoToast.medicine} को छोड़ा गया चिन्हित किया गया।`
                  : `Marked ${undoToast.medicine} as skipped.`}
              </div>
              <button
                type="button"
                onClick={() => handleUndoDose(undoToast.doseId)}
                style={{
                  background: 'var(--accent-teal, #0d9488)',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '6px 14px',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {lang === 'hi' ? 'वापस करें (Undo)' : 'Undo (5 min)'}
              </button>
            </div>
          )}

          {/* ─── 6. TAB: RECOVERY OVERVIEW OR MEDICINES ─── */}
          {(activeNav === 'recovery' || activeNav === 'prescriptions') && (
            <>
              {/* HERO ROW: NEXT MEDICINE & TODAY SUMMARY (Brief Sec 5.2, 6.1) */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.8fr 1fr',
                  gap: '18px',
                  marginBottom: '24px',
                }}
              >
                {/* Left Card: Next Medicine Card */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '22px 24px',
                    boxShadow: 'var(--shadow-card)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                      <span style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                        {lang === 'hi' ? 'अगली दवा' : 'Next medicine'}
                      </span>
                      {todayData?.next_dose && (
                        <span className={`status-pill status-pill-${todayData.next_dose.pill_color}`}>
                          {todayData.next_dose.pill_label}
                        </span>
                      )}
                    </div>

                    {todayData?.next_dose ? (
                      <>
                        <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
                          {todayData.next_dose.medicine} · {todayData.next_dose.scheduled_time}
                        </div>
                        <div style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)' }}>
                          {todayData.next_dose.dose_instructions}
                        </div>
                      </>
                    ) : (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--success-green, #059669)', padding: '12px 0' }}>
                        <IconCheck width={20} height={20} />
                        <span style={{ fontSize: '15px', fontWeight: 700 }}>
                          {lang === 'hi' ? 'आज की सभी दवाइयाँ पूरी हो चुकी हैं।' : 'All medicines done for today.'}
                        </span>
                      </div>
                    )}
                  </div>

                  {todayData?.next_dose && (
                    <div style={{ display: 'flex', gap: '10px', marginTop: '20px' }}>
                      <button
                        type="button"
                        onClick={() => handleTakeDose(todayData.next_dose)}
                        disabled={actionLoading}
                        style={{
                          padding: '10px 22px',
                          borderRadius: '8px',
                          border: 'none',
                          background: 'var(--navy-deep, #0b1528)',
                          color: '#ffffff',
                          fontSize: '13px',
                          fontWeight: 700,
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          minHeight: '44px',
                        }}
                      >
                        <IconCheck width={16} height={16} />
                        <span>{lang === 'hi' ? 'ले ली (Taken)' : 'Taken'}</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleOpenSkipModal(todayData.next_dose)}
                        disabled={actionLoading}
                        style={{
                          padding: '10px 18px',
                          borderRadius: '8px',
                          border: '1px solid var(--border-strong, #cbd5e1)',
                          background: 'var(--bg-base, #f8fafc)',
                          color: 'var(--text-primary, #0f172a)',
                          fontSize: '13px',
                          fontWeight: 600,
                          cursor: 'pointer',
                          minHeight: '44px',
                        }}
                      >
                        <span>{lang === 'hi' ? 'छोड़ें (Skip)' : 'Skip'}</span>
                      </button>
                    </div>
                  )}
                </div>

                {/* Right Card: Today Summary with Dot Indicators (No Percentage - Brief Sec 6.1) */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '22px 24px',
                    boxShadow: 'var(--shadow-card)',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '8px' }}>
                      {lang === 'hi' ? 'आज की प्रगति' : 'Today'}
                    </div>
                    <div style={{ fontSize: '26px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: '4px 0' }}>
                      {lang === 'hi'
                        ? `${todayData?.counts?.planned || 0} में से ${todayData?.counts?.taken || 0} ली`
                        : `${todayData?.counts?.taken || 0} of ${todayData?.counts?.planned || 0} taken`}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', marginBottom: '16px' }}>
                      {todayData?.counts?.pending || 0} {lang === 'hi' ? 'शेष खुराक' : 'remaining today'}
                    </div>

                    {/* Dot Indicators */}
                    <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
                      {(todayData?.all_doses || []).map((d, idx) => {
                        const isTaken = d.status === 'Taken' || d.status === 'Taken_Confirmed';
                        const isSkipped = d.status === 'Skipped';
                        return (
                          <div
                            key={d.id || idx}
                            title={`${d.medicine} (${d.scheduled_time}): ${d.status}`}
                            style={{
                              width: '14px',
                              height: '14px',
                              borderRadius: '50%',
                              background: isTaken
                                ? 'var(--success-green, #059669)'
                                : isSkipped
                                ? 'var(--warning-amber, #d97706)'
                                : 'transparent',
                              border: isTaken || isSkipped ? 'none' : '2px solid var(--border-strong, #cbd5e1)',
                              transition: 'all 0.2s ease',
                            }}
                          />
                        );
                      })}
                    </div>
                  </div>

                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '14px' }}>
                    ● {lang === 'hi' ? 'हरा = ली गई, पीला = छूटी हुई, खाली = आने वाली' : 'Green = taken, Amber = skipped, Hollow = pending'}
                  </div>
                </div>
              </div>

              {/* FOUR KPI STAT CARDS (Brief Sec 6.1: Pulse, Oxygen, Latest Check-in, Next Appointment) */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '18px',
                  marginBottom: '24px',
                }}
              >
                {/* Card 1: Pulse */}
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
                      background: 'var(--warning-amber-soft, #fff7ed)',
                      border: '1px solid var(--warning-amber, #fed7aa)',
                      color: 'var(--warning-amber-text, #c2410c)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconHeartPulse width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    {lang === 'hi' ? 'नाड़ी (Pulse)' : 'Pulse'}
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                    }}
                  >
                    {heartRateValue} <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-muted, #64748b)' }}>bpm</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    {lang === 'hi' ? `नवीनतम रीडिंग, ${hrTime} · ${hrQuality}` : `Latest reading, ${hrTime} · ${hrQuality}`}
                  </div>
                </div>

                {/* Card 2: Blood Oxygen (SpO2) */}
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
                      background: 'var(--accent-blue-soft, #eff6ff)',
                      border: '1px solid var(--accent-blue, #bfdbfe)',
                      color: 'var(--accent-blue, #1d4ed8)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconShieldCheck width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    {lang === 'hi' ? 'ऑक्सीजन स्तर (SpO2)' : 'Oxygen level (SpO2)'}
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                    }}
                  >
                    {spo2Value}%
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    {lang === 'hi' ? `नवीनतम रीडिंग, ${spo2Time} · ${spo2Quality}` : `Latest reading, ${spo2Time} · ${spo2Quality}`}
                  </div>
                </div>

                {/* Card 3: Latest Check-in */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                    cursor: 'pointer',
                  }}
                  onClick={() => setActiveNav('checkin')}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: 'var(--accent-teal-soft, #ecfdf5)',
                      border: '1px solid var(--accent-teal, #a7f3d0)',
                      color: 'var(--accent-teal, #0d9488)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconShieldCheck width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    {lang === 'hi' ? 'दैनिक चेक-इन' : 'Daily check-in'}
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                    }}
                  >
                    {painLevel} <span style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-muted, #64748b)' }}>/ 10</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--accent-teal, #0d9488)', fontWeight: 600 }}>
                    {lang === 'hi' ? 'नया चेक-इन दर्ज करें →' : 'Report today →'}
                  </div>
                </div>

                {/* Card 4: Next Appointment (Replaces duplicate adherence card - Brief Sec 6.1) */}
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
                      background: 'var(--accent-blue-soft, #eff6ff)',
                      border: '1px solid var(--accent-blue, #bfdbfe)',
                      color: 'var(--accent-blue, #1d4ed8)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconCalendar width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    {lang === 'hi' ? 'अगला अपॉइंटमेंट' : 'Next appointment'}
                  </div>
                  <div
                    style={{
                      fontSize: '18px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {todayData?.next_appointment?.formatted_date || (lang === 'hi' ? 'कोई निर्धारित नहीं' : 'None scheduled')}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    {todayData?.next_appointment?.with || (lang === 'hi' ? 'केयर टीम' : 'Care team')}
                  </div>
                </div>
              </div>

              {/* ─── 7. GROUPED MEDICINES TABLE (Morning / Afternoon / Evening / Night) (Brief Sec 6.2) ─── */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '22px 24px',
                  boxShadow: 'var(--shadow-card)',
                  marginBottom: '24px',
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
                      {lang === 'hi' ? "आज की दवाइयाँ" : "Today's medicines"}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted, #94a3b8)' }}>
                      {lang === 'hi'
                        ? 'प्रत्येक खुराक को ले ली या छोड़ें के रूप में चिह्नित करें।'
                        : 'Mark each dose Taken or Skip. Your care team can see your updates.'}
                    </div>
                  </div>
                </div>

                {/* Render Group Helper */}
                {[
                  { title: lang === 'hi' ? 'सुबह (Morning - 12:00 से पहले)' : 'Morning (before 12:00 PM)', list: morningDoses },
                  { title: lang === 'hi' ? 'दोपहर (Afternoon - 12:00 से 4:59 PM)' : 'Afternoon (12:00 PM - 4:59 PM)', list: afternoonDoses },
                  { title: lang === 'hi' ? 'शाम (Evening - 5:00 से 8:59 PM)' : 'Evening (5:00 PM - 8:59 PM)', list: eveningDoses },
                  { title: lang === 'hi' ? 'रात (Night - 9:00 PM onwards)' : 'Night (9:00 PM onwards)', list: nightDoses },
                ]
                  .filter((grp) => grp.list.length > 0)
                  .map((grp, grpIdx) => (
                    <div key={grpIdx} style={{ marginBottom: '24px' }}>
                      <div
                        style={{
                          fontSize: '12px',
                          fontWeight: 700,
                          color: 'var(--accent-teal, #0d9488)',
                          textTransform: 'uppercase',
                          letterSpacing: '0.04em',
                          padding: '6px 0',
                          borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                          marginBottom: '8px',
                        }}
                      >
                        {grp.title}
                      </div>

                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                          <thead>
                            <tr style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                              <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase' }}>
                                {lang === 'hi' ? 'दवा' : 'MEDICINE'}
                              </th>
                              <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase' }}>
                                {lang === 'hi' ? 'समय' : 'SCHEDULED'}
                              </th>
                              <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase' }}>
                                {lang === 'hi' ? 'निर्देश' : 'INSTRUCTIONS'}
                              </th>
                              <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase' }}>
                                {lang === 'hi' ? 'स्थिति' : 'STATUS'}
                              </th>
                              <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase', textAlign: 'right' }}>
                                {lang === 'hi' ? 'कार्रवाई' : 'ACTION'}
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {grp.list.map((d) => {
                              const isTaken = d.status === 'Taken' || d.status === 'Taken_Confirmed';
                              const isSkipped = d.status === 'Skipped';
                              const isUpcoming = d.relative === 'upcoming';

                              return (
                                <tr
                                  key={d.id}
                                  style={{
                                    borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
                                    opacity: isTaken ? 0.65 : 1,
                                    textDecoration: isTaken ? 'line-through' : 'none',
                                    transition: 'background 0.15s ease',
                                  }}
                                >
                                  <td style={{ padding: '12px', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                                    {d.medicine}
                                  </td>
                                  <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-muted, #64748b)', fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)" }}>
                                    {d.scheduled_time}
                                  </td>
                                  <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                                    {d.dose_instructions}
                                  </td>
                                  <td style={{ padding: '12px' }}>
                                    <span className={`status-pill status-pill-${d.pill_color}`}>
                                      {d.pill_label}
                                    </span>
                                  </td>
                                  <td style={{ padding: '12px', textAlign: 'right', textDecoration: 'none' }}>
                                    {isTaken ? (
                                      <button
                                        type="button"
                                        onClick={() => handleUndoDose(d.id)}
                                        style={{
                                          padding: '5px 12px',
                                          borderRadius: '6px',
                                          border: '1px solid var(--border-strong, #cbd5e1)',
                                          background: 'transparent',
                                          color: 'var(--text-secondary, #475569)',
                                          fontSize: '11px',
                                          fontWeight: 600,
                                          cursor: 'pointer',
                                        }}
                                      >
                                        {lang === 'hi' ? 'वापस करें' : 'Undo'}
                                      </button>
                                    ) : isSkipped ? (
                                      <button
                                        type="button"
                                        onClick={() => handleTakeDose(d)}
                                        style={{
                                          padding: '5px 12px',
                                          borderRadius: '6px',
                                          border: '1px solid var(--border-strong, #cbd5e1)',
                                          background: 'transparent',
                                          color: 'var(--text-primary, #0f172a)',
                                          fontSize: '11px',
                                          fontWeight: 600,
                                          cursor: 'pointer',
                                        }}
                                      >
                                        {lang === 'hi' ? 'मैंने ले ली' : 'I took it'}
                                      </button>
                                    ) : isUpcoming ? (
                                      <span
                                        title={lang === 'hi' ? 'आप इसे 1 घंटे पहले ले सकते हैं' : 'You can mark this 1 hour before'}
                                        style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)', fontWeight: 500 }}
                                      >
                                        {lang === 'hi' ? 'आने वाली' : 'Upcoming'}
                                      </span>
                                    ) : (
                                      <div style={{ display: 'inline-flex', gap: '6px', justifyContent: 'flex-end' }}>
                                        <button
                                          type="button"
                                          onClick={() => handleTakeDose(d)}
                                          disabled={actionLoading}
                                          style={{
                                            padding: '6px 14px',
                                            borderRadius: '6px',
                                            border: 'none',
                                            background: 'var(--navy-deep, #0b1528)',
                                            color: '#ffffff',
                                            fontSize: '11px',
                                            fontWeight: 700,
                                            cursor: 'pointer',
                                          }}
                                        >
                                          {lang === 'hi' ? 'ले ली' : 'Taken'}
                                        </button>
                                        <button
                                          type="button"
                                          onClick={() => handleOpenSkipModal(d)}
                                          disabled={actionLoading}
                                          style={{
                                            padding: '6px 10px',
                                            borderRadius: '6px',
                                            border: '1px solid var(--border-strong, #cbd5e1)',
                                            background: 'transparent',
                                            color: 'var(--text-secondary, #475569)',
                                            fontSize: '11px',
                                            fontWeight: 600,
                                            cursor: 'pointer',
                                          }}
                                        >
                                          {lang === 'hi' ? 'छोड़ें' : 'Skip'}
                                        </button>
                                      </div>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}

                {todayData?.all_doses?.length === 0 && (
                  <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted, #94a3b8)', fontSize: '13px' }}>
                    {lang === 'hi' ? 'आज कोई दवा निर्धारित नहीं है।' : 'No medicines planned for today.'}
                  </div>
                )}
              </div>

              {/* ─── 8. WEEK STRIP (Brief Sec 5.2, 6.3) ─── */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '20px 24px',
                  boxShadow: 'var(--shadow-card)',
                  marginBottom: '24px',
                }}
              >
                <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '12px' }}>
                  {lang === 'hi' ? 'इस सप्ताह का संक्षिप्त विवरण' : 'This week'}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '10px' }}>
                  {(todayData?.week || []).map((wDay) => (
                    <div
                      key={wDay.date}
                      style={{
                        padding: '12px 10px',
                        borderRadius: '8px',
                        border: wDay.is_today ? '2px solid var(--accent-blue, #0284c7)' : '1px solid var(--border-subtle, #e2e8f0)',
                        background: wDay.is_today ? 'var(--accent-blue-soft, #eff6ff)' : 'var(--bg-base, #f8fafc)',
                        textAlign: 'center',
                      }}
                    >
                      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #94a3b8)', textTransform: 'uppercase' }}>
                        {wDay.day_name}
                      </div>
                      <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: '4px 0' }}>
                        {wDay.day_num}
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'center', gap: '4px', marginTop: '6px' }}>
                        <div
                          title={`${wDay.taken} of ${wDay.planned} doses taken`}
                          style={{
                            width: '6px',
                            height: '6px',
                            borderRadius: '50%',
                            background:
                              wDay.planned === 0
                                ? 'transparent'
                                : wDay.taken >= wDay.planned
                                ? 'var(--success-green, #059669)'
                                : 'var(--warning-amber, #d97706)',
                          }}
                        />
                        {wDay.appointment && (
                          <div
                            title="Appointment scheduled"
                            style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-blue, #0284c7)' }}
                          />
                        )}
                        {wDay.checkin && (
                          <div
                            title="Check-in reported"
                            style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-teal, #0d9488)' }}
                          />
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {/* ─── 9. TAB: CHECK-IN (Retained from existing, refined styling) ─── */}
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
                <IconShieldCheck width={20} height={20} style={{ color: 'var(--accent-teal, #0d9488)' }} />
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0 }}>
                  {lang === 'hi' ? 'दैनिक स्वास्थ्य चेक-इन' : 'Daily health check-in'}
                </h2>
              </div>
              <p style={{ fontSize: '13px', color: 'var(--text-muted, #64748b)', marginBottom: '20px' }}>
                {lang === 'hi'
                  ? 'बताएं कि आप कैसा महसूस कर रहे हैं और क्या आपको कोई असामान्य लक्षण महसूस हो रहे हैं।'
                  : 'Tell us how you are feeling and if you notice anything unusual.'}
              </p>

              {symptomSuccess && (
                <div
                  style={{
                    background: 'var(--success-green-soft, #f0fdf4)',
                    color: 'var(--success-green-text, #166534)',
                    padding: '12px 16px',
                    borderRadius: '8px',
                    fontSize: '13px',
                    fontWeight: 600,
                    marginBottom: '16px',
                    border: '1px solid var(--success-green, #bbf7d0)',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                  }}
                >
                  <IconCheck width={14} height={14} />
                  <span>{symptomSuccess}</span>
                </div>
              )}

              {symptomGuidance && (
                <div
                  style={{
                    background: 'var(--alert-red-soft, #fef2f2)',
                    border: '1px solid var(--alert-red, #dc2626)',
                    borderRadius: '8px',
                    padding: '12px 16px',
                    marginBottom: '16px',
                    color: 'var(--alert-red-text, #991b1b)',
                    fontSize: '13px',
                    fontWeight: 600,
                  }}
                >
                  {symptomGuidance}
                </div>
              )}

              <form onSubmit={handleSymptomSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                    <span>{lang === 'hi' ? 'दर्द का स्तर (0 से 10)' : 'Pain level (0 to 10)'}</span>
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
                    style={{ width: '100%', accentColor: 'var(--accent-teal, #0d9488)' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
                    {lang === 'hi' ? 'वर्णन करें कि आप अभी कैसा महसूस कर रहे हैं' : 'Describe how you feel right now'}
                  </label>
                  <textarea
                    rows="4"
                    value={symptomText}
                    onChange={(e) => setSymptomText(e.target.value)}
                    placeholder={lang === 'hi' ? 'उदा. थोड़ा थका हुआ, कोई सीने में दर्द नहीं...' : 'e.g. A little tired after walking, no chest pain...'}
                    style={{
                      width: '100%',
                      padding: '12px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-strong, #cbd5e1)',
                      fontSize: '13px',
                      background: 'var(--bg-input, #ffffff)',
                      color: 'var(--text-primary, #0f172a)',
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
                    background: 'var(--navy-deep, #0b1528)',
                    color: '#ffffff',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: !symptomText.trim() ? 'not-allowed' : 'pointer',
                    opacity: !symptomText.trim() ? 0.6 : 1,
                  }}
                >
                  {lang === 'hi' ? 'केयर टीम को भेजें' : 'Send check-in'}
                </button>
              </form>
            </div>
          )}

          {/* ─── 10. TAB: CHAT ASSISTANT (Retained from existing, refined styling) ─── */}
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
                  <IconSparkles width={20} height={20} style={{ color: 'var(--accent-teal, #0d9488)' }} />
                  <div>
                    <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0 }}>
                      {lang === 'hi' ? 'डिस्चार्ज रिकवरी सहायक' : 'Discharge recovery assistant'}
                    </h2>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)' }}>
                      {lang === 'hi'
                        ? 'उत्तर सीधे आपके डिस्चार्ज पेपर्स से लिए जाते हैं'
                        : 'Answers are taken directly from your discharge papers'}
                    </div>
                  </div>
                </div>
                <span className="status-pill status-pill-blue">
                  {lang === 'hi' ? 'केवल डिस्चार्ज पेपर्स' : 'Discharge papers only'}
                </span>
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
                  <div style={{ margin: 'auto', textAlign: 'center', color: 'var(--text-muted, #94a3b8)', fontSize: '13px' }}>
                    {lang === 'hi'
                      ? 'अपनी दवाओं, घाव की देखभाल या डॉक्टर की विज़िट के बारे में पूछें।'
                      : 'Ask about your medicines, wound care, or doctor visits.'}
                  </div>
                ) : (
                  chatMessages.map((msg, i) => {
                    const isUser = msg.role === 'user' || msg.sender === 'Patient';
                    return (
                      <div
                        key={i}
                        style={{
                          alignSelf: isUser ? 'flex-end' : 'flex-start',
                          maxWidth: '80%',
                          padding: '10px 14px',
                          borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                          background: isUser ? 'var(--navy-deep, #0b1528)' : 'var(--bg-base, #f1f5f9)',
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
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #94a3b8)', padding: '6px' }}>
                    {lang === 'hi' ? 'आपके पेपर्स चेक किए जा रहे हैं...' : 'Checking your discharge papers...'}
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
                  placeholder={
                    lang === 'hi'
                      ? 'अपनी दवाओं या डिस्चार्ज निर्देशों के बारे में पूछें...'
                      : 'Ask about your medicines or discharge instructions...'
                  }
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    fontSize: '13px',
                    background: 'var(--bg-input, #ffffff)',
                    color: 'var(--text-primary, #0f172a)',
                  }}
                />
                <button
                  type="submit"
                  disabled={chatLoading || !chatInput.trim()}
                  style={{
                    padding: '0 18px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'var(--navy-deep, #0b1528)',
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

      {/* ─── 11. SKIP DOSE MODAL SHEET (Brief Sec 6.2) ─── */}
      {skipModalDose && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.5)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 110,
          }}
        >
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              borderRadius: '12px',
              padding: '24px',
              width: '90%',
              maxWidth: '440px',
              boxShadow: 'var(--shadow-float)',
            }}
          >
            <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
              {lang === 'hi' ? 'यह दवा क्यों छोड़ रहे हैं?' : 'Why are you skipping this dose?'}
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted, #64748b)', marginBottom: '18px' }}>
              {skipModalDose.medicine} · {skipModalDose.scheduled_time}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '22px' }}>
              {SKIP_REASONS.map((reason) => {
                const isSelected = selectedSkipReason === reason.id;
                return (
                  <button
                    key={reason.id}
                    type="button"
                    onClick={() => setSelectedSkipReason(reason.id)}
                    style={{
                      padding: '10px 14px',
                      borderRadius: '8px',
                      border: isSelected ? '1px solid var(--accent-blue, #0284c7)' : '1px solid var(--border-subtle, #e2e8f0)',
                      background: isSelected ? 'var(--accent-blue-soft, #eff6ff)' : 'var(--bg-base, #f8fafc)',
                      color: isSelected ? 'var(--accent-blue-text, #1d4ed8)' : 'var(--text-primary, #0f172a)',
                      fontWeight: isSelected ? 700 : 500,
                      fontSize: '13px',
                      textAlign: 'left',
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <span>{reason[lang]}</span>
                    {isSelected && <IconCheck width={14} height={14} />}
                  </button>
                );
              })}
            </div>

            <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setSkipModalDose(null)}
                style={{
                  padding: '9px 16px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-strong, #cbd5e1)',
                  background: 'transparent',
                  color: 'var(--text-secondary, #475569)',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {lang === 'hi' ? 'रद्द करें' : 'Cancel'}
              </button>
              <button
                type="button"
                onClick={handleConfirmSkip}
                disabled={actionLoading}
                style={{
                  padding: '9px 18px',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'var(--warning-amber, #d97706)',
                  color: '#ffffff',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {lang === 'hi' ? 'पुष्टि करें (छोड़ें)' : 'Confirm Skip'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
