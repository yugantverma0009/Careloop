import React, { useState, useEffect } from 'react';
import PatientIdentity from './PatientIdentity';
import {
  getShiftHandoff,
  receivePatientHandoff,
  updatePatientContingency,
  logHandoffExport,
} from '../services/api';

export default function ShiftHandoff({ user = {}, onSelectPatient }) {
  const [handoffData, setHandoffData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState('mine'); // 'mine', 'all'
  const [editingPid, setEditingPid] = useState(null);
  const [contingencyDraft, setContingencyDraft] = useState('');
  const [actionMsg, setActionMsg] = useState('');

  const fetchHandoff = async () => {
    setLoading(true);
    try {
      const data = await getShiftHandoff(scope);
      setHandoffData(data);
    } catch (err) {
      console.error('Failed to load shift handoff:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHandoff();
  }, [scope]);

  const handleReceive = async (patientId) => {
    try {
      await receivePatientHandoff(patientId);
      setActionMsg(`Handoff for Patient #${patientId} acknowledged & received.`);
      setTimeout(() => setActionMsg(''), 4000);
      fetchHandoff();
    } catch (err) {
      alert(`Receive failed: ${err.message || 'Error'}`);
    }
  };

  const handleSaveContingency = async (patientId) => {
    if (!contingencyDraft.trim()) return;
    try {
      await updatePatientContingency(patientId, contingencyDraft);
      setEditingPid(null);
      setActionMsg(`Contingency instructions saved for Patient #${patientId}.`);
      setTimeout(() => setActionMsg(''), 4000);
      fetchHandoff();
    } catch (err) {
      alert(`Contingency save failed: ${err.message || 'Error'}`);
    }
  };

  const handleExportPrint = async () => {
    try {
      await logHandoffExport('Print');
      window.print();
    } catch (err) {
      console.error('Print log failed:', err);
      window.print();
    }
  };

  const patients = handoffData?.patients || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Toast Alert */}
      {actionMsg && (
        <div
          style={{
            padding: '12px 16px',
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
          padding: '18px 22px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '14px',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: 'var(--text-primary, #0f172a)' }}>
              Clinical Shift Handoff (I-PASS)
            </h2>
            <span
              style={{
                padding: '3px 8px',
                borderRadius: '6px',
                background: '#f0fdf4',
                color: '#16a34a',
                fontSize: '11px',
                fontWeight: 700,
                border: '1px solid #bbf7d0',
              }}
            >
              {handoffData?.shift_name || 'Day Shift'} · {handoffData?.date}
            </span>
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: '#64748b' }}>
            Deterministic clinical handoff for duty clinicians. Illness severity determined strictly from alert rules.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Scope filter */}
          <div style={{ display: 'flex', gap: '4px' }}>
            <button
              type="button"
              onClick={() => setScope('mine')}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                border: 'none',
                background: scope === 'mine' ? '#0284c7' : 'var(--bg-base, #f1f5f9)',
                color: scope === 'mine' ? '#ffffff' : 'var(--text-secondary, #475569)',
                fontWeight: scope === 'mine' ? 700 : 500,
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              My patients
            </button>
            <button
              type="button"
              onClick={() => setScope('all')}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                border: 'none',
                background: scope === 'all' ? '#0284c7' : 'var(--bg-base, #f1f5f9)',
                color: scope === 'all' ? '#ffffff' : 'var(--text-secondary, #475569)',
                fontWeight: scope === 'all' ? 700 : 500,
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              All patients
            </button>
          </div>

          <button
            type="button"
            onClick={handleExportPrint}
            style={{
              padding: '6px 14px',
              borderRadius: '8px',
              border: '1px solid var(--border-strong, #cbd5e1)',
              background: 'transparent',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            🖨️ Export / Print Handoff
          </button>
        </div>
      </div>

      {/* Patient Handoff Cards List (Simplified 5-line cards per Phase 4 Task 5) */}
      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
          Loading shift handoff report...
        </div>
      ) : patients.length === 0 ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
          No active patients in this handoff view.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {patients.map((p) => {
            const isEditingContingency = editingPid === p.patient_id;
            const openFlags = p.situation_awareness?.open_flags || [];
            const openTasks = p.action_list || [];
            const openItemsText = openFlags.length > 0 || openTasks.length > 0
              ? `${openFlags.length} open flag${openFlags.length === 1 ? '' : 's'}${openFlags.length > 0 ? ` (${openFlags[0].reason})` : ''} · ${openTasks.length} pending task${openTasks.length === 1 ? '' : 's'}`
              : 'No open flags or pending tasks · Vitals on track';

            return (
              <div
                key={p.patient_id}
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderLeft: `4px solid ${
                    p.illness_tier === 'Immediate'
                      ? '#ef4444'
                      : p.illness_tier === 'Urgent'
                      ? '#f59e0b'
                      : p.illness_tier === 'Review soon'
                      ? '#0284c7'
                      : '#10b981'
                  }`,
                  borderRadius: '10px',
                  padding: '16px 20px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                {/* Line 1: Identity & Attention Tier */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <PatientIdentity
                      patientCode={p.patient_code}
                      fullName={p.full_name}
                      ageYears={p.age_years}
                      onClick={() => onSelectPatient && onSelectPatient(p.patient_id)}
                    />
                    <span style={{ fontSize: '12px', color: 'var(--text-secondary, #64748b)' }}>
                      Attending: <strong>{p.attending_doctor}</strong>
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '3px 10px',
                        borderRadius: '12px',
                        background:
                          p.illness_tier === 'Immediate'
                            ? '#fee2e2'
                            : p.illness_tier === 'Urgent'
                            ? '#fef3c7'
                            : p.illness_tier === 'Review soon'
                            ? '#e0f2fe'
                            : '#ecfdf5',
                        color:
                          p.illness_tier === 'Immediate'
                            ? '#dc2626'
                            : p.illness_tier === 'Urgent'
                            ? '#b45309'
                            : p.illness_tier === 'Review soon'
                            ? '#0369a1'
                            : '#059669',
                      }}
                    >
                      {p.illness_tier}
                    </span>
                  </div>
                </div>

                {/* Line 2: One-line Clinical Summary */}
                <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                  <span style={{ color: 'var(--text-muted, #64748b)', fontWeight: 500 }}>Summary: </span>
                  Post-Discharge Day {p.patient_summary.day_number} · {p.patient_summary.condition}
                </div>

                {/* Line 3: Open Items */}
                <div style={{ fontSize: '12px', color: openFlags.length > 0 ? '#b45309' : 'var(--text-secondary, #64748b)' }}>
                  <span style={{ color: 'var(--text-muted, #64748b)', fontWeight: 500 }}>Open items: </span>
                  <strong>{openItemsText}</strong>
                </div>

                {/* Line 4: Nurse-Typed Contingency (If X happens, call Y) */}
                <div style={{ fontSize: '12px', color: 'var(--text-primary, #0f172a)', display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px' }}>
                  <div style={{ flex: 1 }}>
                    <span style={{ color: 'var(--text-muted, #64748b)', fontWeight: 500 }}>Contingency: </span>
                    {isEditingContingency ? (
                      <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                        <input
                          type="text"
                          value={contingencyDraft}
                          onChange={(e) => setContingencyDraft(e.target.value)}
                          placeholder="If X occurs, call Y..."
                          style={{
                            flex: 1,
                            padding: '6px 10px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-strong, #cbd5e1)',
                            fontSize: '12px',
                          }}
                        />
                        <button
                          type="button"
                          onClick={() => handleSaveContingency(p.patient_id)}
                          style={{
                            padding: '6px 12px',
                            borderRadius: '6px',
                            border: 'none',
                            background: '#0284c7',
                            color: '#ffffff',
                            fontSize: '11px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditingPid(null)}
                          style={{
                            padding: '6px 10px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-strong, #cbd5e1)',
                            background: 'transparent',
                            fontSize: '11px',
                            cursor: 'pointer',
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <span style={{ fontStyle: 'italic' }}>"{p.contingency_note}"</span>
                    )}
                  </div>
                  {!isEditingContingency && (
                    <button
                      type="button"
                      onClick={() => {
                        setEditingPid(p.patient_id);
                        setContingencyDraft(p.contingency_note);
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#0284c7',
                        fontSize: '11px',
                        fontWeight: 700,
                        cursor: 'pointer',
                        padding: '0 4px',
                      }}
                    >
                      ✎ Edit
                    </button>
                  )}
                </div>

                {/* Line 5: Synthesis & Action (Mark Received by Doctor) */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '6px', borderTop: '1px solid var(--border-subtle, #f1f5f9)', marginTop: '2px' }}>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)' }}>
                    Shift Synthesis: Duty handoff recorded in audit log.
                  </div>
                  <button
                    type="button"
                    onClick={() => handleReceive(p.patient_id)}
                    disabled={p.is_received}
                    style={{
                      padding: '4px 12px',
                      borderRadius: '6px',
                      border: p.is_received ? '1px solid #a7f3d0' : '1px solid #0284c7',
                      background: p.is_received ? '#ecfdf5' : '#0284c7',
                      color: p.is_received ? '#059669' : '#ffffff',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: p.is_received ? 'default' : 'pointer',
                    }}
                  >
                    {p.is_received ? `✓ Received by Dr. Sharma at ${p.received_at}` : 'Mark received by doctor'}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
