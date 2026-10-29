import React, { useState, useEffect, useRef } from 'react';
import {
  getPatientToday,
  getPatientCalendar,
  getPatientDay,
  downloadAppointmentIcs,
  markDoseTaken,
  skipDose,
  undoDose,
  submitPatientCheckin,
  getPatientCheckins,
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
  IconBell,
  IconMic,
} from './Icons';

const SKIP_REASONS = [
  { id: 'felt_unwell', en: 'Felt unwell', hi: 'तबीयत ठीक नहीं थी' },
  { id: 'ran_out', en: 'Ran out', hi: 'दवा खत्म हो गई' },
  { id: 'forgot', en: 'Forgot', hi: 'भूल गए' },
  { id: 'side_effects', en: 'Had side effects', hi: 'साइड इफेक्ट्स हुए' },
  { id: 'other', en: 'Other', hi: 'अन्य कारण' },
];

const CHECKIN_SYMPTOM_CHIPS = [
  { id: 'tired', en: 'Tired', hi: 'थकान' },
  { id: 'dizzy', en: 'Dizzy', hi: 'चक्कर आना' },
  { id: 'nausea', en: 'Nausea', hi: 'जी मिचलाना' },
  { id: 'fever', en: 'Fever', hi: 'बुखार' },
  { id: 'cough', en: 'Cough', hi: 'खांसी' },
  { id: 'swelling', en: 'Swelling', hi: 'सूजन' },
  { id: 'wound_pain', en: 'Wound pain', hi: 'घाव का दर्द' },
  { id: 'poor_sleep', en: 'Poor sleep', hi: 'नींद न आना' },
  { id: 'short_of_breath', en: 'Short of breath', hi: 'सांस फूलना', emergency: true },
  { id: 'chest_pain', en: 'Chest pain', hi: 'सीने में दर्द', emergency: true },
  { id: 'none_of_these', en: 'None of these', hi: 'इनमें से कोई नहीं', isNone: true },
];

const CHECKIN_LOCATION_CHIPS = [
  { id: 'chest', en: 'Chest', hi: 'छाती/सीना' },
  { id: 'wound_site', en: 'Wound site', hi: 'घाव की जगह' },
  { id: 'head', en: 'Head', hi: 'सिर' },
  { id: 'stomach', en: 'Stomach', hi: 'पेट' },
  { id: 'back', en: 'Back', hi: 'पीठ' },
  { id: 'legs', en: 'Legs', hi: 'पैर' },
  { id: 'other', en: 'Other', hi: 'अन्य' },
];

const CHECKIN_TRENDS = [
  { id: 'better', en: 'Better', hi: 'बेहतर' },
  { id: 'same', en: 'Same', hi: 'वैसा ही' },
  { id: 'worse', en: 'Worse', hi: 'खराब' },
];

export default function CareLoopPatientPortal({ user }) {
  const [lang, setLang] = useState('en');
  const [, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [todayData, setTodayData] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);

  // Active navigation sidebar tab: 'recovery', 'prescriptions', 'calendar', 'checkin', 'chat'
  const [activeNav, setActiveNav] = useState('recovery');

  // Skip Modal State
  const [skipModalDose, setSkipModalDose] = useState(null);
  const [selectedSkipReason, setSelectedSkipReason] = useState('felt_unwell');
  const [actionLoading, setActionLoading] = useState(false);

  // Undo Toast State
  const [undoToast, setUndoToast] = useState(null);

  // Calendar State (Brief Sec 6.3)
  const [calendarMonth, setCalendarMonth] = useState('2026-10');
  const [calendarData, setCalendarData] = useState(null);
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [selectedCalendarDate, setSelectedCalendarDate] = useState('2026-10-29');
  const [dayDetail, setDayDetail] = useState(null);
  const [dayDetailLoading, setDayDetailLoading] = useState(false);
  const [downloadingIcsId, setDownloadingIcsId] = useState(null);

  // In-App Reminders State (Brief Sec 6.8)
  const [remindersOpen, setRemindersOpen] = useState(false);

  // Phase 3 Check-in State (Brief Sec 6.4)
  const [painLevel, setPainLevel] = useState(0);
  const [selectedChips, setSelectedChips] = useState([]);
  const [selectedSites, setSelectedSites] = useState([]);
  const [trend, setTrend] = useState(null);
  const [symptomText, setSymptomText] = useState('');
  const [inputMethod, setInputMethod] = useState('Text');
  const [isListening, setIsListening] = useState(false);
  const [checkinSubmitting, setCheckinSubmitting] = useState(false);
  const [checkinSuccessData, setCheckinSuccessData] = useState(null);
  const [checkinError, setCheckinError] = useState(null);
  const [checkinHistory, setCheckinHistory] = useState([]);
  const [checkinHistoryLoading, setCheckinHistoryLoading] = useState(false);
  const [expandedHistoryId, setExpandedHistoryId] = useState(null);
  const recognitionRef = useRef(null);

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

  // Calendar Loader Functions (Brief Sec 6.3 & 8.3)
  const loadCalendarData = async (month) => {
    try {
      setCalendarLoading(true);
      const data = await getPatientCalendar(month);
      setCalendarData(data);
    } catch (err) {
      console.error('Failed to load calendar data', err);
    } finally {
      setCalendarLoading(false);
    }
  };

  const loadDayDetailData = async (dateStr) => {
    try {
      setDayDetailLoading(true);
      const data = await getPatientDay(dateStr);
      setDayDetail(data);
    } catch (err) {
      console.error('Failed to load day detail', err);
    } finally {
      setDayDetailLoading(false);
    }
  };

  useEffect(() => {
    if (activeNav === 'calendar') {
      loadCalendarData(calendarMonth);
    }
  }, [activeNav, calendarMonth]);

  useEffect(() => {
    if (activeNav === 'calendar' && selectedCalendarDate) {
      loadDayDetailData(selectedCalendarDate);
    }
  }, [activeNav, selectedCalendarDate]);

  const handlePrevMonth = () => {
    const [yStr, mStr] = calendarMonth.split('-');
    let y = parseInt(yStr, 10);
    let m = parseInt(mStr, 10) - 1;
    if (m < 1) {
      m = 12;
      y -= 1;
    }
    const newMonth = `${y}-${String(m).padStart(2, '0')}`;
    setCalendarMonth(newMonth);
  };

  const handleNextMonth = () => {
    const [yStr, mStr] = calendarMonth.split('-');
    let y = parseInt(yStr, 10);
    let m = parseInt(mStr, 10) + 1;
    if (m > 12) {
      m = 1;
      y += 1;
    }
    const newMonth = `${y}-${String(m).padStart(2, '0')}`;
    setCalendarMonth(newMonth);
  };

  const handleJumpToToday = () => {
    const todayStr = todayData?.date || '2026-10-29';
    const monthStr = todayStr.slice(0, 7);
    setCalendarMonth(monthStr);
    setSelectedCalendarDate(todayStr);
  };

  const handleSelectDay = (dateStr) => {
    setSelectedCalendarDate(dateStr);
  };

  const handleDownloadAppointmentIcs = async (apptId) => {
    try {
      setDownloadingIcsId(apptId);
      await downloadAppointmentIcs(apptId);
    } catch (err) {
      console.error('Failed to download .ics', err);
      alert(lang === 'hi' ? 'कैलेंडर फाइल डाउनलोड नहीं हो सकी।' : 'Failed to download calendar event file.');
    } finally {
      setDownloadingIcsId(null);
    }
  };

  // In-App Reminders list (Brief Sec 6.8) - Strictly factual, no clinical diagnoses
  const remindersList = [];
  if (todayData?.next_dose) {
    remindersList.push({
      id: 'next_dose',
      title: lang === 'hi' ? 'अगली दवा' : 'Next Medicine Due',
      desc: `${todayData.next_dose.medicine} · ${todayData.next_dose.scheduled_time} (${todayData.next_dose.pill_label})`,
      action: () => {
        setActiveNav('prescriptions');
        setRemindersOpen(false);
      },
      actionLabel: lang === 'hi' ? 'दवाइयाँ देखें' : 'View medicines',
    });
  }
  if (todayData?.counts?.not_confirmed > 0) {
    remindersList.push({
      id: 'not_confirmed',
      title: lang === 'hi' ? 'पुष्टि बाकी' : 'Dose Not Confirmed',
      desc: lang === 'hi'
        ? `${todayData.counts.not_confirmed} खुराक की पुष्टि लंबित है`
        : `${todayData.counts.not_confirmed} scheduled dose awaiting confirmation`,
      action: () => {
        setActiveNav('prescriptions');
        setRemindersOpen(false);
      },
      actionLabel: lang === 'hi' ? 'खुराक देखें' : 'Review doses',
    });
  }
  if (todayData?.next_appointment) {
    remindersList.push({
      id: 'appointment',
      title: lang === 'hi' ? 'फॉलो-अप अपॉइंटमेंट' : 'Upcoming Follow-up Visit',
      desc: `${todayData.next_appointment.formatted_date} · ${todayData.next_appointment.with}`,
      action: () => {
        setActiveNav('calendar');
        setRemindersOpen(false);
      },
      actionLabel: lang === 'hi' ? 'कैलेंडर में देखें' : 'View calendar',
    });
  }

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

  // Speech recognition helper (Brief Sec 6.4)
  const speechSupported =
    typeof window !== 'undefined' &&
    Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);

  const toggleSpeechRecognition = () => {
    if (!speechSupported) return;

    if (isListening) {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
      setIsListening(false);
      return;
    }

    try {
      const SpeechRecognition =
        window.SpeechRecognition || window.webkitSpeechRecognition;
      const rec = new SpeechRecognition();
      rec.lang = lang === 'hi' ? 'hi-IN' : 'en-US';
      rec.continuous = false;
      rec.interimResults = false;

      rec.onstart = () => {
        setIsListening(true);
      };

      rec.onresult = (e) => {
        const transcript = e.results?.[0]?.[0]?.transcript;
        if (transcript) {
          setSymptomText((prev) => (prev ? `${prev} ${transcript}` : transcript));
          setInputMethod('Voice_Transcript');
        }
      };

      rec.onerror = (e) => {
        console.warn('Speech recognition error:', e);
        setIsListening(false);
      };

      rec.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current = rec;
      rec.start();
    } catch (e) {
      console.warn('Failed to start speech recognition:', e);
      setIsListening(false);
    }
  };

  // Chip toggles
  const handleToggleChip = (chipId) => {
    const chip = CHECKIN_SYMPTOM_CHIPS.find((c) => c.id === chipId);
    if (!chip) return;

    if (chip.isNone) {
      if (selectedChips.includes('none_of_these')) {
        setSelectedChips([]);
      } else {
        setSelectedChips(['none_of_these']);
      }
      return;
    }

    if (selectedChips.includes(chipId)) {
      setSelectedChips(selectedChips.filter((c) => c !== chipId));
    } else {
      setSelectedChips([...selectedChips.filter((c) => c !== 'none_of_these'), chipId]);
    }
  };

  const handleToggleSite = (siteId) => {
    if (selectedSites.includes(siteId)) {
      setSelectedSites(selectedSites.filter((s) => s !== siteId));
    } else {
      setSelectedSites([...selectedSites, siteId]);
    }
  };

  const handleToggleTrend = (trendId) => {
    setTrend((prev) => (prev === trendId ? null : trendId));
  };

  // 14-day Check-in History Loader (Brief Sec 6.4 & 8.4)
  const loadCheckinHistory = async () => {
    try {
      setCheckinHistoryLoading(true);
      const res = await getPatientCheckins(14);
      if (res && res.reports) {
        setCheckinHistory(res.reports);
      }
    } catch (err) {
      console.error('Failed to load checkin history:', err);
    } finally {
      setCheckinHistoryLoading(false);
    }
  };

  useEffect(() => {
    if (activeNav === 'checkin') {
      loadCheckinHistory();
    }
  }, [activeNav]);

  // Draft Safety: load draft from localStorage on mount (Brief Sec 6.4)
  useEffect(() => {
    try {
      const saved = localStorage.getItem('careloop_checkin_draft');
      if (saved) {
        const d = JSON.parse(saved);
        if (typeof d.painLevel === 'number') setPainLevel(d.painLevel);
        if (Array.isArray(d.selectedChips)) setSelectedChips(d.selectedChips);
        if (Array.isArray(d.selectedSites)) setSelectedSites(d.selectedSites);
        if (d.trend) setTrend(d.trend);
        if (d.symptomText) setSymptomText(d.symptomText);
      }
    } catch (e) {
      // ignore JSON parse error
    }
  }, []);

  // Draft Safety: persist draft until submitted
  useEffect(() => {
    if (!checkinSuccessData) {
      try {
        localStorage.setItem(
          'careloop_checkin_draft',
          JSON.stringify({
            painLevel,
            selectedChips,
            selectedSites,
            trend,
            symptomText,
          })
        );
      } catch (e) {
        // ignore storage errors
      }
    }
  }, [painLevel, selectedChips, selectedSites, trend, symptomText, checkinSuccessData]);

  // Check-in Submit Handler (Brief Sec 6.4)
  const handleCheckinSubmit = async (e) => {
    if (e) e.preventDefault();
    if (checkinSubmitting) return;

    let timedOut = false;
    const timeoutId = setTimeout(() => {
      timedOut = true;
      setCheckinError(
        lang === 'hi'
          ? 'सर्वर से जवाब मिलने में समय लग रहा है। कृपया अपना कनेक्शन जांचें और पुनः प्रयास करें।'
          : 'Request is taking longer than usual. Please check your connection and retry.'
      );
    }, 10000);

    try {
      setCheckinSubmitting(true);
      setCheckinError(null);

      const payload = {
        pain_level: painLevel,
        chips: selectedChips,
        sites: selectedSites,
        trend: trend,
        text: symptomText.trim(),
        language: lang,
        input_method: inputMethod,
      };

      const res = await submitPatientCheckin(payload);
      clearTimeout(timeoutId);

      if (!timedOut) {
        try {
          localStorage.removeItem('careloop_checkin_draft');
        } catch (err) {}
        setCheckinSuccessData({
          res,
          payload,
          submittedAt: new Date(),
        });
        await loadCheckinHistory();
        await loadTodayData(true);
      }
    } catch (err) {
      clearTimeout(timeoutId);
      setCheckinError(
        err.message || (lang === 'hi' ? 'चेक-इन भेजने में त्रुटि हुई।' : 'Failed to send check-in.')
      );
    } finally {
      setCheckinSubmitting(false);
    }
  };

  const handleResetCheckinForm = () => {
    setCheckinSuccessData(null);
    setPainLevel(0);
    setSelectedChips([]);
    setSelectedSites([]);
    setTrend(null);
    setSymptomText('');
    setInputMethod('Text');
    setCheckinError(null);
    try {
      localStorage.removeItem('careloop_checkin_draft');
    } catch (e) {}
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
                { id: 'calendar', label: lang === 'hi' ? 'मेरा कैलेंडर' : 'My calendar', Icon: IconCalendar },
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

            {/* In-App Reminders Bell (Brief Sec 6.8) */}
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                onClick={() => setRemindersOpen(!remindersOpen)}
                style={{
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  background: 'var(--bg-surface, #ffffff)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                  color: remindersOpen ? 'var(--accent-teal, #0d9488)' : 'var(--text-secondary, #475569)',
                  position: 'relative',
                  transition: 'all 0.15s ease',
                }}
                aria-label="In-app reminders"
                title={lang === 'hi' ? 'रिमाइंडर' : 'Care Reminders'}
              >
                <IconBell width={17} height={17} />
                {remindersList.length > 0 && (
                  <span
                    style={{
                      position: 'absolute',
                      top: '6px',
                      right: '6px',
                      width: '7px',
                      height: '7px',
                      borderRadius: '50%',
                      background: 'var(--alert-red, #dc2626)',
                    }}
                  />
                )}
              </button>

              {/* Reminders Popover Menu */}
              {remindersOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: '44px',
                    right: 0,
                    width: '320px',
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #cbd5e1)',
                    borderRadius: '12px',
                    boxShadow: 'var(--shadow-float)',
                    padding: '16px',
                    zIndex: 100,
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', paddingBottom: '8px', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                    <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                      {lang === 'hi' ? 'केयर रिमाइंडर' : 'Care Reminders'}
                    </div>
                    <button
                      type="button"
                      onClick={() => setRemindersOpen(false)}
                      style={{ background: 'none', border: 'none', fontSize: '13px', cursor: 'pointer', color: 'var(--text-muted, #64748b)' }}
                      aria-label="Close"
                    >
                      ✕
                    </button>
                  </div>

                  {remindersList.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {remindersList.map((rem) => (
                        <div
                          key={rem.id}
                          style={{
                            padding: '10px 12px',
                            borderRadius: '8px',
                            background: 'var(--bg-base, #f8fafc)',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                          }}
                        >
                          <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                            {rem.title}
                          </div>
                          <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', margin: '3px 0 8px' }}>
                            {rem.desc}
                          </div>
                          <button
                            type="button"
                            onClick={rem.action}
                            style={{
                              background: 'var(--accent-teal, #0d9488)',
                              color: '#ffffff',
                              border: 'none',
                              borderRadius: '6px',
                              padding: '5px 10px',
                              fontSize: '11px',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            {rem.actionLabel}
                          </button>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div style={{ padding: '14px 8px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                      {lang === 'hi' ? 'सब ठीक है! कोई लंबित रिमाइंडर नहीं है।' : 'All clear! No pending reminders.'}
                    </div>
                  )}
                </div>
              )}
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

              {/* ─── RECOVERY PLAN CHECKLIST (Brief Sec 6.6) ─── */}
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
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <div
                      style={{
                        width: '28px',
                        height: '28px',
                        borderRadius: '6px',
                        background: 'var(--accent-teal-soft, #ecfdf5)',
                        color: 'var(--accent-teal, #0d9488)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      <IconShieldCheck width={16} height={16} />
                    </div>
                    <div>
                      <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                        {lang === 'hi' ? 'रिकवरी प्लान चेकलिस्ट' : 'Recovery Plan Checklist'}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
                        {lang === 'hi' ? 'डिस्चार्ज सारांश के आधार पर वास्तविक रिकॉर्ड' : 'Factual items verified from your care plan records'}
                      </div>
                    </div>
                  </div>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: '12px',
                      background: 'var(--accent-blue-soft, #eff6ff)',
                      color: 'var(--accent-blue, #0284c7)',
                    }}
                  >
                    {lang === 'hi' ? 'सक्रिय' : 'Active'}
                  </span>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                    gap: '14px',
                  }}
                >
                  {/* Checklist Item 1: Next Appointment */}
                  <div
                    style={{
                      padding: '14px 16px',
                      borderRadius: '10px',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      background: 'var(--bg-base, #f8fafc)',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      gap: '8px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                      <div
                        style={{
                          width: '24px',
                          height: '24px',
                          borderRadius: '6px',
                          background: 'var(--accent-blue-soft, #eff6ff)',
                          color: 'var(--accent-blue, #0284c7)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          flexShrink: 0,
                          marginTop: '2px',
                        }}
                      >
                        <IconCalendar width={14} height={14} />
                      </div>
                      <div>
                        <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                          {lang === 'hi' ? 'फॉलो-अप अपॉइंटमेंट' : 'Follow-up visit'}
                        </div>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                          {todayData?.plan_checklist?.next_appointment?.date || (lang === 'hi' ? 'कोई निर्धारित नहीं' : 'None scheduled')}
                        </div>
                        {todayData?.plan_checklist?.next_appointment?.doctor && (
                          <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                            {todayData.plan_checklist.next_appointment.doctor}
                          </div>
                        )}
                      </div>
                    </div>
                    {todayData?.plan_checklist?.next_appointment?.id && (
                      <button
                        type="button"
                        onClick={() => handleDownloadAppointmentIcs(todayData.plan_checklist.next_appointment.id)}
                        disabled={downloadingIcsId === todayData.plan_checklist.next_appointment.id}
                        style={{
                          alignSelf: 'flex-start',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '4px 10px',
                          borderRadius: '6px',
                          border: '1px solid var(--accent-blue, #0284c7)',
                          background: 'transparent',
                          color: 'var(--accent-blue, #0284c7)',
                          fontSize: '11px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        <IconCalendar width={12} height={12} />
                        <span>{downloadingIcsId === todayData.plan_checklist.next_appointment.id ? (lang === 'hi' ? 'डाउनलोड हो रहा है...' : 'Downloading...') : (lang === 'hi' ? 'कैलेंडर में जोड़ें (.ics)' : 'Add to calendar (.ics)')}</span>
                      </button>
                    )}
                  </div>

                  {/* Checklist Item 2: Medicine Course */}
                  <div
                    style={{
                      padding: '14px 16px',
                      borderRadius: '10px',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      background: 'var(--bg-base, #f8fafc)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                    }}
                  >
                    <div
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '6px',
                        background: 'var(--accent-teal-soft, #ecfdf5)',
                        color: 'var(--accent-teal, #0d9488)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: '2px',
                      }}
                    >
                      <IconPill width={14} height={14} />
                    </div>
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                        {lang === 'hi' ? 'दवा कोर्स' : 'Medicine course'}
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                        {todayData?.plan_checklist?.course_end_date
                          ? (lang === 'hi' ? `${todayData.plan_checklist.course_end_date} तक सक्रिय` : `Active through ${todayData.plan_checklist.course_end_date}`)
                          : (lang === 'hi' ? 'सक्रिय प्रिस्क्रिप्शन' : 'Active prescription course')}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                        {lang === 'hi' ? 'डॉक्टर के निर्देशानुसार' : 'As prescribed in discharge papers'}
                      </div>
                    </div>
                  </div>

                  {/* Checklist Item 3: Check-ins this week */}
                  <div
                    style={{
                      padding: '14px 16px',
                      borderRadius: '10px',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      background: 'var(--bg-base, #f8fafc)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                    }}
                  >
                    <div
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '6px',
                        background: 'var(--success-green-soft, #f0fdf4)',
                        color: 'var(--success-green, #059669)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: '2px',
                      }}
                    >
                      <IconCheck width={14} height={14} />
                    </div>
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                        {lang === 'hi' ? 'इस सप्ताह चेक-इन' : 'Check-ins this week'}
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                        {todayData?.plan_checklist?.checkins_this_week || '0 of 7 days'}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                        {lang === 'hi' ? 'केयर टीम को दैनिक स्थिति भेजें' : 'Reported to your care team'}
                      </div>
                    </div>
                  </div>

                  {/* Checklist Item 4: Day after discharge */}
                  <div
                    style={{
                      padding: '14px 16px',
                      borderRadius: '10px',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      background: 'var(--bg-base, #f8fafc)',
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '10px',
                    }}
                  >
                    <div
                      style={{
                        width: '24px',
                        height: '24px',
                        borderRadius: '6px',
                        background: 'var(--accent-blue-soft, #eff6ff)',
                        color: 'var(--accent-blue, #0284c7)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        marginTop: '2px',
                      }}
                    >
                      <IconActivity width={14} height={14} />
                    </div>
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                        {lang === 'hi' ? 'रिकवरी अवधि' : 'Recovery progress'}
                      </div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                        {lang === 'hi'
                          ? `डिस्चार्ज के बाद दिन ${todayData?.plan_checklist?.day_after_discharge || 1}`
                          : `Day ${todayData?.plan_checklist?.day_after_discharge || 1} after discharge`}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                        {lang === 'hi' ? 'घर पर स्वास्थ्य लाभ' : 'Post-hospital recovery at home'}
                      </div>
                    </div>
                  </div>
                </div>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                    {lang === 'hi' ? 'इस सप्ताह का संक्षिप्त विवरण' : 'This week'}
                  </div>
                  <button
                    type="button"
                    onClick={() => setActiveNav('calendar')}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--accent-teal, #0d9488)',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    {lang === 'hi' ? 'पूरा कैलेंडर देखें →' : 'View full calendar →'}
                  </button>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: '10px' }}>
                  {(todayData?.week || []).map((wDay) => (
                    <div
                      key={wDay.date}
                      onClick={() => {
                        setSelectedCalendarDate(wDay.date);
                        setActiveNav('calendar');
                      }}
                      style={{
                        padding: '12px 10px',
                        borderRadius: '8px',
                        border: wDay.is_today ? '2px solid var(--accent-blue, #0284c7)' : '1px solid var(--border-subtle, #e2e8f0)',
                        background: wDay.is_today ? 'var(--accent-blue-soft, #eff6ff)' : 'var(--bg-base, #f8fafc)',
                        textAlign: 'center',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                      title="Click to view day in calendar"
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

          {/* ─── TAB: MY CALENDAR (Brief Sec 6.3 & 8.3) ─── */}
          {activeNav === 'calendar' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              {/* Header and Month Controls */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 24px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <div style={{ fontSize: '10px', color: 'var(--text-muted, #94a3b8)', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    {lang === 'hi' ? 'शेड्यूल और अपॉइंटमेंट्स' : 'SCHEDULE & APPOINTMENTS'}
                  </div>
                  <h1 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: '2px 0 0' }}>
                    {lang === 'hi' ? 'मेरा कैलेंडर' : 'My calendar'}
                  </h1>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <button
                    type="button"
                    onClick={handleJumpToToday}
                    style={{
                      padding: '7px 14px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-strong, #cbd5e1)',
                      background: 'var(--bg-base, #f8fafc)',
                      color: 'var(--text-primary, #0f172a)',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    {lang === 'hi' ? 'आज' : 'Today'}
                  </button>

                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      background: 'var(--bg-base, #f8fafc)',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      padding: '2px',
                    }}
                  >
                    <button
                      type="button"
                      onClick={handlePrevMonth}
                      style={{
                        padding: '6px 12px',
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '14px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        borderRadius: '6px',
                      }}
                      title="Previous month"
                      aria-label="Previous month"
                    >
                      ‹
                    </button>
                    <span
                      style={{
                        fontSize: '13px',
                        fontWeight: 700,
                        color: 'var(--text-primary, #0f172a)',
                        padding: '0 12px',
                        minWidth: '130px',
                        textAlign: 'center',
                      }}
                    >
                      {calendarData?.month_name || calendarMonth}
                    </span>
                    <button
                      type="button"
                      onClick={handleNextMonth}
                      style={{
                        padding: '6px 12px',
                        border: 'none',
                        background: 'transparent',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '14px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        borderRadius: '6px',
                      }}
                      title="Next month"
                      aria-label="Next month"
                    >
                      ›
                    </button>
                  </div>
                </div>
              </div>

              {/* Two Column Layout: Left Month Grid & Upcoming; Right Day Inspection Sheet */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1.4fr 1fr',
                  gap: '24px',
                  alignItems: 'start',
                }}
              >
                {/* Left Column: Month Grid */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  <div
                    style={{
                      background: 'var(--bg-surface, #ffffff)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      borderRadius: '12px',
                      padding: '22px 24px',
                      boxShadow: 'var(--shadow-card)',
                    }}
                  >
                    {/* Weekday headers */}
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(7, 1fr)',
                        gap: '6px',
                        marginBottom: '10px',
                        textAlign: 'center',
                      }}
                    >
                      {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((dayName, idx) => {
                        const hindiNames = ['सोम', 'मंगल', 'बुध', 'गुरु', 'शुक्र', 'शनि', 'रवि'];
                        return (
                          <div
                            key={dayName}
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              color: 'var(--text-muted, #94a3b8)',
                              textTransform: 'uppercase',
                              padding: '4px 0',
                            }}
                          >
                            {lang === 'hi' ? hindiNames[idx] : dayName}
                          </div>
                        );
                      })}
                    </div>

                    {/* Month Days Grid */}
                    {calendarLoading ? (
                      <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                        {lang === 'hi' ? 'कैलेंडर लोड हो रहा है...' : 'Loading calendar...'}
                      </div>
                    ) : (
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(7, 1fr)',
                          gap: '6px',
                        }}
                      >
                        {/* Pad leading empty cells for day_of_week of 1st day */}
                        {calendarData?.days?.length > 0 &&
                          Array.from({ length: calendarData.days[0].day_of_week }).map((_, i) => (
                            <div key={`empty-${i}`} style={{ height: '70px', background: 'transparent' }} />
                          ))}

                        {/* Actual day cells */}
                        {(calendarData?.days || []).map((d) => {
                          const isSelected = selectedCalendarDate === d.date;
                          const isToday = d.is_today;

                          // Accessible label
                          const doseStatusText =
                            d.planned > 0
                              ? `${d.taken} of ${d.planned} medicines taken`
                              : 'No medicines';
                          const apptText = d.has_appointment ? 'Appointment scheduled' : '';
                          const checkinText = d.has_checkin ? 'Check-in reported' : '';
                          const ariaLabel = `${d.date}, ${doseStatusText}, ${apptText}, ${checkinText}`.trim();

                          return (
                            <button
                              key={d.date}
                              type="button"
                              onClick={() => handleSelectDay(d.date)}
                              aria-label={ariaLabel}
                              style={{
                                height: '72px',
                                padding: '6px 8px',
                                borderRadius: '8px',
                                border: isSelected
                                  ? '2px solid var(--accent-teal, #0d9488)'
                                  : isToday
                                  ? '2px solid var(--accent-blue, #0284c7)'
                                  : '1px solid var(--border-subtle, #e2e8f0)',
                                background: isSelected
                                  ? 'var(--accent-teal-soft, #ecfdf5)'
                                  : isToday
                                  ? 'var(--accent-blue-soft, #eff6ff)'
                                  : 'var(--bg-base, #f8fafc)',
                                display: 'flex',
                                flexDirection: 'column',
                                justifyContent: 'space-between',
                                cursor: 'pointer',
                                textAlign: 'left',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                                <span
                                  style={{
                                    fontSize: '13px',
                                    fontWeight: isToday || isSelected ? 800 : 600,
                                    color: isToday
                                      ? 'var(--accent-blue, #0284c7)'
                                      : 'var(--text-primary, #0f172a)',
                                  }}
                                >
                                  {d.day}
                                </span>
                                {d.has_appointment && (
                                  <span
                                    title="Appointment scheduled"
                                    style={{
                                      width: '6px',
                                      height: '6px',
                                      borderRadius: '50%',
                                      background: 'var(--accent-blue, #0284c7)',
                                    }}
                                  />
                                )}
                              </div>

                              {/* Indicators Row */}
                              <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '4px' }}>
                                {d.is_future && d.planned > 0 ? (
                                  <span
                                    style={{
                                      fontSize: '10px',
                                      fontWeight: 700,
                                      color: 'var(--text-muted, #64748b)',
                                      fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                                    }}
                                  >
                                    {d.planned}rx
                                  </span>
                                ) : d.planned > 0 ? (
                                  <div
                                    title={`${d.taken} of ${d.planned} doses taken`}
                                    style={{
                                      width: '7px',
                                      height: '7px',
                                      borderRadius: '50%',
                                      background:
                                        d.taken >= d.planned
                                          ? 'var(--success-green, #059669)'
                                          : 'var(--warning-amber, #d97706)',
                                    }}
                                  />
                                ) : null}

                                {d.has_checkin && (
                                  <div
                                    title={`Check-in reported${d.max_pain !== null ? ` (Pain: ${d.max_pain}/10)` : ''}`}
                                    style={{
                                      width: '7px',
                                      height: '7px',
                                      borderRadius: '50%',
                                      background: 'var(--accent-teal, #0d9488)',
                                    }}
                                  />
                                )}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}

                    {/* Legend */}
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        flexWrap: 'wrap',
                        gap: '16px',
                        marginTop: '18px',
                        paddingTop: '14px',
                        borderTop: '1px solid var(--border-subtle, #e2e8f0)',
                        fontSize: '11px',
                        color: 'var(--text-muted, #64748b)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success-green, #059669)' }} />
                        <span>{lang === 'hi' ? 'सभी दवाइयाँ लीं' : 'All medicines taken'}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--warning-amber, #d97706)' }} />
                        <span>{lang === 'hi' ? 'छूटी या लंबित' : 'Doses missed / unconfirmed'}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-blue, #0284c7)' }} />
                        <span>{lang === 'hi' ? 'अपॉइंटमेंट' : 'Appointment'}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-teal, #0d9488)' }} />
                        <span>{lang === 'hi' ? 'दैनिक चेक-इन' : 'Daily check-in'}</span>
                      </div>
                    </div>
                  </div>

                  {/* Upcoming Appointments List */}
                  <div
                    style={{
                      background: 'var(--bg-surface, #ffffff)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      borderRadius: '12px',
                      padding: '22px 24px',
                      boxShadow: 'var(--shadow-card)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <IconCalendar width={16} height={16} style={{ color: 'var(--accent-blue, #0284c7)' }} />
                        <h2 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: 0 }}>
                          {lang === 'hi' ? 'आगामी फॉलो-अप अपॉइंटमेंट्स' : 'Upcoming Follow-up Appointments'}
                        </h2>
                      </div>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                        {calendarData?.upcoming_appointments?.length || 0} {lang === 'hi' ? 'निर्धारित' : 'scheduled'}
                      </span>
                    </div>

                    {calendarData?.upcoming_appointments?.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {calendarData.upcoming_appointments.map((appt) => (
                          <div
                            key={appt.id}
                            style={{
                              padding: '14px 16px',
                              borderRadius: '10px',
                              border: '1px solid var(--border-subtle, #e2e8f0)',
                              background: 'var(--bg-base, #f8fafc)',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              flexWrap: 'wrap',
                              gap: '12px',
                            }}
                          >
                            <div>
                              <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                                {appt.formatted_date}
                              </div>
                              <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
                                {appt.doctor_name} · <span style={{ color: 'var(--text-muted, #64748b)' }}>{appt.department}</span>
                              </div>
                              <div style={{ fontSize: '11px', color: 'var(--accent-blue, #0284c7)', fontWeight: 600, marginTop: '2px' }}>
                                {appt.type}
                              </div>
                            </div>

                            <button
                              type="button"
                              onClick={() => handleDownloadAppointmentIcs(appt.id)}
                              disabled={downloadingIcsId === appt.id}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '8px 14px',
                                borderRadius: '8px',
                                border: '1px solid var(--accent-blue, #0284c7)',
                                background: 'transparent',
                                color: 'var(--accent-blue, #0284c7)',
                                fontSize: '12px',
                                fontWeight: 700,
                                cursor: 'pointer',
                                minHeight: '38px',
                              }}
                            >
                              <IconCalendar width={14} height={14} />
                              <span>
                                {downloadingIcsId === appt.id
                                  ? (lang === 'hi' ? 'डाउनलोड हो रहा है...' : 'Downloading...')
                                  : (lang === 'hi' ? 'अपने कैलेंडर में जोड़ें (.ics)' : 'Add to my calendar (.ics)')}
                              </span>
                            </button>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div style={{ textAlign: 'center', padding: '24px 0', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                        {lang === 'hi' ? 'कोई आगामी अपॉइंटमेंट निर्धारित नहीं है।' : 'No upcoming appointments scheduled.'}
                      </div>
                    )}
                  </div>
                </div>

                {/* Right Column: Day Inspection Sheet */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '22px 24px',
                    boxShadow: 'var(--shadow-card)',
                    position: 'sticky',
                    top: '84px',
                  }}
                >
                  <div style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)', paddingBottom: '14px', marginBottom: '16px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 700, textTransform: 'uppercase' }}>
                      {lang === 'hi' ? 'दिन का विवरण' : 'DAY INSPECTION'}
                    </div>
                    <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                      {dayDetail?.formatted_date || selectedCalendarDate}
                    </div>
                  </div>

                  {dayDetailLoading ? (
                    <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                      {lang === 'hi' ? 'विवरण लोड हो रहा है...' : 'Loading day detail...'}
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                      {/* Section 1: Prescribed Doses */}
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 800, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', marginBottom: '10px' }}>
                          {lang === 'hi' ? 'निर्धारित दवाइयाँ' : 'PRESCRIBED DOSES'} ({dayDetail?.doses?.length || 0})
                        </div>
                        {dayDetail?.doses?.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {dayDetail.doses.map((dose) => (
                              <div
                                key={dose.id}
                                style={{
                                  padding: '10px 12px',
                                  borderRadius: '8px',
                                  border: '1px solid var(--border-subtle, #e2e8f0)',
                                  background: 'var(--bg-base, #f8fafc)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  justifyContent: 'space-between',
                                }}
                              >
                                <div>
                                  <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                                    {dose.medicine}
                                  </div>
                                  <div style={{ fontSize: '11px', color: 'var(--text-secondary, #475569)' }}>
                                    {dose.scheduled_time} · {dose.dose_instructions}
                                  </div>
                                  {dose.patient_note && (
                                    <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontStyle: 'italic', marginTop: '2px' }}>
                                      Note: {dose.patient_note}
                                    </div>
                                  )}
                                </div>
                                <span
                                  style={{
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    padding: '3px 8px',
                                    borderRadius: '12px',
                                    background:
                                      dose.status === 'Taken_Confirmed' || dose.status === 'Taken'
                                        ? 'var(--success-green-soft, #f0fdf4)'
                                        : dose.status === 'Skipped'
                                        ? 'var(--bg-card-hover, #f1f5f9)'
                                        : 'var(--warning-amber-soft, #fffbeb)',
                                    color:
                                      dose.status === 'Taken_Confirmed' || dose.status === 'Taken'
                                        ? 'var(--success-green-text, #166534)'
                                        : dose.status === 'Skipped'
                                        ? 'var(--text-muted, #64748b)'
                                        : 'var(--warning-amber-text, #92400e)',
                                  }}
                                >
                                  {dose.status === 'Taken_Confirmed'
                                    ? (lang === 'hi' ? 'ले ली' : 'Taken')
                                    : dose.status === 'Skipped'
                                    ? (lang === 'hi' ? 'छोड़ी गई' : 'Skipped')
                                    : (lang === 'hi' ? 'लंबित' : 'Not confirmed')}
                                </span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontStyle: 'italic', padding: '6px 0' }}>
                            {lang === 'hi' ? 'इस दिन कोई दवा निर्धारित नहीं थी।' : 'No medicines scheduled on this day.'}
                          </div>
                        )}
                      </div>

                      {/* Section 2: Appointments */}
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 800, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', marginBottom: '10px' }}>
                          {lang === 'hi' ? 'अपॉइंटमेंट्स' : 'APPOINTMENTS'} ({dayDetail?.appointments?.length || 0})
                        </div>
                        {dayDetail?.appointments?.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {dayDetail.appointments.map((appt) => (
                              <div
                                key={appt.id}
                                style={{
                                  padding: '10px 12px',
                                  borderRadius: '8px',
                                  border: '1px solid var(--border-subtle, #e2e8f0)',
                                  background: 'var(--bg-base, #f8fafc)',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                  <div>
                                    <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                                      {appt.doctor_name}
                                    </div>
                                    <div style={{ fontSize: '11px', color: 'var(--text-secondary, #475569)' }}>
                                      {appt.formatted_time} · {appt.department}
                                    </div>
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() => handleDownloadAppointmentIcs(appt.id)}
                                    disabled={downloadingIcsId === appt.id}
                                    style={{
                                      padding: '4px 8px',
                                      borderRadius: '6px',
                                      border: '1px solid var(--accent-blue, #0284c7)',
                                      background: 'transparent',
                                      color: 'var(--accent-blue, #0284c7)',
                                      fontSize: '11px',
                                      fontWeight: 700,
                                      cursor: 'pointer',
                                    }}
                                  >
                                    .ics
                                  </button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontStyle: 'italic', padding: '6px 0' }}>
                            {lang === 'hi' ? 'कोई अपॉइंटमेंट निर्धारित नहीं था।' : 'No appointments scheduled.'}
                          </div>
                        )}
                      </div>

                      {/* Section 3: Check-in / Symptoms */}
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 800, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', marginBottom: '10px' }}>
                          {lang === 'hi' ? 'दैनिक चेक-इन और दर्द' : 'CHECK-IN & SYMPTOMS'} ({dayDetail?.checkins?.length || 0})
                        </div>
                        {dayDetail?.checkins?.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            {dayDetail.checkins.map((chk) => (
                              <div
                                key={chk.id}
                                style={{
                                  padding: '10px 12px',
                                  borderRadius: '8px',
                                  border: '1px solid var(--border-subtle, #e2e8f0)',
                                  background: 'var(--bg-base, #f8fafc)',
                                }}
                              >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                  <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                                    {chk.reported_at}
                                  </span>
                                  {chk.pain_level !== null && (
                                    <span
                                      style={{
                                        fontSize: '12px',
                                        fontWeight: 800,
                                        fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                                        color:
                                          chk.pain_level >= 7
                                            ? 'var(--alert-red, #dc2626)'
                                            : chk.pain_level >= 4
                                            ? 'var(--warning-amber, #d97706)'
                                            : 'var(--success-green, #059669)',
                                      }}
                                    >
                                      Pain: {chk.pain_level}/10
                                    </span>
                                  )}
                                </div>
                                {chk.note && (
                                  <div style={{ fontSize: '12px', color: 'var(--text-primary, #0f172a)', marginTop: '4px' }}>
                                    {chk.note}
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontStyle: 'italic', padding: '6px 0' }}>
                            {lang === 'hi' ? 'इस दिन कोई चेक-इन दर्ज नहीं किया गया।' : 'No check-in recorded on this day.'}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* ─── 9. TAB: CHECK-IN (Phase 3 Upgrade: Brief Sec 6.4 & 8.4) ─── */}
          {activeNav === 'checkin' && (
            <div style={{ maxWidth: '740px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Check-in Form Card */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '28px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                {/* Header */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: '8px',
                        background: 'var(--accent-teal-subtle, #ccfbf1)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'var(--accent-teal, #0d9488)',
                      }}
                    >
                      <IconShieldCheck width={20} height={20} />
                    </div>
                    <div>
                      <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: 'var(--text-primary, #0f172a)' }}>
                        {lang === 'hi' ? 'दैनिक स्वास्थ्य चेक-इन' : 'Daily health check-in'}
                      </h2>
                      <p style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', margin: '2px 0 0 0' }}>
                        {lang === 'hi'
                          ? '30 सेकंड से कम समय लगता है · सीधे आपकी देखभाल टीम को भेजा जाता है'
                          : 'Takes less than 30 seconds · Sent directly to your care team'}
                      </p>
                    </div>
                  </div>

                  {!checkinSuccessData && (
                    <button
                      type="button"
                      onClick={handleResetCheckinForm}
                      style={{
                        background: 'none',
                        border: 'none',
                        fontSize: '12px',
                        color: 'var(--text-muted, #64748b)',
                        cursor: 'pointer',
                        textDecoration: 'underline',
                      }}
                    >
                      {lang === 'hi' ? 'रीसेट करें' : 'Clear draft'}
                    </button>
                  )}
                </div>

                {/* POST-SUBMISSION CONFIRMATION STATE */}
                {checkinSuccessData ? (
                  <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
                    {/* Emergency notice if emergency flag was hit */}
                    {checkinSuccessData.res?.emergency && (
                      <div
                        style={{
                          background: 'var(--alert-red-soft, #fef2f2)',
                          border: '2px solid var(--alert-red, #dc2626)',
                          borderRadius: '10px',
                          padding: '16px',
                          color: 'var(--alert-red-text, #991b1b)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                          <IconAlertTriangle width={20} height={20} style={{ color: 'var(--alert-red, #dc2626)' }} />
                          <strong style={{ fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            {lang === 'hi' ? 'आपातकालीन सूचना' : 'Emergency Notice'}
                          </strong>
                        </div>
                        <p style={{ fontSize: '13px', margin: '0 0 8px 0', lineHeight: 1.5, fontWeight: 600 }}>
                          {lang === 'hi'
                            ? 'यदि आपको सीने में तेज दर्द, सांस लेने में अत्यधिक तकलीफ या अचानक कमजोरी महसूस हो, तो तुरंत 112 पर कॉल करें।'
                            : 'If you have severe chest pain, shortness of breath, or sudden collapse, call 112 immediately.'}
                        </p>
                        {checkinSuccessData.res?.guidance && (
                          <div
                            style={{
                              fontSize: '12px',
                              background: 'rgba(255, 255, 255, 0.7)',
                              padding: '10px 12px',
                              borderRadius: '6px',
                              border: '1px solid rgba(220, 38, 38, 0.2)',
                            }}
                          >
                            {checkinSuccessData.res.guidance}
                          </div>
                        )}
                        <div style={{ marginTop: '8px', fontSize: '12px', fontWeight: 700 }}>
                          {lang === 'hi' ? 'आपातकालीन सहायता: 112' : 'Emergency Assistance: Call 112'}
                        </div>
                      </div>
                    )}

                    {/* Factual Confirmation Card */}
                    <div
                      style={{
                        background: 'var(--success-green-soft, #f0fdf4)',
                        border: '1px solid var(--success-green, #bbf7d0)',
                        borderRadius: '10px',
                        padding: '18px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                        <div
                          style={{
                            width: '24px',
                            height: '24px',
                            borderRadius: '50%',
                            background: 'var(--success-green, #10b981)',
                            color: '#ffffff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          <IconCheck width={14} height={14} />
                        </div>
                        <h3 style={{ fontSize: '15px', fontWeight: 800, margin: 0, color: 'var(--success-green-text, #166534)' }}>
                          {lang === 'hi' ? 'आपकी स्थिति केयर टीम को भेज दी गई है' : 'Sent to your care team'}
                        </h3>
                      </div>
                      <p style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', margin: '0 0 14px 0' }}>
                        {lang === 'hi'
                          ? `रिपोर्ट आईडी #${checkinSuccessData.res?.report_id || ''} दर्ज कर ली गई है। डॉक्टर और नर्सिंग स्टाफ इसे अपने बोर्ड पर देख सकते हैं।`
                          : `Report #${checkinSuccessData.res?.report_id || ''} recorded. Your doctor and nurses can see this update on their clinical triage board.`}
                      </p>

                      <div
                        style={{
                          background: 'var(--bg-surface, #ffffff)',
                          border: '1px solid var(--border-subtle, #e2e8f0)',
                          borderRadius: '8px',
                          padding: '12px 14px',
                          display: 'grid',
                          gridTemplateColumns: '1fr 1fr',
                          gap: '10px',
                          fontSize: '12px',
                        }}
                      >
                        <div>
                          <span style={{ color: 'var(--text-muted, #64748b)' }}>{lang === 'hi' ? 'दर्द का स्तर:' : 'Pain score:'}</span>{' '}
                          <strong>
                            {checkinSuccessData.payload.pain_level !== null ? `${checkinSuccessData.payload.pain_level} / 10` : 'Not rated'}
                          </strong>
                        </div>
                        <div>
                          <span style={{ color: 'var(--text-muted, #64748b)' }}>{lang === 'hi' ? 'कल की तुलना में:' : 'Vs yesterday:'}</span>{' '}
                          <strong style={{ textTransform: 'capitalize' }}>
                            {checkinSuccessData.payload.trend || 'Not specified'}
                          </strong>
                        </div>
                        <div style={{ gridColumn: '1 / -1' }}>
                          <span style={{ color: 'var(--text-muted, #64748b)' }}>{lang === 'hi' ? 'लक्षण:' : 'Symptoms:'}</span>{' '}
                          <strong>
                            {checkinSuccessData.payload.chips?.length > 0
                              ? checkinSuccessData.payload.chips.join(', ')
                              : 'None selected'}
                          </strong>
                        </div>
                        {checkinSuccessData.payload.sites?.length > 0 && (
                          <div style={{ gridColumn: '1 / -1' }}>
                            <span style={{ color: 'var(--text-muted, #64748b)' }}>{lang === 'hi' ? 'स्थान:' : 'Locations:'}</span>{' '}
                            <strong>{checkinSuccessData.payload.sites.join(', ')}</strong>
                          </div>
                        )}
                        {checkinSuccessData.payload.text && (
                          <div style={{ gridColumn: '1 / -1', borderTop: '1px solid var(--border-subtle, #e2e8f0)', paddingTop: '8px' }}>
                            <span style={{ color: 'var(--text-muted, #64748b)' }}>{lang === 'hi' ? 'विवरण:' : 'Notes:'}</span>{' '}
                            <span>{checkinSuccessData.payload.text}</span>
                          </div>
                        )}
                      </div>

                      <div style={{ display: 'flex', gap: '10px', marginTop: '16px' }}>
                        <button
                          type="button"
                          onClick={handleResetCheckinForm}
                          style={{
                            padding: '8px 16px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-strong, #cbd5e1)',
                            background: 'var(--bg-surface, #ffffff)',
                            color: 'var(--text-primary, #0f172a)',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          {lang === 'hi' ? 'दूसरा चेक-इन भेजें' : 'Submit another check-in'}
                        </button>
                        <button
                          type="button"
                          onClick={() => setActiveNav('recovery')}
                          style={{
                            padding: '8px 16px',
                            borderRadius: '6px',
                            border: 'none',
                            background: 'var(--navy-deep, #0b1528)',
                            color: '#ffffff',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          {lang === 'hi' ? 'होम पर लौटें' : 'Return to Overview'}
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  /* ACTIVE CHECK-IN FORM */
                  <form onSubmit={handleCheckinSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '22px', marginTop: '18px' }}>
                    {/* 1. Pain Scale (0 to 10) */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                        <label style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                          1. {lang === 'hi' ? 'दर्द का स्तर (0 से 10)' : 'Pain scale (0 to 10)'}
                        </label>
                        <div
                          style={{
                            fontSize: '12px',
                            fontWeight: 800,
                            padding: '3px 10px',
                            borderRadius: '999px',
                            background:
                              painLevel >= 7
                                ? 'var(--alert-red-soft, #fef2f2)'
                                : painLevel >= 4
                                ? 'var(--warning-amber-soft, #fffbeb)'
                                : 'var(--success-green-soft, #f0fdf4)',
                            color:
                              painLevel >= 7
                                ? 'var(--alert-red-text, #991b1b)'
                                : painLevel >= 4
                                ? 'var(--warning-amber-text, #b45309)'
                                : 'var(--success-green-text, #166534)',
                            border: `1px solid ${
                              painLevel >= 7
                                ? 'var(--alert-red, #dc2626)'
                                : painLevel >= 4
                                ? 'var(--warning-amber, #d97706)'
                                : 'var(--success-green, #10b981)'
                            }`,
                          }}
                        >
                          {painLevel} / 10 ·{' '}
                          {painLevel === 0
                            ? lang === 'hi' ? 'कोई दर्द नहीं' : 'No pain'
                            : painLevel <= 3
                            ? lang === 'hi' ? 'हल्का' : 'Mild'
                            : painLevel <= 6
                            ? lang === 'hi' ? 'मध्यम' : 'Moderate'
                            : lang === 'hi' ? 'अत्यधिक दर्द' : 'Severe / Worst pain'}
                        </div>
                      </div>

                      {/* 11 Tappable Number Buttons */}
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: 'repeat(11, minmax(0, 1fr))',
                          gap: '6px',
                        }}
                      >
                        {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => {
                          const isSelected = painLevel === num;
                          const activeColor =
                            num === 0 ? '#10b981' : num <= 3 ? '#0d9488' : num <= 6 ? '#d97706' : '#dc2626';
                          const numBg = isSelected ? activeColor : 'var(--bg-surface-alt, #f8fafc)';
                          const numBorder = isSelected ? activeColor : 'var(--border-subtle, #e2e8f0)';

                          return (
                            <button
                              key={num}
                              type="button"
                              onClick={() => setPainLevel(num)}
                              aria-label={`Pain score ${num}`}
                              style={{
                                height: '46px',
                                borderRadius: '8px',
                                border: `2px solid ${isSelected ? numBorder : 'var(--border-subtle, #e2e8f0)'}`,
                                background: isSelected ? numBg : 'var(--bg-surface-alt, #f8fafc)',
                                color: isSelected ? '#ffffff' : 'var(--text-primary, #0f172a)',
                                fontSize: '15px',
                                fontWeight: isSelected ? 800 : 600,
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                              }}
                            >
                              {num}
                            </button>
                          );
                        })}
                      </div>

                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          fontSize: '11px',
                          color: 'var(--text-muted, #64748b)',
                          marginTop: '6px',
                          padding: '0 2px',
                        }}
                      >
                        <span>0 = {lang === 'hi' ? 'कोई दर्द नहीं' : 'No pain'}</span>
                        <span>10 = {lang === 'hi' ? 'अत्यधिक दर्द' : 'Worst pain possible'}</span>
                      </div>
                    </div>

                    {/* 2. Quick Symptoms (Multi-select chips) */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '8px' }}>
                        2. {lang === 'hi' ? 'त्वरित लक्षण (लागू होने वाले सभी चुनें)' : 'Quick symptoms (tap all that apply)'}
                      </label>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {CHECKIN_SYMPTOM_CHIPS.map((chip) => {
                          const isSelected = selectedChips.includes(chip.id);
                          return (
                            <button
                              key={chip.id}
                              type="button"
                              onClick={() => handleToggleChip(chip.id)}
                              style={{
                                padding: '8px 14px',
                                borderRadius: '20px',
                                border: `1.5px solid ${
                                  isSelected
                                    ? chip.emergency
                                      ? 'var(--alert-red, #dc2626)'
                                      : 'var(--accent-teal, #0d9488)'
                                    : 'var(--border-subtle, #e2e8f0)'
                                }`,
                                background: isSelected
                                  ? chip.emergency
                                    ? 'var(--alert-red-soft, #fef2f2)'
                                    : 'var(--accent-teal-subtle, #ccfbf1)'
                                  : 'var(--bg-surface-alt, #f8fafc)',
                                color: isSelected
                                  ? chip.emergency
                                    ? 'var(--alert-red-text, #991b1b)'
                                    : 'var(--accent-teal, #0d9488)'
                                  : 'var(--text-secondary, #475569)',
                                fontSize: '12px',
                                fontWeight: isSelected ? 700 : 500,
                                cursor: 'pointer',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '6px',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              {chip.emergency && (
                                <span
                                  style={{
                                    width: '6px',
                                    height: '6px',
                                    borderRadius: '50%',
                                    background: 'var(--alert-red, #dc2626)',
                                  }}
                                />
                              )}
                              <span>{chip[lang] || chip.en}</span>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* 3. Where is it? (Optional Location Chips) */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '8px' }}>
                        3. {lang === 'hi' ? 'दर्द या परेशानी कहां है? (वैकल्पिक)' : 'Where is it? (optional)'}
                      </label>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {CHECKIN_LOCATION_CHIPS.map((loc) => {
                          const isSelected = selectedSites.includes(loc.id);
                          return (
                            <button
                              key={loc.id}
                              type="button"
                              onClick={() => handleToggleSite(loc.id)}
                              style={{
                                padding: '6px 12px',
                                borderRadius: '16px',
                                border: `1.5px solid ${
                                  isSelected ? 'var(--navy-deep, #0b1528)' : 'var(--border-subtle, #e2e8f0)'
                                }`,
                                background: isSelected ? 'var(--navy-deep, #0b1528)' : 'var(--bg-surface-alt, #f8fafc)',
                                color: isSelected ? '#ffffff' : 'var(--text-secondary, #475569)',
                                fontSize: '12px',
                                fontWeight: isSelected ? 700 : 500,
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              {loc[lang] || loc.en}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* 4. Compared with yesterday (Optional) */}
                    <div>
                      <label style={{ display: 'block', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '8px' }}>
                        4. {lang === 'hi' ? 'कल की तुलना में (वैकल्पिक)' : 'Compared with yesterday (optional)'}
                      </label>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
                        {CHECKIN_TRENDS.map((t) => {
                          const isSelected = trend === t.id;
                          return (
                            <button
                              key={t.id}
                              type="button"
                              onClick={() => handleToggleTrend(t.id)}
                              style={{
                                padding: '10px',
                                borderRadius: '8px',
                                border: `1.5px solid ${
                                  isSelected ? 'var(--accent-teal, #0d9488)' : 'var(--border-subtle, #e2e8f0)'
                                }`,
                                background: isSelected ? 'var(--accent-teal-subtle, #ccfbf1)' : 'var(--bg-surface-alt, #f8fafc)',
                                color: isSelected ? 'var(--accent-teal, #0d9488)' : 'var(--text-secondary, #475569)',
                                fontSize: '13px',
                                fontWeight: isSelected ? 800 : 600,
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                              }}
                            >
                              {t[lang] || t.en}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    {/* 5. Add details (Optional text + Voice Input) */}
                    <div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <label style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                          5. {lang === 'hi' ? 'अतिरिक्त विवरण (वैकल्पिक)' : 'Add details (optional)'}
                        </label>
                        {speechSupported && (
                          <button
                            type="button"
                            onClick={toggleSpeechRecognition}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '6px',
                              padding: '5px 12px',
                              borderRadius: '6px',
                              border: isListening ? '1px solid #ef4444' : '1px solid var(--border-subtle, #e2e8f0)',
                              background: isListening ? '#fef2f2' : 'var(--bg-surface-alt, #f8fafc)',
                              color: isListening ? '#dc2626' : 'var(--text-secondary, #475569)',
                              fontSize: '12px',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            <IconMic width={14} height={14} style={{ color: isListening ? '#dc2626' : 'inherit' }} />
                            <span>
                              {isListening
                                ? (lang === 'hi' ? 'सुन रहे हैं...' : 'Listening...')
                                : (lang === 'hi' ? 'बोलकर बताएं' : 'Voice input')}
                            </span>
                          </button>
                        )}
                      </div>

                      <textarea
                        rows="3"
                        maxLength={1000}
                        value={symptomText}
                        onChange={(e) => setSymptomText(e.target.value)}
                        placeholder={
                          lang === 'hi'
                            ? 'उदा. दोपहर के भोजन के बाद हल्का दर्द हुआ, कोई सांस की समस्या नहीं...'
                            : 'e.g. A little tired after walking, no chest pain, dressing is clean...'
                        }
                        style={{
                          width: '100%',
                          padding: '12px',
                          borderRadius: '8px',
                          border: '1px solid var(--border-strong, #cbd5e1)',
                          fontSize: '13px',
                          background: 'var(--bg-input, #ffffff)',
                          color: 'var(--text-primary, #0f172a)',
                          resize: 'vertical',
                          fontFamily: 'inherit',
                          lineHeight: 1.5,
                        }}
                      />
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          fontSize: '11px',
                          color: 'var(--text-muted, #64748b)',
                          marginTop: '4px',
                        }}
                      >
                        <span>
                          {inputMethod === 'Voice_Transcript' && (
                            <span style={{ color: 'var(--accent-teal, #0d9488)', fontWeight: 600 }}>
                              ✓ {lang === 'hi' ? 'आवाज से ट्रांसक्रिप्ट किया गया' : 'Voice transcript recorded'}
                            </span>
                          )}
                        </span>
                        <span>{symptomText.length} / 1000</span>
                      </div>
                    </div>

                    {/* Error Notice */}
                    {checkinError && (
                      <div
                        style={{
                          background: 'var(--alert-red-soft, #fef2f2)',
                          border: '1px solid var(--alert-red, #dc2626)',
                          borderRadius: '8px',
                          padding: '12px 16px',
                          color: 'var(--alert-red-text, #991b1b)',
                          fontSize: '13px',
                          fontWeight: 600,
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span>{checkinError}</span>
                        <button
                          type="button"
                          onClick={handleCheckinSubmit}
                          style={{
                            padding: '4px 10px',
                            background: 'var(--alert-red, #dc2626)',
                            color: '#ffffff',
                            border: 'none',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          {lang === 'hi' ? 'पुनः प्रयास' : 'Retry'}
                        </button>
                      </div>
                    )}

                    {/* Sticky Bottom Submit Button */}
                    <button
                      type="submit"
                      disabled={checkinSubmitting}
                      style={{
                        padding: '14px 20px',
                        borderRadius: '10px',
                        border: 'none',
                        background: 'var(--navy-deep, #0b1528)',
                        color: '#ffffff',
                        fontSize: '14px',
                        fontWeight: 700,
                        cursor: checkinSubmitting ? 'not-allowed' : 'pointer',
                        opacity: checkinSubmitting ? 0.7 : 1,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '8px',
                        boxShadow: 'var(--shadow-card)',
                        transition: 'background 0.15s ease',
                      }}
                    >
                      <IconSend width={16} height={16} />
                      <span>
                        {checkinSubmitting
                          ? (lang === 'hi' ? 'भेजा जा रहा है...' : 'Sending to care team...')
                          : (lang === 'hi' ? 'केयर टीम को भेजें' : 'Send to my care team')}
                      </span>
                    </button>
                  </form>
                )}
              </div>

              {/* 14-DAY CHECK-IN HISTORY CARD (Brief Sec 6.4 & 8.4) */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '24px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <IconClock width={18} height={18} style={{ color: 'var(--accent-teal, #0d9488)' }} />
                    <h3 style={{ fontSize: '15px', fontWeight: 800, margin: 0, color: 'var(--text-primary, #0f172a)' }}>
                      {lang === 'hi' ? 'पिछले 14 दिनों का चेक-इन इतिहास' : 'Past 14 days check-in history'}
                    </h3>
                  </div>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
                    {checkinHistory.length} {lang === 'hi' ? 'रिकॉर्ड' : 'entries'}
                  </span>
                </div>

                {checkinHistoryLoading ? (
                  <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    {lang === 'hi' ? 'इतिहास लोड हो रहा है...' : 'Loading check-in history...'}
                  </div>
                ) : checkinHistory.length === 0 ? (
                  <div
                    style={{
                      padding: '24px',
                      textAlign: 'center',
                      color: 'var(--text-muted, #64748b)',
                      fontSize: '13px',
                      fontStyle: 'italic',
                      background: 'var(--bg-surface-alt, #f8fafc)',
                      borderRadius: '8px',
                    }}
                  >
                    {lang === 'hi'
                      ? 'पिछले 14 दिनों में कोई चेक-इन दर्ज नहीं किया गया।'
                      : 'No check-ins recorded in the last 14 days.'}
                  </div>
                ) : (
                  <div>
                    {/* Factual comparison note if at least 2 entries exist */}
                    {checkinHistory.length >= 2 && (
                      <div
                        style={{
                          background: 'var(--bg-surface-alt, #f8fafc)',
                          border: '1px solid var(--border-subtle, #e2e8f0)',
                          borderRadius: '8px',
                          padding: '10px 14px',
                          fontSize: '12px',
                          color: 'var(--text-secondary, #475569)',
                          marginBottom: '14px',
                        }}
                      >
                        <strong>{lang === 'hi' ? 'तुलना (तथ्य):' : 'Fact-based summary:'}</strong>{' '}
                        {lang === 'hi'
                          ? `नवीनतम चेक-इन पर दर्द स्तर ${checkinHistory[0].pain_level ?? 'अव्यक्त'} था (${checkinHistory[0].formatted_date || checkinHistory[0].date})। पिछले चेक-इन पर दर्द ${checkinHistory[1].pain_level ?? 'अव्यक्त'} था (${checkinHistory[1].formatted_date || checkinHistory[1].date})।`
                          : `Pain was ${checkinHistory[0].pain_level ?? 'unrated'} on ${checkinHistory[0].formatted_date || checkinHistory[0].date} and ${checkinHistory[1].pain_level ?? 'unrated'} on ${checkinHistory[1].formatted_date || checkinHistory[1].date}.`}
                      </div>
                    )}

                    {/* History items list */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {checkinHistory.map((rep) => {
                        const isExpanded = expandedHistoryId === rep.id;
                        const pScore = rep.pain_level;
                        const pillBg =
                          pScore >= 7
                            ? 'var(--alert-red-soft, #fef2f2)'
                            : pScore >= 4
                            ? 'var(--warning-amber-soft, #fffbeb)'
                            : 'var(--success-green-soft, #f0fdf4)';
                        const pillText =
                          pScore >= 7
                            ? 'var(--alert-red-text, #991b1b)'
                            : pScore >= 4
                            ? 'var(--warning-amber-text, #b45309)'
                            : 'var(--success-green-text, #166534)';
                        const pillBorder =
                          pScore >= 7
                            ? 'var(--alert-red, #dc2626)'
                            : pScore >= 4
                            ? 'var(--warning-amber, #d97706)'
                            : 'var(--success-green, #10b981)';

                        return (
                          <div
                            key={rep.id}
                            style={{
                              border: '1px solid var(--border-subtle, #e2e8f0)',
                              borderRadius: '8px',
                              padding: '12px 16px',
                              background: 'var(--bg-surface, #ffffff)',
                              transition: 'all 0.15s ease',
                            }}
                          >
                            <div
                              onClick={() => setExpandedHistoryId(isExpanded ? null : rep.id)}
                              style={{
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center',
                                cursor: 'pointer',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                                <span
                                  style={{
                                    fontSize: '12px',
                                    fontWeight: 800,
                                    padding: '3px 8px',
                                    borderRadius: '6px',
                                    background: pillBg,
                                    color: pillText,
                                    border: `1px solid ${pillBorder}`,
                                    fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
                                  }}
                                >
                                  {pScore !== null ? `Pain ${pScore}/10` : 'No score'}
                                </span>
                                <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                                  {rep.formatted_date || rep.reported_at}
                                </span>
                                {rep.emergency && (
                                  <span
                                    style={{
                                      fontSize: '11px',
                                      fontWeight: 700,
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      background: 'var(--alert-red-soft, #fef2f2)',
                                      color: 'var(--alert-red-text, #991b1b)',
                                      border: '1px solid var(--alert-red, #dc2626)',
                                    }}
                                  >
                                    Emergency Flag
                                  </span>
                                )}
                              </div>

                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                {rep.input_method === 'Voice_Transcript' && (
                                  <span
                                    style={{
                                      fontSize: '11px',
                                      color: 'var(--text-muted, #64748b)',
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: '4px',
                                    }}
                                  >
                                    <IconMic width={12} height={12} />
                                    Voice
                                  </span>
                                )}
                                <span style={{ fontSize: '12px', color: 'var(--accent-teal, #0d9488)', fontWeight: 600 }}>
                                  {isExpanded ? (lang === 'hi' ? 'कम करें' : 'Hide') : (lang === 'hi' ? 'विवरण' : 'Details')}
                                </span>
                              </div>
                            </div>

                            {/* Tags row */}
                            {rep.tags && rep.tags.length > 0 && (
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '8px' }}>
                                {rep.tags.map((t, idx) => (
                                  <span
                                    key={idx}
                                    style={{
                                      fontSize: '11px',
                                      padding: '2px 8px',
                                      borderRadius: '12px',
                                      background: 'var(--bg-surface-alt, #f8fafc)',
                                      border: '1px solid var(--border-subtle, #e2e8f0)',
                                      color: 'var(--text-secondary, #475569)',
                                    }}
                                  >
                                    {t}
                                  </span>
                                ))}
                              </div>
                            )}

                            {/* Expanded note text */}
                            {isExpanded && (
                              <div
                                style={{
                                  marginTop: '10px',
                                  paddingTop: '10px',
                                  borderTop: '1px solid var(--border-subtle, #e2e8f0)',
                                  fontSize: '12px',
                                  color: 'var(--text-primary, #0f172a)',
                                  lineHeight: 1.5,
                                }}
                              >
                                <strong>{lang === 'hi' ? 'नोट:' : 'Patient note:'}</strong>{' '}
                                {rep.text || (lang === 'hi' ? 'कोई नोट नहीं लिखा गया।' : 'No note provided.')}
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
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
