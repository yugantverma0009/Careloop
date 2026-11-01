import React, { useState, useEffect, useRef } from 'react';
import {
  getPatientToday,
  getPatientCalendar,
  getPatientDay,
  downloadAppointmentIcs,
  getAppointmentGoogleCalendarUrl,
  markDoseTaken,
  skipDose,
  undoDose,
  submitPatientCheckin,
  getPatientCheckins,
  sendChatMessage,
  getChatHistory,
  askCareTeamForChatMessage,
  submitChatFeedback,
  getFamilySharingStatus,
  toggleFamilySharing,
  submitFallResponse,
  logout,
} from '../services/api';
import SwitchDemoWorkspace from './SwitchDemoWorkspace';
import ThemeToggle from './ThemeToggle';
import CheckinGuide from './CheckinGuide';
import WoundPhotoUpload from './WoundPhotoUpload';
import PatientMyPlanView from './PatientMyPlanView';
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
  IconThumbsUp,
  IconThumbsDown,
  IconX,
  IconFileText,
  IconRefresh,
  IconGoogleCalendar,
  IconExternalLink,
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

const CHAT_STARTER_CHIPS = [
  { id: 'next_visit', en: 'When is my next visit?', hi: 'मेरी अगली मुलाक़ात कब है?' },
  { id: 'today_doses', en: 'What medicines do I take today?', hi: 'मुझे आज कौन सी दवाइयाँ लेनी हैं?' },
  { id: 'warning_signs', en: 'What warning signs should I watch for?', hi: 'मुझे किन ख़तरे के लक्षणों का ध्यान रखना चाहिए?' },
  { id: 'course_end', en: 'Until when do I take my medicines?', hi: 'मुझे कब तक दवाइयाँ लेनी हैं?' },
];

const EMERGENCY_KEYWORDS = [
  'chest pain',
  'short of breath',
  'shortness of breath',
  'breathless',
  'severe bleeding',
  'collapse',
  'fainted',
  'unconscious',
  'सीने में दर्द',
  'सांस फूलना',
  'साँस लेने में तकलीफ़',
  'बेहोश',
  'अत्यधिक रक्तस्राव',
];

export default function CareLoopPatientPortal({ user }) {
  const [lang, setLang] = useState('en');
  const [, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState('');
  const [todayData, setTodayData] = useState(null);
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [conversationId, setConversationId] = useState(() =>
    typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `conv-${Date.now()}`
  );
  const [selectedSource, setSelectedSource] = useState(null);
  const [expandedPassageId, setExpandedPassageId] = useState(null);
  const [feedbackState, setFeedbackState] = useState({});
  const [activeFeedbackPromptId, setActiveFeedbackPromptId] = useState(null);
  const [careTeamContactState, setCareTeamContactState] = useState({});

  // Active navigation sidebar tab: 'recovery', 'prescriptions', 'checkin', 'chat'
  const [activeNav, setActiveNav] = useState('recovery');
  const [medicinesSubTab, setMedicinesSubTab] = useState('doses'); // 'doses' or 'calendar'

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

  // Phase 3 Check-in State (Brief Sec 6.4) & Phase 2 Check-in Guide
  const [checkinMode, setCheckinMode] = useState('guided'); // 'guided' | 'quick'
  const [painLevel, setPainLevel] = useState(0);
  const [selectedChips, setSelectedChips] = useState([]);
  const [selectedSites, setSelectedSites] = useState([]);
  const [trend, setTrend] = useState(null);
  const [symptomText, setSymptomText] = useState('');
  const [inputMethod, setInputMethod] = useState('Text');
  const [isListening, setIsListening] = useState(false);
  const [checkinSubmitting, setCheckinSubmitting] = useState(false);

  // Plain-code immediate emergency detection (chips or text in English & Hindi)
  const hasEmergencyTrigger =
    selectedChips.some((id) => {
      const chip = CHECKIN_SYMPTOM_CHIPS.find((c) => c.id === id);
      return chip && chip.emergency;
    }) ||
    EMERGENCY_KEYWORDS.some((kw) => (symptomText || '').toLowerCase().includes(kw));

  // Family Sharing Consent State (Section 2.4 & Phase 2)
  const [familySharingEnabled, setFamilySharingEnabled] = useState(true);
  const [sharingLoading, setSharingLoading] = useState(false);

  useEffect(() => {
    getFamilySharingStatus()
      .then((res) => {
        if (res && res.sharing_enabled !== undefined) {
          setFamilySharingEnabled(Boolean(res.sharing_enabled));
        }
      })
      .catch(() => {});
  }, []);

  const handleToggleSharing = async () => {
    try {
      setSharingLoading(true);
      const nextStatus = !familySharingEnabled;
      await toggleFamilySharing(nextStatus);
      setFamilySharingEnabled(nextStatus);
    } catch (err) {
      alert(err.message || 'Failed to update sharing consent');
    } finally {
      setSharingLoading(false);
    }
  };
  const [checkinSuccessData, setCheckinSuccessData] = useState(null);
  const [checkinError, setCheckinError] = useState(null);
  const [checkinHistory, setCheckinHistory] = useState([]);
  const [checkinHistoryLoading, setCheckinHistoryLoading] = useState(false);
  const [expandedHistoryId, setExpandedHistoryId] = useState(null);
  const recognitionRef = useRef(null);

  const chatEndRef = useRef(null);

  const [lastUpdatedTime, setLastUpdatedTime] = useState(() => new Date().toLocaleTimeString());
  const [fallSubmitting, setFallSubmitting] = useState(false);
  const [fallFeedback, setFallFeedback] = useState(null);

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
      setLastUpdatedTime(new Date().toLocaleTimeString());
      if (Array.isArray(chatRes)) {
        setChatMessages(chatRes);
        const initialFeedback = {};
        chatRes.forEach((msg) => {
          if (msg.rating !== null && msg.rating !== undefined && msg.message_id) {
            initialFeedback[msg.message_id] = { rating: msg.rating, status: 'submitted' };
          }
        });
        if (Object.keys(initialFeedback).length > 0) {
          setFeedbackState((prev) => ({ ...prev, ...initialFeedback }));
        }
      }
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

  const handleFallResponse = async (eventId, responseType) => {
    try {
      setFallSubmitting(true);
      await submitFallResponse(eventId, responseType);
      if (responseType === 'Ok') {
        setFallFeedback({
          type: 'ok',
          text: lang === 'hi'
            ? 'पुष्टि करने के लिए धन्यवाद। आपकी देखभाल टीम को सूचित कर दिया गया है कि आप ठीक हैं।'
            : 'Thanks for confirming. Your care team has been notified that you are OK.',
        });
      } else {
        setFallFeedback({
          type: 'help',
          text: lang === 'hi'
            ? 'चेतावनी जारी की गई। डॉ. शर्मा और नर्स प्रिया को तुरंत सूचित कर दिया गया है।'
            : 'Alert raised. Dr. Sharma and Nurse Priya have been alerted immediately.',
        });
      }
      setTimeout(() => setFallFeedback(null), 10000);
      await loadTodayData(true);
    } catch (err) {
      console.error('Failed to submit fall response', err);
    } finally {
      setFallSubmitting(false);
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

  // Keyboard accessibility: Escape key closes any active modal or drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (selectedSource) {
          setSelectedSource(null);
        } else if (skipModalDose) {
          setSkipModalDose(null);
        } else if (remindersOpen) {
          setRemindersOpen(false);
        } else if (activeFeedbackPromptId) {
          setActiveFeedbackPromptId(null);
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [selectedSource, skipModalDose, remindersOpen, activeFeedbackPromptId]);

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
    if (activeNav === 'calendar' || (activeNav === 'prescriptions' && medicinesSubTab === 'calendar')) {
      loadCalendarData(calendarMonth);
    }
  }, [activeNav, medicinesSubTab, calendarMonth]);

  useEffect(() => {
    if ((activeNav === 'calendar' || (activeNav === 'prescriptions' && medicinesSubTab === 'calendar')) && selectedCalendarDate) {
      loadDayDetailData(selectedCalendarDate);
    }
  }, [activeNav, medicinesSubTab, selectedCalendarDate]);

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

  const handleOpenGoogleCalendar = async (appt) => {
    if (!appt) return;
    try {
      if (appt.google_calendar_url) {
        window.open(appt.google_calendar_url, '_blank', 'noopener,noreferrer');
        return;
      }
      if (appt.id) {
        try {
          const res = await getAppointmentGoogleCalendarUrl(appt.id);
          if (res?.google_calendar_url) {
            window.open(res.google_calendar_url, '_blank', 'noopener,noreferrer');
            return;
          }
        } catch (e) {
          console.warn('Falling back to client-built Google Calendar URL', e);
        }
      }
      const doc = appt.doctor || appt.doctor_name || appt.with || 'Care Team Clinician';
      const dept = appt.type || appt.department || 'Care Clinic';
      const title = `Follow-up visit with ${doc}`;
      const details = `Follow-up appointment at CareLoop (${dept}). Please arrive 10 minutes early with your discharge summary papers.`;
      const location = 'CareLoop Hospital & Clinics';

      let datesStr = '';
      const rawDate = appt.scheduled_at || appt.at || appt.date;
      if (rawDate) {
        const d = new Date(rawDate);
        if (!isNaN(d.getTime())) {
          const pad = (n) => String(n).padStart(2, '0');
          const toUtc = (dt) =>
            `${dt.getUTCFullYear()}${pad(dt.getUTCMonth() + 1)}${pad(dt.getUTCDate())}T${pad(dt.getUTCHours())}${pad(dt.getUTCMinutes())}${pad(dt.getUTCSeconds())}Z`;
          datesStr = `${toUtc(d)}/${toUtc(new Date(d.getTime() + 30 * 60000))}`;
        }
      }

      const q = new URLSearchParams({
        action: 'TEMPLATE',
        text: title,
        details: details,
        location: location,
      });
      if (datesStr) q.set('dates', datesStr);
      window.open(`https://calendar.google.com/calendar/render?${q.toString()}`, '_blank', 'noopener,noreferrer');
    } catch (err) {
      console.error('Failed to open Google Calendar', err);
      window.open('https://calendar.google.com', '_blank', 'noopener,noreferrer');
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

  // Chat message submit (Phase 4 Brief Sec 8)
  const handleSendMessage = async (e, directText = null) => {
    if (e && e.preventDefault) e.preventDefault();
    const userText = (directText || chatInput).trim();
    if (!userText || chatLoading) return;

    if (!directText) setChatInput('');

    const tempUserMsgId = `usr-${Date.now()}`;
    const currConvId = conversationId || `conv-${Date.now()}`;
    if (!conversationId) setConversationId(currConvId);

    setChatMessages((prev) => [
      ...prev,
      {
        id: tempUserMsgId,
        message_id: tempUserMsgId,
        role: 'user',
        sender: 'Patient',
        content: userText,
        message_text: userText,
        timestamp: new Date().toISOString(),
        created_at: new Date().toISOString(),
      },
    ]);
    setChatLoading(true);

    try {
      const res = await sendChatMessage(userText, lang, currConvId);
      const asstText = res.answer || res.response || res.reply || res.message;
      setChatMessages((prev) => [
        ...prev,
        {
          id: res.message_id || `asst-${Date.now()}`,
          message_id: res.message_id,
          role: 'assistant',
          sender: 'AI_Assistant',
          content: asstText,
          message_text: asstText,
          grounded: res.is_grounded,
          is_grounded: res.is_grounded,
          answer_type: res.answer_type || 'grounded',
          sources: res.sources || [],
          action_suggested: res.action_suggested,
          timestamp: new Date().toISOString(),
          created_at: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      console.error('Chat error', err);
      setChatMessages((prev) => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          sender: 'AI_Assistant',
          content:
            lang === 'hi'
              ? 'कनेक्ट करने में समस्या हुई। कृपया पुनः प्रयास करें या केयर टीम को कॉल करें।'
              : "I couldn't connect right now. Please try again or call your care team.",
          grounded: false,
          isError: true,
          failedText: userText,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleFeedback = async (messageId, rating, comment = null) => {
    if (!messageId) return;
    setFeedbackState((prev) => ({
      ...prev,
      [messageId]: { rating, status: 'submitted', comment },
    }));
    setActiveFeedbackPromptId(null);
    try {
      await submitChatFeedback(messageId, rating, comment);
    } catch (err) {
      console.error('Chat feedback error', err);
    }
  };

  const handleAskCareTeam = async (messageId) => {
    if (!messageId) return;
    setCareTeamContactState((prev) => ({
      ...prev,
      [messageId]: { status: 'loading' },
    }));
    try {
      const res = await askCareTeamForChatMessage(messageId);
      if (res.status === 'task_already_exists' || res.created === false) {
        setCareTeamContactState((prev) => ({
          ...prev,
          [messageId]: { status: 'already_sent', taskId: res.task_id },
        }));
        setUndoToast(
          lang === 'hi'
            ? 'इस विषय पर आपकी केयर टीम के पास आज का अनुरोध पहले से खुला है।'
            : 'Your care team already has an open request for this topic today.'
        );
      } else {
        setCareTeamContactState((prev) => ({
          ...prev,
          [messageId]: { status: 'sent', taskId: res.task_id },
        }));
        setUndoToast(
          lang === 'hi'
            ? 'आपकी केयर टीम को अनुरोध भेज दिया गया है।'
            : 'Request sent to your care team.'
        );
      }
    } catch (err) {
      console.error('Ask care team error', err);
      setCareTeamContactState((prev) => ({
        ...prev,
        [messageId]: { status: 'error' },
      }));
    }
  };

  const handleNewChat = () => {
    const newConv = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `conv-${Date.now()}`;
    setConversationId(newConv);
    setChatMessages([]);
  };

  // Derived telemetry metrics (filtered so invalid noise never becomes the headline)
  const validReadings = (todayData?.readings || []).filter(
    (r) => r.quality !== 'Invalid' && r.quality !== 'Noise' && r.is_valid !== false && r.is_valid !== 0
  );
  const hrReading = validReadings.find((r) => r.type?.toLowerCase().includes('heart') || r.type?.toLowerCase().includes('pulse')) || todayData?.readings?.find((r) => r.type?.toLowerCase().includes('heart') || r.type?.toLowerCase().includes('pulse'));
  const heartRateValue = hrReading?.value ?? 72;
  const hrQuality = hrReading?.quality ?? 'Valid';
  const hrTime = hrReading?.measured_time ?? '09:15 AM';

  const spo2Reading = validReadings.find((r) => r.type?.toLowerCase().includes('spo2') || r.type?.toLowerCase().includes('oxygen')) || todayData?.readings?.find((r) => r.type?.toLowerCase().includes('spo2') || r.type?.toLowerCase().includes('oxygen'));
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
                { id: 'recovery', label: lang === 'hi' ? 'होम' : 'Home', Icon: IconActivity },
                { id: 'plan', label: lang === 'hi' ? 'मेरी योजना' : 'My plan', Icon: IconFileText },
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
                  label: lang === 'hi' ? 'मेरे कागज़ात से पूछें' : 'Ask my papers',
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

            {/* Role Chip (Phase 2 & Section 2.5) */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '5px 12px',
                borderRadius: '20px',
                backgroundColor: 'var(--role-patient-soft, #f0fdfa)',
                border: '1px solid var(--role-patient, #0d9488)',
                color: 'var(--role-patient-text, #0f766e)',
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              <span>{lang === 'hi' ? 'मरीज़ (Patient)' : 'Patient'}</span>
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
                  {activeNav === 'recovery' && (lang === 'hi' ? 'मेरी रिकवरी' : 'MY RECOVERY')}
                  {activeNav === 'plan' && (lang === 'hi' ? 'मेरी योजना' : 'MY PLAN')}
                  {activeNav === 'prescriptions' && (lang === 'hi' ? 'दवाइयाँ और शेड्यूल' : 'MY MEDICINES')}
                  {activeNav === 'checkin' && (lang === 'hi' ? 'दैनिक चेक-इन' : 'MY CHECK-IN')}
                  {activeNav === 'chat' && (lang === 'hi' ? 'मेरे कागज़ात' : 'MY PAPERS')} ·{' '}
                  {lang === 'hi'
                    ? `डिस्चार्ज के बाद दिन ${todayData?.day_after_discharge || 3}`
                    : `Day ${todayData?.day_after_discharge || 3} after discharge`}
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
                {activeNav === 'recovery' && (lang === 'hi' ? `नमस्ते ${todayData?.name || 'आरव'}` : `Hi ${todayData?.name || 'Aarav'}`)}
                {activeNav === 'plan' && (lang === 'hi' ? 'मेरी रिकवरी योजना' : 'My Personal Recovery Plan')}
                {activeNav === 'prescriptions' && (lang === 'hi' ? 'दवाइयाँ और कैलेंडर' : 'Medicines & Calendar')}
                {activeNav === 'checkin' && (lang === 'hi' ? 'दैनिक स्वास्थ्य चेक-इन' : 'Daily health check-in')}
                {activeNav === 'chat' && (lang === 'hi' ? 'डिस्चार्ज रिकवरी सहायक' : 'Ask my papers')}
              </h1>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', margin: 0 }}>
                {todayData?.formatted_date || 'Thursday, 29 October 2026'} ·{' '}
                {lang === 'hi'
                  ? 'अपनी दैनिक दवाइयाँ, स्मार्टवॉच रीडिंग और देखभाल योजना देखें।'
                  : 'Check your daily medicines, watch readings, and care team updates.'}
              </p>
            </div>
          </div>

          {/* ─── Active Fall Prompt Banner (Phase 5) ─── */}
          {todayData?.fall_prompt && (
            <div
              role="alert"
              aria-live="assertive"
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '2px solid var(--alert-red, #dc2626)',
                borderRadius: '12px',
                padding: '16px 20px',
                marginBottom: '20px',
                boxShadow: '0 4px 14px rgba(220, 38, 38, 0.15)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                    style={{
                      width: '38px',
                      height: '38px',
                      borderRadius: '50%',
                      background: 'var(--alert-red-soft, #fef2f2)',
                      color: 'var(--alert-red, #dc2626)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: '18px',
                      fontWeight: 800,
                    }}
                  >
                    !
                  </div>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '15px', color: 'var(--text-primary, #0f172a)' }}>
                      {lang === 'hi'
                        ? 'केयरलूप जांच: आपकी घड़ी से अचानक हलचल दर्ज की गई।'
                        : 'CareLoop check: We noticed sudden movement from your watch.'}
                    </div>
                    <div style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
                      {lang === 'hi'
                        ? `क्या आप ठीक हैं? (प्रतीक्षा समय: ${todayData.fall_prompt.wait_minutes || 2} मिनट)`
                        : `Are you OK? (Waiting ${todayData.fall_prompt.wait_minutes || 2} minutes before alerting staff)`}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '10px' }}>
                  <button
                    type="button"
                    onClick={() => handleFallResponse(todayData.fall_prompt.event_id, 'Ok')}
                    disabled={fallSubmitting}
                    style={{
                      background: 'var(--success-green, #059669)',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '8px',
                      padding: '9px 18px',
                      fontWeight: 700,
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    {lang === 'hi' ? '✓ मैं ठीक हूँ' : "✓ I'm OK"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleFallResponse(todayData.fall_prompt.event_id, 'Need_Help')}
                    disabled={fallSubmitting}
                    style={{
                      background: 'var(--alert-red, #dc2626)',
                      color: '#ffffff',
                      border: 'none',
                      borderRadius: '8px',
                      padding: '9px 18px',
                      fontWeight: 700,
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    {lang === 'hi' ? '🚨 मुझे मदद चाहिए' : '🚨 I need help'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Fall Response Feedback Banner */}
          {fallFeedback && (
            <div
              style={{
                background: fallFeedback.type === 'ok' ? 'var(--success-green-soft, #f0fdf4)' : 'var(--alert-red-soft, #fef2f2)',
                border: `1px solid ${fallFeedback.type === 'ok' ? 'var(--success-green, #059669)' : 'var(--alert-red, #dc2626)'}`,
                borderRadius: '12px',
                padding: '14px 18px',
                marginBottom: '20px',
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
              }}
            >
              <div style={{ fontWeight: 600, fontSize: '13px', color: fallFeedback.type === 'ok' ? 'var(--success-green, #059669)' : 'var(--alert-red, #dc2626)' }}>
                {fallFeedback.text}
              </div>
            </div>
          )}

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
              role="status"
              aria-live="polite"
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

          {/* ─── 6. TAB: RECOVERY HOME ─── */}
          {activeNav === 'recovery' && (
            <>
              {/* Family Sharing Consent Card / Switch (Section 2.4 & Phase 2) */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '16px 20px',
                  boxShadow: 'var(--shadow-card)',
                  marginBottom: '20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <div
                    style={{
                      width: '38px',
                      height: '38px',
                      borderRadius: '8px',
                      backgroundColor: familySharingEnabled ? 'var(--role-family-soft, #fffbeb)' : 'var(--bg-card-hover, #f1f5f9)',
                      color: familySharingEnabled ? 'var(--role-family, #d97706)' : 'var(--text-muted, #64748b)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconShieldCheck width={20} height={20} />
                  </div>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                      {lang === 'hi' ? 'परिवार के साथ साझा करना' : 'Family sharing'}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
                      {familySharingEnabled
                        ? (lang === 'hi' ? 'नेहा पटेल (पत्नी) के साथ रिकवरी अपडेट साझा किए जा रहे हैं।' : 'Sharing allowed with Neha Patel (Spouse).')
                        : (lang === 'hi' ? 'परिवार के साथ साझा करना बंद है। कोई डेटा नहीं भेजा जा रहा है।' : 'Family sharing is turned off. Access disabled.')}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: familySharingEnabled ? 'var(--role-family, #d97706)' : 'var(--text-muted, #64748b)' }}>
                    {familySharingEnabled ? (lang === 'hi' ? 'चालू (On)' : 'On') : (lang === 'hi' ? 'बंद (Off)' : 'Off')}
                  </span>
                  <button
                    type="button"
                    onClick={handleToggleSharing}
                    disabled={sharingLoading}
                    style={{
                      width: '48px',
                      height: '26px',
                      borderRadius: '13px',
                      backgroundColor: familySharingEnabled ? 'var(--role-family, #d97706)' : 'var(--border-strong, #cbd5e1)',
                      border: 'none',
                      position: 'relative',
                      cursor: 'pointer',
                      transition: 'background-color 0.2s ease',
                    }}
                    title="Toggle family sharing consent"
                  >
                    <div
                      style={{
                        width: '20px',
                        height: '20px',
                        borderRadius: '10px',
                        backgroundColor: '#ffffff',
                        position: 'absolute',
                        top: '3px',
                        left: familySharingEnabled ? '25px' : '3px',
                        transition: 'left 0.2s ease',
                        boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                      }}
                    />
                  </button>
                </div>
              </div>

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

                  <div style={{ marginTop: '14px', borderTop: '1px solid var(--border-subtle, #e2e8f0)', paddingTop: '10px' }}>
                    <button
                      type="button"
                      onClick={() => { setActiveNav('prescriptions'); setMedicinesSubTab('doses'); }}
                      style={{
                        background: 'none',
                        border: 'none',
                        color: 'var(--accent-teal, #0d9488)',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        padding: 0,
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '4px',
                      }}
                    >
                      <span>{lang === 'hi' ? 'दवाइयों का पूरा शेड्यूल और कैलेंडर देखें →' : 'View all scheduled medicines & calendar →'}</span>
                    </button>
                  </div>
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

              {/* Telemetry Live Bar & Watch Status (Phase 5) */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '14px',
                  flexWrap: 'wrap',
                  gap: '8px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    {lang === 'hi' ? 'स्मार्टवॉच स्थिति' : 'Watch Telemetry'}
                  </span>
                  {todayData?.device_health?.has_device ? (
                    <span className="status-pill status-pill-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', fontSize: '11px', padding: '3px 8px' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#059669', display: 'inline-block' }} />
                      Watch: {todayData.device_health.connectivity_status === 'Online' ? 'Online' : 'Standby'} · {todayData.device_health.battery_pct}% Battery
                    </span>
                  ) : (
                    <span className="status-pill status-pill-neutral" style={{ fontSize: '11px', padding: '3px 8px' }}>
                      Watch: Standby
                    </span>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                  <span style={{ width: '7px', height: '7px', borderRadius: '50%', backgroundColor: '#0284c7', display: 'inline-block' }} />
                  <span style={{ fontWeight: 700, color: '#0284c7' }}>Live</span>
                  <span>·</span>
                  <span>Updated {lastUpdatedTime}</span>
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
                  {todayData?.next_appointment?.id && (
                    <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={() => handleOpenGoogleCalendar(todayData.next_appointment)}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '4px',
                          padding: '3px 8px',
                          borderRadius: '5px',
                          border: '1px solid #4285F4',
                          background: 'rgba(66, 133, 244, 0.08)',
                          color: '#1a73e8',
                          fontSize: '10px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                        title={lang === 'hi' ? 'गूगल कैलेंडर में जोड़ें' : 'Add to Google Calendar'}
                      >
                        <IconGoogleCalendar width={11} height={11} />
                        <span>Google</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDownloadAppointmentIcs(todayData.next_appointment.id)}
                        disabled={downloadingIcsId === todayData.next_appointment.id}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '3px',
                          padding: '3px 6px',
                          borderRadius: '5px',
                          border: '1px solid var(--border-subtle, #cbd5e1)',
                          background: 'transparent',
                          color: 'var(--text-secondary, #475569)',
                          fontSize: '10px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                        title="Download .ics"
                      >
                        .ics
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {todayData?.data_check_note && (
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '8px 14px',
                    borderRadius: '8px',
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    fontSize: '12px',
                    color: 'var(--text-muted, #64748b)',
                    marginTop: '-6px',
                    marginBottom: '16px',
                  }}
                >
                  <span>ℹ️</span>
                  <span>{todayData.data_check_note}</span>
                </div>
              )}

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
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                        <button
                          type="button"
                          onClick={() => handleOpenGoogleCalendar(todayData.plan_checklist.next_appointment)}
                          style={{
                            alignSelf: 'flex-start',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '5px 11px',
                            borderRadius: '6px',
                            border: '1px solid #4285F4',
                            background: 'rgba(66, 133, 244, 0.08)',
                            color: '#1a73e8',
                            fontSize: '11px',
                            fontWeight: 700,
                            cursor: 'pointer',
                            transition: 'all 0.15s ease',
                          }}
                          title={lang === 'hi' ? 'गूगल कैलेंडर में जोड़ें' : 'Add to Google Calendar'}
                        >
                          <IconGoogleCalendar width={13} height={13} />
                          <span>{lang === 'hi' ? 'गूगल कैलेंडर' : 'Google Calendar'}</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDownloadAppointmentIcs(todayData.plan_checklist.next_appointment.id)}
                          disabled={downloadingIcsId === todayData.plan_checklist.next_appointment.id}
                          style={{
                            alignSelf: 'flex-start',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            padding: '5px 9px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-subtle, #cbd5e1)',
                            background: 'transparent',
                            color: 'var(--text-secondary, #475569)',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                          title={lang === 'hi' ? 'Apple या Outlook के लिए .ics डाउनलोड करें' : 'Download .ics for Apple / Outlook'}
                        >
                          <IconCalendar width={12} height={12} />
                          <span>{downloadingIcsId === todayData.plan_checklist.next_appointment.id ? (lang === 'hi' ? 'डाउनलोड...' : 'Downloading...') : '.ics'}</span>
                        </button>
                      </div>
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

          {/* ─── TAB: MY PLAN (Phase 4 Feature F5) ─── */}
          {activeNav === 'plan' && (
            <PatientMyPlanView
              lang={lang}
              onAskAssistant={(query) => {
                setChatInput(query);
                setActiveNav('chat');
              }}
            />
          )}

          {/* ─── 7. TAB: MEDICINES (GROUPED DOSES & CALENDAR) ─── */}
          {(activeNav === 'prescriptions' || activeNav === 'calendar') && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Sub-Tabs: Today's doses vs Calendar */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '12px 18px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => { setActiveNav('prescriptions'); setMedicinesSubTab('doses'); }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: (medicinesSubTab === 'doses' && activeNav !== 'calendar') ? '1px solid var(--accent-teal, #0d9488)' : '1px solid var(--border-subtle, #e2e8f0)',
                      background: (medicinesSubTab === 'doses' && activeNav !== 'calendar') ? 'rgba(13, 148, 136, 0.12)' : 'var(--bg-surface, #ffffff)',
                      color: (medicinesSubTab === 'doses' && activeNav !== 'calendar') ? 'var(--accent-teal, #0d9488)' : 'var(--text-secondary, #475569)',
                      fontWeight: (medicinesSubTab === 'doses' && activeNav !== 'calendar') ? 700 : 500,
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    <IconPill width={16} height={16} />
                    <span>{lang === 'hi' ? "आज की दवाइयाँ" : "Today's doses"}</span>
                    {remainingDosesCount > 0 && (
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '1px 6px',
                          borderRadius: '10px',
                          background: 'var(--accent-teal, #0d9488)',
                          color: '#ffffff',
                        }}
                      >
                        {remainingDosesCount}
                      </span>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => { setActiveNav('prescriptions'); setMedicinesSubTab('calendar'); }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 16px',
                      borderRadius: '8px',
                      border: (medicinesSubTab === 'calendar' || activeNav === 'calendar') ? '1px solid var(--accent-teal, #0d9488)' : '1px solid var(--border-subtle, #e2e8f0)',
                      background: (medicinesSubTab === 'calendar' || activeNav === 'calendar') ? 'rgba(13, 148, 136, 0.12)' : 'var(--bg-surface, #ffffff)',
                      color: (medicinesSubTab === 'calendar' || activeNav === 'calendar') ? 'var(--accent-teal, #0d9488)' : 'var(--text-secondary, #475569)',
                      fontWeight: (medicinesSubTab === 'calendar' || activeNav === 'calendar') ? 700 : 500,
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    <IconCalendar width={16} height={16} />
                    <span>{lang === 'hi' ? 'कैलेंडर और अपॉइंटमेंट्स' : 'Calendar & Appointments'}</span>
                  </button>
                </div>
              </div>

              {(medicinesSubTab === 'doses' && activeNav !== 'calendar') ? (
                /* Grouped Medicines Table */
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
              ) : (
                /* ─── CALENDAR (Month Grid & Day Detail) ─── */
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
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <IconCalendar width={16} height={16} style={{ color: 'var(--accent-blue, #0284c7)' }} />
                        <h2 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: 0 }}>
                          {lang === 'hi' ? 'आगामी फॉलो-अप अपॉइंटमेंट्स' : 'Upcoming Follow-up Appointments'}
                        </h2>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <a
                          href="https://calendar.google.com"
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            fontSize: '11px',
                            fontWeight: 700,
                            color: '#1a73e8',
                            textDecoration: 'none',
                            padding: '4px 9px',
                            borderRadius: '6px',
                            background: 'rgba(66, 133, 244, 0.08)',
                            border: '1px solid rgba(66, 133, 244, 0.25)',
                          }}
                          title={lang === 'hi' ? 'गूगल कैलेंडर खोलें' : 'Open Google Calendar in new tab'}
                        >
                          <IconGoogleCalendar width={13} height={13} />
                          <span>{lang === 'hi' ? 'गूगल कैलेंडर खोलें' : 'Google Calendar'}</span>
                          <IconExternalLink width={10} height={10} />
                        </a>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                          {calendarData?.upcoming_appointments?.length || 0} {lang === 'hi' ? 'निर्धारित' : 'scheduled'}
                        </span>
                      </div>
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

                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <button
                                type="button"
                                onClick={() => handleOpenGoogleCalendar(appt)}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                  padding: '8px 14px',
                                  borderRadius: '8px',
                                  border: '1px solid #4285F4',
                                  background: 'rgba(66, 133, 244, 0.08)',
                                  color: '#1a73e8',
                                  fontSize: '12px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                  minHeight: '38px',
                                  transition: 'all 0.15s ease',
                                }}
                                title={lang === 'hi' ? 'गूगल कैलेंडर में जोड़ें' : 'Add to Google Calendar'}
                              >
                                <IconGoogleCalendar width={15} height={15} />
                                <span>{lang === 'hi' ? 'गूगल कैलेंडर' : 'Google Calendar'}</span>
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDownloadAppointmentIcs(appt.id)}
                                disabled={downloadingIcsId === appt.id}
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                  padding: '8px 12px',
                                  borderRadius: '8px',
                                  border: '1px solid var(--border-subtle, #cbd5e1)',
                                  background: 'transparent',
                                  color: 'var(--text-secondary, #475569)',
                                  fontSize: '12px',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  minHeight: '38px',
                                }}
                                title={lang === 'hi' ? 'Apple या Outlook के लिए .ics फ़ाइल डाउनलोड करें' : 'Download .ics for Apple / Outlook'}
                              >
                                <IconCalendar width={14} height={14} />
                                <span>
                                  {downloadingIcsId === appt.id
                                    ? (lang === 'hi' ? 'डाउनलोड...' : 'Downloading...')
                                    : '.ics (Apple / Outlook)'}
                                </span>
                              </button>
                            </div>
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
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                    <button
                                      type="button"
                                      onClick={() => handleOpenGoogleCalendar(appt)}
                                      style={{
                                        padding: '4px 8px',
                                        borderRadius: '6px',
                                        border: '1px solid #4285F4',
                                        background: 'rgba(66, 133, 244, 0.08)',
                                        color: '#1a73e8',
                                        fontSize: '11px',
                                        fontWeight: 700,
                                        cursor: 'pointer',
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: '4px',
                                      }}
                                      title={lang === 'hi' ? 'गूगल कैलेंडर में जोड़ें' : 'Add to Google Calendar'}
                                    >
                                      <IconGoogleCalendar width={11} height={11} />
                                      <span>Google</span>
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleDownloadAppointmentIcs(appt.id)}
                                      disabled={downloadingIcsId === appt.id}
                                      style={{
                                        padding: '4px 8px',
                                        borderRadius: '6px',
                                        border: '1px solid var(--border-subtle, #cbd5e1)',
                                        background: 'transparent',
                                        color: 'var(--text-secondary, #475569)',
                                        fontSize: '11px',
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                      }}
                                      title={lang === 'hi' ? 'Apple या Outlook के लिए .ics डाउनलोड करें' : 'Download .ics'}
                                    >
                                      .ics
                                    </button>
                                  </div>
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

                {/* Mode Switcher: Guided Guide vs Quick Form */}
                {!checkinSuccessData && (
                  <div
                    style={{
                      display: 'flex',
                      gap: '8px',
                      background: 'var(--bg-base, #f1f5f9)',
                      padding: '4px',
                      borderRadius: '8px',
                      marginBottom: '18px',
                      marginTop: '10px',
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => setCheckinMode('guided')}
                      style={{
                        flex: 1,
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: 'none',
                        background: checkinMode === 'guided' ? '#ffffff' : 'transparent',
                        color: checkinMode === 'guided' ? '#0b1528' : 'var(--text-secondary, #475569)',
                        fontWeight: checkinMode === 'guided' ? 700 : 500,
                        fontSize: '12px',
                        cursor: 'pointer',
                        boxShadow: checkinMode === 'guided' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                      }}
                    >
                      {lang === 'hi' ? '🧭 गाइडेड चेक-इन (अनुशंसित)' : '🧭 Check-in Guide (Recommended)'}
                    </button>
                    <button
                      type="button"
                      onClick={() => setCheckinMode('quick')}
                      style={{
                        flex: 1,
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: 'none',
                        background: checkinMode === 'quick' ? '#ffffff' : 'transparent',
                        color: checkinMode === 'quick' ? '#0b1528' : 'var(--text-secondary, #475569)',
                        fontWeight: checkinMode === 'quick' ? 700 : 500,
                        fontSize: '12px',
                        cursor: 'pointer',
                        boxShadow: checkinMode === 'quick' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                      }}
                    >
                      {lang === 'hi' ? '⚡ त्वरित फॉर्म' : '⚡ Quick Form'}
                    </button>
                  </div>
                )}

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
                ) : checkinMode === 'guided' ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    <CheckinGuide
                      lang={lang}
                      onComplete={(res) => {
                        setCheckinSuccessData({
                          res,
                          payload: {
                            pain_level: res.pain_level ?? 0,
                            trend: 'Completed via Guide',
                            chips: [],
                            sites: [],
                            text: res.message || 'Check-in completed',
                          },
                        });
                        getPatientCheckins(14).then(setCheckinHistory).catch(() => {});
                      }}
                      onEmergency={() => {
                        getPatientCheckins(14).then(setCheckinHistory).catch(() => {});
                      }}
                    />

                    {/* Phase 3 Feature F4: Wound Photo Check-in */}
                    <WoundPhotoUpload
                      lang={lang}
                      onOpenDischargePapers={() => setActiveNav('chat')}
                    />
                  </div>
                ) : (
                  /* ACTIVE CHECK-IN FORM */
                  <form onSubmit={handleCheckinSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '22px', marginTop: '18px' }}>
                    {/* Emergency Notice when emergency chip or keywords triggered */}
                    {hasEmergencyTrigger && (
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
                            {lang === 'hi' ? 'आपातकालीन चेतावनी - तत्काल सहायता' : 'Emergency Notice - Call 112 Immediately'}
                          </strong>
                        </div>
                        <p style={{ fontSize: '13px', margin: '0 0 10px 0', lineHeight: 1.5, fontWeight: 600 }}>
                          {lang === 'hi'
                            ? 'यदि आपको सीने में दर्द, सांस लेने में अत्यधिक तकलीफ या अचानक कमजोरी महसूस हो, तो तुरंत 112 पर कॉल करें। ऐप के जवाब की प्रतीक्षा न करें।'
                            : 'If you have chest pain, shortness of breath, or sudden weakness, call 112 immediately. Do not wait for an app response.'}
                        </p>
                        <a
                          href="tel:112"
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '6px',
                            padding: '8px 16px',
                            borderRadius: '6px',
                            background: 'var(--alert-red, #dc2626)',
                            color: '#ffffff',
                            fontWeight: 700,
                            fontSize: '12px',
                            textDecoration: 'none',
                          }}
                        >
                          📞 {lang === 'hi' ? '112 पर कॉल करें' : 'Call 112 Now'}
                        </a>
                      </div>
                    )}

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
                      {lang === 'hi' ? 'हालिया 7 दिनों का चेक-इन इतिहास' : 'Recent 7 days check-in history'}
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

          {/* ─── 10. TAB: CHAT ASSISTANT (Phase 4 Upgraded Grounded Assistant) ─── */}
          {activeNav === 'chat' && (
            <div
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '12px',
                padding: '24px',
                height: '620px',
                display: 'flex',
                flexDirection: 'column',
                maxWidth: '860px',
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
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <div
                    style={{
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: 'rgba(13, 148, 136, 0.12)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      color: 'var(--accent-teal, #0d9488)',
                    }}
                  >
                    <IconSparkles width={20} height={20} />
                  </div>
                  <div>
                    <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--text-primary, #0f172a)' }}>
                      {lang === 'hi' ? 'डिस्चार्ज रिकवरी सहायक' : 'Discharge recovery assistant'}
                    </h2>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                      {lang === 'hi'
                        ? 'उत्तर आपके डिस्चार्ज पेपर्स से आते हैं, मूल अंश के साथ।'
                        : 'Answers come from your discharge papers, with the passage shown.'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={handleNewChat}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      padding: '6px 12px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'var(--bg-base, #f8fafc)',
                      color: 'var(--text-primary, #0f172a)',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                    title={lang === 'hi' ? 'नया संवाद शुरू करें' : 'Start a fresh conversation'}
                  >
                    <IconRefresh width={13} height={13} />
                    {lang === 'hi' ? 'नया संवाद' : 'New chat'}
                  </button>
                  <span className="status-pill status-pill-blue">
                    <IconShieldCheck width={12} height={12} style={{ marginRight: '4px' }} />
                    {lang === 'hi' ? 'आपके पेपर्स से' : 'From your papers'}
                  </span>
                </div>
              </div>

              {/* Chat Message Scroll Area */}
              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                  paddingRight: '6px',
                }}
              >
                {chatMessages.length === 0 ? (
                  <div
                    style={{
                      margin: 'auto',
                      maxWidth: '560px',
                      textAlign: 'center',
                      padding: '24px 16px',
                    }}
                  >
                    <div
                      style={{
                        width: '48px',
                        height: '48px',
                        borderRadius: '50%',
                        background: 'rgba(13, 148, 136, 0.1)',
                        color: 'var(--accent-teal, #0d9488)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        margin: '0 auto 12px auto',
                      }}
                    >
                      <IconSparkles width={26} height={26} />
                    </div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
                      {lang === 'hi' ? 'आज मैं आपकी क्या मदद करूँ?' : 'How can I help you recover?'}
                    </div>
                    <p style={{ fontSize: '13px', color: 'var(--text-muted, #64748b)', marginBottom: '20px', lineHeight: 1.5 }}>
                      {lang === 'hi'
                        ? 'अपनी दवाओं, अगली डॉक्टर विज़िट, घाव की देखभाल या रिकवरी के नियमों के बारे में पूछें। नीचे दिए गए किसी भी सुझाव पर टैप करें:'
                        : 'Ask any question about your medications, appointments, wound care, or recovery rules. Tap a starter question to begin:'}
                    </p>

                    {/* Starter Chips Grid (Brief Sec 8.2) */}
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
                        gap: '8px',
                        textAlign: 'left',
                      }}
                    >
                      {CHAT_STARTER_CHIPS.map((chip) => (
                        <button
                          key={chip.id}
                          type="button"
                          onClick={() => handleSendMessage(null, chip[lang])}
                          disabled={chatLoading}
                          style={{
                            padding: '10px 14px',
                            borderRadius: '10px',
                            border: '1px solid var(--border-subtle, #cbd5e1)',
                            background: 'var(--bg-base, #f8fafc)',
                            color: 'var(--text-primary, #0f172a)',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            transition: 'all 0.15s ease',
                          }}
                        >
                          <span>{chip[lang]}</span>
                          <span style={{ color: 'var(--accent-teal, #0d9488)', marginLeft: '6px' }}>→</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  chatMessages.map((msg, i) => {
                    const isUser = msg.role === 'user' || msg.sender === 'Patient';
                    const msgId = msg.message_id || msg.id;
                    const feedback = feedbackState[msgId];
                    const careTeamState = careTeamContactState[msgId];
                    const isEmergency = msg.answer_type === 'emergency';
                    const isRefusal = msg.answer_type === 'refusal_dose';
                    const isNotFound = msg.answer_type === 'not_found';
                    const sources = Array.isArray(msg.sources) ? msg.sources : [];

                    return (
                      <div
                        key={msgId || i}
                        style={{
                          alignSelf: isUser ? 'flex-end' : 'flex-start',
                          maxWidth: '82%',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '6px',
                        }}
                      >
                        {/* Message Bubble */}
                        <div
                          style={{
                            padding: '12px 16px',
                            borderRadius: isUser ? '14px 14px 2px 14px' : '14px 14px 14px 2px',
                            background: isUser
                              ? 'var(--navy-deep, #0b1528)'
                              : isEmergency
                              ? 'rgba(239, 68, 68, 0.08)'
                              : 'var(--bg-base, #f1f5f9)',
                            border: isEmergency
                              ? '1.5px solid #ef4444'
                              : isUser
                              ? 'none'
                              : '1px solid var(--border-subtle, #e2e8f0)',
                            color: isUser ? '#ffffff' : 'var(--text-primary, #0f172a)',
                            fontSize: '13px',
                            lineHeight: 1.6,
                            boxShadow: isUser ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                          }}
                        >
                          {/* Emergency Banner Styling */}
                          {isEmergency && (
                            <div
                              style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '8px',
                                color: '#b91c1c',
                                fontWeight: 800,
                                fontSize: '13px',
                                marginBottom: '8px',
                                paddingBottom: '6px',
                                borderBottom: '1px solid rgba(239, 68, 68, 0.2)',
                              }}
                            >
                              <IconAlertTriangle width={18} height={18} style={{ color: '#ef4444' }} />
                              <span>{lang === 'hi' ? 'आपातकालीन सूचना - तुरंत 112 पर कॉल करें' : 'Emergency Notice - Call 112 Immediately'}</span>
                            </div>
                          )}

                          <div style={{ whiteSpace: 'pre-wrap' }}>
                            {msg.content || msg.message_text || msg.text}
                          </div>

                          {/* Emergency Direct Call Button */}
                          {isEmergency && (
                            <div style={{ marginTop: '12px' }}>
                              <a
                                href="tel:112"
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                  padding: '8px 14px',
                                  borderRadius: '8px',
                                  background: '#dc2626',
                                  color: '#ffffff',
                                  textDecoration: 'none',
                                  fontWeight: 700,
                                  fontSize: '12px',
                                }}
                              >
                                📞 {lang === 'hi' ? '112 पर आपातकालीन कॉल करें' : 'Call 112 Emergency'}
                              </a>
                            </div>
                          )}

                          {/* Refusal / Not Found: Ask My Care Team Action (Brief Sec 8.3 & 8.6) */}
                          {(isRefusal || isNotFound || msg.action_suggested === 'ask_care_team') && !isUser && (
                            <div
                              style={{
                                marginTop: '12px',
                                paddingTop: '10px',
                                borderTop: '1px dashed var(--border-subtle, #cbd5e1)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                flexWrap: 'wrap',
                                gap: '8px',
                              }}
                            >
                              <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                                {lang === 'hi'
                                  ? 'क्या आप चाहते हैं कि डॉक्टर या नर्स आपसे संपर्क करें?'
                                  : 'Would you like a clinician to review this request?'}
                              </span>
                              <button
                                type="button"
                                onClick={() => handleAskCareTeam(msgId)}
                                disabled={careTeamState?.status === 'loading' || careTeamState?.status === 'sent' || careTeamState?.status === 'already_sent'}
                                style={{
                                  padding: '6px 12px',
                                  borderRadius: '6px',
                                  border: '1px solid var(--accent-teal, #0d9488)',
                                  background: careTeamState?.status === 'sent' || careTeamState?.status === 'already_sent' ? 'var(--accent-teal, #0d9488)' : '#ffffff',
                                  color: careTeamState?.status === 'sent' || careTeamState?.status === 'already_sent' ? '#ffffff' : 'var(--accent-teal, #0d9488)',
                                  fontSize: '12px',
                                  fontWeight: 700,
                                  cursor: careTeamState?.status === 'sent' || careTeamState?.status === 'already_sent' ? 'default' : 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                }}
                              >
                                {careTeamState?.status === 'loading'
                                  ? (lang === 'hi' ? 'भेजा जा रहा है...' : 'Sending...')
                                  : careTeamState?.status === 'sent'
                                  ? (lang === 'hi' ? '✓ अनुरोध भेज दिया गया' : '✓ Request Sent')
                                  : careTeamState?.status === 'already_sent'
                                  ? (lang === 'hi' ? '✓ पहले से लंबित' : '✓ Already awaiting review')
                                  : (lang === 'hi' ? '👨‍⚕️ केयर टीम से पूछें' : '👨‍⚕️ Ask My Care Team')}
                              </button>
                            </div>
                          )}

                          {/* Error Retry Option */}
                          {msg.isError && msg.failedText && (
                            <div style={{ marginTop: '8px' }}>
                              <button
                                type="button"
                                onClick={() => handleSendMessage(null, msg.failedText)}
                                style={{
                                  padding: '4px 10px',
                                  borderRadius: '6px',
                                  border: '1px solid #cbd5e1',
                                  background: '#ffffff',
                                  color: 'var(--text-primary, #0f172a)',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '4px',
                                }}
                              >
                                <IconRefresh width={11} height={11} />
                                {lang === 'hi' ? 'पुनः प्रयास करें' : 'Retry'}
                              </button>
                            </div>
                          )}
                        </div>

                        {/* Grounded Source Pill Chips (Brief Sec 8.3 & 8.4) */}
                        {!isUser && sources.length > 0 && (
                          <div
                            style={{
                              display: 'flex',
                              flexWrap: 'wrap',
                              gap: '6px',
                              alignItems: 'center',
                              paddingLeft: '4px',
                            }}
                          >
                            <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                              {lang === 'hi' ? 'स्रोत:' : 'Sources:'}
                            </span>
                            {sources.map((src, srcIdx) => {
                              const label = src.label || (src.tool_name
                                ? 'From your care plan'
                                : `Discharge summary - ${src.section_title || 'General'}${src.page_no ? ` - p.${src.page_no}` : ''}`);

                              return (
                                <div key={srcIdx} style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                                  <button
                                    type="button"
                                    onClick={() => setSelectedSource(src)}
                                    style={{
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: '4px',
                                      padding: '3px 8px',
                                      borderRadius: '12px',
                                      border: '1px solid var(--border-subtle, #cbd5e1)',
                                      background: 'var(--bg-surface, #ffffff)',
                                      color: 'var(--text-primary, #0f172a)',
                                      fontSize: '11px',
                                      fontWeight: 600,
                                      cursor: 'pointer',
                                      transition: 'border-color 0.15s ease',
                                    }}
                                    title={lang === 'hi' ? 'स्रोत विवरण देखने के लिए क्लिक करें' : 'Click to inspect source passage in drawer'}
                                  >
                                    <span>{label}</span>
                                    <span style={{ color: 'var(--text-muted, #94a3b8)', fontSize: '10px' }}>↗</span>
                                  </button>
                                  {src.text && (
                                    <button
                                      type="button"
                                      onClick={() => setExpandedPassageId(expandedPassageId === `${msgId}-${srcIdx}` ? null : `${msgId}-${srcIdx}`)}
                                      style={{
                                        background: 'none',
                                        border: 'none',
                                        color: 'var(--accent-blue, #0284c7)',
                                        fontSize: '11px',
                                        cursor: 'pointer',
                                        padding: '2px 4px',
                                        fontWeight: 600,
                                      }}
                                    >
                                      {expandedPassageId === `${msgId}-${srcIdx}`
                                        ? (lang === 'hi' ? 'अंश छिपाएं' : 'Hide passage')
                                        : (lang === 'hi' ? 'अंश देखें' : 'Show passage')}
                                    </button>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        )}

                        {/* Inline Expanded Passage Display */}
                        {sources && sources.length > 0 && sources.map((src, srcIdx) => {
                          if (expandedPassageId !== `${msgId}-${srcIdx}` || !src.text) return null;
                          return (
                            <div
                              key={`inline-passage-${srcIdx}`}
                              style={{
                                margin: '4px 0 8px 6px',
                                padding: '8px 12px',
                                background: 'var(--bg-subtle, #f8fafc)',
                                borderRadius: '6px',
                                fontSize: '12px',
                                lineHeight: '1.45',
                                color: 'var(--text-secondary, #334155)',
                                borderLeft: '3px solid var(--accent-blue, #0284c7)',
                              }}
                            >
                              <div style={{ fontWeight: 600, fontSize: '11px', marginBottom: '3px', color: 'var(--text-muted, #64748b)' }}>
                                {src.label || (src.section_title ? `Discharge summary - ${src.section_title}` : 'Source passage')}
                              </div>
                              <div>{src.text}</div>
                            </div>
                          );
                        })}

                        {/* Assistant Actions Bar: Feedback Thumbs + Timestamp */}
                        {!isUser && !msg.isError && (
                          <div
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              paddingLeft: '6px',
                              fontSize: '11px',
                              color: 'var(--text-muted, #94a3b8)',
                              gap: '8px',
                            }}
                          >
                            {/* Thumbs Up / Down Buttons (Brief Sec 8.3 & 8.5) */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <button
                                type="button"
                                onClick={() => handleFeedback(msgId, 1)}
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  padding: '2px 4px',
                                  cursor: 'pointer',
                                  color: feedback?.rating === 1 ? 'var(--accent-teal, #0d9488)' : 'var(--text-muted, #94a3b8)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  borderRadius: '4px',
                                }}
                                title={lang === 'hi' ? 'मददगार लगा' : 'Helpful'}
                              >
                                <IconThumbsUp width={13} height={13} />
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  if (activeFeedbackPromptId === msgId) {
                                    setActiveFeedbackPromptId(null);
                                  } else {
                                    setActiveFeedbackPromptId(msgId);
                                    handleFeedback(msgId, -1);
                                  }
                                }}
                                style={{
                                  background: 'none',
                                  border: 'none',
                                  padding: '2px 4px',
                                  cursor: 'pointer',
                                  color: feedback?.rating === -1 ? '#ef4444' : 'var(--text-muted, #94a3b8)',
                                  display: 'flex',
                                  alignItems: 'center',
                                  borderRadius: '4px',
                                }}
                                title={lang === 'hi' ? 'मददगार नहीं लगा' : 'Not helpful'}
                              >
                                <IconThumbsDown width={13} height={13} />
                              </button>

                              {feedback?.rating === 1 && (
                                <span style={{ fontSize: '10px', color: 'var(--accent-teal, #0d9488)' }}>
                                  {lang === 'hi' ? 'धन्यवाद!' : 'Helpful'}
                                </span>
                              )}
                              {feedback?.rating === -1 && (
                                <span style={{ fontSize: '10px', color: '#ef4444' }}>
                                  {lang === 'hi' ? 'फ़ीडबैक दर्ज' : 'Recorded'}
                                </span>
                              )}
                            </div>

                            {/* Timestamp (12-hour format e.g. 8:04 PM) */}
                            {msg.timestamp && (
                              <span style={{ fontSize: '10px' }}>
                                {new Date(msg.timestamp).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: true })}
                              </span>
                            )}
                          </div>
                        )}

                        {/* Optional Inline Comment Prompt for Thumbs Down */}
                        {activeFeedbackPromptId === msgId && (
                          <div
                            style={{
                              marginTop: '2px',
                              padding: '8px 10px',
                              borderRadius: '8px',
                              border: '1px solid var(--border-subtle, #cbd5e1)',
                              background: 'var(--bg-base, #f8fafc)',
                              fontSize: '11px',
                            }}
                          >
                            <div style={{ fontWeight: 600, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
                              {lang === 'hi' ? 'क्या समस्या थी?' : 'What was the issue?'}
                            </div>
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginBottom: '6px' }}>
                              {[
                                { id: 'incorrect', en: 'Incorrect', hi: 'गलत तथ्य' },
                                { id: 'confusing', en: 'Confusing', hi: 'समझ नहीं आया' },
                                { id: 'missing', en: 'Missing detail', hi: 'अधूरी जानकारी' },
                              ].map((opt) => (
                                <button
                                  key={opt.id}
                                  type="button"
                                  onClick={() => handleFeedback(msgId, -1, opt[lang])}
                                  style={{
                                    padding: '3px 8px',
                                    borderRadius: '6px',
                                    border: '1px solid var(--border-subtle, #cbd5e1)',
                                    background: '#ffffff',
                                    color: 'var(--text-primary, #0f172a)',
                                    fontSize: '10px',
                                    cursor: 'pointer',
                                  }}
                                >
                                  {opt[lang]}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })
                )}

                {chatLoading && (
                  <div
                    style={{
                      alignSelf: 'flex-start',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '8px 14px',
                      borderRadius: '12px',
                      background: 'var(--bg-base, #f1f5f9)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      fontSize: '12px',
                      color: 'var(--text-muted, #64748b)',
                    }}
                  >
                    <IconSparkles width={14} height={14} style={{ color: 'var(--accent-teal, #0d9488)' }} />
                    <span>{lang === 'hi' ? 'आपके पेपर्स व केयर प्लान में खोज रहे हैं...' : 'Checking discharge papers and recovery plan...'}</span>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Chat Input Form */}
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
                      ? 'अपनी दवाओं, अगली विज़िट या घाव की देखभाल के बारे में पूछें...'
                      : 'Ask about your medicines, next visit, or wound care...'
                  }
                  style={{
                    flex: 1,
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    fontSize: '13px',
                    background: 'var(--bg-input, #ffffff)',
                    color: 'var(--text-primary, #0f172a)',
                    outline: 'none',
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
                    cursor: !chatInput.trim() || chatLoading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    opacity: !chatInput.trim() || chatLoading ? 0.6 : 1,
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
          onClick={() => setSkipModalDose(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="skip-modal-title"
            style={{
              background: 'var(--bg-surface, #ffffff)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              borderRadius: '12px',
              padding: '24px',
              width: '90%',
              maxWidth: '440px',
              boxShadow: 'var(--shadow-float)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div id="skip-modal-title" style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginBottom: '4px' }}>
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

      {/* ─── 12. SOURCE INSPECTION MODAL DRAWER (Brief Sec 8.4) ─── */}
      {selectedSource && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.5)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 120,
          }}
          onClick={() => setSelectedSource(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="source-drawer-title"
            style={{
              background: 'var(--bg-surface, #ffffff)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              borderRadius: '14px',
              padding: '24px',
              width: '92%',
              maxWidth: '560px',
              boxShadow: 'var(--shadow-float)',
              maxHeight: '85vh',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '10px',
                    background: 'rgba(13, 148, 136, 0.12)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--accent-teal, #0d9488)',
                  }}
                >
                  <IconFileText width={20} height={20} />
                </div>
                <div>
                  <h3 id="source-drawer-title" style={{ fontSize: '15px', fontWeight: 800, margin: 0, color: 'var(--text-primary, #0f172a)' }}>
                    {lang === 'hi' ? 'स्रोत रिकॉर्ड विवरण' : 'Source record passage'}
                  </h3>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    {lang === 'hi'
                      ? 'यह उत्तर आपके प्रमाणित मेडिकल रिकॉर्ड से सत्यापित है'
                      : 'This answer was verified directly against this record'}
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setSelectedSource(null)}
                aria-label={lang === 'hi' ? 'बंद करें' : 'Close'}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted, #94a3b8)',
                  cursor: 'pointer',
                  padding: '4px',
                }}
              >
                <IconX width={18} height={18} />
              </button>
            </div>

            {/* Badges */}
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <span className="status-pill status-pill-blue" style={{ fontSize: '11px' }}>
                📄 {selectedSource.doc_title || (selectedSource.tool_name ? 'Care Plan Database' : 'Discharge Summary')}
              </span>
              {selectedSource.section_title && (
                <span className="status-pill status-pill-neutral" style={{ fontSize: '11px' }}>
                  🔖 {selectedSource.section_title}
                </span>
              )}
              {selectedSource.page_no && (
                <span className="status-pill status-pill-neutral" style={{ fontSize: '11px' }}>
                  Page {selectedSource.page_no}
                </span>
              )}
              {selectedSource.tool_name && (
                <span className="status-pill status-pill-green" style={{ fontSize: '11px' }}>
                  Tool: {selectedSource.tool_name}
                </span>
              )}
            </div>

            {/* Snippet / Text Quote */}
            <div
              style={{
                flex: 1,
                overflowY: 'auto',
                background: 'var(--bg-base, #f8fafc)',
                border: '1px solid var(--border-subtle, #cbd5e1)',
                borderRadius: '10px',
                padding: '16px',
                fontSize: '13px',
                lineHeight: 1.6,
                color: 'var(--text-primary, #0f172a)',
                whiteSpace: 'pre-wrap',
                fontFamily: 'inherit',
                maxHeight: '320px',
              }}
            >
              {selectedSource.snippet ||
                selectedSource.text ||
                (typeof selectedSource.tool_data === 'object'
                  ? JSON.stringify(selectedSource.tool_data, null, 2)
                  : 'No passage text recorded for this citation.')}
            </div>

            {/* Footer */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                paddingTop: '8px',
                borderTop: '1px solid var(--border-subtle, #e2e8f0)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--accent-teal, #0d9488)', fontWeight: 600 }}>
                <IconShieldCheck width={14} height={14} />
                <span>{lang === 'hi' ? 'चिकित्सकीय रूप से प्रमाणित' : 'Grounded hospital record'}</span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedSource(null)}
                style={{
                  padding: '7px 16px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-strong, #cbd5e1)',
                  background: 'var(--navy-deep, #0b1528)',
                  color: '#ffffff',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                {lang === 'hi' ? 'बंद करें' : 'Close'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
