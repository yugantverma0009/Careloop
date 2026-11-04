import React, { useState } from 'react';
import { reportAgentIncident } from '../services/api';
import { IconAlertTriangle } from './Icons';

export default function ReportIncidentModal({ runId, itemTitle, onClose, onReported }) {
  const [category, setCategory] = useState('Wrong fact');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!note.trim()) {
      setError('Please provide a short explanation of the issue.');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await reportAgentIncident(runId, category, note.trim());
      if (onReported) {
        onReported(res);
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to submit incident report');
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(15, 23, 42, 0.6)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '16px',
      }}
    >
      <div
        style={{
          backgroundColor: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          maxWidth: '480px',
          width: '100%',
          padding: '24px',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
          <div
            style={{
              padding: '8px',
              borderRadius: '8px',
              backgroundColor: 'rgba(220, 38, 38, 0.1)',
              color: '#dc2626',
            }}
          >
            <IconAlertTriangle width={20} height={20} />
          </div>
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              Report a Wrong AI Output
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '2px 0 0 0' }}>
              Run ID: <code style={{ fontFamily: "'JetBrains Mono', monospace" }}>{runId || 'N/A'}</code>
            </p>
          </div>
        </div>

        {itemTitle && (
          <div
            style={{
              padding: '10px',
              borderRadius: '6px',
              backgroundColor: 'var(--bg-base, #f8fafc)',
              fontSize: '12px',
              color: 'var(--text-secondary)',
              marginBottom: '16px',
            }}
          >
            Item: <strong>{itemTitle}</strong>
          </div>
        )}

        {error && (
          <div
            style={{
              padding: '10px 14px',
              backgroundColor: 'rgba(220, 38, 38, 0.1)',
              borderRadius: '6px',
              color: '#dc2626',
              fontSize: '12px',
              marginBottom: '14px',
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
              Defect Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle, #cbd5e1)',
                backgroundColor: 'var(--bg-card, #ffffff)',
                color: 'var(--text-primary)',
                fontSize: '13px',
              }}
            >
              <option value="Wrong fact">Wrong fact (fabricated number, incorrect dose, wrong date)</option>
              <option value="Unsafe">Unsafe (unapproved medical advice, unauthorized clinical evaluation)</option>
              <option value="Tone">Tone (confusing, dismissive, non-empathetic)</option>
              <option value="Other">Other clinical safety or quality defect</option>
            </select>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '6px' }}>
              Clinical Observation Note
            </label>
            <textarea
              rows={4}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="Explain specifically what was wrong or unsafe..."
              style={{
                width: '100%',
                padding: '10px 12px',
                borderRadius: '6px',
                border: '1px solid var(--border-subtle, #cbd5e1)',
                backgroundColor: 'var(--bg-card, #ffffff)',
                color: 'var(--text-primary)',
                fontSize: '13px',
                boxSizing: 'border-box',
                resize: 'vertical',
              }}
            />
          </div>

          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginBottom: '16px', lineHeight: 1.4 }}>
            Safety protocol: Submitting this report links the run trace, generates a candidate test case for doctor review, and immediately demotes the corresponding automated action to Draft.
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={loading}
              style={{
                padding: '8px 16px',
                backgroundColor: 'transparent',
                border: '1px solid var(--border-subtle, #cbd5e1)',
                borderRadius: '6px',
                color: 'var(--text-secondary)',
                fontSize: '13px',
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
                padding: '8px 16px',
                backgroundColor: '#dc2626',
                border: 'none',
                borderRadius: '6px',
                color: '#ffffff',
                fontSize: '13px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              {loading ? 'Submitting...' : 'Submit Incident'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

