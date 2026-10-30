import React, { useState } from 'react';
import { logContactCall } from '../services/api';
import { IconPhone } from './Icons';

export default function NurseCallModal({
  isOpen,
  onClose,
  patient,
  onCallLogged,
}) {
  const [channel, setChannel] = useState('Phone');
  const [outcome, setOutcome] = useState('Reached');
  const [summary, setSummary] = useState('');
  const [completeTask, setCompleteTask] = useState(Boolean(patient?.taskId));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen || !patient) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!summary.trim() || summary.trim().length < 3) {
      setError('Please enter a brief call summary (at least 3 characters).');
      return;
    }
    setError('');
    setLoading(true);

    try {
      await logContactCall({
        patient_id: patient.patientId,
        flag_id: patient.flagId || null,
        task_id: patient.taskId || null,
        channel,
        outcome,
        summary: summary.trim(),
        complete_task: completeTask && Boolean(patient.taskId),
        outcome_code: outcome === 'Reached' ? 'Reached_And_Advised' : outcome === 'No_Answer' ? 'No_Answer' : 'Reached_And_Advised',
      });

      if (onCallLogged) {
        onCallLogged({
          patientId: patient.patientId,
          channel,
          outcome,
          summary: summary.trim(),
        });
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to log call.');
    } finally {
      setLoading(false);
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
    >
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '14px',
          width: '100%',
          maxWidth: '480px',
          boxShadow: 'var(--shadow-card-hover)',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 24px',
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
                Log Patient Contact
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary, #64748b)' }}>
                {patient.patientName} ({patient.patientCode})
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

        {/* Content Form */}
        <form onSubmit={handleSubmit} style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
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

          {/* Patient Contact Info */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '10px 14px',
              borderRadius: '8px',
              background: 'var(--bg-base, #f8fafc)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
            }}
          >
            <div>
              <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>CONTACT NUMBER</div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                {patient.phone || '+91 98765 43210'}
              </div>
            </div>
            <a
              href={`tel:${patient.phone || '+919876543210'}`}
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color: '#0284c7',
                textDecoration: 'none',
                padding: '6px 12px',
                borderRadius: '6px',
                border: '1px solid #bae6fd',
                background: '#f0f9ff',
              }}
            >
              📞 Call Now
            </a>
          </div>

          {/* Channel Selector */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
              Channel
            </label>
            <div style={{ display: 'flex', gap: '8px' }}>
              {[
                { id: 'Phone', label: '📞 Telephone Call' },
                { id: 'SMS', label: '💬 SMS Notice (Logged)' },
              ].map((ch) => (
                <button
                  key={ch.id}
                  type="button"
                  onClick={() => setChannel(ch.id)}
                  style={{
                    flex: 1,
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: channel === ch.id ? '1px solid #0284c7' : '1px solid var(--border-subtle, #cbd5e1)',
                    background: channel === ch.id ? '#f0f9ff' : 'var(--bg-surface, #ffffff)',
                    color: channel === ch.id ? '#0284c7' : 'var(--text-secondary, #475569)',
                    fontSize: '12px',
                    fontWeight: channel === ch.id ? 700 : 500,
                    cursor: 'pointer',
                  }}
                >
                  {ch.label}
                </button>
              ))}
            </div>
          </div>

          {/* Outcome Dropdown */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
              Contact Outcome
            </label>
            <select
              value={outcome}
              onChange={(e) => setOutcome(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 10px',
                borderRadius: '6px',
                border: '1px solid var(--border-strong, #cbd5e1)',
                background: 'var(--bg-surface, #ffffff)',
                color: 'var(--text-primary, #0f172a)',
                fontSize: '13px',
              }}
            >
              <option value="Reached">Reached and advised patient</option>
              <option value="No_Answer">No answer / voicemail left</option>
              <option value="Left_Message">Left message with caregiver</option>
              <option value="Declined">Call declined</option>
            </select>
          </div>

          {/* Summary Textarea */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
              Call Summary / Advice Given
            </label>
            <textarea
              rows={3}
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="Spoke with patient regarding symptoms, verified recovery guidelines..."
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

          {/* Complete Task checkbox if linked */}
          {patient.taskId && (
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: 'var(--text-primary, #0f172a)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={completeTask}
                onChange={(e) => setCompleteTask(e.target.checked)}
              />
              <span>Mark associated follow-up task #{patient.taskId} completed</span>
            </label>
          )}

          {/* Footer Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              style={{
                padding: '8px 16px',
                borderRadius: '6px',
                border: '1px solid var(--border-strong, #cbd5e1)',
                background: 'transparent',
                color: 'var(--text-secondary, #475569)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              style={{
                padding: '8px 18px',
                borderRadius: '6px',
                border: 'none',
                background: '#0284c7',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
              }}
            >
              {loading ? 'Saving...' : 'Save Call Log'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
