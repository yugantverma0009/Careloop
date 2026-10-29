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

      {/* Patient Handoff Cards List */}
      {loading ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
          Loading shift handoff report...
        </div>
      ) : patients.length === 0 ? (
        <div style={{ padding: '60px', textAlign: 'center', color: '#94a3b8' }}>
          No active patients in this handoff view.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {patients.map((p) => {
            const isEditingContingency = editingPid === p.patient_id;
            return (
              <div
                key={p.patient_id}
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '20px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '14px',
                }}
              >
                {/* Section I: Identity & Illness Severity Tier */}
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle, #e2e8f0)', paddingBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <PatientIdentity
                      patientCode={p.patient_code}
                      fullName={p.full_name}
                      ageYears={p.age_years}
                      onClick={() => onSelectPatient && onSelectPatient(p.patient_id)}
                    />
                    <div style={{ fontSize: '12px', color: '#64748b' }}>
                      Attending: <strong>{p.attending_doctor}</strong> · Discharged {p.patient_summary.discharge_date}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '10px', fontWeight: 800, color: '#64748b', textTransform: 'uppercase' }}>
                        I — ILLNESS ATTENTION TIER
                      </div>
                      <span
                        className={`status-pill ${
                          p.illness_tier === 'Immediate'
                            ? 'status-pill-red'
                            : p.illness_tier === 'Urgent'
                            ? 'status-pill-red'
                            : p.illness_tier === 'Review soon'
                            ? 'status-pill-amber'
                            : 'status-pill-green'
                        }`}
                        style={{ fontSize: '12px', padding: '3px 10px', marginTop: '2px', display: 'inline-block' }}
                      >
                        {p.illness_tier}
                      </span>
                    </div>

                    {/* Synthesis: Receiver Tick */}
                    <button
                      type="button"
                      onClick={() => handleReceive(p.patient_id)}
                      disabled={p.is_received}
                      style={{
                        padding: '6px 14px',
                        borderRadius: '8px',
                        border: p.is_received ? '1px solid #a7f3d0' : '1px solid #0284c7',
                        background: p.is_received ? '#ecfdf5' : '#0284c7',
                        color: p.is_received ? '#059669' : '#ffffff',
                        fontSize: '12px',
                        fontWeight: 700,
                        cursor: p.is_received ? 'default' : 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      {p.is_received ? `✓ Received at ${p.received_at}` : 'Mark Received'}
                    </button>
                  </div>
                </div>

                {/* Section P & A: Patient Summary and Action List */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  {/* P — Patient Summary */}
                  <div style={{ background: 'var(--bg-base, #f8fafc)', padding: '14px 16px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#0284c7', textTransform: 'uppercase', marginBottom: '6px' }}>
                      P — PATIENT SUMMARY
                    </div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                      Post-Discharge Day {p.patient_summary.day_number}: {p.patient_summary.condition}
                    </div>
                    <div style={{ fontSize: '12px', color: '#64748b', marginTop: '4px' }}>
                      Care plan active. Standard telemetry monitoring in progress.
                    </div>
                  </div>

                  {/* A — Action List */}
                  <div style={{ background: 'var(--bg-base, #f8fafc)', padding: '14px 16px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#059669', textTransform: 'uppercase', marginBottom: '6px' }}>
                      A — ACTION LIST ({p.action_list.length} Open Tasks)
                    </div>
                    {p.action_list.length === 0 ? (
                      <div style={{ fontSize: '12px', color: '#94a3b8' }}>No pending action tasks.</div>
                    ) : (
                      <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '12px', lineHeight: '1.5' }}>
                        {p.action_list.map((task) => (
                          <li key={task.task_id} style={{ marginBottom: '4px' }}>
                            <strong>{task.reason}</strong>{' '}
                            <span style={{ color: '#64748b' }}>(Owner: {task.owner} · Due: {task.due_at ? task.due_at.slice(0, 16) : 'Today'})</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </div>

                {/* Section S: Situation Awareness & Contingency Planning */}
                <div style={{ background: 'var(--bg-base, #f8fafc)', padding: '14px 16px', borderRadius: '8px', borderLeft: '4px solid #f59e0b' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                    <div style={{ fontSize: '11px', fontWeight: 800, color: '#d97706', textTransform: 'uppercase' }}>
                      S — SITUATION AWARENESS & CONTINGENCY PLANNING
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
                        }}
                      >
                        ✎ Edit Contingency
                      </button>
                    )}
                  </div>

                  {/* Open flags chips */}
                  {p.situation_awareness.open_flags?.length > 0 && (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '8px' }}>
                      {p.situation_awareness.open_flags.map((fl) => (
                        <span
                          key={fl.flag_id}
                          style={{
                            padding: '3px 8px',
                            borderRadius: '6px',
                            background: '#fee2e2',
                            color: '#dc2626',
                            fontSize: '11px',
                            fontWeight: 700,
                          }}
                        >
                          Alert: {fl.reason}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Contingency note text or edit form */}
                  {isEditingContingency ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '6px' }}>
                      <textarea
                        rows={2}
                        value={contingencyDraft}
                        onChange={(e) => setContingencyDraft(e.target.value)}
                        placeholder="If X occurs, call Y and execute plan Z..."
                        style={{
                          width: '100%',
                          padding: '8px 10px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-strong, #cbd5e1)',
                          fontSize: '12px',
                        }}
                      />
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        <button
                          type="button"
                          onClick={() => setEditingPid(null)}
                          style={{
                            padding: '4px 10px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-strong, #cbd5e1)',
                            background: 'transparent',
                            fontSize: '11px',
                            cursor: 'pointer',
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => handleSaveContingency(p.patient_id)}
                          style={{
                            padding: '4px 12px',
                            borderRadius: '6px',
                            border: 'none',
                            background: '#0f172a',
                            color: '#ffffff',
                            fontSize: '11px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Save Contingency
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: '12px', color: 'var(--text-primary, #0f172a)', fontStyle: 'italic' }}>
                      "{p.contingency_note}"
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
