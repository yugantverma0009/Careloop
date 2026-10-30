import React, { useState, useEffect } from 'react';
import {
  getNurseCallList,
  acknowledgeFlag,
  escalateFlagToDoctor,
  resolveRoutineFlag,
} from '../services/api';
import PatientIdentity from './PatientIdentity';
import NurseCallModal from './NurseCallModal';
import NurseTaskCompleteModal from './NurseTaskCompleteModal';
import NurseProposeLimitModal from './NurseProposeLimitModal';
import {
  IconCheck,
  IconPhone,
  IconShieldCheck,
} from './Icons';

export default function NurseCallListView({ onSelectPatient }) {
  const [data, setData] = useState({
    cards: { calls_to_make: 0, visits_today: 0, pending_limit_requests: 0, active_patients: 5 },
    call_items: [],
    tasks_due_today: [],
    on_track_patients: [],
  });
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState('');

  // Modals state
  const [callModalTarget, setCallModalTarget] = useState(null);
  const [taskModalTarget, setTaskModalTarget] = useState(null);
  const [limitModalTarget, setLimitModalTarget] = useState(null);
  const [resolvePromptFlag, setResolvePromptFlag] = useState(null);
  const [resolveNote, setResolveNote] = useState('');

  const loadCallList = async () => {
    try {
      const res = await getNurseCallList();
      if (res) setData(res);
    } catch (err) {
      console.error('Failed to load nurse call list', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCallList();
    const interval = setInterval(loadCallList, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleAcknowledge = async (flagId) => {
    try {
      await acknowledgeFlag(flagId, 'Acknowledged via nurse call list');
      setActionMsg(`Flag #${flagId} acknowledged by Lead Nurse Priya Nair.`);
      setTimeout(() => setActionMsg(''), 4000);
      loadCallList();
    } catch (err) {
      alert(`Acknowledge failed: ${err.message}`);
    }
  };

  const handleAskDoctor = async (flagId, patientName) => {
    const note = prompt(`Enter clinical escalation note for Dr. Sharma regarding ${patientName}:`, 'Nurse requested doctor review');
    if (note === null) return;
    try {
      await escalateFlagToDoctor(flagId, note || 'Nurse requested doctor review');
      setActionMsg(`Flag #${flagId} escalated to Dr. Ananya Sharma.`);
      setTimeout(() => setActionMsg(''), 4000);
      loadCallList();
    } catch (err) {
      alert(`Escalation failed: ${err.message}`);
    }
  };

  const handleOpenResolve = (item) => {
    if (item.needs_doctor_to_resolve) {
      alert('Clinical Role Boundary: Immediate and Urgent alerts require Attending Physician Dr. Sharma to resolve. Please use "Ask doctor" to escalate.');
      return;
    }
    setResolvePromptFlag(item);
    setResolveNote('Contacted patient via phone protocol; guidance reviewed and verified.');
  };

  const handleConfirmResolve = async () => {
    if (!resolvePromptFlag) return;
    if (!resolveNote.trim() || resolveNote.trim().length < 5) {
      alert('A resolution note of at least 5 characters is required.');
      return;
    }
    try {
      await resolveRoutineFlag(resolvePromptFlag.flag_id, 'Phone_Resolved', resolveNote.trim());
      setActionMsg(`Flag #${resolvePromptFlag.flag_id} resolved by Lead Nurse Priya Nair.`);
      setTimeout(() => setActionMsg(''), 4000);
      setResolvePromptFlag(null);
      loadCallList();
    } catch (err) {
      alert(`Resolve failed: ${err.message}`);
    }
  };

  const cards = data.cards || {};
  const callItems = data.call_items || [];
  const tasksDue = data.tasks_due_today || [];
  const onTrackPatients = data.on_track_patients || [];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Toast Alert */}
      {actionMsg && (
        <div
          style={{
            padding: '12px 18px',
            borderRadius: '8px',
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            color: '#059669',
            fontSize: '13px',
            fontWeight: 700,
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <IconCheck width={15} height={15} />
          <span>{actionMsg}</span>
        </div>
      )}

      {/* Header Banner */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '11px',
              fontWeight: 800,
              color: 'var(--role-nurse, #0284c7)',
              letterSpacing: '0.06em',
              textTransform: 'uppercase',
              marginBottom: '6px',
            }}
          >
            <IconShieldCheck width={14} height={14} />
            <span>NURSE DESK</span>
          </div>
          <h1
            style={{
              fontSize: '26px',
              fontWeight: 800,
              color: 'var(--text-primary, #0f172a)',
              letterSpacing: '-0.025em',
              marginBottom: '4px',
            }}
          >
            My call list
          </h1>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', margin: 0 }}>
            Work the call list. Every alert shows why it was raised, how long it has waited and what to do next.
          </p>
        </div>
      </div>

      {/* 4 KPI Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '16px',
        }}
      >
        {/* Card 1: Calls to make */}
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderLeft: '4px solid #0284c7',
            borderRadius: '12px',
            padding: '18px 20px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Calls to make
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#0284c7', marginTop: '6px' }}>
            {cards.calls_to_make}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Open alerts & queued tasks
          </div>
        </div>

        {/* Card 2: Visits / Tasks today */}
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderLeft: '4px solid #10b981',
            borderRadius: '12px',
            padding: '18px 20px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Visits today
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#10b981', marginTop: '6px' }}>
            {cards.visits_today}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Scheduled follow-ups & inquiries
          </div>
        </div>

        {/* Card 3: Pending limit requests */}
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderLeft: '4px solid #f59e0b',
            borderRadius: '12px',
            padding: '18px 20px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Pending limit requests
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#d97706', marginTop: '6px' }}>
            {cards.pending_limit_requests}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            Awaiting Dr. Sharma's sign-off
          </div>
        </div>

        {/* Card 4: Active patients */}
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderLeft: '4px solid #6366f1',
            borderRadius: '12px',
            padding: '18px 20px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '11px', color: '#64748b', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Active patients
          </div>
          <div style={{ fontSize: '28px', fontWeight: 800, color: '#4f46e5', marginTop: '6px' }}>
            {cards.active_patients}
          </div>
          <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
            In post-discharge recovery
          </div>
        </div>
      </div>

      {/* Main Call List Queue */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '20px',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '16px',
            borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
            paddingBottom: '12px',
          }}
        >
          <div>
            <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
              Call List Queue ({callItems.length} Open Alerts)
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary, #64748b)' }}>
              Ordered by urgency. Urgent items require Dr. Sharma to resolve; routine items can be resolved by nurse after call.
            </div>
          </div>
          <span style={{ fontSize: '11px', fontWeight: 700, padding: '3px 10px', borderRadius: '12px', background: '#e0f2fe', color: '#0369a1' }}>
            Live Queue Active
          </span>
        </div>

        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
            Loading prioritized call list...
          </div>
        ) : callItems.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontWeight: 600 }}>
            No open alerts for your patients.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {callItems.map((item) => {
              const isImmediate = item.tier === 'Immediate';
              const isUrgent = item.tier === 'Urgent';

              return (
                <div
                  key={item.flag_id}
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: `1px solid ${
                      isImmediate ? '#fca5a5' : isUrgent ? '#fde68a' : 'var(--border-subtle, #e2e8f0)'
                    }`,
                    borderLeft: `4px solid ${
                      isImmediate ? '#ef4444' : isUrgent ? '#f59e0b' : '#0284c7'
                    }`,
                    borderRadius: '10px',
                    padding: '16px 18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {/* Top Bar: Identity, Tier, and Target Countdown */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <PatientIdentity
                        patientCode={item.patient_code}
                        fullName={item.patient_name}
                        ageYears={item.age}
                        onClick={() => onSelectPatient && onSelectPatient(item.patient_id)}
                      />
                      <span style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
                        {item.condition} · Tel: <strong>{item.phone}</strong>
                      </span>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {/* Target Timer Pill */}
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '3px 10px',
                          borderRadius: '12px',
                          background: item.is_overdue ? '#fee2e2' : '#f0fdf4',
                          color: item.is_overdue ? '#dc2626' : '#15803d',
                          border: `1px solid ${item.is_overdue ? '#fca5a5' : '#bbf7d0'}`,
                        }}
                      >
                        ⏱ {item.target_display}
                      </span>

                      {/* Tier Pill */}
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '3px 10px',
                          borderRadius: '12px',
                          background: isImmediate ? '#fee2e2' : isUrgent ? '#fef3c7' : '#e0f2fe',
                          color: isImmediate ? '#dc2626' : isUrgent ? '#b45309' : '#0369a1',
                        }}
                      >
                        {item.tier}
                      </span>
                    </div>
                  </div>

                  {/* Reason & Physician Approval State */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                        {item.reason}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '4px' }}>
                        {item.needs_doctor_to_resolve ? (
                          <span style={{ fontSize: '11px', fontWeight: 700, color: '#dc2626', background: '#fef2f2', padding: '2px 8px', borderRadius: '4px', border: '1px solid #fecaca' }}>
                            ⚠️ Needs doctor to resolve
                          </span>
                        ) : (
                          <span style={{ fontSize: '11px', fontWeight: 600, color: '#059669', background: '#ecfdf5', padding: '2px 8px', borderRadius: '4px', border: '1px solid #a7f3d0' }}>
                            ✓ Routine: nurse may resolve after call
                          </span>
                        )}

                        {item.is_escalated && (
                          <span style={{ fontSize: '11px', fontWeight: 700, color: '#7c3aed', background: '#f5f3ff', padding: '2px 8px', borderRadius: '4px', border: '1px solid #ddd6fe' }}>
                            ✓ Escalated to Dr. Sharma by {item.escalated_by} at {item.escalated_at || 'today'}
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Action Buttons Row */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      paddingTop: '8px',
                      borderTop: '1px solid var(--border-subtle, #f1f5f9)',
                      marginTop: '2px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {/* Button: Call */}
                      <button
                        type="button"
                        onClick={() =>
                          setCallModalTarget({
                            patientId: item.patient_id,
                            patientName: item.patient_name,
                            patientCode: item.patient_code,
                            phone: item.phone,
                            flagId: item.flag_id,
                          })
                        }
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '6px 14px',
                          borderRadius: '6px',
                          border: 'none',
                          background: '#0284c7',
                          color: '#ffffff',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        <IconPhone width={13} height={13} />
                        <span>Call</span>
                      </button>

                      {/* Button: Acknowledge */}
                      <button
                        type="button"
                        onClick={() => handleAcknowledge(item.flag_id)}
                        disabled={item.status === 'Acknowledged'}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-strong, #cbd5e1)',
                          background: item.status === 'Acknowledged' ? '#f1f5f9' : 'transparent',
                          color: item.status === 'Acknowledged' ? '#94a3b8' : 'var(--text-primary, #0f172a)',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: item.status === 'Acknowledged' ? 'default' : 'pointer',
                        }}
                      >
                        {item.status === 'Acknowledged' ? '✓ Acknowledged' : 'Acknowledge'}
                      </button>

                      {/* Button: Ask Doctor */}
                      <button
                        type="button"
                        onClick={() => handleAskDoctor(item.flag_id, item.patient_name)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: '1px solid #7c3aed',
                          background: '#f5f3ff',
                          color: '#6d28d9',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        ↗ Ask doctor
                      </button>

                      {/* Button: Done / Resolve */}
                      <button
                        type="button"
                        onClick={() => handleOpenResolve(item)}
                        style={{
                          padding: '6px 14px',
                          borderRadius: '6px',
                          border: item.needs_doctor_to_resolve ? '1px dashed #cbd5e1' : '1px solid #10b981',
                          background: item.needs_doctor_to_resolve ? '#f8fafc' : '#ecfdf5',
                          color: item.needs_doctor_to_resolve ? '#94a3b8' : '#059669',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: item.needs_doctor_to_resolve ? 'not-allowed' : 'pointer',
                        }}
                        title={item.needs_doctor_to_resolve ? 'Needs doctor to resolve' : 'Resolve routine flag'}
                      >
                        ✓ Done
                      </button>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {/* Button: Propose Limit */}
                      <button
                        type="button"
                        onClick={() =>
                          setLimitModalTarget({
                            patientId: item.patient_id,
                            patientName: item.patient_name,
                            patientCode: item.patient_code,
                          })
                        }
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-strong, #cbd5e1)',
                          background: 'transparent',
                          color: 'var(--text-secondary, #475569)',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        ⚙ Propose limit
                      </button>

                      {/* Button: Open Patient */}
                      <button
                        type="button"
                        onClick={() => onSelectPatient && onSelectPatient(item.patient_id)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-strong, #cbd5e1)',
                          background: 'transparent',
                          color: 'var(--text-primary, #0f172a)',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        Open patient →
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Calls Due Today Section (Follow-up Tasks) */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '20px',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div>
            <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
              Calls Due Today ({tasksDue.length} Tasks)
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary, #64748b)' }}>
              Scheduled nurse follow-ups, medication inquiries, and post-discharge recovery checks.
            </div>
          </div>
          <span style={{ fontSize: '11px', fontWeight: 700, padding: '3px 10px', borderRadius: '12px', background: '#ecfdf5', color: '#059669' }}>
            Daily Tasks
          </span>
        </div>

        {tasksDue.length === 0 ? (
          <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8' }}>
            No scheduled follow-up tasks due today.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {tasksDue.map((t) => (
              <div
                key={t.task_id}
                style={{
                  background: 'var(--bg-base, #f8fafc)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                  <div
                    style={{
                      width: '28px',
                      height: '28px',
                      borderRadius: '6px',
                      background: t.priority === 'High' ? '#fee2e2' : '#fef3c7',
                      color: t.priority === 'High' ? '#dc2626' : '#b45309',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontWeight: 800,
                      fontSize: '11px',
                    }}
                  >
                    {t.priority === 'High' ? '!' : '•'}
                  </div>
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                      {t.patient_name} ({t.patient_code}) · <span style={{ fontWeight: 500, color: '#64748b' }}>{t.reason}</span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                      Due: {t.due_at} · Tel: {t.phone}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <button
                    type="button"
                    onClick={() =>
                      setCallModalTarget({
                        patientId: t.patient_id,
                        patientName: t.patient_name,
                        patientCode: t.patient_code,
                        phone: t.phone,
                        taskId: t.task_id,
                      })
                    }
                    style={{
                      padding: '5px 12px',
                      borderRadius: '6px',
                      border: 'none',
                      background: '#0284c7',
                      color: '#ffffff',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '4px',
                    }}
                  >
                    <IconPhone width={12} height={12} />
                    <span>Call</span>
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setTaskModalTarget({
                        taskId: t.task_id,
                        patientName: t.patient_name,
                        patientCode: t.patient_code,
                        reason: t.reason,
                        priority: t.priority,
                      })
                    }
                    style={{
                      padding: '5px 12px',
                      borderRadius: '6px',
                      border: '1px solid #10b981',
                      background: '#ecfdf5',
                      color: '#059669',
                      fontSize: '11px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    ✓ Complete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Quiet Patients Reassuring Row */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderLeft: '4px solid #10b981',
          borderRadius: '10px',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '28px',
              height: '28px',
              borderRadius: '50%',
              background: '#ecfdf5',
              color: '#059669',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              fontSize: '13px',
            }}
          >
            ✓
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
              Patients on track: {onTrackPatients.length}. Zero open alerts.
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
              {onTrackPatients.map((p) => `${p.full_name} (${p.patient_code} · Day ${p.relative_day})`).join(' · ') ||
                'Aarav Patel (CL-00001 · Day 3) · Kabir Mehta (CL-00004 · Day 9)'}
            </div>
          </div>
        </div>
        <span style={{ fontSize: '11px', fontWeight: 700, padding: '3px 10px', borderRadius: '12px', background: '#ecfdf5', color: '#059669' }}>
          Quiet: No Open Alerts
        </span>
      </div>

      {/* Modals */}
      <NurseCallModal
        isOpen={Boolean(callModalTarget)}
        onClose={() => setCallModalTarget(null)}
        patient={callModalTarget}
        onCallLogged={() => {
          setActionMsg('Contact call successfully recorded to patient log and audit.');
          setTimeout(() => setActionMsg(''), 4000);
          loadCallList();
        }}
      />

      <NurseTaskCompleteModal
        isOpen={Boolean(taskModalTarget)}
        onClose={() => setTaskModalTarget(null)}
        task={taskModalTarget}
        onTaskCompleted={() => {
          setActionMsg('Task marked resolved and logged.');
          setTimeout(() => setActionMsg(''), 4000);
          loadCallList();
        }}
      />

      <NurseProposeLimitModal
        isOpen={Boolean(limitModalTarget)}
        onClose={() => setLimitModalTarget(null)}
        patient={limitModalTarget}
        onProposalSubmitted={() => {
          setActionMsg('Rule limit modification proposed for Dr. Ananya Sharma.');
          setTimeout(() => setActionMsg(''), 4000);
          loadCallList();
        }}
      />

      {/* Prompt modal for resolving routine flag */}
      {resolvePromptFlag && (
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
              borderRadius: '12px',
              width: '100%',
              maxWidth: '460px',
              padding: '22px',
              boxShadow: 'var(--shadow-card-hover)',
              display: 'flex',
              flexDirection: 'column',
              gap: '14px',
            }}
          >
            <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
              Resolve Routine Alert #{resolvePromptFlag.flag_id}
            </div>
            <div style={{ fontSize: '12px', color: '#64748b' }}>
              Patient: <strong>{resolvePromptFlag.patient_name}</strong> ({resolvePromptFlag.patient_code})<br />
              Reason: {resolvePromptFlag.reason}
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#0f172a', marginBottom: '6px' }}>
                Nurse Resolution Note ($\ge 5$ characters)
              </label>
              <textarea
                rows={3}
                value={resolveNote}
                onChange={(e) => setResolveNote(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-strong, #cbd5e1)',
                  fontSize: '12px',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button
                type="button"
                onClick={() => setResolvePromptFlag(null)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-strong, #cbd5e1)',
                  background: 'transparent',
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmResolve}
                style={{
                  padding: '6px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#059669',
                  color: '#ffffff',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Confirm Resolution
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
