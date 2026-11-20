import React, { useState, useEffect } from 'react';
import {
  getMyPlan,
  getPatientUnderstandingCheck,
  submitUnderstandingAnswer,
  planMyDay,
  getPlanIcsUrl,
} from '../services/api';
import {
  IconPill,
  IconClock,
  IconAlertTriangle,
  IconActivity,
  IconCheck,
  IconShieldCheck,
  IconFileText,
} from './Icons';

export default function PatientMyPlanView({ lang = 'en', onAskAssistant }) {
  const isHindi = lang === 'hi';
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [planData, setPlanData] = useState(null);
  const [activeCategory, setActiveCategory] = useState('all'); // 'all', 'today', 'medicines', 'wound_care', 'warning_signs', 'appointments', 'activities'
  const [activityChecked, setActivityChecked] = useState({});
  const [checkQuestions, setCheckQuestions] = useState([]);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [submittingCheck, setSubmittingCheck] = useState({});
  const [checkFeedback, setCheckFeedback] = useState({});
  const [dayPlan, setDayPlan] = useState(null);
  const [dayPlanLoading, setDayPlanLoading] = useState(false);
  const [showDayPlan, setShowDayPlan] = useState(false);

  const handlePlanMyDay = async () => {
    setDayPlanLoading(true);
    setShowDayPlan(true);
    try {
      const res = await planMyDay(lang);
      setDayPlan(res);
    } catch (err) {
      alert(err.message || 'Could not load day schedule');
    } finally {
      setDayPlanLoading(false);
    }
  };

  const loadPlanAndCheck = async () => {
    setLoading(true);
    setError(null);
    try {
      const plan = await getMyPlan();
      setPlanData(plan);
      try {
        const checkRes = await getPatientUnderstandingCheck();
        setCheckQuestions(checkRes.questions || []);
      } catch (e) {
        // Understanding check optional
      }
    } catch (err) {
      setError(err.message || (isHindi ? 'रिकवरी योजना लोड करने में असमर्थ।' : 'Unable to load recovery plan.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadPlanAndCheck();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleToggleActivity = (itemId) => {
    setActivityChecked((prev) => ({
      ...prev,
      [itemId]: !prev[itemId],
    }));
  };

  const handleSelectOption = (checkId, optionIdx) => {
    setSelectedAnswers((prev) => ({
      ...prev,
      [checkId]: optionIdx,
    }));
  };

  const handleSubmitCheckAnswer = async (checkId) => {
    const optIdx = selectedAnswers[checkId];
    if (optIdx === undefined) return;

    setSubmittingCheck((prev) => ({ ...prev, [checkId]: true }));
    try {
      const res = await submitUnderstandingAnswer(checkId, optIdx);
      setCheckFeedback((prev) => ({
        ...prev,
        [checkId]: res.message || (isHindi ? 'पुष्टि के लिए धन्यवाद।' : 'Thank you for confirming your understanding.'),
      }));
      // Refresh questions
      const checkRes = await getPatientUnderstandingCheck();
      setCheckQuestions(checkRes.questions || []);
    } catch (err) {
      alert(`Submission failed: ${err.message}`);
    } finally {
      setSubmittingCheck((prev) => ({ ...prev, [checkId]: false }));
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '60px 20px', textAlign: 'center', color: 'var(--text-secondary, #64748b)' }}>
        <div style={{ fontSize: '15px', fontWeight: 600 }}>
          {isHindi ? 'आपकी व्यक्तिगत रिकवरी योजना लोड हो रही है...' : 'Loading your recovery plan...'}
        </div>
      </div>
    );
  }

  if (error || !planData) {
    return (
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '48px 24px',
          textAlign: 'center',
          maxWidth: '640px',
          margin: '20px auto',
        }}
      >
        <div style={{ fontSize: '36px', marginBottom: '12px' }}>📋</div>
        <h3 style={{ margin: '0 0 8px 0', fontSize: '18px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
          {isHindi ? 'रिकवरी योजना की तैयारी जारी है' : 'Personal Recovery Plan in Progress'}
        </h3>
        <p style={{ margin: '0 0 20px 0', fontSize: '14px', color: 'var(--text-secondary, #64748b)', lineHeight: '1.5' }}>
          {isHindi
            ? 'आपकी देखभाल टीम वर्तमान में आपके डिस्चार्ज सारांश के आधार पर आपकी व्यक्तिगत रिकवरी योजना की समीक्षा कर रही है। कृपया कुछ समय बाद पुनः देखें।'
            : 'Your care team is reviewing your personalized plan based on your hospital discharge papers. Approved recovery steps will appear here shortly.'}
        </p>
        <button
          type="button"
          onClick={loadPlanAndCheck}
          style={{
            padding: '10px 20px',
            background: 'var(--accent-teal, #0f766e)',
            color: '#ffffff',
            border: 'none',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {isHindi ? 'पुनः जांचें' : 'Check Again'}
        </button>
      </div>
    );
  }

  const filterCategories = [
    { id: 'all', label: isHindi ? 'सभी निर्देश' : 'All Guidelines', count: planData.all_items?.length || 0 },
    { id: 'today', label: isHindi ? 'आज के कार्य' : 'Today & Schedule', count: planData.today_items?.length || 0 },
    { id: 'medicines', label: isHindi ? 'दवाएं' : 'Medicines', count: planData.medicines?.length || 0 },
    { id: 'wound_care', label: isHindi ? 'चीरा और घाव' : 'Incision & Wound', count: planData.wound_care?.length || 0 },
    { id: 'warning_signs', label: isHindi ? 'सावधानी के संकेत' : 'Warning Signs', count: planData.warning_signs?.length || 0 },
    { id: 'appointments', label: isHindi ? 'अपॉइंटमेंट' : 'Appointments', count: planData.appointments?.length || 0 },
    { id: 'activities', label: isHindi ? 'शारीरिक गतिविधि' : 'Activity & Walking', count: planData.activities?.length || 0 },
  ];

  const getFilteredItems = () => {
    switch (activeCategory) {
      case 'today':
        return planData.today_items || [];
      case 'medicines':
        return planData.medicines || [];
      case 'wound_care':
        return planData.wound_care || [];
      case 'warning_signs':
        return planData.warning_signs || [];
      case 'appointments':
        return planData.appointments || [];
      case 'activities':
        return planData.activities || [];
      default:
        return planData.all_items || [];
    }
  };

  const itemsToDisplay = getFilteredItems();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Plan Header Card */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'flex-start',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '5px',
                padding: '4px 10px',
                borderRadius: '6px',
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid #10b981',
                color: '#065f46',
                fontSize: '11px',
                fontWeight: 700,
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              <IconShieldCheck style={{ width: '13px', height: '13px' }} />
              {isHindi ? 'डॉक्टर द्वारा स्वीकृत' : 'Doctor Approved'}
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-secondary, #64748b)' }}>
              Version {planData.version}
            </span>
          </div>

          <h2 style={{ margin: '0 0 6px 0', fontSize: '20px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
            {isHindi ? 'आपकी व्यक्तिगत रिकवरी योजना' : 'My Personal Recovery Plan'}
          </h2>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary, #64748b)', lineHeight: '1.5' }}>
            {isHindi
              ? `स्वीकृत: ${planData.approved_by_name} द्वारा। यह योजना सीधे आपके अस्पताल डिस्चार्ज सारांश के आधार पर तैयार की गई है।`
              : `Approved by ${planData.approved_by_name}. Structured step-by-step guidance grounded in your official hospital discharge summary.`}
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            if (onAskAssistant) onAskAssistant('Can you explain my recovery plan and medication schedule?');
          }}
          style={{
            padding: '10px 16px',
            background: 'var(--accent-teal, #0f766e)',
            color: '#ffffff',
            border: 'none',
            borderRadius: '8px',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>💬</span>
          {isHindi ? 'योजना के बारे में पूछें' : 'Ask Assistant About Plan'}
        </button>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={handlePlanMyDay}
            style={{
              padding: '10px 16px',
              background: 'var(--accent-blue, #0284c7)',
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span>📅</span>
            {dayPlanLoading
              ? (isHindi ? 'योजना बन रही है...' : 'Planning...')
              : (isHindi ? 'मेरे दिन की योजना बनाएं' : 'Plan my day')}
          </button>

          <button
            type="button"
            onClick={() => {
              if (onAskAssistant) onAskAssistant('Can you explain my recovery plan and medication schedule?');
            }}
            style={{
              padding: '10px 16px',
              background: 'var(--accent-teal, #0f766e)',
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span>💬</span>
            {isHindi ? 'योजना के बारे में पूछें' : 'Ask Assistant About Plan'}
          </button>
        </div>
      </div>

      {/* Phase 5: Plan My Day Schedule View */}
      {showDayPlan && dayPlan && (
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--accent-blue, #0284c7)',
            borderRadius: '12px',
            padding: '24px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '20px' }}>📅</span>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                {isHindi ? 'आज का रिकवरी शेड्यूल (निश्चित समय सारिणी)' : "Today's Recovery Schedule"}
              </h3>
            </div>
            <div style={{ display: 'flex', gap: '8px' }}>
              <a
                href={getPlanIcsUrl()}
                download="careloop_schedule.ics"
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '6px 12px',
                  background: 'var(--accent-teal, #0d9488)',
                  color: '#ffffff',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: 600,
                  textDecoration: 'none',
                }}
              >
                <span>📥</span>
                {isHindi ? 'कैलेंडर में जोड़ें (.ics)' : 'Add to calendar (.ics)'}
              </a>
              <button
                type="button"
                onClick={() => setShowDayPlan(false)}
                style={{
                  padding: '6px 10px',
                  background: 'transparent',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  borderRadius: '6px',
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                ✕ {isHindi ? 'बंद करें' : 'Close'}
              </button>
            </div>
          </div>

          <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: 'var(--accent-blue, #0284c7)', fontWeight: 600 }}>
            ℹ️ {dayPlan.safe_planning_notice}
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
            {dayPlan.slots && dayPlan.slots.map((slot, sIdx) => (
              <div
                key={sIdx}
                style={{
                  background: 'var(--bg-subtle, #f8fafc)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '8px',
                  padding: '12px',
                }}
              >
                <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary, #0f172a)', marginBottom: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '4px' }}>
                  {slot.period}
                </div>
                {slot.items && slot.items.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {slot.items.map((it, itIdx) => (
                      <div key={itIdx} style={{ fontSize: '12px', background: '#ffffff', padding: '8px', borderRadius: '6px', border: '1px solid #f1f5f9' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 600, color: '#0f172a' }}>
                          <span>{it.title}</span>
                          <span style={{ color: 'var(--text-muted, #64748b)', fontSize: '11px' }}>{it.time}</span>
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-secondary, #64748b)', marginTop: '2px' }}>
                          {it.detail}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)', fontStyle: 'italic' }}>
                    {isHindi ? 'कोई निर्धारित गतिविधि नहीं' : 'No scheduled items'}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Emergency Red Flag Callout */}
      <div
        style={{
          background: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '12px',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '14px',
        }}
      >
        <div style={{ color: '#dc2626', marginTop: '2px' }}>
          <IconAlertTriangle style={{ width: '22px', height: '22px' }} />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: '13px', fontWeight: 700, color: '#991b1b', marginBottom: '3px' }}>
            {isHindi ? 'आपातकालीन चेतावनी संकेत — तुरंत 112 पर कॉल करें' : 'Emergency Warning Signs — Call 112 Immediately'}
          </div>
          <div style={{ fontSize: '12px', color: '#7f1d1d', lineHeight: '1.5' }}>
            {isHindi
              ? 'यदि आपको सीने में अत्यधिक दर्द, अचानक सांस फूलना, 38.5°C से अधिक बुखार, या चीरे से भारी रक्तस्राव हो, तो प्रतीक्षा न करें — तुरंत 112 पर कॉल करें या SOS दबाएं।'
              : 'If you experience severe chest tightness, sudden shortness of breath, fever > 38.5°C, or sudden wound bleeding, do not wait for chat review — call 112 immediately or trigger SOS.'}
          </div>
        </div>
      </div>

      {/* Category Filter Chips */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
        {filterCategories.map((cat) => {
          const isActive = activeCategory === cat.id;
          return (
            <button
              key={cat.id}
              type="button"
              onClick={() => setActiveCategory(cat.id)}
              style={{
                padding: '6px 14px',
                borderRadius: '20px',
                fontSize: '12px',
                fontWeight: isActive ? 700 : 500,
                border: isActive ? '1px solid var(--accent-teal, #0f766e)' : '1px solid var(--border-subtle, #cbd5e1)',
                background: isActive ? 'var(--accent-teal, #0f766e)' : 'var(--bg-surface, #ffffff)',
                color: isActive ? '#ffffff' : 'var(--text-secondary, #475569)',
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.15s ease',
              }}
            >
              <span>{cat.label}</span>
              <span
                style={{
                  fontSize: '11px',
                  opacity: isActive ? 0.9 : 0.7,
                  background: isActive ? 'rgba(255,255,255,0.2)' : 'var(--bg-subtle, #f1f5f9)',
                  padding: '1px 6px',
                  borderRadius: '10px',
                }}
              >
                {cat.count}
              </span>
            </button>
          );
        })}
      </div>

      {/* Plan Items List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {itemsToDisplay.map((item, idx) => {
          const isActivity = item.item_type === 'Activity';
          const isWarning = item.item_type === 'Warning_Sign';
          const isDone = isActivity && activityChecked[item.item_id];

          return (
            <div
              key={item.item_id || idx}
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: isWarning ? '1px solid rgba(239, 68, 68, 0.3)' : '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '12px',
                padding: '18px 22px',
                boxShadow: 'var(--shadow-card)',
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                transition: 'border-color 0.2s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                  {isActivity ? (
                    <input
                      type="checkbox"
                      checked={!!isDone}
                      onChange={() => handleToggleActivity(item.item_id)}
                      style={{ marginTop: '3px', cursor: 'pointer', width: '18px', height: '18px', accentColor: 'var(--accent-teal, #0f766e)' }}
                    />
                  ) : item.item_type === 'Medicine' ? (
                    <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(14, 165, 233, 0.1)', color: '#0284c7' }}>
                      <IconPill style={{ width: '18px', height: '18px' }} />
                    </div>
                  ) : item.item_type === 'Wound_Care' ? (
                    <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' }}>
                      <IconShieldCheck style={{ width: '18px', height: '18px' }} />
                    </div>
                  ) : item.item_type === 'Warning_Sign' ? (
                    <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' }}>
                      <IconAlertTriangle style={{ width: '18px', height: '18px' }} />
                    </div>
                  ) : item.item_type === 'Appointment' ? (
                    <div style={{ padding: '6px', borderRadius: '8px', background: 'rgba(168, 85, 247, 0.1)', color: '#9333ea' }}>
                      <IconClock style={{ width: '18px', height: '18px' }} />
                    </div>
                  ) : (
                    <div style={{ padding: '6px', borderRadius: '8px', background: 'var(--bg-subtle, #f1f5f9)', color: '#64748b' }}>
                      <IconActivity style={{ width: '18px', height: '18px' }} />
                    </div>
                  )}

                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                      <h4
                        style={{
                          margin: 0,
                          fontSize: '15px',
                          fontWeight: 700,
                          color: isDone ? 'var(--text-secondary, #64748b)' : 'var(--text-primary, #0f172a)',
                          textDecoration: isDone ? 'line-through' : 'none',
                        }}
                      >
                        {item.title}
                      </h4>
                      {item.schedule_text && (
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            padding: '2px 8px',
                            borderRadius: '6px',
                            background: 'var(--bg-subtle, #f1f5f9)',
                            color: 'var(--text-secondary, #475569)',
                          }}
                        >
                          🕒 {item.schedule_text}
                        </span>
                      )}
                    </div>

                    <p
                      style={{
                        margin: '6px 0 0 0',
                        fontSize: '13px',
                        color: 'var(--text-secondary, #334155)',
                        lineHeight: '1.5',
                      }}
                    >
                      {item.detail}
                    </p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    if (onAskAssistant) {
                      onAskAssistant(`From my recovery plan, tell me more about: ${item.title}. Passage: "${item.detail}"`);
                    }
                  }}
                  style={{
                    padding: '5px 10px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle, #cbd5e1)',
                    background: 'transparent',
                    color: 'var(--text-secondary, #475569)',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <IconFileText style={{ width: '12px', height: '12px' }} />
                  {isHindi ? 'पूछें' : 'Ask about this'}
                </button>
              </div>

              {/* Source Passage Footnote */}
              <div
                style={{
                  borderTop: '1px dashed var(--border-subtle, #e2e8f0)',
                  paddingTop: '8px',
                  marginTop: '4px',
                  fontSize: '11px',
                  color: 'var(--text-secondary, #64748b)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <span>{item.source_label || '📄 Discharge summary · General'}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Understanding Check Card (Feature F5 P2) */}
      {checkQuestions && checkQuestions.length > 0 && (
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '12px',
            padding: '24px',
            boxShadow: 'var(--shadow-card)',
            marginTop: '10px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
            <span style={{ fontSize: '18px' }}>💡</span>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
              {isHindi ? 'रिकवरी समझ की पुष्टि' : 'Recovery Understanding Confirmation'}
            </h3>
          </div>
          <p style={{ margin: '0 0 18px 0', fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
            {isHindi
              ? 'यह त्वरित जांच यह सुनिश्चित करती है कि आप घर पर अपनी देखभाल को लेकर आश्वस्त हैं। कोई परीक्षा या अंक नहीं हैं।'
              : 'A brief confirmation to verify your recovery instructions are clear. There are no scores or grades.'}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {checkQuestions.map((q, idx) => {
              const selected = selectedAnswers[q.check_id];
              const isSubmitting = submittingCheck[q.check_id];
              const feedback = checkFeedback[q.check_id];

              return (
                <div
                  key={q.check_id}
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    background: 'var(--bg-subtle, #f8fafc)',
                  }}
                >
                  <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary, #0f172a)', marginBottom: '10px' }}>
                    {idx + 1}. {q.question_text}
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {q.options?.map((opt, optIdx) => (
                      <label
                        key={optIdx}
                        style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '10px',
                          fontSize: '13px',
                          color: 'var(--text-primary, #1e293b)',
                          cursor: q.answered ? 'default' : 'pointer',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          background: selected === optIdx || (q.answered && q.selected_option_index === optIdx) ? 'rgba(15, 118, 110, 0.08)' : 'transparent',
                        }}
                      >
                        <input
                          type="radio"
                          name={`q-${q.check_id}`}
                          disabled={q.answered}
                          checked={selected === optIdx || (q.answered && q.selected_option_index === optIdx)}
                          onChange={() => handleSelectOption(q.check_id, optIdx)}
                          style={{ marginTop: '2px', accentColor: 'var(--accent-teal, #0f766e)' }}
                        />
                        <span>{opt}</span>
                      </label>
                    ))}
                  </div>

                  {!q.answered && (
                    <button
                      type="button"
                      disabled={selected === undefined || isSubmitting}
                      onClick={() => handleSubmitCheckAnswer(q.check_id)}
                      style={{
                        marginTop: '12px',
                        padding: '6px 14px',
                        background: selected !== undefined ? 'var(--accent-teal, #0f766e)' : '#cbd5e1',
                        color: '#ffffff',
                        border: 'none',
                        borderRadius: '6px',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: selected !== undefined ? 'pointer' : 'not-allowed',
                      }}
                    >
                      {isSubmitting ? (isHindi ? 'जमा हो रहा है...' : 'Saving...') : (isHindi ? 'उत्तर की पुष्टि करें' : 'Confirm Answer')}
                    </button>
                  )}

                  {(q.answered || feedback) && (
                    <div
                      style={{
                        marginTop: '10px',
                        fontSize: '12px',
                        fontWeight: 600,
                        color: '#065f46',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <IconCheck style={{ width: '14px', height: '14px' }} />
                      <span>{feedback || (isHindi ? 'निर्देश समझ लिए गए।' : 'Guideline confirmed.')}</span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

