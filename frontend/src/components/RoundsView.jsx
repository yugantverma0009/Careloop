import React, { useState, useEffect } from 'react';
import {
  getRounds,
  pauseRounds,
  resumeRounds,
  runRoundsNow,
  sendDeviceEvent,
} from '../services/api';
import {
  IconClock,
  IconCheck,
  IconAlertTriangle,
  IconRefresh,
  IconX,
  IconUser,
  IconShieldCheck,
  IconActivity,
  IconPhone,
} from './Icons';

export default function RoundsView({ currentUser }) {
  const [roundsData, setRoundsData] = useState(null);
  const [activeTab, setActiveTab] = useState('upcoming'); // 'upcoming' | 'history'
  const [loading, setLoading] = useState(true);
  const [runningNow, setRunningNow] = useState(false);
  const [runMessage, setRunMessage] = useState('');
  const [simulatingFall, setSimulatingFall] = useState(false);

  const handleSimulateFall = async () => {
    try {
      setSimulatingFall(true);
      const res = await sendDeviceEvent({
        device_id: 'DEV-ESP32-005',
        event_type: 'Possible_Fall',
        occurred_at: Math.floor(Date.now() / 1000),
        details: {
          peak_movement: 4.1,
          stillness_seconds: 18,
          battery_pct: 78,
        },
      });
      setRunMessage(`Simulated possible fall for Sunita (DEV-ESP32-005): ${res.message || 'Prompt dispatched'}`);
      await loadData();
      setTimeout(() => setRunMessage(''), 8000);
    } catch (err) {
      setRunMessage(`Simulation failed: ${err.message || 'Error'}`);
    } finally {
      setSimulatingFall(false);
    }
  };

  // Pause Modal state
  const [pauseModalOpen, setPauseModalOpen] = useState(false);
  const [selectedPatient, setSelectedPatient] = useState(null);
  const [pauseHours, setPauseHours] = useState(4);
  const [pauseReason, setPauseReason] = useState('Patient resting / procedural pause');
  const [pauseSubmitting, setPauseSubmitting] = useState(false);

  const isDemoTools =
    window.location.search.includes('demo_tools') ||
    localStorage.getItem('demo_tools') === 'true' ||
    process.env.REACT_APP_DEMO_TOOLS === 'true';

  const loadData = async () => {
    try {
      setLoading(true);
      const data = await getRounds();
      setRoundsData(data);
    } catch (err) {
      console.error('Failed to load rounds data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // 30s auto-refresh
    return () => clearInterval(interval);
  }, []);

  const handleRunNow = async () => {
    try {
      setRunningNow(true);
      setRunMessage('');
      const res = await runRoundsNow();
      setRunMessage(`Executed ${res.result?.executed || 0} action(s), Skipped ${res.result?.skipped || 0}`);
      await loadData();
    } catch (err) {
      setRunMessage(`Execution error: ${err.message}`);
    } finally {
      setRunningNow(false);
      setTimeout(() => setRunMessage(''), 5000);
    }
  };

  const handleOpenPauseModal = (patient) => {
    setSelectedPatient(patient);
    setPauseHours(4);
    setPauseReason('Clinician temporary hold');
    setPauseModalOpen(true);
  };

  const handleConfirmPause = async () => {
    if (!selectedPatient) return;
    try {
      setPauseSubmitting(true);
      await pauseRounds(selectedPatient.patient_id, pauseHours, pauseReason);
      setPauseModalOpen(false);
      setSelectedPatient(null);
      await loadData();
    } catch (err) {
      alert(`Failed to pause rounds: ${err.message}`);
    } finally {
      setPauseSubmitting(false);
    }
  };

  const handleResume = async (patientId) => {
    try {
      await resumeRounds(patientId);
      await loadData();
    } catch (err) {
      alert(`Failed to resume rounds: ${err.message}`);
    }
  };

  const counters = roundsData?.counters || {
    upcoming: 0,
    done_24h: 0,
    skipped_24h: 0,
    failed_24h: 0,
    paused_patients: 0,
  };

  return (
    <div style={{ padding: '24px 32px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* 1. Header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: '24px',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h1
              style={{
                fontSize: '22px',
                fontWeight: 800,
                color: 'var(--text-primary, #0f172a)',
                margin: 0,
                letterSpacing: '-0.02em',
              }}
            >
              Rounds
            </h1>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '12px',
                background: 'var(--accent-blue-soft, #eff6ff)',
                color: 'var(--accent-blue-text, #1d4ed8)',
                textTransform: 'uppercase',
              }}
            >
              Visible Scheduler
            </span>
          </div>
          <p
            style={{
              fontSize: '13px',
              color: 'var(--text-secondary, #475569)',
              margin: '4px 0 0',
            }}
          >
            "Automate the routine. Propose the rest. Humans decide." Transparent 24-hour lookahead, execution history, and patient pause.
          </p>
        </div>

        {/* Demo Tools Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {isDemoTools && (
            <>
              <button
                type="button"
                onClick={handleSimulateFall}
                disabled={simulatingFall}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '8px 14px',
                  borderRadius: '8px',
                  background: 'var(--alert-red, #dc2626)',
                  color: '#ffffff',
                  border: 'none',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: simulatingFall ? 'not-allowed' : 'pointer',
                  opacity: simulatingFall ? 0.7 : 1,
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <span>{simulatingFall ? 'Simulating...' : 'Simulate Possible Fall (Sunita)'}</span>
              </button>
              <button
                type="button"
                onClick={handleRunNow}
                disabled={runningNow}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '8px 16px',
                  borderRadius: '8px',
                  background: 'var(--navy-deep, #0b1528)',
                  color: '#ffffff',
                  border: 'none',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: runningNow ? 'not-allowed' : 'pointer',
                  opacity: runningNow ? 0.7 : 1,
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <IconRefresh width={14} height={14} className={runningNow ? 'spin' : ''} />
                <span>{runningNow ? 'Running...' : 'Run due actions now'}</span>
              </button>
            </>
          )}

          <button
            type="button"
            onClick={loadData}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 12px',
              borderRadius: '8px',
              background: 'var(--bg-surface, #ffffff)',
              color: 'var(--text-secondary, #475569)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <IconRefresh width={13} height={13} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {runMessage && (
        <div
          style={{
            padding: '10px 16px',
            borderRadius: '8px',
            background: 'var(--success-green-soft, #f0fdf4)',
            color: 'var(--success-green-text, #166534)',
            border: '1px solid rgba(5, 150, 105, 0.2)',
            fontSize: '12px',
            fontWeight: 600,
            marginBottom: '16px',
          }}
        >
          ✓ {runMessage}
        </div>
      )}

      {/* 2. KPI Summary Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
          gap: '14px',
          marginBottom: '24px',
        }}
      >
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '10px',
            padding: '16px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
            Next 24h Lookahead
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--accent-blue, #0284c7)', marginTop: '4px' }}>
            {counters.upcoming}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
            Dose reminders & check-ins
          </div>
        </div>

        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '10px',
            padding: '16px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
            Completed (Last 24h)
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--success-green, #059669)', marginTop: '4px' }}>
            {counters.done_24h}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
            Verified with audit rows
          </div>
        </div>

        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '10px',
            padding: '16px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
            Policy Suppressed
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--warning-amber, #d97706)', marginTop: '4px' }}>
            {counters.skipped_24h}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
            Quiet hours / STOP / Emergency
          </div>
        </div>

        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '10px',
            padding: '16px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
            Paused Patients
          </div>
          <div style={{ fontSize: '24px', fontWeight: 800, color: counters.paused_patients > 0 ? '#dc2626' : 'var(--text-primary, #0f172a)', marginTop: '4px' }}>
            {counters.paused_patients}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
            Temporary clinician hold
          </div>
        </div>
      </div>

      {/* 3. Active Escalation Timers (Keeping escalation visible) */}
      {roundsData?.escalation_timers && roundsData.escalation_timers.length > 0 && (
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid rgba(220, 38, 38, 0.25)',
            borderLeft: '4px solid var(--alert-red, #dc2626)',
            borderRadius: '10px',
            padding: '16px 20px',
            marginBottom: '24px',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconAlertTriangle width={16} height={16} color="var(--alert-red, #dc2626)" />
              <span style={{ fontSize: '12px', fontWeight: 800, color: 'var(--alert-red-text, #991b1b)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                Active Clinical Escalation Ladders ({roundsData.escalation_timers.length})
              </span>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
              Deterministic timers; repeats until acknowledged
            </span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {roundsData.escalation_timers.map((t) => (
              <div
                key={t.flag_id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '8px 12px',
                  background: 'var(--alert-red-soft, #fef2f2)',
                  borderRadius: '6px',
                  fontSize: '12px',
                }}
              >
                <div>
                  <strong>{t.patient_name}</strong> ({t.patient_code}) —{' '}
                  <span style={{ color: 'var(--text-secondary, #475569)' }}>{t.reason}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      color: t.is_overdue ? '#dc2626' : '#b45309',
                    }}
                  >
                    {t.is_overdue ? `Overdue by ${t.age_minutes - t.target_minutes}m` : `Target: ${t.remaining_minutes}m remaining`}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 4. Tabs & Content */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle, #e2e8f0)', marginBottom: '20px' }}>
        <button
          type="button"
          onClick={() => setActiveTab('upcoming')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: activeTab === 'upcoming' ? 700 : 500,
            color: activeTab === 'upcoming' ? 'var(--accent-blue, #0284c7)' : 'var(--text-secondary, #475569)',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'upcoming' ? '2px solid var(--accent-blue, #0284c7)' : '2px solid transparent',
            cursor: 'pointer',
          }}
        >
          Next 24 Hours Lookahead ({counters.upcoming})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('history')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: activeTab === 'history' ? 700 : 500,
            color: activeTab === 'history' ? 'var(--accent-blue, #0284c7)' : 'var(--text-secondary, #475569)',
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'history' ? '2px solid var(--accent-blue, #0284c7)' : '2px solid transparent',
            cursor: 'pointer',
          }}
        >
          Last 24 Hours History ({counters.done_24h + counters.skipped_24h})
        </button>
      </div>

      {loading ? (
        <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #64748b)' }}>
          Loading Rounds automation schedule...
        </div>
      ) : activeTab === 'upcoming' ? (
        /* UPCOMING LOOKAHEAD (Grouped by Patient) */
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {roundsData?.upcoming_by_patient?.length === 0 ? (
            <div style={{ padding: '32px', textAlign: 'center', background: 'var(--bg-surface, #ffffff)', borderRadius: '10px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
              No automated actions scheduled for the next 24 hours.
            </div>
          ) : (
            roundsData?.upcoming_by_patient?.map((grp) => (
              <div
                key={grp.patient_id}
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '20px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                {/* Patient Header Strip */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                    paddingBottom: '12px',
                    marginBottom: '14px',
                    flexWrap: 'wrap',
                    gap: '10px',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div
                      style={{
                        width: '32px',
                        height: '32px',
                        borderRadius: '50%',
                        background: 'var(--accent-blue-soft, #eff6ff)',
                        color: 'var(--accent-blue, #0284c7)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontWeight: 800,
                        fontSize: '13px',
                      }}
                    >
                      {grp.patient_name[0]}
                    </div>
                    <div>
                      <div style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                        {grp.patient_name}{' '}
                        <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                          ({grp.patient_code})
                        </span>
                      </div>
                      {grp.is_paused && (
                        <div style={{ fontSize: '11px', color: '#dc2626', fontWeight: 700, marginTop: '2px' }}>
                          ⏸ Rounds Paused until {grp.paused_until} — "{grp.pause_reason}"
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Pause / Resume Controls */}
                  <div>
                    {grp.is_paused ? (
                      <button
                        type="button"
                        onClick={() => handleResume(grp.patient_id)}
                        style={{
                          padding: '6px 14px',
                          borderRadius: '6px',
                          background: 'var(--success-green-soft, #f0fdf4)',
                          color: 'var(--success-green-text, #166534)',
                          border: '1px solid rgba(5, 150, 105, 0.25)',
                          fontSize: '12px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        ▶ Resume Rounds
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleOpenPauseModal(grp)}
                        style={{
                          padding: '6px 12px',
                          borderRadius: '6px',
                          background: 'var(--bg-surface, #ffffff)',
                          color: 'var(--text-secondary, #475569)',
                          border: '1px solid var(--border-subtle, #e2e8f0)',
                          fontSize: '12px',
                          fontWeight: 600,
                          cursor: 'pointer',
                        }}
                      >
                        ⏸ Pause Rounds
                      </button>
                    )}
                  </div>
                </div>

                {/* Patient Actions Table */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {grp.actions.map((act) => (
                    <div
                      key={act.action_id}
                      style={{
                        display: 'grid',
                        gridTemplateColumns: '100px 140px 80px 1fr',
                        alignItems: 'center',
                        gap: '12px',
                        padding: '10px 12px',
                        background: 'var(--bg-card-hover, #f8fafc)',
                        borderRadius: '8px',
                        fontSize: '12px',
                      }}
                    >
                      <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                        {act.run_at_str} <span style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)' }}>{act.run_at_date}</span>
                      </div>
                      <div>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: '10px',
                            fontSize: '11px',
                            fontWeight: 700,
                            background: '#f1f5f9',
                            color: '#334155',
                          }}
                        >
                          {act.action_type.replace('_', ' ')}
                        </span>
                      </div>
                      <div>
                        <span
                          style={{
                            fontSize: '10px',
                            fontWeight: 700,
                            color: act.channel === 'SMS' ? '#0284c7' : '#059669',
                            textTransform: 'uppercase',
                          }}
                        >
                          {act.channel}
                        </span>
                      </div>
                      <div style={{ color: 'var(--text-secondary, #475569)' }}>
                        <strong>Why:</strong> {act.reason}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* LAST 24 HOURS HISTORY */
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '12px',
            overflow: 'hidden',
            boxShadow: 'var(--shadow-card)',
          }}
        >
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-card-hover, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>TIME</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>PATIENT</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>ACTION</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>STATUS</th>
                <th style={{ padding: '12px 16px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>REASON & OUTCOME</th>
              </tr>
            </thead>
            <tbody>
              {roundsData?.history_list?.length === 0 ? (
                <tr>
                  <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted, #64748b)' }}>
                    No execution history recorded in the last 24 hours.
                  </td>
                </tr>
              ) : (
                roundsData?.history_list?.map((h) => {
                  const isDone = h.status === 'Done';
                  const isSkipped = h.status === 'Skipped';
                  return (
                    <tr
                      key={h.action_id}
                      style={{
                        borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                      }}
                    >
                      <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                        {h.done_at_str || h.run_at_str}
                      </td>
                      <td style={{ padding: '12px 16px', fontWeight: 700 }}>
                        {h.patient_name} <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 500 }}>({h.patient_code})</span>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span style={{ fontWeight: 600 }}>{h.action_type.replace('_', ' ')}</span>{' '}
                        <span style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)' }}>({h.channel})</span>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            fontSize: '11px',
                            fontWeight: 700,
                            background: isDone ? 'var(--success-green-soft, #f0fdf4)' : isSkipped ? 'var(--warning-amber-soft, #fffbeb)' : '#fef2f2',
                            color: isDone ? 'var(--success-green-text, #166534)' : isSkipped ? 'var(--warning-amber-text, #92400e)' : '#dc2626',
                          }}
                        >
                          {h.status}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-secondary, #475569)' }}>
                        <div><strong>Why:</strong> {h.reason}</div>
                        {h.result && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '2px' }}>
                            <strong>Result:</strong> {h.result}
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* 5. Pause Modal */}
      {pauseModalOpen && selectedPatient && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(15, 23, 42, 0.6)',
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
              maxWidth: '460px',
              width: '100%',
              padding: '24px',
              boxShadow: 'var(--shadow-float)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--text-primary, #0f172a)' }}>
                Pause Rounds: {selectedPatient.patient_name}
              </h3>
              <button
                type="button"
                onClick={() => setPauseModalOpen(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
              >
                <IconX width={18} height={18} />
              </button>
            </div>

            <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', marginBottom: '16px' }}>
              Temporarily suspends automated dose reminders, check-in prompts, and non-emergency tasks for this patient.
            </p>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Pause Duration
              </label>
              <select
                value={pauseHours}
                onChange={(e) => setPauseHours(parseInt(e.target.value, 10))}
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  fontSize: '13px',
                  background: 'var(--bg-surface, #ffffff)',
                  color: 'inherit',
                }}
              >
                <option value={2}>2 Hours</option>
                <option value={4}>4 Hours</option>
                <option value={8}>8 Hours</option>
                <option value={12}>12 Hours</option>
                <option value={24}>24 Hours</option>
              </select>
            </div>

            <div style={{ marginBottom: '20px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '6px' }}>
                Clinical Reason (Audit Recorded)
              </label>
              <input
                type="text"
                value={pauseReason}
                onChange={(e) => setPauseReason(e.target.value)}
                placeholder="e.g. Patient resting post-procedure"
                style={{
                  width: '100%',
                  padding: '8px 12px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  fontSize: '13px',
                  background: 'var(--bg-surface, #ffffff)',
                  color: 'inherit',
                }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setPauseModalOpen(false)}
                style={{
                  padding: '8px 14px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  background: 'var(--bg-surface, #ffffff)',
                  color: 'var(--text-secondary, #475569)',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmPause}
                disabled={pauseSubmitting || !pauseReason.trim()}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#dc2626',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: pauseSubmitting || !pauseReason.trim() ? 'not-allowed' : 'pointer',
                  opacity: pauseSubmitting || !pauseReason.trim() ? 0.6 : 1,
                }}
              >
                {pauseSubmitting ? 'Pausing...' : 'Confirm Pause'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
