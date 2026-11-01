import React, { useState, useEffect } from 'react';
import { getAllApprovedRules, updateAlertRule } from '../services/api';
import { IconShieldCheck, IconCheck } from './Icons';

export default function DoctorLimitsView({ user = {} }) {
  const [rules, setRules] = useState([]);
  const [selectedPid, setSelectedPid] = useState('all');
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState('');

  // Edit modal
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [newThreshold, setNewThreshold] = useState('');
  const [changeReason, setChangeReason] = useState('');
  const [saving, setSaving] = useState(false);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const data = await getAllApprovedRules(selectedPid === 'all' ? null : parseInt(selectedPid, 10));
      setRules(data || []);
    } catch (err) {
      console.error('Failed to load approved rules:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, [selectedPid]);

  const handleOpenEdit = (rule) => {
    setEditingRule(rule);
    setNewThreshold(rule.threshold_value);
    setChangeReason('');
    setEditModalOpen(true);
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editingRule || !newThreshold || !changeReason.trim() || changeReason.trim().length < 5) {
      alert('A clinical justification of at least 5 characters is required.');
      return;
    }
    setSaving(true);
    try {
      await updateAlertRule(
        editingRule.rule_id,
        parseFloat(newThreshold),
        changeReason.trim(),
        editingRule.window_hours,
        editingRule.severity
      );
      setActionMsg(`Approved limit for ${editingRule.full_name} (${editingRule.rule_type}) updated to ${newThreshold}.`);
      setEditModalOpen(false);
      setEditingRule(null);
      setTimeout(() => setActionMsg(''), 5000);
      await fetchRules();
    } catch (err) {
      alert(`Update failed: ${err.message || 'Error'}`);
    } finally {
      setSaving(false);
    }
  };

  const formatThresholdDisplay = (r) => {
    const val = parseFloat(r.threshold_value);
    if (r.measurement_type === 'Heart_Rate') {
      return r.rule_type === 'Reading_Above' ? `> ${val} bpm` : `< ${val} bpm`;
    }
    if (r.measurement_type === 'SpO2') {
      return `< ${val} %`;
    }
    if (r.rule_type === 'Pain_At_Least') {
      return `≥ ${val} / 10`;
    }
    if (r.rule_type === 'Missed_Doses') {
      return `≥ ${val} doses in 48h`;
    }
    if (r.rule_type === 'No_Data_Hours') {
      return `> ${val} hours silent`;
    }
    if (r.rule_type === 'Missed_Checkins') {
      return `≥ ${val} missed check-ins`;
    }
    if (r.rule_type === 'Possible_Fall') {
      return `Wait ${val || 2} min prompt`;
    }
    return `${val}`;
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Toast Alert */}
      {actionMsg && (
        <div
          style={{
            padding: '12px 18px',
            borderRadius: '8px',
            background: 'var(--accent-tint, #ecfdf5)',
            border: '1px solid var(--accent-subtle, #a7f3d0)',
            color: 'var(--accent-color, #059669)',
            fontSize: '13px',
            fontWeight: 700,
          }}
        >
          ✓ {actionMsg}
        </div>
      )}

      {/* Header Bar */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '20px 24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '14px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 800,
                color: 'var(--role-doctor, #7c3aed)',
                textTransform: 'uppercase',
                letterSpacing: '0.04em',
              }}
            >
              DOCTOR CLINICAL GOVERNANCE
            </span>
          </div>
          <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
            Patient Approved Limits
          </h2>
          <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
            All telemetry rules require Dr. Sharma&rsquo;s signature. The system alerts only when readings cross these approved limits.
          </p>
        </div>

        {/* Patient Filter Pills */}
        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All Patients' },
            { id: '1', label: 'CL-00001 Aarav' },
            { id: '2', label: 'CL-00002 Meera' },
            { id: '3', label: 'CL-00003 Rajesh' },
            { id: '4', label: 'CL-00004 Kabir' },
            { id: '5', label: 'CL-00005 Sunita' },
          ].map((pt) => (
            <button
              key={pt.id}
              type="button"
              onClick={() => setSelectedPid(pt.id)}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                border: 'none',
                background: selectedPid === pt.id ? 'var(--role-doctor, #7c3aed)' : 'var(--bg-base, #f1f5f9)',
                color: selectedPid === pt.id ? '#ffffff' : 'var(--text-secondary, #475569)',
                fontSize: '12px',
                fontWeight: selectedPid === pt.id ? 700 : 500,
                cursor: 'pointer',
              }}
            >
              {pt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Rules Table */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-card)',
          overflow: 'hidden',
        }}
      >
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
          <thead>
            <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)', color: 'var(--text-muted, #64748b)', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              <th style={{ padding: '12px 18px' }}>Patient</th>
              <th style={{ padding: '12px 16px' }}>Clinical Metric & Rule</th>
              <th style={{ padding: '12px 16px' }}>Approved Limit</th>
              <th style={{ padding: '12px 16px' }}>Severity</th>
              <th style={{ padding: '12px 16px' }}>Approved By</th>
              <th style={{ padding: '12px 16px' }}>Approval Date</th>
              <th style={{ padding: '12px 18px', textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                  Loading approved limits...
                </td>
              </tr>
            ) : rules.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                  No approved alert rules found for this patient selection.
                </td>
              </tr>
            ) : (
              rules.map((r) => (
                <tr
                  key={r.rule_id}
                  style={{
                    borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
                    transition: 'background 0.15s ease',
                  }}
                >
                  <td style={{ padding: '14px 18px' }}>
                    <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                      {r.full_name}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                      {r.age} y · {r.patient_code} · {r.condition_summary || 'Recovery'}
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                      {r.rule_type.replace(/_/g, ' ')}
                    </div>
                    {r.measurement_type && (
                      <div style={{ fontSize: '11px', color: '#0284c7', fontWeight: 600 }}>
                        {r.measurement_type.replace(/_/g, ' ')}
                      </div>
                    )}
                    {r.rule_type === 'Possible_Fall' && (
                      <div style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)', marginTop: '3px' }}>
                        Prompts: {r.prompts_sent || 0} sent · {r.prompts_ok || 0} OK · {r.prompts_unanswered || 0} unanswered
                      </div>
                    )}
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <span
                      style={{
                        padding: '3px 8px',
                        borderRadius: '6px',
                        background: 'var(--role-doctor-soft, #f5f3ff)',
                        color: 'var(--role-doctor, #7c3aed)',
                        fontWeight: 800,
                        fontSize: '12px',
                        border: '1px solid #ddd6fe',
                      }}
                    >
                      {formatThresholdDisplay(r)}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <span
                      style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '10px',
                        textTransform: 'uppercase',
                        background: r.severity === 'Urgent_Review' ? '#fef2f2' : '#fffbeb',
                        color: r.severity === 'Urgent_Review' ? '#dc2626' : '#d97706',
                      }}
                    >
                      {r.severity ? r.severity.replace(/_/g, ' ') : 'Review Soon'}
                    </span>
                  </td>
                  <td style={{ padding: '14px 16px' }}>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                      {r.approved_by_name || 'Dr. Ananya Sharma'}
                    </div>
                    <div style={{ fontSize: '11px', color: '#059669', fontWeight: 600 }}>
                      ✓ Attending Physician
                    </div>
                  </td>
                  <td style={{ padding: '14px 16px', color: 'var(--text-secondary, #64748b)', fontSize: '12px' }}>
                    {r.approved_at ? new Date(r.approved_at).toLocaleDateString() : 'Active baseline'}
                  </td>
                  <td style={{ padding: '14px 18px', textAlign: 'right' }}>
                    <button
                      type="button"
                      onClick={() => handleOpenEdit(r)}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-strong, #cbd5e1)',
                        background: 'var(--bg-surface, #ffffff)',
                        color: 'var(--role-doctor, #7c3aed)',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: 'pointer',
                      }}
                    >
                      Adjust limit
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Edit Limit Modal */}
      {editModalOpen && editingRule && (
        <div className="modal-overlay" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '480px',
              width: '100%',
              boxShadow: 'var(--shadow-lg)',
            }}
          >
            <h3 style={{ fontSize: '16px', fontWeight: 800, margin: '0 0 8px 0', color: 'var(--role-doctor, #7c3aed)' }}>
              Adjust Doctor-Approved Limit
            </h3>
            <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 16px 0' }}>
              Modify telemetry boundary for <strong>{editingRule.full_name}</strong> ({editingRule.rule_type}). Changes require a clinical justification and will be signed under Dr. Ananya Sharma.
            </p>

            <form onSubmit={handleSaveEdit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  New Approved Limit Value *
                </label>
                <input
                  type="number"
                  step="any"
                  required
                  value={newThreshold}
                  onChange={(e) => setNewThreshold(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    fontSize: '13px',
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Clinical Justification * (minimum 5 characters)
                </label>
                <textarea
                  rows={3}
                  required
                  placeholder="e.g. Adjusting resting HR ceiling to 110 bpm following post-operative beta-blocker titration"
                  value={changeReason}
                  onChange={(e) => setChangeReason(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    fontSize: '12px',
                  }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setEditModalOpen(false)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'transparent',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving || !newThreshold || !changeReason.trim() || changeReason.trim().length < 5}
                  style={{
                    padding: '8px 18px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'var(--role-doctor, #7c3aed)',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {saving ? 'Signing & Saving...' : 'Sign & Apply Limit'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
