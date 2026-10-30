import React, { useState } from 'react';
import { completeCareTask } from '../services/api';
import { IconCheck } from './Icons';

export default function NurseTaskCompleteModal({
  isOpen,
  onClose,
  task,
  onTaskCompleted,
}) {
  const [outcomeCode, setOutcomeCode] = useState('Reached_And_Advised');
  const [outcomeNotes, setOutcomeNotes] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen || !task) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!outcomeNotes.trim() || outcomeNotes.trim().length < 3) {
      setError('Please provide completion notes (at least 3 characters).');
      return;
    }
    setError('');
    setLoading(true);

    try {
      await completeCareTask(task.taskId, outcomeCode, outcomeNotes.trim());
      if (onTaskCompleted) {
        onTaskCompleted(task.taskId, outcomeCode);
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to complete task.');
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
                background: '#ecfdf5',
                color: '#059669',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <IconCheck width={16} height={16} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                Complete Care Task #{task.taskId}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary, #64748b)' }}>
                {task.patientName} ({task.patientCode})
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

        {/* Task Details Info */}
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

          <div
            style={{
              padding: '12px 14px',
              borderRadius: '8px',
              background: 'var(--bg-base, #f8fafc)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
            }}
          >
            <div style={{ fontSize: '11px', fontWeight: 800, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
              TASK REASON
            </div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
              {task.reason}
            </div>
          </div>

          {/* Outcome Code Dropdown */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
              Task Outcome Code
            </label>
            <select
              value={outcomeCode}
              onChange={(e) => setOutcomeCode(e.target.value)}
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
              <option value="Reached_And_Advised">Reached and advised</option>
              <option value="Appointment_Set">Appointment set</option>
              <option value="No_Answer">No answer</option>
              <option value="Escalated_To_Doctor">Escalated to doctor</option>
              <option value="No_Action_Needed">No action needed</option>
            </select>
          </div>

          {/* Notes */}
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
              Clinical Outcome Notes
            </label>
            <textarea
              rows={3}
              value={outcomeNotes}
              onChange={(e) => setOutcomeNotes(e.target.value)}
              placeholder="Clinical details of task completion..."
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
                background: '#059669',
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {loading ? 'Completing...' : 'Mark Task Resolved'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

