import React, { useState, useEffect } from 'react';
import PatientIdentity from './PatientIdentity';
import {
  getStaffTasks,
  claimTask,
  assignTask,
  completeTask,
  snoozeTask,
  logCommunication,
} from '../services/api';

export default function TaskQueue({ staffMembers = [], user = {}, onSelectPatient }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scope, setScope] = useState('mine'); // 'mine', 'unassigned', 'team', 'all'
  const [status, setStatus] = useState('pending'); // 'pending', 'completed', 'all'
  const [priority, setPriority] = useState('all');
  const [search, setSearch] = useState('');
  const [overdueOnly, setOverdueOnly] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);

  // Modals state
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [outcomeCode, setOutcomeCode] = useState('Reached_And_Advised');
  const [outcomeNotes, setOutcomeNotes] = useState('');
  const [snoozeModalOpen, setSnoozeModalOpen] = useState(false);
  const [snoozeHours, setSnoozeHours] = useState(4);
  const [snoozeReason, setSnoozeReason] = useState('');
  const [assignModalOpen, setAssignModalOpen] = useState(false);
  const [targetStaffId, setTargetStaffId] = useState('');
  const [assignNote, setAssignNote] = useState('');
  const [contactModalOpen, setContactModalOpen] = useState(false);
  const [contactChannel, setContactChannel] = useState('Phone');
  const [contactOutcome, setContactOutcome] = useState('Reached');
  const [contactSummary, setContactSummary] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [loadError, setLoadError] = useState('');

  const fetchTasks = async () => {
    setLoading(true);
    setLoadError('');
    try {
      const data = await getStaffTasks({
        scope,
        status,
        priority: priority === 'all' ? undefined : priority,
        search: search.trim() || undefined,
        overdue: overdueOnly ? true : undefined,
      });
      setTasks(data || []);
    } catch (err) {
      console.error('Failed to load task queue:', err);
      setLoadError(err.message || 'Failed to load task queue');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTasks();
  }, [scope, status, priority, overdueOnly]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchTasks();
  };

  const handleClaim = async (taskId) => {
    try {
      await claimTask(taskId);
      setActionMsg(`Task #${taskId} claimed successfully.`);
      setTimeout(() => setActionMsg(''), 4000);
      fetchTasks();
    } catch (err) {
      alert(`Claim failed: ${err.message || 'Error'}`);
    }
  };

  const handleCompleteSubmit = async (e) => {
    e.preventDefault();
    if (!selectedTask) return;
    try {
      await completeTask(selectedTask.followup_id, outcomeCode, outcomeNotes);
      setCompleteModalOpen(false);
      setOutcomeNotes('');
      setActionMsg(`Task #${selectedTask.followup_id} completed with outcome: ${outcomeCode}`);
      setTimeout(() => setActionMsg(''), 4000);
      fetchTasks();
    } catch (err) {
      alert(`Complete failed: ${err.message || 'Error'}`);
    }
  };

  const handleSnoozeSubmit = async (e) => {
    e.preventDefault();
    if (!selectedTask) return;
    try {
      await snoozeTask(selectedTask.followup_id, snoozeHours, snoozeReason);
      setSnoozeModalOpen(false);
      setSnoozeReason('');
      setActionMsg(`Task #${selectedTask.followup_id} snoozed by ${snoozeHours} hours.`);
      setTimeout(() => setActionMsg(''), 4000);
      fetchTasks();
    } catch (err) {
      alert(`Snooze failed: ${err.message || 'Error'}`);
    }
  };

  const handleAssignSubmit = async (e) => {
    e.preventDefault();
    if (!selectedTask || !targetStaffId) return;
    try {
      await assignTask(selectedTask.followup_id, Number(targetStaffId), assignNote);
      setAssignModalOpen(false);
      setAssignNote('');
      setActionMsg(`Task #${selectedTask.followup_id} assigned successfully.`);
      setTimeout(() => setActionMsg(''), 4000);
      fetchTasks();
    } catch (err) {
      alert(`Assign failed: ${err.message || 'Error'}`);
    }
  };

  const handleLogContactSubmit = async (e) => {
    e.preventDefault();
    if (!selectedTask) return;
    try {
      await logCommunication(
        selectedTask.patient_id,
        contactChannel,
        contactOutcome,
        contactSummary,
        selectedTask.flag_id || null,
        selectedTask.followup_id
      );
      setContactModalOpen(false);
      setContactSummary('');
      setActionMsg(`Communication logged for Task #${selectedTask.followup_id}.`);
      setTimeout(() => setActionMsg(''), 4000);
    } catch (err) {
      alert(`Log contact failed: ${err.message || 'Error'}`);
    }
  };

  const overdueCount = tasks.filter((t) => t.is_overdue).length;
  const urgentCount = tasks.filter((t) => t.priority === 'Urgent_Review').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Toast banner */}
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

      {/* Error banner */}
      {loadError && (
        <div
          style={{
            padding: '12px 16px',
            borderRadius: '8px',
            background: '#fee2e2',
            border: '1px solid #fca5a5',
            color: '#991b1b',
            fontSize: '13px',
            fontWeight: 700,
          }}
        >
          ⚠️ {loadError}
        </div>
      )}

      {/* Header Stat Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
        <div className="stat-card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#64748b', fontWeight: 600 }}>Active Tasks In Queue</div>
          <div style={{ fontSize: '26px', fontWeight: 800, marginTop: '4px', color: 'var(--text-primary, #0f172a)' }}>
            {tasks.length}
          </div>
        </div>
        <div className="stat-card" style={{ padding: '16px 20px', borderLeft: overdueCount > 0 ? '4px solid #ef4444' : '1px solid var(--border-subtle, #e2e8f0)' }}>
          <div style={{ fontSize: '12px', color: overdueCount > 0 ? '#ef4444' : '#64748b', fontWeight: 700 }}>
            {overdueCount > 0 ? '⚠️ Overdue Tasks' : 'Overdue Tasks'}
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, marginTop: '4px', color: overdueCount > 0 ? '#ef4444' : 'var(--text-primary, #0f172a)' }}>
            {overdueCount}
          </div>
        </div>
        <div className="stat-card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '12px', color: '#f59e0b', fontWeight: 700 }}>Urgent Review</div>
          <div style={{ fontSize: '26px', fontWeight: 800, marginTop: '4px', color: '#f59e0b' }}>
            {urgentCount}
          </div>
        </div>
      </div>

      {/* Filters Toolbar */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '16px 20px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '14px',
          boxShadow: 'var(--shadow-card)',
        }}
      >
        {/* Scope buttons */}
        <div style={{ display: 'flex', gap: '6px' }}>
          {[
            { id: 'mine', label: 'My tasks' },
            { id: 'team', label: 'Team tasks' },
            { id: 'unassigned', label: 'Unassigned' },
            { id: 'all', label: 'All tasks' },
          ].map((sc) => (
            <button
              key={sc.id}
              type="button"
              onClick={() => setScope(sc.id)}
              style={{
                padding: '6px 12px',
                borderRadius: '8px',
                border: 'none',
                background: scope === sc.id ? '#0284c7' : 'var(--bg-base, #f1f5f9)',
                color: scope === sc.id ? '#ffffff' : 'var(--text-secondary, #475569)',
                fontWeight: scope === sc.id ? 700 : 500,
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              {sc.label}
            </button>
          ))}
        </div>

        {/* Status toggle & Overdue checkbox */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            style={{
              padding: '6px 10px',
              borderRadius: '8px',
              border: '1px solid var(--border-strong, #cbd5e1)',
              background: 'var(--bg-base, #ffffff)',
              color: 'var(--text-primary, #0f172a)',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            <option value="pending">Status: Pending only</option>
            <option value="completed">Status: Completed only</option>
            <option value="all">Status: All</option>
          </select>

          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={overdueOnly}
              onChange={(e) => setOverdueOnly(e.target.checked)}
            />
            <span>Overdue only</span>
          </label>
        </div>

        {/* Search */}
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', gap: '8px' }}>
          <input
            type="text"
            placeholder="Search patient, code, reason..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: '1px solid var(--border-strong, #cbd5e1)',
              background: 'var(--bg-base, #ffffff)',
              color: 'var(--text-primary, #0f172a)',
              fontSize: '12px',
              minWidth: '220px',
            }}
          />
          <button
            type="submit"
            style={{
              padding: '6px 12px',
              borderRadius: '8px',
              border: 'none',
              background: '#0f172a',
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
            }}
          >
            Search
          </button>
        </form>
      </div>

      {/* Tasks Table */}
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
            <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b' }}>PATIENT IDENTITY</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b' }}>TASK & REASON</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b' }}>PRIORITY</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b' }}>DUE STATUS</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b' }}>OWNER</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b' }}>STATUS</th>
              <th style={{ padding: '12px 16px', fontWeight: 700, color: '#64748b', textAlign: 'right' }}>ACTIONS</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                  Loading tasks queue...
                </td>
              </tr>
            ) : tasks.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
                  No tasks found matching current filters.
                </td>
              </tr>
            ) : (
              tasks.map((t) => {
                const isOverdue = t.is_overdue;
                return (
                  <tr
                    key={t.followup_id}
                    style={{
                      borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                      background: isOverdue ? 'rgba(239, 68, 68, 0.03)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '14px 16px', verticalAlign: 'top' }}>
                      <PatientIdentity
                        patientCode={t.patient_code}
                        fullName={t.patient_name}
                        ageYears={t.age_years}
                        onClick={() => onSelectPatient && onSelectPatient(t.patient_id)}
                      />
                    </td>
                    <td style={{ padding: '14px 16px', verticalAlign: 'top', maxWidth: '320px' }}>
                      <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)', lineHeight: '1.4' }}>
                        {t.reason}
                      </div>
                      {t.flag_id && (
                        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '4px' }}>
                          Linked to Flag #{t.flag_id} {t.flag_severity ? `(${t.flag_severity === 'Review_Soon' ? 'Review soon' : t.flag_severity === 'Urgent_Review' ? 'Urgent' : t.flag_severity})` : ''}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px', verticalAlign: 'top' }}>
                      <span
                        className={`status-pill ${
                          t.priority === 'Urgent_Review'
                            ? 'status-pill-red'
                            : t.priority === 'Review_Soon'
                            ? 'status-pill-amber'
                            : 'status-pill-blue'
                        }`}
                      >
                        {t.priority_label || (t.priority === 'Review_Soon' ? 'Review soon' : t.priority === 'Urgent_Review' ? 'Urgent' : t.priority)}
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px', verticalAlign: 'top' }}>
                      {isOverdue ? (
                        <span
                          style={{
                            display: 'inline-block',
                            padding: '3px 8px',
                            borderRadius: '6px',
                            background: '#fef2f2',
                            color: '#ef4444',
                            border: '1px solid #fecaca',
                            fontWeight: 700,
                            fontSize: '11px',
                          }}
                        >
                          ⚠️ {t.overdue_label}
                        </span>
                      ) : (
                        <span style={{ color: '#64748b', fontSize: '11px', fontWeight: 600 }}>
                          {t.overdue_label || 'Today'}
                        </span>
                      )}
                      <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '2px' }}>
                        Due: {t.due_at ? t.due_at.slice(0, 16).replace('T', ' ') : 'None'}
                      </div>
                    </td>
                    <td style={{ padding: '14px 16px', verticalAlign: 'top' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                        {t.assigned_staff_name || 'Unassigned'}
                      </div>
                      {t.assigned_staff_id === user.staff_id && (
                        <span style={{ fontSize: '10px', color: '#0284c7', fontWeight: 700 }}>● You</span>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px', verticalAlign: 'top' }}>
                      <span
                        className={`status-pill ${
                          t.status === 'Resolved' ? 'status-pill-green' : 'status-pill-amber'
                        }`}
                      >
                        {t.status}
                      </span>
                      {t.outcome_code && (
                        <div style={{ fontSize: '10px', color: '#059669', marginTop: '2px', fontWeight: 600 }}>
                          {t.outcome_code.replace(/_/g, ' ')}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '14px 16px', verticalAlign: 'top', textAlign: 'right' }}>
                      {t.status !== 'Resolved' ? (
                        <div style={{ display: 'inline-flex', gap: '6px' }}>
                          {/* Claim button if not mine */}
                          {t.assigned_staff_id !== user.staff_id && (
                            <button
                              type="button"
                              onClick={() => handleClaim(t.followup_id)}
                              style={{
                                padding: '4px 8px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-strong, #cbd5e1)',
                                background: 'transparent',
                                color: 'var(--text-primary, #0f172a)',
                                fontSize: '11px',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              Claim
                            </button>
                          )}
                          {/* Assign button */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedTask(t);
                              setAssignModalOpen(true);
                            }}
                            style={{
                              padding: '4px 8px',
                              borderRadius: '6px',
                              border: '1px solid var(--border-strong, #cbd5e1)',
                              background: 'transparent',
                              color: 'var(--text-primary, #0f172a)',
                              fontSize: '11px',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            Assign
                          </button>
                          {/* Snooze button */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedTask(t);
                              setSnoozeModalOpen(true);
                            }}
                            style={{
                              padding: '4px 8px',
                              borderRadius: '6px',
                              border: '1px solid var(--border-strong, #cbd5e1)',
                              background: 'transparent',
                              color: 'var(--text-primary, #0f172a)',
                              fontSize: '11px',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            Snooze
                          </button>
                          {/* Call button */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedTask(t);
                              setContactModalOpen(true);
                            }}
                            style={{
                              padding: '4px 8px',
                              borderRadius: '6px',
                              border: '1px solid #38bdf8',
                              background: '#f0f9ff',
                              color: '#0284c7',
                              fontSize: '11px',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            📞 Log Call
                          </button>
                          {/* Complete button */}
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedTask(t);
                              setCompleteModalOpen(true);
                            }}
                            style={{
                              padding: '4px 10px',
                              borderRadius: '6px',
                              border: 'none',
                              background: '#059669',
                              color: '#ffffff',
                              fontSize: '11px',
                              fontWeight: 700,
                              cursor: 'pointer',
                            }}
                          >
                            Complete
                          </button>
                        </div>
                      ) : (
                        <span style={{ fontSize: '11px', color: '#94a3b8' }}>
                          Resolved {t.completed_at ? t.completed_at.slice(0, 10) : ''}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>

      {/* MODAL: COMPLETE TASK (Mandatory Outcome Code) */}
      {completeModalOpen && selectedTask && (
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
            <h3 style={{ fontSize: '16px', fontWeight: 800, margin: '0 0 12px 0' }}>
              Complete Task #{selectedTask.followup_id}
            </h3>
            <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 16px 0' }}>
              Select a clinical outcome code to resolve this follow-up item. This action will be recorded in the audit trail.
            </p>
            <form onSubmit={handleCompleteSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Outcome Code *
                </label>
                <select
                  value={outcomeCode}
                  onChange={(e) => setOutcomeCode(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                    fontWeight: 600,
                  }}
                >
                  <option value="Reached_And_Advised">Reached and advised patient / caregiver</option>
                  <option value="Appointment_Set">Clinic appointment scheduled</option>
                  <option value="No_Answer">No answer (call attempt logged)</option>
                  <option value="Escalated_To_Doctor">Escalated to attending doctor</option>
                  <option value="No_Action_Needed">No clinical action needed</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Outcome Clinical Notes
                </label>
                <textarea
                  rows={3}
                  value={outcomeNotes}
                  onChange={(e) => setOutcomeNotes(e.target.value)}
                  placeholder="Record summary of guidance provided or follow-up details..."
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setCompleteModalOpen(false)}
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
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#059669',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Complete & Resolve Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: SNOOZE TASK */}
      {snoozeModalOpen && selectedTask && (
        <div className="modal-overlay" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '440px',
              width: '100%',
              boxShadow: 'var(--shadow-lg)',
            }}
          >
            <h3 style={{ fontSize: '16px', fontWeight: 800, margin: '0 0 12px 0' }}>
              Snooze Task #{selectedTask.followup_id}
            </h3>
            <p style={{ fontSize: '12px', color: '#64748b', margin: '0 0 16px 0' }}>
              Extend the due time of this task. A clinical reason is required.
            </p>
            <form onSubmit={handleSnoozeSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Snooze Duration (Hours) *
                </label>
                <select
                  value={snoozeHours}
                  onChange={(e) => setSnoozeHours(Number(e.target.value))}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                    fontWeight: 600,
                  }}
                >
                  <option value={2}>2 Hours</option>
                  <option value={4}>4 Hours</option>
                  <option value={8}>8 Hours</option>
                  <option value={24}>24 Hours (Next Day)</option>
                  <option value={48}>48 Hours</option>
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Clinical Justification Reason *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Patient resting post-procedure, callback planned"
                  value={snoozeReason}
                  onChange={(e) => setSnoozeReason(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setSnoozeModalOpen(false)}
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
                  disabled={!snoozeReason.trim() || snoozeReason.trim().length < 3}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#0284c7',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Confirm Snooze
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: ASSIGN TASK */}
      {assignModalOpen && selectedTask && (
        <div className="modal-overlay" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              borderRadius: '12px',
              padding: '24px',
              maxWidth: '440px',
              width: '100%',
              boxShadow: 'var(--shadow-lg)',
            }}
          >
            <h3 style={{ fontSize: '16px', fontWeight: 800, margin: '0 0 12px 0' }}>
              Assign Task #{selectedTask.followup_id}
            </h3>
            <form onSubmit={handleAssignSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Assign to Team Member *
                </label>
                <select
                  required
                  value={targetStaffId}
                  onChange={(e) => setTargetStaffId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                    fontWeight: 600,
                  }}
                >
                  <option value="">Select staff member...</option>
                  {staffMembers.map((s) => (
                    <option key={s.staff_id} value={s.staff_id}>
                      {s.full_name} ({s.staff_role})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Handoff Note
                </label>
                <input
                  type="text"
                  placeholder="Optional instruction for the assignee..."
                  value={assignNote}
                  onChange={(e) => setAssignNote(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setAssignModalOpen(false)}
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
                  disabled={!targetStaffId}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#0f172a',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Assign Task
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: LOG COMMUNICATION (Feature D-15) */}
      {contactModalOpen && selectedTask && (
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
            <h3 style={{ fontSize: '16px', fontWeight: 800, margin: '0 0 12px 0' }}>
              Log Contact with {selectedTask.patient_name} ({selectedTask.patient_code})
            </h3>
            <form onSubmit={handleLogContactSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                    Channel *
                  </label>
                  <select
                    value={contactChannel}
                    onChange={(e) => setContactChannel(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-strong, #cbd5e1)',
                      background: 'var(--bg-base, #ffffff)',
                      fontSize: '12px',
                    }}
                  >
                    <option value="Phone">Phone Call</option>
                    <option value="SMS">SMS Message</option>
                    <option value="In_Person">In Person</option>
                    <option value="Video">Video Call</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                    Outcome *
                  </label>
                  <select
                    value={contactOutcome}
                    onChange={(e) => setContactOutcome(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-strong, #cbd5e1)',
                      background: 'var(--bg-base, #ffffff)',
                      fontSize: '12px',
                    }}
                  >
                    <option value="Reached">Reached</option>
                    <option value="No_Answer">No Answer</option>
                    <option value="Left_Message">Left Message</option>
                    <option value="Wrong_Number">Wrong Number</option>
                    <option value="Declined">Declined</option>
                  </select>
                </div>
              </div>
              <div>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, marginBottom: '6px' }}>
                  Call / Message Summary
                </label>
                <textarea
                  rows={3}
                  value={contactSummary}
                  onChange={(e) => setContactSummary(e.target.value)}
                  placeholder="Summary of call discussion, symptoms reviewed, or advice given..."
                  style={{
                    width: '100%',
                    padding: '8px 10px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-strong, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    fontSize: '12px',
                  }}
                />
              </div>
              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '6px' }}>
                <button
                  type="button"
                  onClick={() => setContactModalOpen(false)}
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
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: 'none',
                    background: '#0284c7',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  Save to Contact Log
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
