import React, { useState, useEffect, useRef } from 'react';
import PatientIdentity from './PatientIdentity';
import {
  acknowledgeFlag,
  resolveFlag,
  dismissFlag,
  assignFlag,
  escalateFlagNow,
} from '../services/api';

/**
 * FlagDrawer Component (D-03, D-10, D-18)
 *
 * Slide-in detail drawer for clinical flags.
 * Includes:
 * - Patient identity (Name, Age, Code CL-0000X, Condition)
 * - Clinical Why & Evidence with Data Quality indicators
 * - Rule approver & threshold
 * - 4-step Escalation Ladder with "Escalate Now"
 * - Audit Trail (flag_events)
 * - State-specific closed-loop actions (Acknowledge, Resolve with code/note, Dismiss)
 */
export default function FlagDrawer({
  flag = null,
  staffMembers = [],
  currentStaffId = null,
  onClose,
  onActionSuccess,
}) {
  const [activeTab, setActiveTab] = useState('overview'); // 'overview', 'evidence', 'ladder', 'history'
  const [loadingAction, setLoadingAction] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  
  // Modal states
  const [actionModal, setActionModal] = useState(null); // 'resolve', 'dismiss', 'assign', 'escalate'
  const [modalNote, setModalNote] = useState('');
  const [resolutionCode, setResolutionCode] = useState('No_Action_Needed');
  const [targetStaffId, setTargetStaffId] = useState(staffMembers[0]?.staff_id || '');
  const [createFollowupTask, setCreateFollowupTask] = useState(false);

  const drawerRef = useRef(null);

  // Esc key closes drawer
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (actionModal) {
          setActionModal(null);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [actionModal, onClose]);

  if (!flag) return null;

  const {
    flag_id,
    patient = {},
    reason,
    severity,
    tier = 'Routine',
    source_type,
    status,
    created_at,
    owner_name,
    acknowledged_by_name,
    acknowledged_at,
    resolved_by_name,
    resolved_at,
    resolution_code,
    resolution_note,
    evidence = {},
    rule = {},
    escalation_ladder = [],
    history = [],
  } = flag;

  const isUrgentOrImmediate = tier === 'Immediate' || severity === 'Urgent_Review';

  // Action handlers
  const handleAcknowledge = async () => {
    setLoadingAction(true);
    setErrorMsg('');
    try {
      await acknowledgeFlag(flag_id, modalNote || 'Acknowledged via portal drawer', createFollowupTask);
      onActionSuccess?.('Flag acknowledged successfully');
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to acknowledge flag');
    } finally {
      setLoadingAction(false);
    }
  };

  const handleResolve = async () => {
    if (isUrgentOrImmediate && (!modalNote || modalNote.trim().length < 5)) {
      setErrorMsg('A clinical note of at least 5 characters is required for urgent/immediate flags.');
      return;
    }
    setLoadingAction(true);
    setErrorMsg('');
    try {
      await resolveFlag(flag_id, resolutionCode, modalNote);
      onActionSuccess?.('Flag resolved successfully');
      setActionModal(null);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to resolve flag');
    } finally {
      setLoadingAction(false);
    }
  };

  const handleDismiss = async () => {
    if (!modalNote || modalNote.trim().length < 3) {
      setErrorMsg('Please provide a reason for dismissing this flag.');
      return;
    }
    setLoadingAction(true);
    setErrorMsg('');
    try {
      await dismissFlag(flag_id, resolutionCode || 'False_Alarm', modalNote);
      onActionSuccess?.('Flag dismissed');
      setActionModal(null);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to dismiss flag');
    } finally {
      setLoadingAction(false);
    }
  };

  const handleAssign = async () => {
    if (!targetStaffId) {
      setErrorMsg('Please select a staff member.');
      return;
    }
    setLoadingAction(true);
    setErrorMsg('');
    try {
      await assignFlag(flag_id, Number(targetStaffId), modalNote);
      onActionSuccess?.('Flag reassigned');
      setActionModal(null);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to assign flag');
    } finally {
      setLoadingAction(false);
    }
  };

  const handleEscalate = async () => {
    setLoadingAction(true);
    setErrorMsg('');
    try {
      await escalateFlagNow(flag_id, modalNote || 'Manual escalation requested');
      onActionSuccess?.('Flag escalated to attending physician');
      setActionModal(null);
      onClose();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to escalate flag');
    } finally {
      setLoadingAction(false);
    }
  };

  // Tier color styling
  const getTierBadge = () => {
    switch (tier) {
      case 'Immediate':
        return { bg: '#fef2f2', border: '#fecaca', color: '#dc2626', label: 'Immediate (<15m target)' };
      case 'Urgent':
        return { bg: '#fffbeb', border: '#fde68a', color: '#b45309', label: 'Urgent (<2h target)' };
      case 'Review_Soon':
        return { bg: '#eff6ff', border: '#bfdbfe', color: '#1d4ed8', label: 'Review soon (<24h target)' };
      default:
        return { bg: '#f8fafc', border: '#e2e8f0', color: '#475569', label: 'Routine review' };
    }
  };

  const tierBadge = getTierBadge();

  // Data quality badge styling (D-18)
  const getQualityBadge = (quality) => {
    switch (quality) {
      case 'Good':
        return { bg: '#ecfdf5', color: '#047857', border: '#a7f3d0', label: 'Good Quality' };
      case 'Questionable':
        return { bg: '#fffbeb', color: '#b45309', border: '#fde68a', label: 'Questionable' };
      case 'Invalid':
        return { bg: '#fef2f2', color: '#b91c1c', border: '#fecaca', label: 'Invalid' };
      case 'Simulated':
        return { bg: '#f5f3ff', color: '#6d28d9', border: '#ddd6fe', label: 'Simulated' };
      default:
        return { bg: '#f1f5f9', color: '#475569', border: '#cbd5e1', label: quality || 'Unverified' };
    }
  };

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(15, 23, 42, 0.45)',
          backdropFilter: 'blur(2px)',
          zIndex: 999,
          animation: 'fadeIn 0.15s ease',
        }}
      />

      {/* Drawer Container */}
      <aside
        ref={drawerRef}
        aria-label="Flag details drawer"
        style={{
          position: 'fixed',
          top: 0,
          right: 0,
          bottom: 0,
          width: '580px',
          maxWidth: '92vw',
          background: 'var(--bg-surface, #ffffff)',
          borderLeft: '1px solid var(--border-subtle, #e2e8f0)',
          boxShadow: '-8px 0 32px rgba(15, 23, 42, 0.15)',
          zIndex: 1000,
          display: 'flex',
          flexDirection: 'column',
          fontFamily: "'Inter', sans-serif",
        }}
      >
        {/* Drawer Header */}
        <header
          style={{
            padding: '20px 24px',
            borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            background: 'var(--bg-surface, #ffffff)',
          }}
        >
          <div style={{ flex: 1, paddingRight: '16px' }}>
            <PatientIdentity patient={patient} size="md" />
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '10px' }}>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  padding: '3px 8px',
                  borderRadius: '6px',
                  background: tierBadge.bg,
                  color: tierBadge.color,
                  border: `1px solid ${tierBadge.border}`,
                }}
              >
                {tierBadge.label}
              </span>
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 600,
                  padding: '3px 8px',
                  borderRadius: '6px',
                  background: status === 'Open' ? '#fef2f2' : status === 'Acknowledged' ? '#f0fdf4' : '#f1f5f9',
                  color: status === 'Open' ? '#dc2626' : status === 'Acknowledged' ? '#16a34a' : '#64748b',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                }}
              >
                {status}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            style={{
              background: 'transparent',
              border: 'none',
              fontSize: '20px',
              fontWeight: 600,
              color: 'var(--text-muted, #94a3b8)',
              cursor: 'pointer',
              padding: '4px 8px',
              borderRadius: '6px',
            }}
          >
            ✕
          </button>
        </header>

        {/* Navigation Tabs */}
        <nav
          style={{
            display: 'flex',
            borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
            padding: '0 24px',
            background: 'var(--bg-base, #f8fafc)',
          }}
        >
          {[
            { id: 'overview', label: 'Clinical Overview' },
            { id: 'evidence', label: 'Evidence & Quality' },
            { id: 'ladder', label: 'Escalation Ladder' },
            { id: 'history', label: `History (${history.length})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '12px 14px',
                border: 'none',
                background: 'transparent',
                fontSize: '13px',
                fontWeight: activeTab === tab.id ? 700 : 500,
                color: activeTab === tab.id ? '#0f172a' : '#64748b',
                borderBottom: activeTab === tab.id ? '2px solid #0f172a' : '2px solid transparent',
                cursor: 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Error message if any */}
        {errorMsg && (
          <div
            style={{
              padding: '10px 24px',
              background: '#fef2f2',
              borderBottom: '1px solid #fecaca',
              color: '#b91c1c',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            ⚠️ {errorMsg}
          </div>
        )}

        {/* Content Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Reason Card */}
              <div
                style={{
                  padding: '16px',
                  borderRadius: '8px',
                  background: 'var(--bg-base, #f8fafc)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Clinical Why / Reason
                </div>
                <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary, #0f172a)', lineHeight: '1.4' }}>
                  {reason}
                </div>
                <div style={{ fontSize: '12px', color: '#64748b', marginTop: '10px', display: 'flex', gap: '16px' }}>
                  <span>Source: <strong>{source_type}</strong></span>
                  <span>Raised: <strong>{created_at ? new Date(created_at).toLocaleString('en-IN') : '-'}</strong></span>
                </div>
              </div>

              {/* Ownership & Status */}
              <div
                style={{
                  padding: '16px',
                  borderRadius: '8px',
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '10px' }}>
                  Ownership & Review Status
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '13px' }}>
                  <div>
                    <span style={{ color: '#94a3b8' }}>Current Owner:</span>
                    <div style={{ fontWeight: 600, color: '#0f172a' }}>{owner_name || 'Unassigned (Triage Pool)'}</div>
                  </div>
                  <div>
                    <span style={{ color: '#94a3b8' }}>Acknowledged By:</span>
                    <div style={{ fontWeight: 600, color: '#0f172a' }}>
                      {acknowledged_by_name ? `${acknowledged_by_name} (${new Date(acknowledged_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})` : 'Not yet seen'}
                    </div>
                  </div>
                  {resolved_by_name && (
                    <>
                      <div>
                        <span style={{ color: '#94a3b8' }}>Resolved By:</span>
                        <div style={{ fontWeight: 600, color: '#0f172a' }}>
                          {resolved_by_name} {resolved_at ? `(${new Date(resolved_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })})` : ''}
                        </div>
                      </div>
                      <div>
                        <span style={{ color: '#94a3b8' }}>Resolution Code:</span>
                        <div style={{ fontWeight: 600, color: '#0f172a' }}>{resolution_code}</div>
                      </div>
                    </>
                  )}
                </div>
                {resolution_note && (
                  <div style={{ marginTop: '12px', padding: '10px', borderRadius: '6px', background: '#f8fafc', fontSize: '12px', color: '#475569' }}>
                    <strong>Resolution Note:</strong> {resolution_note}
                  </div>
                )}
              </div>

              {/* Rule Card */}
              <div
                style={{
                  padding: '16px',
                  borderRadius: '8px',
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                }}
              >
                <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Trigger Rule & Governance
                </div>
                <div style={{ fontSize: '13px', color: '#334155', lineHeight: '1.5' }}>
                  <div><strong>Rule Type:</strong> {rule.rule_type || 'Safety Protocol'}</div>
                  <div><strong>Threshold:</strong> {rule.threshold_value || 'Emergency Keyword Pattern'}</div>
                  <div>
                    <strong>Approved By:</strong> {rule.approved_by_name || 'Clinical Safety Protocol'}
                    {rule.approved_at && ` on ${new Date(rule.approved_at).toLocaleDateString()}`}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: EVIDENCE */}
          {activeTab === 'evidence' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
                  Raw Evidence Data
                </span>
                {evidence.data_quality && (
                  <span
                    style={{
                      fontSize: '11px',
                      fontWeight: 700,
                      padding: '3px 8px',
                      borderRadius: '6px',
                      background: getQualityBadge(evidence.data_quality).bg,
                      color: getQualityBadge(evidence.data_quality).color,
                      border: `1px solid ${getQualityBadge(evidence.data_quality).border}`,
                    }}
                  >
                    {getQualityBadge(evidence.data_quality).label}
                  </span>
                )}
              </div>

              {evidence.details ? (
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    background: 'var(--bg-base, #f8fafc)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '12px',
                    color: '#1e293b',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                  }}
                >
                  {JSON.stringify(evidence.details, null, 2)}
                </div>
              ) : (
                <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                  No standalone reading record linked. Flag was raised from patient symptom notes or emergency detection.
                </div>
              )}

              <div
                style={{
                  padding: '12px 16px',
                  borderRadius: '6px',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  fontSize: '12px',
                  color: '#64748b',
                }}
              >
                🔒 <strong>Clinical Data Integrity:</strong> All sensor telemetry is verified against device calibration thresholds. Patient self-reports are preserved verbatim without AI alteration.
              </div>
            </div>
          )}

          {/* TAB 3: ESCALATION LADDER (D-10) */}
          {activeTab === 'ladder' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a' }}>
                    Escalation Progression
                  </div>
                  <div style={{ fontSize: '12px', color: '#64748b' }}>
                    Automated clinical safety ladder until acknowledged.
                  </div>
                </div>

                {status === 'Open' && (
                  <button
                    type="button"
                    onClick={() => setActionModal('escalate')}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #fecaca',
                      background: '#fef2f2',
                      color: '#dc2626',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    ⚡ Escalate Now
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
                {escalation_ladder.map((step, idx) => {
                  const isDone = step.delivery_status === 'Acknowledged' || step.delivery_status === 'Sent';
                  const isSkipped = step.delivery_status === 'Skipped_No_Consent';
                  return (
                    <div
                      key={step.escalation_id || idx}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '12px',
                        padding: '12px 16px',
                        borderRadius: '8px',
                        background: isDone ? '#f0fdf4' : isSkipped ? '#fffbeb' : '#f8fafc',
                        border: `1px solid ${isDone ? '#bbf7d0' : isSkipped ? '#fde68a' : '#e2e8f0'}`,
                      }}
                    >
                      <div
                        style={{
                          width: '24px',
                          height: '24px',
                          borderRadius: '50%',
                          background: isDone ? '#16a34a' : isSkipped ? '#d97706' : '#cbd5e1',
                          color: '#ffffff',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '11px',
                          fontWeight: 700,
                          flexShrink: 0,
                        }}
                      >
                        {isDone ? '✓' : idx + 1}
                      </div>

                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                          <span style={{ fontSize: '13px', fontWeight: 700, color: '#0f172a' }}>
                            {step.step_type?.replace('_', ' ')} ({step.channel})
                          </span>
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 600,
                              color: isDone ? '#15803d' : isSkipped ? '#b45309' : '#64748b',
                            }}
                          >
                            {step.delivery_status}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: '#64748b', marginTop: '2px' }}>
                          {step.notes || 'Automated protocol trigger'}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>

              {status !== 'Open' && (
                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: '6px',
                    background: '#f0fdf4',
                    border: '1px solid #bbf7d0',
                    fontSize: '12px',
                    color: '#166534',
                    fontWeight: 600,
                  }}
                >
                  ✓ Escalation ladder halted because flag was acknowledged by {acknowledged_by_name || 'Care Team'}.
                </div>
              )}
            </div>
          )}

          {/* TAB 4: AUDIT HISTORY */}
          {activeTab === 'history' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '14px', fontWeight: 700, color: '#0f172a', marginBottom: '4px' }}>
                Append-Only Flag Audit Log
              </div>

              {history.length === 0 ? (
                <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                  No event transactions logged for this flag yet.
                </div>
              ) : (
                history.map((ev, idx) => (
                  <div
                    key={ev.flag_event_id || idx}
                    style={{
                      padding: '12px 14px',
                      borderRadius: '8px',
                      background: 'var(--bg-base, #f8fafc)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      fontSize: '12px',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span style={{ fontWeight: 700, color: '#0f172a' }}>
                        {ev.event_type} · {ev.staff_name || 'System Rule Engine'}
                      </span>
                      <span style={{ color: '#94a3b8', fontFamily: "'JetBrains Mono', monospace" }}>
                        {new Date(ev.created_at).toLocaleString('en-IN')}
                      </span>
                    </div>
                    {ev.note && (
                      <div style={{ marginTop: '6px', color: '#475569' }}>
                        {ev.note}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {/* Drawer Footer Actions */}
        <footer
          style={{
            padding: '16px 24px',
            borderTop: '1px solid var(--border-subtle, #e2e8f0)',
            background: 'var(--bg-surface, #ffffff)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: '12px',
          }}
        >
          {status === 'Open' ? (
            <>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setActionModal('dismiss')}
                  disabled={loadingAction}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    background: 'var(--bg-base, #f8fafc)',
                    color: 'var(--text-secondary, #475569)',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Dismiss as False Alarm
                </button>
                <button
                  type="button"
                  onClick={() => setActionModal('assign')}
                  disabled={loadingAction}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    background: 'var(--bg-base, #f8fafc)',
                    color: 'var(--text-secondary, #475569)',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Assign...
                </button>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: '#64748b', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={createFollowupTask}
                    onChange={(e) => setCreateFollowupTask(e.target.checked)}
                  />
                  Create Task
                </label>
                <button
                  type="button"
                  onClick={handleAcknowledge}
                  disabled={loadingAction}
                  style={{
                    padding: '8px 18px',
                    borderRadius: '6px',
                    border: 'none',
                    background: '#0f172a',
                    color: '#ffffff',
                    fontSize: '13px',
                    fontWeight: 700,
                    cursor: 'pointer',
                  }}
                >
                  {loadingAction ? 'Acknowledging...' : 'Acknowledge Flag'}
                </button>
              </div>
            </>
          ) : status === 'Acknowledged' ? (
            <>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  type="button"
                  onClick={() => setActionModal('assign')}
                  disabled={loadingAction}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    background: 'var(--bg-base, #f8fafc)',
                    color: 'var(--text-secondary, #475569)',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Reassign...
                </button>
              </div>

              <button
                type="button"
                onClick={() => setActionModal('resolve')}
                disabled={loadingAction}
                style={{
                  padding: '8px 20px',
                  borderRadius: '6px',
                  border: 'none',
                  background: '#16a34a',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                Resolve Flag...
              </button>
            </>
          ) : (
            <div style={{ width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '13px', color: '#64748b' }}>
                This flag is <strong>{status}</strong>.
              </span>
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  color: '#0f172a',
                  fontSize: '12px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Close Drawer
              </button>
            </div>
          )}
        </footer>
      </aside>

      {/* ACTION MODAL OVERLAY */}
      {actionModal && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.6)',
            zIndex: 1100,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
          }}
        >
          <div
            style={{
              background: '#ffffff',
              borderRadius: '12px',
              padding: '24px',
              width: '460px',
              maxWidth: '100%',
              boxShadow: '0 20px 40px rgba(0,0,0,0.2)',
              fontFamily: "'Inter', sans-serif",
            }}
          >
            <div style={{ fontSize: '16px', fontWeight: 800, color: '#0f172a', marginBottom: '8px' }}>
              {actionModal === 'resolve' && 'Resolve Clinical Flag'}
              {actionModal === 'dismiss' && 'Dismiss as False Alarm'}
              {actionModal === 'assign' && 'Assign Flag Ownership'}
              {actionModal === 'escalate' && 'Confirm Manual Escalation'}
            </div>

            <div style={{ fontSize: '13px', color: '#64748b', marginBottom: '16px' }}>
              {actionModal === 'resolve' && 'Select the clinical outcome and provide resolution notes.'}
              {actionModal === 'dismiss' && 'Record the false alarm reason to update rule performance metrics.'}
              {actionModal === 'assign' && 'Select the colleague to take ownership of this flag.'}
              {actionModal === 'escalate' && 'Immediate notification will be dispatched to the attending physician.'}
            </div>

            {/* Resolution Code Dropdown */}
            {(actionModal === 'resolve' || actionModal === 'dismiss') && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                  Resolution Code *
                </label>
                <select
                  value={resolutionCode}
                  onChange={(e) => setResolutionCode(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '13px',
                    color: '#0f172a',
                  }}
                >
                  {actionModal === 'resolve' ? (
                    <>
                      <option value="No_Action_Needed">No Action Needed</option>
                      <option value="Patient_Contacted">Patient Contacted</option>
                      <option value="Appointment_Arranged">Appointment Arranged</option>
                      <option value="Referred_To_Emergency">Referred to Emergency Care</option>
                      <option value="Device_Or_Data_Issue">Device or Data Issue</option>
                      <option value="Duplicate">Duplicate Flag</option>
                    </>
                  ) : (
                    <>
                      <option value="False_Alarm">False Alarm (Sensor Artifact)</option>
                      <option value="Duplicate">Duplicate / Repeated Alert</option>
                      <option value="Device_Or_Data_Issue">Device Transmission Glitch</option>
                    </>
                  )}
                </select>
              </div>
            )}

            {/* Assign Colleague Dropdown */}
            {actionModal === 'assign' && (
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                  Assign to Staff Member *
                </label>
                <select
                  value={targetStaffId}
                  onChange={(e) => setTargetStaffId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    border: '1px solid #cbd5e1',
                    fontSize: '13px',
                    color: '#0f172a',
                  }}
                >
                  {staffMembers.map((sm) => (
                    <option key={sm.staff_id} value={sm.staff_id}>
                      {sm.full_name} ({sm.staff_role})
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Note Textarea */}
            <div style={{ marginBottom: '18px' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 700, color: '#334155', marginBottom: '6px' }}>
                Clinical Note {actionModal === 'resolve' && isUrgentOrImmediate ? '(Min. 5 characters required *)' : ''}
              </label>
              <textarea
                value={modalNote}
                onChange={(e) => setModalNote(e.target.value)}
                placeholder="Enter justification or clinical context..."
                rows={3}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  fontSize: '13px',
                  fontFamily: 'inherit',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            {/* Modal Buttons */}
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
              <button
                type="button"
                onClick={() => setActionModal(null)}
                disabled={loadingAction}
                style={{
                  padding: '8px 16px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  color: '#475569',
                  fontSize: '13px',
                  fontWeight: 600,
                  cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={
                  actionModal === 'resolve'
                    ? handleResolve
                    : actionModal === 'dismiss'
                    ? handleDismiss
                    : actionModal === 'assign'
                    ? handleAssign
                    : handleEscalate
                }
                disabled={loadingAction}
                style={{
                  padding: '8px 18px',
                  borderRadius: '6px',
                  border: 'none',
                  background: actionModal === 'resolve' ? '#16a34a' : '#0f172a',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: 'pointer',
                }}
              >
                {loadingAction ? 'Processing...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
