import React, { useState, useEffect, useRef, useCallback } from 'react';
import { AgenticLogo } from '../App';
import {
  sendChatMessage,
  sendVoiceMessage,
  sendWoundImage,
  triggerReminder,
  submitPatientReply,
  getPatientPersonalization,
  getChatHistory,
  markTaskComplete,
} from '../services/api';

export const IconCameraScan = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
    <circle cx="12" cy="13" r="4" />
  </svg>
);

export const IconMic = ({ className }) => (
  <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" y1="19" x2="12" y2="23" />
    <line x1="8" y1="23" x2="16" y2="23" />
  </svg>
);

const toMsgObjects = (dbArray) =>
  dbArray.map((msg) => ({
    sender: msg.role === 'nurse' || msg.role === 'system' ? 'nurse' : 'patient',
    text: msg.content,
    automated: msg.automated || false,
  }));

const TriageDashboard = ({ patientId, messages, setMessages, viewMode, setViewMode, onPatientNameLoad }) => {

  const [input, setInput]                     = useState('');
  const [loading, setLoading]                 = useState(false);
  const messagesEndRef                        = useRef(null);
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedFile, setSelectedFile]       = useState(null);
  const [imagePreview, setImagePreview]       = useState(null);
  const fileInputRef                          = useRef(null);

  const [isSendingSMS, setIsSendingSMS] = useState(false);
  const [isRecording, setIsRecording]   = useState(false);
  const mediaRecorderRef                = useRef(null);
  const audioChunksRef                  = useRef([]);

  const [dailyRoutine, setDailyRoutine] = useState([]);
  const [careTeam, setCareTeam]         = useState([]);
  const [appointments, setAppointments] = useState([]);
  const [patientName, setPatientName]   = useState('');

  const [heartRate, setHeartRate] = useState(0);
  const [oxygen, setOxygen]       = useState(98);

  const lastMsgCountRef = useRef(0);


  const applyHistory = useCallback((dbArray) => {
    if (!Array.isArray(dbArray)) return;
    setMessages(toMsgObjects(dbArray));
    lastMsgCountRef.current = dbArray.length;
  }, [setMessages]);

  const fetchAndApply = useCallback(async (force = false) => {
    try {
      const data = await getChatHistory(patientId);
      if (!data || !Array.isArray(data)) return;
      if (force || data.length !== lastMsgCountRef.current) {
        applyHistory(data);
      }
    } catch (e) {
      console.error('History fetch failed:', e);
    }
  }, [patientId, applyHistory]);



  useEffect(() => {
    if (!patientId) return;
    const ws = new WebSocket(`ws://localhost:8000/ws/vitals/${patientId}`);
    ws.onopen    = () => console.log('🔗 WebSocket Connected');
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setHeartRate(data.bpm > 0 ? data.bpm : 0);
      } catch {}
    };
    ws.onerror = () => {};
    ws.onclose = () => setHeartRate(0);
    return () => ws.close();
  }, [patientId]);

  const fetchPersonalData = useCallback(async () => {
    try {
      const data = await getPatientPersonalization(patientId);
      if (data && !data.error) {
        setDailyRoutine(data.daily_routine || []);
        setCareTeam(data.care_team || []);
        setAppointments(data.appointments || []);
        const resolvedName = data.name || '';
        setPatientName(resolvedName);
        if (onPatientNameLoad) onPatientNameLoad(resolvedName);
      }
    } catch {}
  }, [patientId]);

  useEffect(() => {
    fetchPersonalData();
    const id = setInterval(fetchPersonalData, 5000);
    return () => clearInterval(id);
  }, [fetchPersonalData]);


  useEffect(() => {
    lastMsgCountRef.current = 0;

    const init = async () => {
      setLoading(true);
      try {
        const data = await getChatHistory(patientId);
        if (!data || data.length === 0) {
          setMessages([{ sender: 'nurse', text: 'Hello. I am your AI Recovery Nurse. How are you feeling today?' }]);
          lastMsgCountRef.current = 0;
        } else {
          applyHistory(data);
        }
      } catch {} finally {
        setLoading(false);
      }
    };

    init();

    const id = setInterval(() => fetchAndApply(false), 5000);
    return () => clearInterval(id);

  }, [patientId]); 

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, viewMode]);


  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input;
    setInput('');
    setLoading(true);

    setMessages((prev) => [...prev, { sender: 'patient', text: userMsg }]);
    lastMsgCountRef.current += 1;

    const confirmKeywords = /^(yes|done|taken|ok|completed|complete|i did|i have|ya|yep|yeah|sure)\b/i;
    if (confirmKeywords.test(userMsg.trim())) {
      const firstPending = dailyRoutine.find((t) => !t.completed);
      if (firstPending) {
        setDailyRoutine((prev) =>
          prev.map((t) => t.id === firstPending.id ? { ...t, completed: true } : t)
        );
        try { await markTaskComplete(patientId, firstPending.id); } catch {}
      }
    }

    try {
      await sendChatMessage(patientId, userMsg);
      await fetchAndApply(true);
    } catch {
      setMessages((prev) => [...prev, { sender: 'nurse', text: '⚠️ Connection error. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      mediaRecorderRef.current = mr;
      audioChunksRef.current = [];
      mr.ondataavailable = (e) => { if (e.data.size > 0) audioChunksRef.current.push(e.data); };
      mr.onstop = handleStopRecording;
      mr.start();
      setIsRecording(true);
    } catch {
      alert('Microphone access denied.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      mediaRecorderRef.current.stream.getTracks().forEach((t) => t.stop());
    }
  };

  const handleStopRecording = async () => {
    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    setLoading(true);
    setMessages((prev) => [...prev, { sender: 'patient', text: '🎙️ Processing voice...' }]);
    lastMsgCountRef.current += 1;

    try {
      const data = await sendVoiceMessage(patientId, audioBlob);
      if (data.audio) {
        const audio = new Audio(`data:audio/mp3;base64,${data.audio}`);
        audio.play().catch(() => {});
      }
      await fetchAndApply(true);
    } catch {
      setMessages((prev) => [...prev, { sender: 'nurse', text: '⚠️ Error processing audio.' }]);
    } finally {
      setLoading(false);
    }
  };

  const submitUpload = async () => {
    if (!selectedFile) return;
    setShowUploadModal(false);
    setLoading(true);
    setMessages((prev) => [...prev, { sender: 'patient', text: 'Uploaded Image', image: imagePreview }]);
    lastMsgCountRef.current += 1;

    try {
      await sendWoundImage(patientId, selectedFile);
      await fetchAndApply(true);
    } catch {
      setMessages((prev) => [
        ...prev,
        { sender: 'nurse', text: '⚠️ Image analysis unavailable. Please describe what you see instead.' },
      ]);
    } finally {
      setLoading(false);
      setSelectedFile(null);
      setImagePreview(null);
    }
  };

  const handleFileSelect = (e) => {
    const f = e.target.files?.[0];
    if (f) { setSelectedFile(f); setImagePreview(URL.createObjectURL(f)); }
  };

  const handleTaskComplete = async (taskId) => {
    setDailyRoutine((prev) => prev.map((t) => t.id === taskId ? { ...t, completed: true } : t));
    try {
      await markTaskComplete(patientId, taskId);
    } catch {
      setDailyRoutine((prev) => prev.map((t) => t.id === taskId ? { ...t, completed: false } : t));
    }
  };

  const handleDemoTrigger = async () => {
    setIsSendingSMS(true);
    try {
      await triggerReminder(patientId, 'task_3');
      const firstName = patientName ? patientName.split(' ')[0] : 'there';
      setMessages((prev) => [...prev, {
        sender: 'nurse',
        text: `🔴 ALERT: Hi ${firstName}, I just sent a reminder for your Amoxicillin (500mg) due at 09:00 AM. Have you taken it yet?`,
      }]);
      alert('📲 SMS Sent to Patient!');
    } catch {
      alert('Error sending SMS');
    } finally {
      setIsSendingSMS(false);
    }
  };

  const handleDemoReply = async () => {
    try { await submitPatientReply(patientId, 'task_3', 'YES'); } catch { alert('Error simulating reply'); }
  };



  const CalendarWidget = () => {
    const now = new Date();
    const MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

    const normalizeMonth = (m) => {
      if (!m) return 'Jan';
      const s = String(m).trim();
      const idx = MONTH_NAMES.findIndex(mn => mn.toLowerCase() === s.slice(0, 3).toLowerCase());
      return idx >= 0 ? MONTH_NAMES[idx] : s.slice(0, 3);
    };

    const allNormalized = [...appointments].map(a => {
      const month = normalizeMonth(a.month);
      return { ...a, month, _date: new Date(a.year, MONTH_NAMES.indexOf(month), a.day) };
    });

    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

    const upcoming = allNormalized.filter(a => a._date >= today).sort((a, b) => a._date - b._date);
    const past     = allNormalized.filter(a => a._date < today).sort((a, b) => b._date - a._date);
    const nextAppt = upcoming[0] || past[0] || null;

    const displayMonth   = nextAppt ? nextAppt.month : MONTH_NAMES[now.getMonth()];
    const displayYear    = nextAppt ? nextAppt.year  : now.getFullYear();
    const monthIndex     = MONTH_NAMES.indexOf(displayMonth);
    const daysInMonth    = new Date(displayYear, monthIndex + 1, 0).getDate();
    const firstDayOffset = new Date(displayYear, monthIndex, 1).getDay();
    const highlightedDays = new Set(nextAppt ? [nextAppt.day] : []);
    const blanks = Array(firstDayOffset).fill(null);
    const dates  = Array.from({ length: daysInMonth }, (_, i) => i + 1);

    return (
      <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 20, padding: 24, boxShadow: 'var(--shadow)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <h3 className="font-display" style={{ color: 'var(--accent)', fontWeight: 800, letterSpacing: '2px', fontSize: 13, textTransform: 'uppercase' }}>
            {displayMonth}
          </h3>
          <span className="font-mono" style={{ fontSize: 12, color: 'var(--text-3)' }}>{displayYear}</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, textAlign: 'center', marginBottom: 10 }}>
          {['S','M','T','W','T','F','S'].map((d, i) => (
            <div key={i} className="font-mono" style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)' }}>{d}</div>
          ))}
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, placeItems: 'center' }}>
          {[...blanks, ...dates].map((date, i) => {
            const isHighlighted = date && highlightedDays.has(date);
            const appt = isHighlighted
              ? appointments.find(a => a.month === displayMonth && a.year === displayYear && a.day === date)
              : null;
            return (
              <div key={i} title={appt?.note || ''}
                style={{
                  height: 32, width: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 12, borderRadius: '50%', transition: 'all .2s',
                  background: isHighlighted ? 'var(--accent)' : 'transparent',
                  color: isHighlighted ? '#07090F' : date ? 'var(--text-2)' : 'transparent',
                  fontWeight: isHighlighted ? 800 : 500,
                  boxShadow: isHighlighted ? '0 0 14px var(--accent-glow)' : 'none',
                  cursor: isHighlighted ? 'pointer' : 'default',
                }}>
                {date}
              </div>
            );
          })}
        </div>
        <div style={{ marginTop: 16, paddingTop: 16, borderTop: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <p style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-2)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
            Upcoming Follow-ups
          </p>
          <span className="font-mono" style={{ fontSize: 11, color: 'var(--accent)' }}>
            {appointments.length} scheduled
          </span>
        </div>
      </div>
    );
  };

  const VitalsWidget = () => (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 20, padding: 22, boxShadow: 'var(--shadow)' }}>
      <h3 className="font-mono" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.5px', color: 'var(--text-3)', marginBottom: 16, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{
          width: 8, height: 8, borderRadius: '50%',
          background: heartRate > 0 ? 'var(--green)' : 'var(--red-alert)',
          boxShadow: heartRate > 0 ? '0 0 10px rgba(16,185,129,0.8)' : '0 0 10px rgba(255,68,68,0.8)',
          animation: 'pulse 1.8s ease infinite',
        }} />
        {heartRate > 0 ? 'Live Telemetry' : 'Watch Standby'}
      </h3>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
        <div style={{ flex: 1 }}>
          <span style={{ color: 'var(--text-3)', fontSize: 10, textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>Heart Rate</span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginTop: 2 }}>
            <span className="font-display" style={{ fontSize: 32, fontWeight: 800, color: 'var(--text-1)', lineHeight: 1 }}>
              {heartRate > 0 ? heartRate : '--'}
            </span>
            <span className="font-mono" style={{ fontSize: 12, color: 'var(--text-3)' }}>bpm</span>
          </div>
          <div style={{ width: '100%', height: 4, background: 'rgba(255,255,255,0.06)', marginTop: 10, borderRadius: 100, overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              background: 'linear-gradient(90deg, #FF4444 0%, #F59E0B 100%)',
              width: `${Math.min(100, (heartRate / 150) * 100)}%`,
              transition: 'all .3s ease',
              borderRadius: 100,
            }} />
          </div>
        </div>
        <div style={{ width: 1, height: 48, background: 'var(--border)' }} />
        <div style={{ flex: 1 }}>
          <span style={{ color: 'var(--text-3)', fontSize: 10, textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.5px' }}>SpO₂</span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 4, marginTop: 2 }}>
            <span className="font-display" style={{ fontSize: 32, fontWeight: 800, color: 'var(--accent)', lineHeight: 1 }}>
              {oxygen}
            </span>
            <span className="font-mono" style={{ fontSize: 12, color: 'var(--text-3)' }}>%</span>
          </div>
          <div style={{ width: '100%', height: 4, background: 'rgba(255,255,255,0.06)', marginTop: 10, borderRadius: 100, overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              background: 'linear-gradient(90deg, var(--accent) 0%, #3B82F6 100%)',
              width: `${oxygen}%`,
              transition: 'all 1s ease',
              borderRadius: 100,
            }} />
          </div>
        </div>
      </div>
    </div>
  );

  const CareTeamWidget = () => (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 20, padding: 22, boxShadow: 'var(--shadow)' }}>
      <h3 className="font-mono" style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '1.5px', color: 'var(--text-3)', marginBottom: 16 }}>
        Assigned Care Team
      </h3>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {careTeam.length > 0 ? (
          careTeam.map((doc, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <img
                src={doc.image || `https://ui-avatars.com/api/?name=${encodeURIComponent(doc.name)}&background=0D1117&color=00D4AA`}
                alt={doc.name}
                style={{ width: 40, height: 40, borderRadius: 12, objectFit: 'cover', border: '1px solid var(--border)' }}
              />
              <div>
                <p style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--text-1)' }}>{doc.name}</p>
                <p style={{ fontSize: 11, color: 'var(--accent)', fontWeight: 500 }}>{doc.role}</p>
              </div>
            </div>
          ))
        ) : (
          <p style={{ fontSize: 12, color: 'var(--text-3)' }}>Loading team...</p>
        )}
      </div>
    </div>
  );

  const handleLogout = () => {
    sessionStorage.removeItem('authToken');
    sessionStorage.removeItem('authRole');
    sessionStorage.removeItem('authPatientId');
    window.location.href = '/';
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)', color: 'var(--text-1)', paddingBottom: 80 }}>

      {/* Patient Recovery Sub-Toolbar */}
      <div style={{
        backgroundColor: 'var(--bg-surface)',
        borderBottom: '1px solid var(--border)',
        padding: '12px 24px',
      }}>
        <div style={{ maxWidth: 1400, margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{
              width: 38, height: 38, borderRadius: 12,
              background: 'var(--accent-dim)', border: '1.5px solid var(--accent)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--accent)', fontWeight: 800, fontSize: 16,
            }}>
              {patientName ? patientName.charAt(0).toUpperCase() : 'P'}
            </div>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <h2 style={{ fontSize: 16, fontWeight: 800, color: 'var(--text-1)', lineHeight: 1.2, margin: 0, fontFamily: "'Outfit', sans-serif" }}>
                  {patientName || 'Post-Discharge Patient'}
                </h2>
                <span className="badge-clinical badge-teal" style={{ fontSize: 11 }}>ACTIVE RECOVERY</span>
              </div>
              <span className="font-mono" style={{ fontSize: 11, color: 'var(--text-3)' }}>
                Patient ID: {patientId}
              </span>
            </div>
          </div>

          {/* View Mode Toggle: Dashboard vs Nurse Chat */}
          <div style={{ display: 'flex', alignItems: 'center', background: 'var(--bg-elevated)', borderRadius: 10, padding: 3, border: '1px solid var(--border)' }}>
            <button
              onClick={() => setViewMode('home')}
              style={{
                padding: '7px 18px', fontSize: 12, fontWeight: 700, borderRadius: 8, border: 'none', cursor: 'pointer',
                fontFamily: 'Inter, sans-serif', transition: 'all .2s',
                background: viewMode === 'home' ? 'var(--accent)' : 'transparent',
                color: viewMode === 'home' ? 'var(--accent-contrast)' : 'var(--text-2)',
                boxShadow: viewMode === 'home' ? '0 2px 10px var(--accent-glow)' : 'none',
              }}
            >
              MY DASHBOARD
            </button>
            <button
              onClick={() => setViewMode('chat')}
              style={{
                padding: '7px 18px', fontSize: 12, fontWeight: 700, borderRadius: 8, border: 'none', cursor: 'pointer',
                fontFamily: 'Inter, sans-serif', transition: 'all .2s',
                display: 'flex', alignItems: 'center', gap: 6,
                background: viewMode === 'chat' ? 'var(--accent)' : 'transparent',
                color: viewMode === 'chat' ? 'var(--accent-contrast)' : 'var(--text-2)',
                boxShadow: viewMode === 'chat' ? '0 2px 10px var(--accent-glow)' : 'none',
              }}
            >
              <span>NURSE CHAT</span>
              <span className="badge-clinical badge-teal" style={{ padding: '2px 6px', fontSize: 10 }}>AI</span>
            </button>
          </div>

          {/* Vitals quick glance */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-2)' }}>
              <span className="material-icons-round" style={{ fontSize: 16, color: 'var(--red-alert)' }}>favorite</span>
              <span>{heartRate ? `${heartRate} BPM` : '72 BPM'}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontFamily: "'JetBrains Mono', monospace", color: 'var(--text-2)' }}>
              <span className="material-icons-round" style={{ fontSize: 16, color: 'var(--blue)' }}>water_drop</span>
              <span>{oxygen ? `${oxygen}% SpO2` : '98% SpO2'}</span>
            </div>
          </div>

        </div>
      </div>

      <div className="max-w-7xl mx-auto p-4 md:p-8">

        {viewMode === 'home' && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
            <div className="lg:col-span-8 flex flex-col gap-6">

              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 20, padding: 32, boxShadow: 'var(--shadow)' }}>
                <h2 className="font-display" style={{ fontSize: 26, fontWeight: 300, color: 'var(--text-1)', marginBottom: 8 }}>
                  {patientName ? (
                    <>Good Morning, <span style={{ fontWeight: 800, color: 'var(--accent)' }}>{patientName.split(' ')[0]}</span>.</>
                  ) : (
                    <div style={{ height: 32, width: 220, background: 'rgba(255,255,255,0.05)', borderRadius: 8 }} />
                  )}
                </h2>
                <p style={{ color: 'var(--text-2)', fontSize: 14 }}>
                  You have completed{' '}
                  <strong style={{ color: 'var(--accent)', fontWeight: 700 }}>{dailyRoutine.filter((t) => t.completed).length}</strong>{' '}
                  of {dailyRoutine.length} tasks today. Keep up the great recovery momentum!
                </p>
              </div>

              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 20, padding: 26, flex: 1, boxShadow: 'var(--shadow)' }}>
                <h3 className="font-mono" style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-3)', marginBottom: 24, textTransform: 'uppercase', letterSpacing: '1.5px' }}>
                  Today's Recovery Roadmap
                </h3>
                <div style={{ position: 'relative', marginLeft: 12, paddingBottom: 16 }}>
                  {dailyRoutine.length > 0 ? (
                    dailyRoutine.map((item, idx) => {
                      const isLast = idx === dailyRoutine.length - 1;
                      return (
                        <div key={idx} style={{ position: 'relative', paddingLeft: 32, paddingBottom: 28 }}>
                          {!isLast && (
                            <div style={{
                              position: 'absolute', left: 7, top: 20, width: 2, height: '100%',
                              background: item.completed ? 'var(--accent)' : 'rgba(255,255,255,0.08)',
                              transition: 'all .4s ease',
                            }} />
                          )}
                          <div style={{
                            position: 'absolute', left: -1, top: 2, width: 18, height: 18, borderRadius: '50%',
                            border: `2px solid ${item.completed ? 'var(--accent)' : 'rgba(255,255,255,0.2)'}`,
                            background: item.completed ? 'var(--accent)' : 'var(--bg-base)',
                            zIndex: 10, display: 'flex', alignItems: 'center', justifyContent: 'center',
                            boxShadow: item.completed ? '0 0 12px var(--accent-glow)' : 'none',
                            transition: 'all .3s ease',
                          }}>
                            {item.completed && (
                              <svg className="w-3 h-3 text-slate-950" viewBox="0 0 20 20" fill="currentColor">
                                <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                              </svg>
                            )}
                          </div>
                          <div
                            onClick={() => !item.completed && handleTaskComplete(item.id)}
                            style={{
                              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                              padding: '12px 16px', borderRadius: 12,
                              background: item.completed ? 'rgba(255,255,255,0.02)' : 'rgba(255,255,255,0.04)',
                              border: `1px solid ${item.completed ? 'transparent' : 'var(--border)'}`,
                              cursor: item.completed ? 'default' : 'pointer',
                              transition: 'all .2s ease',
                            }}
                            onMouseEnter={e => { if(!item.completed) { e.currentTarget.style.borderColor = 'rgba(0,212,170,0.3)'; e.currentTarget.style.background = 'var(--accent-dim)'; }}}
                            onMouseLeave={e => { if(!item.completed) { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; }}}
                          >
                            <div>
                              <p style={{
                                fontSize: 14, fontWeight: 500,
                                color: item.completed ? 'var(--text-3)' : 'var(--text-1)',
                                textDecoration: item.completed ? 'line-through' : 'none',
                                transition: 'all .2s',
                              }}>
                                {item.title}
                              </p>
                              <p className="font-mono" style={{ fontSize: 11, color: 'var(--text-3)', marginTop: 2 }}>{item.time}</p>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{
                                padding: '3px 9px', borderRadius: 6, fontSize: 10, fontWeight: 700,
                                fontFamily: 'JetBrains Mono, monospace', letterSpacing: '0.5px', textTransform: 'uppercase',
                                background: item.type === 'med' ? 'rgba(59,130,246,0.15)' : item.type === 'meal' ? 'rgba(245,158,11,0.15)' : 'rgba(16,185,129,0.15)',
                                color: item.type === 'med' ? '#60A5FA' : item.type === 'meal' ? '#FBBF24' : '#34D399',
                                border: `1px solid ${item.type === 'med' ? 'rgba(59,130,246,0.3)' : item.type === 'meal' ? 'rgba(245,158,11,0.3)' : 'rgba(16,185,129,0.3)'}`,
                              }}>
                                {item.type}
                              </span>
                              {!item.completed && (
                                <span className="font-mono" style={{ fontSize: 9, color: 'var(--accent)', fontWeight: 700 }}>MARK ✓</span>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <p style={{ color: 'var(--text-3)', fontSize: 13, paddingLeft: 32 }}>Loading recovery schedule...</p>
                  )}
                </div>
              </div>
            </div>

            <div className="lg:col-span-4 flex flex-col gap-6">
              <VitalsWidget />
              <CalendarWidget />
              <CareTeamWidget />
            </div>
          </div>
        )}

        {viewMode === 'chat' && (
          <div className="h-[calc(100vh-140px)] flex flex-col lg:flex-row gap-6">
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: 'var(--bg-surface)', borderRadius: 20, border: '1px solid var(--border)', overflow: 'hidden', boxShadow: 'var(--shadow)' }}>
              <div style={{ padding: '14px 20px', background: 'var(--bg-elevated)', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent)', boxShadow: '0 0 10px var(--accent)', animation: 'pulse 1.8s ease infinite' }} />
                <p className="font-mono" style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent)', letterSpacing: '1px', textTransform: 'uppercase' }}>
                  Live Clinical Companion: NurseAI
                </p>
              </div>

              <div style={{ flex: 1, overflowY: 'auto', padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>
                {messages.map((msg, index) => (
                  <div key={index} style={{ display: 'flex', justifyContent: msg.sender === 'patient' ? 'flex-end' : 'flex-start' }}>
                    <div style={{
                      maxWidth: '82%', padding: '14px 18px', borderRadius: 18, fontSize: 14, lineHeight: 1.65,
                      borderBottomRightRadius: msg.sender === 'patient' ? 4 : 18,
                      borderBottomLeftRadius: msg.sender === 'nurse' ? 4 : 18,
                      background: msg.sender === 'patient'
                        ? 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)'
                        : msg.automated
                          ? 'rgba(245,158,11,0.1)'
                          : 'var(--bg-elevated)',
                      color: msg.sender === 'patient' ? '#07090F' : 'var(--text-1)',
                      fontWeight: msg.sender === 'patient' ? 600 : 400,
                      border: msg.sender === 'patient'
                        ? 'none'
                        : msg.automated
                          ? '1px solid rgba(245,158,11,0.3)'
                          : '1px solid var(--border)',
                      borderLeft: msg.sender === 'nurse' && !msg.automated ? '3px solid var(--accent)' : undefined,
                      boxShadow: msg.sender === 'patient' ? '0 4px 14px var(--accent-glow)' : '0 2px 10px rgba(0,0,0,0.3)',
                    }}>
                      {msg.automated && (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                          <span className="font-mono" style={{ fontSize: 9, fontWeight: 700, letterSpacing: '1px', color: '#FBBF24', textTransform: 'uppercase' }}>
                            ⏰ Scheduled Reminder
                          </span>
                        </div>
                      )}
                      {msg.image && <img src={msg.image} style={{ width: '100%', height: 'auto', borderRadius: 12, marginBottom: 10, objectFit: 'cover' }} alt="wound capture" />}
                      {msg.text}
                    </div>
                  </div>
                ))}
                {loading && (
                  <div className="font-mono" style={{ fontSize: 11, color: 'var(--accent)', fontStyle: 'italic', marginLeft: 12 }}>
                    NurseAI is reasoning...
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <div style={{ padding: 16, background: 'var(--bg-elevated)', borderTop: '1px solid var(--border)', display: 'flex', gap: 12, alignItems: 'center' }}>
                <button
                  onClick={() => setShowUploadModal(true)}
                  style={{
                    padding: 10, color: 'var(--slate)', background: 'rgba(255,255,255,0.04)',
                    border: '1px solid var(--border)', borderRadius: 12, cursor: 'pointer',
                    transition: 'all .2s', display: 'flex', alignItems: 'center', justifyContent: 'center'
                  }}
                  onMouseEnter={e => { e.currentTarget.style.color = 'var(--accent)'; e.currentTarget.style.borderColor = 'rgba(0,212,170,0.3)'; }}
                  onMouseLeave={e => { e.currentTarget.style.color = 'var(--slate)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
                  title="Upload wound or symptom photo"
                >
                  <IconCameraScan className="w-5 h-5" />
                </button>
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                  placeholder={isRecording ? 'Listening to voice...' : 'Type symptoms or ask your nurse...'}
                  disabled={isRecording}
                  style={{
                    flex: 1, padding: '12px 16px', borderRadius: 12, fontSize: 14,
                    background: isRecording ? 'rgba(255,68,68,0.1)' : 'var(--bg-surface)',
                    color: isRecording ? '#FF6B6B' : 'var(--text-1)',
                    border: `1px solid ${isRecording ? 'rgba(255,68,68,0.4)' : 'var(--border)'}`,
                    outline: 'none', transition: 'all .2s',
                  }}
                />
                {input.trim() === '' ? (
                  <button
                    onMouseDown={startRecording}
                    onMouseUp={stopRecording}
                    style={{
                      padding: 11, borderRadius: 12, border: 'none', cursor: 'pointer',
                      background: isRecording ? '#FF4444' : 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
                      color: isRecording ? '#fff' : '#07090F',
                      boxShadow: '0 4px 14px var(--accent-glow)',
                      transition: 'all .2s', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}
                    title="Hold to speak"
                  >
                    <IconMic className="w-5 h-5" />
                  </button>
                ) : (
                  <button
                    onClick={handleSend}
                    style={{
                      padding: '12px 22px', borderRadius: 12, border: 'none', cursor: 'pointer',
                      background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
                      color: '#07090F', fontWeight: 800, fontSize: 13,
                      boxShadow: '0 4px 16px var(--accent-glow)',
                      transition: 'all .2s', fontFamily: 'Inter, sans-serif',
                    }}
                  >
                    SEND
                  </button>
                )}
              </div>
            </div>

            <div className="hidden lg:flex w-80 flex-col gap-4">
              <VitalsWidget />
              <div style={{ background: 'var(--bg-surface)', border: '1px solid rgba(0,212,170,0.25)', borderRadius: 20, padding: 20 }}>
                <p className="font-mono" style={{ fontSize: 10, color: 'var(--accent)', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 6 }}>
                  💡 Recovery Advice
                </p>
                <p style={{ fontSize: 12.5, color: 'var(--text-2)', lineHeight: 1.6 }}>
                  If you feel sudden dizziness or chest discomfort, rest immediately and type "I feel dizzy" for prompt clinical escalation.
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {showUploadModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 100,
          background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(10px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
        }}>
          <div style={{
            background: 'var(--bg-elevated)', border: '1px solid var(--border-bright)',
            borderRadius: 22, padding: 28, width: '100%', maxWidth: 420,
            boxShadow: '0 20px 60px rgba(0,0,0,0.8)',
          }}>
            <h3 className="font-display" style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-1)', marginBottom: 16 }}>
              Upload Wound Photo
            </h3>
            <div
              onClick={() => fileInputRef.current?.click()}
              style={{
                border: '2px dashed rgba(0,212,170,0.3)',
                height: 180, display: 'flex', alignItems: 'center', justifyContent: 'center',
                borderRadius: 16, cursor: 'pointer', background: 'rgba(0,212,170,0.03)',
                transition: 'all .2s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(0,212,170,0.3)'}
            >
              {imagePreview ? (
                <img src={imagePreview} style={{ height: '100%', objectFit: 'contain', borderRadius: 12 }} alt="preview" />
              ) : (
                <div style={{ textAlign: 'center' }}>
                  <IconCameraScan className="w-10 h-10 mx-auto mb-2 text-teal-400" />
                  <span style={{ fontSize: 13, color: 'var(--text-2)' }}>Tap or drop photo here</span>
                  <p style={{ fontSize: 10, color: 'var(--text-3)', marginTop: 4 }}>JPEG, PNG accepted</p>
                </div>
              )}
            </div>
            <input type="file" ref={fileInputRef} onChange={handleFileSelect} accept="image/*" className="hidden" />
            <div style={{ display: 'flex', gap: 12, marginTop: 22 }}>
              <button
                onClick={() => { setShowUploadModal(false); setSelectedFile(null); setImagePreview(null); }}
                style={{
                  flex: 1, padding: '12px 0', color: 'var(--text-2)', background: 'rgba(255,255,255,0.05)',
                  border: '1px solid var(--border)', borderRadius: 12, fontWeight: 600, fontSize: 13,
                  cursor: 'pointer', transition: 'all .2s', fontFamily: 'Inter, sans-serif',
                }}
              >
                Cancel
              </button>
              <button
                onClick={submitUpload}
                disabled={!selectedFile}
                style={{
                  flex: 1, padding: '12px 0',
                  background: 'linear-gradient(135deg, var(--accent) 0%, var(--accent-dark) 100%)',
                  color: '#07090F', border: 'none', borderRadius: 12, fontWeight: 800, fontSize: 13,
                  cursor: selectedFile ? 'pointer' : 'not-allowed', opacity: selectedFile ? 1 : 0.4,
                  boxShadow: '0 4px 16px var(--accent-glow)', transition: 'all .2s', fontFamily: 'Inter, sans-serif',
                }}
              >
                Upload & Analyze
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default TriageDashboard;