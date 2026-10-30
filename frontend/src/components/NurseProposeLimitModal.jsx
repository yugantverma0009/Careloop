import React, { useState, useEffect } from 'react';
import { getAllApprovedRules, proposeLimitChange } from '../services/api';
import { IconShieldCheck } from './Icons';

export default function NurseProposeLimitModal({
  isOpen,
  onClose,
  patient,
  onProposalSubmitted,
}) {
  const [rules, setRules] = useState([]);
  const [selectedRuleId, setSelectedRuleId] = useState('');
  const [proposedValue, setProposedValue] = useState('');
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen && patient?.patientId) {
      setLoading(true);
      setError('');
      getAllApprovedRules(patient.patientId)
        .then((data) => {
          setRules(data || []);
          if (data && data.length > 0) {
            setSelectedRuleId(String(data[0].rule_id));
            setProposedValue(String(data[0].threshold_value));
          }
        })
        .catch((err) => setError('Failed to load rules: ' + err.message))
        .finally(() => setLoading(false));
    }
  }, [isOpen, patient]);

  if (!isOpen || !patient) return null;

  const currentRule = rules.find((r) => String(r.rule_id) === String(selectedRuleId));

  const handleRuleChange = (e) => {
    const rId = e.target.value;
    setSelectedRuleId(rId);
    const r = rules.find((item) => String(item.rule_id) === String(rId));
    if (r) {
      setProposedValue(String(r.threshold_value));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedRuleId) {
      setError('Please select a rule to adjust.');
      return;
    }
    const val = parseFloat(proposedValue);
    if (isNaN(val)) {
      setError('Please enter a valid numeric threshold value.');
      return;
    }
    if (!reason.trim() || reason.trim().length < 5) {
      setError('A clinical justification of at least 5 characters is required for doctor review.');
      return;
    }

    setSubmitting(true);
    setError('');

    try {
      await proposeLimitChange(
        Number(selectedRuleId),
        val,
        reason.trim(),
        currentRule?.window_hours || null,
        currentRule?.severity || null
      );

      if (onProposalSubmitted) {
        onProposalSubmitted({
          ruleId: Number(selectedRuleId),
          proposedValue: val,
          reason: reason.trim(),
        });
      }
      onClose();
    } catch (err) {
      setError(err.message || 'Failed to submit proposal.');
    } finally {
      setSubmitting(false);
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
          maxWidth: '500px',
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
              <IconShieldCheck width={16} height={16} />
            </div>
            <div>
              <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                Propose Alert Limit Adjustment
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

          {/* Governance Notice */}
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '8px',
              background: '#eff6ff',
              border: '1px solid #bfdbfe',
              color: '#1e40af',
              fontSize: '12px',
              lineHeight: '1.4',
            }}
          >
            <strong>Clinical Governance Rule:</strong> Nurses propose limit modifications based on clinical observation. Proposing sends this request directly to <strong>Dr. Ananya Sharma's Approvals Queue</strong> for mandatory physician review and sign-off.
          </div>

          {loading ? (
            <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
              Loading patient rules...
            </div>
          ) : (
            <>
              {/* Rule selector */}
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
                  Target Clinical Alert Rule
                </label>
                <select
                  value={selectedRuleId}
                  onChange={handleRuleChange}
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
                  {rules.map((r) => (
                    <option key={r.rule_id} value={r.rule_id}>
                      {r.rule_type} ({r.measurement_type || 'General'}) — Current: {r.threshold_value} (Approved by {r.approved_by_name || 'Dr. Sharma'})
                    </option>
                  ))}
                </select>
              </div>

              {currentRule && (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div style={{ padding: '10px 12px', background: 'var(--bg-base, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
                    <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 600 }}>CURRENT VALUE</div>
                    <div style={{ fontSize: '14px', fontWeight: 800, color: '#0f172a', marginTop: '2px' }}>
                      {currentRule.threshold_value} {currentRule.measurement_type === 'SpO2' ? '%' : currentRule.measurement_type === 'HeartRate' ? 'bpm' : ''}
                    </div>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                      PROPOSED VALUE
                    </label>
                    <input
                      type="number"
                      step="any"
                      value={proposedValue}
                      onChange={(e) => setProposedValue(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 10px',
                        borderRadius: '6px',
                        border: '1px solid #0284c7',
                        background: 'var(--bg-surface, #ffffff)',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '14px',
                        fontWeight: 700,
                      }}
                    />
                  </div>
                </div>
              )}

              {/* Clinical Justification */}
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
                  Clinical Justification for Dr. Sharma
                </label>
                <textarea
                  rows={3}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="e.g., Patient consistently reports baseline heart rate around 55 bpm post-op without dizziness..."
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
            </>
          )}

          {/* Footer Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '6px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
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
              disabled={submitting || loading}
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
              {submitting ? 'Submitting...' : 'Submit Proposal for Doctor'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
