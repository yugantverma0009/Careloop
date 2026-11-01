import React, { useState, useEffect } from 'react';
import { getActiveCheckinTemplate, startCheckinSession, recordCheckinAnswer } from '../services/api';
import {
  IconShieldCheck,
  IconAlertTriangle,
  IconCheck,
  IconMic,
  IconArrowRight,
  IconClock,
} from './Icons';

export default function CheckinGuide({ lang = 'en', onComplete, onEmergency }) {
  const [template, setTemplate] = useState(null);
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [emergencyAlert, setEmergencyAlert] = useState(null);

  useEffect(() => {
    initGuide();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initGuide = async () => {
    setLoading(true);
    setError(null);
    try {
      const tmpl = await getActiveCheckinTemplate();
      setTemplate(tmpl);
      const sess = await startCheckinSession('App_Guided');
      setSession(sess);
    } catch (err) {
      setError(err.message || 'Failed to initialize check-in guide.');
    } finally {
      setLoading(false);
    }
  };

  const handleListen = (text) => {
    if (typeof window === 'undefined' || !('speechSynthesis' in window)) {
      alert('Speech audio is not supported in this browser.');
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang === 'hi' ? 'hi-IN' : 'en-IN';
    utterance.rate = 0.92;
    window.speechSynthesis.speak(utterance);
  };

  const handleStartVoice = (questionId) => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert(lang === 'hi' ? 'आपका ब्राउज़र वॉइस इनपुट का समर्थन नहीं करता।' : 'Voice recognition is not supported in this browser.');
      return;
    }
    const rec = new SpeechRecognition();
    rec.lang = lang === 'hi' ? 'hi-IN' : 'en-IN';
    rec.continuous = false;
    rec.interimResults = true;
    rec.onstart = () => setIsListening(true);
    rec.onend = () => setIsListening(false);
    rec.onerror = () => setIsListening(false);
    rec.onresult = (e) => {
      const transcript = Array.from(e.results).map((r) => r[0].transcript).join('');
      setAnswers((prev) => ({ ...prev, [questionId]: transcript }));
    };
    rec.start();
  };

  const handleSelectAnswer = (questionId, value) => {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleNextStep = async () => {
    if (!session || !template) return;
    const questions = template.questions || [];
    const q = questions[currentStep];
    const val = answers[q.question_id];

    if (val === undefined || val === '') {
      alert(lang === 'hi' ? 'कृपया आगे बढ़ने से पहले उत्तर चुनें।' : 'Please select an answer before proceeding.');
      return;
    }

    setSubmitting(true);
    try {
      const res = await recordCheckinAnswer(session.session_id, q.question_id, val);
      
      // If emergency triggered on Question 2
      if (res.emergency || res.status === 'emergency_triggered') {
        setEmergencyAlert(res);
        if (onEmergency) onEmergency(res);
        return;
      }

      if (res.completed) {
        if (onComplete) onComplete(res);
      } else {
        setCurrentStep((prev) => prev + 1);
      }
    } catch (err) {
      alert(`Submission error: ${err.message || 'Error'}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
        <IconClock width={24} height={24} style={{ margin: '0 auto 10px', display: 'block' }} />
        {lang === 'hi' ? 'चेक-इन गाइड लोड हो रहा है...' : 'Starting guided check-in...'}
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '24px', background: 'var(--bg-base, #f8fafc)', borderRadius: '10px', textAlign: 'center' }}>
        <p style={{ color: 'var(--alert-red, #dc2626)', fontSize: '13px', margin: '0 0 12px 0' }}>{error}</p>
        <button
          type="button"
          onClick={initGuide}
          style={{
            padding: '6px 14px',
            borderRadius: '6px',
            border: 'none',
            background: 'var(--navy-deep, #0b1528)',
            color: '#fff',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {lang === 'hi' ? 'पुनः प्रयास करें' : 'Retry'}
        </button>
      </div>
    );
  }

  // EMERGENCY ALERT STATE
  if (emergencyAlert) {
    return (
      <div
        style={{
          background: 'var(--alert-red-soft, #fef2f2)',
          border: '2px solid var(--alert-red, #dc2626)',
          borderRadius: '12px',
          padding: '24px',
          color: 'var(--alert-red-text, #991b1b)',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <IconAlertTriangle width={28} height={28} style={{ color: 'var(--alert-red, #dc2626)' }} />
          <div>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              {lang === 'hi' ? 'आपातकालीन सुरक्षा अलर्ट' : 'Immediate Safety Alert'}
            </h3>
            <p style={{ margin: '2px 0 0 0', fontSize: '12px', opacity: 0.9 }}>
              {lang === 'hi' ? 'आपकी देखभाल टीम को तत्काल अलर्ट भेजा गया है' : 'Your care team has been notified immediately'}
            </p>
          </div>
        </div>

        <div
          style={{
            background: '#ffffff',
            padding: '14px 16px',
            borderRadius: '8px',
            border: '1px solid rgba(220, 38, 38, 0.25)',
            fontSize: '13px',
            lineHeight: 1.6,
            fontWeight: 600,
            color: '#0f172a',
          }}
        >
          {lang === 'hi' ? emergencyAlert.guidance_hi : emergencyAlert.guidance_en}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '10px', paddingTop: '6px' }}>
          <a
            href="tel:112"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              borderRadius: '8px',
              background: 'var(--alert-red, #dc2626)',
              color: '#ffffff',
              fontSize: '13px',
              fontWeight: 800,
              textDecoration: 'none',
              boxShadow: '0 2px 4px rgba(220, 38, 38, 0.3)',
            }}
          >
            <span>🚨 {lang === 'hi' ? 'तत्काल 112 डायल करें' : 'Immediately Dial 112'}</span>
          </a>
          <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
            Flag #{emergencyAlert.flag_id} · Urgent Review Active
          </span>
        </div>
      </div>
    );
  }

  const questions = template?.questions || [];
  const currentQ = questions[currentStep];
  if (!currentQ) return null;

  const currentVal = answers[currentQ.question_id];
  const questionText = lang === 'hi' ? currentQ.text_hi : currentQ.text_en;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Step Progress Bar & Dots */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
            {lang === 'hi'
              ? `प्रश्न ${currentStep + 1} / ${questions.length}`
              : `Question ${currentStep + 1} of ${questions.length}`}
          </span>
          <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
            {template.name}
          </span>
        </div>

        {/* Dots */}
        <div style={{ display: 'flex', gap: '6px' }}>
          {questions.map((q, idx) => (
            <div
              key={q.question_id}
              style={{
                flex: 1,
                height: '6px',
                borderRadius: '3px',
                background:
                  idx === currentStep
                    ? 'var(--accent-teal, #0d9488)'
                    : idx < currentStep
                    ? 'var(--role-patient, #0284c7)'
                    : 'var(--border-subtle, #e2e8f0)',
                transition: 'all 0.2s ease',
              }}
            />
          ))}
        </div>
      </div>

      {/* Question Card */}
      <div
        style={{
          background: 'var(--bg-base, #f8fafc)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '22px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '12px', marginBottom: '18px' }}>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', lineHeight: 1.45 }}>
            {questionText}
          </h3>
          <button
            type="button"
            onClick={() => handleListen(questionText)}
            title={lang === 'hi' ? 'सुनें (ऑडियो)' : 'Listen aloud'}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: '1px solid var(--border-subtle, #cbd5e1)',
              background: '#ffffff',
              color: 'var(--text-secondary, #475569)',
              fontSize: '11px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              flexShrink: 0,
            }}
          >
            <span>🔊</span>
            <span>{lang === 'hi' ? 'सुनें' : 'Listen'}</span>
          </button>
        </div>

        {/* Question Type: Scale 0 to 10 */}
        {currentQ.response_type === 'Scale_0_10' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600, marginBottom: '8px' }}>
              <span>{lang === 'hi' ? '0 = कोई दर्द नहीं' : '0 = No pain'}</span>
              <span>{lang === 'hi' ? '10 = असहनीय दर्द' : '10 = Worst pain'}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(11, 1fr)', gap: '6px' }}>
              {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((num) => {
                const isSelected = String(currentVal) === String(num);
                const isHigh = num >= 7;
                const isMid = num >= 4 && num < 7;
                return (
                  <button
                    key={num}
                    type="button"
                    onClick={() => handleSelectAnswer(currentQ.question_id, String(num))}
                    style={{
                      height: '46px',
                      borderRadius: '8px',
                      border: isSelected ? '2px solid #0f172a' : '1px solid var(--border-subtle, #cbd5e1)',
                      background: isSelected
                        ? '#0b1528'
                        : isHigh
                        ? '#fef2f2'
                        : isMid
                        ? '#fffbeb'
                        : '#ffffff',
                      color: isSelected
                        ? '#ffffff'
                        : isHigh
                        ? '#dc2626'
                        : isMid
                        ? '#d97706'
                        : '#0f172a',
                      fontSize: '15px',
                      fontWeight: 800,
                      cursor: 'pointer',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    {num}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Question Type: Yes / No */}
        {currentQ.response_type === 'Yes_No' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <button
              type="button"
              onClick={() => handleSelectAnswer(currentQ.question_id, 'No')}
              style={{
                padding: '18px',
                borderRadius: '10px',
                border: currentVal === 'No' ? '2px solid var(--success-green, #059669)' : '1px solid var(--border-subtle, #cbd5e1)',
                background: currentVal === 'No' ? 'var(--success-green-soft, #f0fdf4)' : '#ffffff',
                color: currentVal === 'No' ? 'var(--success-green, #059669)' : 'var(--text-primary, #0f172a)',
                fontSize: '16px',
                fontWeight: 800,
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.15s ease',
              }}
            >
              ✓ {lang === 'hi' ? 'नहीं (कोई लक्षण नहीं)' : 'No (None)'}
            </button>

            <button
              type="button"
              onClick={() => handleSelectAnswer(currentQ.question_id, 'Yes')}
              style={{
                padding: '18px',
                borderRadius: '10px',
                border: currentVal === 'Yes' ? '2px solid var(--alert-red, #dc2626)' : '1px solid var(--border-subtle, #cbd5e1)',
                background: currentVal === 'Yes' ? 'var(--alert-red-soft, #fef2f2)' : '#ffffff',
                color: currentVal === 'Yes' ? 'var(--alert-red, #dc2626)' : 'var(--text-primary, #0f172a)',
                fontSize: '16px',
                fontWeight: 800,
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.15s ease',
              }}
            >
              ⚠️ {lang === 'hi' ? 'हाँ (मुझे यह लक्षण है)' : 'Yes (I have this)'}
            </button>
          </div>
        )}

        {/* Question Type: Choice */}
        {currentQ.response_type === 'Choice' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {(currentQ.choices || []).map((ch) => {
              const isSelected = currentVal === ch.key;
              const label = lang === 'hi' ? ch.label_hi : ch.label_en;
              return (
                <button
                  key={ch.key}
                  type="button"
                  onClick={() => handleSelectAnswer(currentQ.question_id, ch.key)}
                  style={{
                    padding: '14px 18px',
                    borderRadius: '10px',
                    border: isSelected ? '2px solid var(--role-patient, #0284c7)' : '1px solid var(--border-subtle, #cbd5e1)',
                    background: isSelected ? '#eff6ff' : '#ffffff',
                    color: isSelected ? '#0284c7' : 'var(--text-primary, #0f172a)',
                    fontSize: '14px',
                    fontWeight: isSelected ? 800 : 600,
                    cursor: 'pointer',
                    textAlign: 'left',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <span>{label}</span>
                  {isSelected && <IconCheck width={18} height={18} style={{ color: '#0284c7' }} />}
                </button>
              );
            })}
          </div>
        )}

        {/* Question Type: Text (with Voice Recognition) */}
        {currentQ.response_type === 'Text' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '8px' }}>
              <button
                type="button"
                onClick={() => handleStartVoice(currentQ.question_id)}
                style={{
                  padding: '6px 12px',
                  borderRadius: '6px',
                  border: isListening ? '1px solid var(--alert-red, #dc2626)' : '1px solid var(--border-subtle, #cbd5e1)',
                  background: isListening ? '#fef2f2' : '#ffffff',
                  color: isListening ? '#dc2626' : 'var(--text-secondary, #475569)',
                  fontSize: '11px',
                  fontWeight: 700,
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <IconMic width={14} height={14} style={{ color: isListening ? '#dc2626' : 'inherit' }} />
                <span>
                  {isListening
                    ? (lang === 'hi' ? 'बोलें, सुन रहा हूँ...' : 'Listening...')
                    : (lang === 'hi' ? 'बोलकर बताएं' : 'Voice Input')}
                </span>
              </button>
            </div>

            <textarea
              rows={3}
              placeholder={lang === 'hi' ? 'कोई अतिरिक्त लक्षण या विवरण यहाँ लिखें...' : 'Type or speak any additional notes for your care team...'}
              value={currentVal || ''}
              onChange={(e) => handleSelectAnswer(currentQ.question_id, e.target.value)}
              style={{
                width: '100%',
                padding: '12px',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle, #cbd5e1)',
                background: '#ffffff',
                color: 'var(--text-primary, #0f172a)',
                fontSize: '13px',
                boxSizing: 'border-box',
              }}
            />
          </div>
        )}
      </div>

      {/* Navigation Footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <button
          type="button"
          onClick={() => setCurrentStep((prev) => Math.max(0, prev - 1))}
          disabled={currentStep === 0 || submitting}
          style={{
            padding: '8px 18px',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle, #cbd5e1)',
            background: 'transparent',
            color: 'var(--text-secondary, #475569)',
            fontSize: '13px',
            fontWeight: 600,
            cursor: currentStep === 0 ? 'not-allowed' : 'pointer',
            opacity: currentStep === 0 ? 0.4 : 1,
          }}
        >
          {lang === 'hi' ? '← पिछला' : '← Back'}
        </button>

        <button
          type="button"
          onClick={handleNextStep}
          disabled={submitting}
          style={{
            padding: '10px 24px',
            borderRadius: '8px',
            border: 'none',
            background: 'var(--navy-deep, #0b1528)',
            color: '#ffffff',
            fontSize: '13px',
            fontWeight: 700,
            cursor: submitting ? 'wait' : 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <span>
            {currentStep === questions.length - 1
              ? (lang === 'hi' ? 'चेक-इन सबमिट करें' : 'Submit Check-in')
              : (lang === 'hi' ? 'अगला →' : 'Next Question →')}
          </span>
          <IconArrowRight width={14} height={14} />
        </button>
      </div>
    </div>
  );
}
