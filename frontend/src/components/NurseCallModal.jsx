import React, { useState, useEffect, useRef } from 'react';
import { API_BASE, logContactCall } from '../services/api';
import { IconPhone } from './Icons';

const QUICK_REPORTS = [
  'Fatigue after walk',
  'Denies acute chest pain',
  'Morning meds taken on time',
  'Mild tenderness at surgical site',
  'Breathing comfortably at rest',
  'Slight dizziness on standing',
];

const QUICK_ACTIONS = [
  'Rest with legs elevated',
  'Continue scheduled medications',
  'Maintain hydration & rest',
  'Re-test vital signs in 2h',
  'Call clinic if symptoms change',
];

export default function NurseCallModal({
  isOpen,
  onClose,
  patient,
  onCallLogged,
}) {
  const [reached, setReached] = useState(true);
  const [selectedReports, setSelectedReports] = useState([]);
  const [selectedActions, setSelectedActions] = useState([]);
  const [needsDoctor, setNeedsDoctor] = useState(false);

  // Voice Note Dictation state (Browser Web Speech API, zero audio stored)
  const [isRecording, setIsRecording] = useState(false);
  const [voiceTranscript, setVoiceTranscript] = useState('');
  const recognitionRef = useRef(null);

  // Agent Drafting & Approval State
  const [drafting, setDrafting] = useState(false);
  const [draftResult, setDraftResult] = useState(null);
  const [editedNote, setEditedNote] = useState('');
  const [editedTask, setEditedTask] = useState('');
  const [editedMessage, setEditedMessage] = useState('');
  const [approving, setApproving] = useState(false);
  const [error, setError] = useState('');
  const [clickCount, setClickCount] = useState(0);

  const token = localStorage.getItem('careloop_token');

  useEffect(() => {
    if (!isOpen) {
      setDraftResult(null);
      setSelectedReports([]);
      setSelectedActions([]);
      setVoiceTranscript('');
      setNeedsDoctor(false);
      setReached(true);
      setError('');
      setClickCount(0);
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
      setIsRecording(false);
    }
  }, [isOpen]);

  if (!isOpen || !patient) return null;

  const toggleReport = (rep) => {
    setClickCount((c) => c + 1);
    setSelectedReports((prev) =>
      prev.includes(rep) ? prev.filter((r) => r !== rep) : [...prev, rep]
    );
  };

  const toggleAction = (act) => {
    setClickCount((c) => c + 1);
    setSelectedActions((prev) =>
      prev.includes(act) ? prev.filter((a) => a !== act) : [...prev, act]
    );
  };

  // Browser Speech Recognition for optional voice note
  const toggleVoiceRecording = () => {
    setClickCount((c) => c + 1);
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please type directly into the dictation box.');
      return;
    }

    if (isRecording) {
      if (recognitionRef.current) recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      try {
        const recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-US';

        recognition.onresult = (event) => {
          let current = '';
          for (let i = 0; i < event.results.length; i++) {
            current += event.results[i][0].transcript + ' ';
          }
          setVoiceTranscript(current.trim());
        };

        recognition.onerror = (e) => {
          console.error('Speech recognition error', e);
          setIsRecording(false);
        };

        recognition.onend = () => {
          setIsRecording(false);
        };

        recognitionRef.current = recognition;
        recognition.start();
        setIsRecording(true);
      } catch (err) {
        console.error('Failed to start speech recognition', err);
        setIsRecording(false);
      }
    }
  };

  // Step 1: Request draft from Call Notes Agent
  const handleGenerateDraft = async () => {
    setClickCount((c) => c + 1);
    setDrafting(true);
    setError('');

    try {
      const res = await fetch(`${API_BASE}/agent/call-notes/draft`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          patient_id: patient.patientId,
          reached,
          patient_reports: selectedReports,
          actions_agreed: selectedActions,
          voice_transcript: voiceTranscript,
          needs_doctor: needsDoctor,
          call_script_id: patient.callScriptId || null,
        }),
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to draft call records.');
      }

      const draft = await res.json();
      setDraftResult(draft);
      setEditedNote(draft.note_text);
      setEditedTask(draft.task_description);
      setEditedMessage(draft.patient_message);
    } catch (err) {
      setError(err.message || 'Failed to generate call note draft.');
    } finally {
      setDrafting(false);
    }
  };

  // Step 2: One-click Approve and Commit
  const handleApproveAndSign = async () => {
    setClickCount((c) => c + 1);
    setApproving(true);
    setError('');

    try {
      const editedBody = {
        ...draftResult,
        note_text: editedNote,
        task_description: editedTask,
        patient_message: editedMessage,
      };

      const res = await fetch(`${API_BASE}/agent/call-notes/approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          draft_id: draftResult.draft_id,
          edited_body: editedBody,
        }),
      });

      if (!res.ok) {
        throw new Error('Failed to approve and save call records.');
      }

      if (onCallLogged) {
        onCallLogged({
          patientId: patient.patientId,
          channel: 'Phone',
          outcome: reached ? 'Reached' : 'No_Answer',
          summary: editedNote,
        });
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to commit call records.');
    } finally {
      setApproving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(3px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 100,
        padding: '20px',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '14px',
          width: '100%',
          maxWidth: '640px',
          maxHeight: '90vh',
          boxShadow: 'var(--shadow-card-hover)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '16px 20px',
            borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-base, #f8fafc)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: '#e0f2fe',
                color: '#0284c7',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <IconPhone width={16} height={16} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                Nurse Call Form &amp; Call Notes Agent
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-secondary, #64748b)' }}>
                {patient.patientName} ({patient.patientCode}) · Tel: <strong>{patient.phone || '+91-98765-43210'}</strong>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: '18px',
              color: '#94a3b8',
              cursor: 'pointer',
              padding: '4px',
            }}
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {error && (
            <div
              style={{
                padding: '10px 14px',
                borderRadius: '6px',
                background: '#fee2e2',
                color: '#dc2626',
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              {error}
            </div>
          )}

          {/* Contact status toggle */}
          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              onClick={() => {
                setClickCount((c) => c + 1);
                setReached(true);
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: '6px',
                border: reached ? '2px solid #0284c7' : '1px solid #cbd5e1',
                background: reached ? '#f0f9ff' : '#ffffff',
                color: reached ? '#0284c7' : '#475569',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              ✓ Patient Reached
            </button>
            <button
              type="button"
              onClick={() => {
                setClickCount((c) => c + 1);
                setReached(false);
              }}
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: '6px',
                border: !reached ? '2px solid #f59e0b' : '1px solid #cbd5e1',
                background: !reached ? '#fffbeb' : '#ffffff',
                color: !reached ? '#d97706' : '#475569',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              ⚠️ No Answer / Voicemail
            </button>
          </div>

          {reached && (
            <>
              {/* Quick Picks 1: Patient Reports */}
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: '#64748b', marginBottom: '6px', letterSpacing: '0.04em' }}>
                  Quick Picks: Patient Reports (Click to select)
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {QUICK_REPORTS.map((rep) => {
                    const isSelected = selectedReports.includes(rep);
                    return (
                      <button
                        key={rep}
                        type="button"
                        onClick={() => toggleReport(rep)}
                        style={{
                          padding: '5px 10px',
                          borderRadius: '16px',
                          border: isSelected ? '1px solid #0284c7' : '1px solid #cbd5e1',
                          background: isSelected ? '#eff6ff' : '#ffffff',
                          color: isSelected ? '#0284c7' : '#334155',
                          fontSize: '11px',
                          fontWeight: isSelected ? 700 : 500,
                          cursor: 'pointer',
                        }}
                      >
                        {isSelected ? '✓ ' : '+ '}
                        {rep}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Quick Picks 2: Actions Agreed */}
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: '#64748b', marginBottom: '6px', letterSpacing: '0.04em' }}>
                  Quick Picks: Actions Agreed
                </label>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {QUICK_ACTIONS.map((act) => {
                    const isSelected = selectedActions.includes(act);
                    return (
                      <button
                        key={act}
                        type="button"
                        onClick={() => toggleAction(act)}
                        style={{
                          padding: '5px 10px',
                          borderRadius: '16px',
                          border: isSelected ? '1px solid #059669' : '1px solid #cbd5e1',
                          background: isSelected ? '#ecfdf5' : '#ffffff',
                          color: isSelected ? '#059669' : '#334155',
                          fontSize: '11px',
                          fontWeight: isSelected ? 700 : 500,
                          cursor: 'pointer',
                        }}
                      >
                        {isSelected ? '✓ ' : '+ '}
                        {act}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Optional Voice Note (Speech recognition) */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <label style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: '#64748b', letterSpacing: '0.04em' }}>
                    Optional Voice Dictation (Speech-to-Text)
                  </label>
                  <button
                    type="button"
                    onClick={toggleVoiceRecording}
                    style={{
                      background: isRecording ? '#dc2626' : '#f1f5f9',
                      color: isRecording ? '#ffffff' : '#334155',
                      border: 'none',
                      borderRadius: '4px',
                      padding: '3px 8px',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <span>{isRecording ? '🔴 Listening...' : '🎤 Dictate voice note'}</span>
                  </button>
                </div>
                <textarea
                  rows={2}
                  value={voiceTranscript}
                  onChange={(e) => setVoiceTranscript(e.target.value)}
                  placeholder="Click 'Dictate voice note' or type custom dictation here (local transcript only — zero audio stored on server)..."
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-surface, #ffffff)',
                    color: 'var(--text-primary, #0f172a)',
                    fontSize: '12px',
                    resize: 'none',
                  }}
                />
              </div>

              {/* Needs Doctor Checkbox */}
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', fontWeight: 600, color: '#dc2626', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={needsDoctor}
                  onChange={(e) => {
                    setClickCount((c) => c + 1);
                    setNeedsDoctor(e.target.checked);
                  }}
                />
                <span>⚠️ Needs doctor review (flags for physician attention)</span>
              </label>
            </>
          )}

          {/* Draft button (if not yet drafted) */}
          {!draftResult ? (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #e2e8f0', paddingTop: '12px' }}>
              <span style={{ fontSize: '11px', color: '#64748b' }}>
                Clicks: <strong>{clickCount}</strong> (3-click workflow target)
              </span>
              <button
                type="button"
                onClick={handleGenerateDraft}
                disabled={drafting}
                style={{
                  padding: '8px 18px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#0284c7',
                  color: '#ffffff',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {drafting ? 'Agent Drafting...' : '✨ Draft with Call Notes Agent'}
              </button>
            </div>
          ) : (
            /* Prepared Drafts Review Section */
            <div
              style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: '8px',
                padding: '14px',
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: '#0284c7', letterSpacing: '0.04em' }}>
                  ✓ AI-Prepared Drafts (Review &amp; Edit)
                </span>
                <span style={{ fontSize: '10px', color: '#64748b' }}>No facts beyond your input</span>
              </div>

              {/* 1. Clinical Note */}
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  1. Clinical Note (clinician_notes):
                </label>
                <textarea
                  rows={3}
                  value={editedNote}
                  onChange={(e) => setEditedNote(e.target.value)}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '11px', background: '#ffffff' }}
                />
              </div>

              {/* 2. Follow-up Task */}
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  2. Follow-up Task (follow_up_tasks due in 24h):
                </label>
                <input
                  type="text"
                  value={editedTask}
                  onChange={(e) => setEditedTask(e.target.value)}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '11px', background: '#ffffff' }}
                />
              </div>

              {/* 3. Patient Message */}
              <div>
                <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#334155', marginBottom: '4px' }}>
                  3. Patient Message (patient_updates):
                </label>
                <textarea
                  rows={2}
                  value={editedMessage}
                  onChange={(e) => setEditedMessage(e.target.value)}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontSize: '11px', background: '#ffffff' }}
                />
              </div>

              {/* Approve & Sign Button */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #cbd5e1', paddingTop: '10px' }}>
                <span style={{ fontSize: '11px', color: '#059669', fontWeight: 700 }}>
                  ✓ Ready to commit in 1 atomic action
                </span>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() => setDraftResult(null)}
                    style={{ padding: '6px 12px', borderRadius: '6px', border: '1px solid #cbd5e1', background: '#ffffff', fontSize: '11px', fontWeight: 600, cursor: 'pointer' }}
                  >
                    Re-draft
                  </button>
                  <button
                    type="button"
                    onClick={handleApproveAndSign}
                    disabled={approving}
                    style={{
                      padding: '8px 20px',
                      borderRadius: '6px',
                      border: 'none',
                      background: '#059669',
                      color: '#ffffff',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    {approving ? 'Committing...' : '✓ Approve & Sign (1 Click)'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
