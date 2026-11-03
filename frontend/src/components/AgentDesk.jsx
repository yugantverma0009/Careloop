import React, { useState, useEffect } from 'react';
import { API_BASE } from '../services/api';
import ReportIncidentModal from './ReportIncidentModal';
import {
  IconShieldCheck,
  IconClock,
  IconCheck,
  IconAlertTriangle,
  IconX,
  IconActivity,
  IconFileText,
  IconRefresh
} from './Icons';

export default function AgentDesk({ currentUser, onSelectPatient }) {
  const isDoctor = currentUser?.account_role === 'Doctor';
  const roleAccent = isDoctor ? 'var(--navy-deep, #0b1528)' : 'var(--accent-teal, #0d9488)';
  const roleAccentSoft = isDoctor ? '#e0f2fe' : 'var(--accent-teal-soft, #ecfdf5)';

  const [loading, setLoading] = useState(true);
  const [deskData, setDeskData] = useState({
    global_paused: false,
    waiting_for_you: [],
    done_for_you: [],
    needs_a_decision: [],
    work_saved: {}
  });
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [traceData, setTraceData] = useState(null);
  const [traceLoading, setTraceLoading] = useState(false);

  const [editingDraftId, setEditingDraftId] = useState(null);
  const [editText, setEditText] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [incidentModalRun, setIncidentModalRun] = useState(null);

  // Phase 4 Routine Draft Review & Diff State
  const [reviewMode, setReviewMode] = useState('standard'); // 'standard' | 'routine_diff'
  const [routineData, setRoutineData] = useState({ drafts: [], type_eligibility: {}, batch_threshold_required: 95.0 });
  const [activeDraftIndex, setActiveDraftIndex] = useState(0);
  const [batchLoading, setBatchLoading] = useState(false);

  const token = localStorage.getItem('careloop_token');

  const fetchDeskData = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/agent/desk`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setDeskData(data);
      }
    } catch (err) {
      console.error('Failed to load Agent Desk:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchRoutineDrafts = async () => {
    try {
      const res = await fetch(`${API_BASE}/agent/drafts/routine`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setRoutineData(data);
      }
    } catch (err) {
      console.error('Failed to load routine drafts:', err);
    }
  };

  useEffect(() => {
    fetchDeskData();
    fetchRoutineDrafts();
  }, []);

  // Phase 4: Keyboard shortcuts (j/k move, a approve, e edit, r reject)
  useEffect(() => {
    if (reviewMode !== 'routine_diff') return;

    const handleKeyDown = (e) => {
      if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;

      const drafts = routineData.drafts || [];
      if (!drafts.length) return;

      const activeDraft = drafts[activeDraftIndex];

      if (e.key === 'j') {
        e.preventDefault();
        setActiveDraftIndex((prev) => Math.min(prev + 1, drafts.length - 1));
      } else if (e.key === 'k') {
        e.preventDefault();
        setActiveDraftIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === 'a' && activeDraft) {
        e.preventDefault();
        handleDraftAction(activeDraft.draft_id, 'accept');
      } else if (e.key === 'e' && activeDraft) {
        e.preventDefault();
        setEditingDraftId(activeDraft.draft_id);
        setEditText(activeDraft.draft_text);
      } else if (e.key === 'r' && activeDraft) {
        e.preventDefault();
        handleDraftAction(activeDraft.draft_id, 'reject');
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [reviewMode, activeDraftIndex, routineData]);

  const handleBatchApprove = async (draftType) => {
    if (!window.confirm(`Approve all passing drafts of type '${draftType}'? Every item will be individually audited.`)) return;
    try {
      setBatchLoading(true);
      const res = await fetch(`${API_BASE}/agent/drafts/batch-approve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ draft_type: draftType })
      });
      const data = await res.json();
      if (res.ok) {
        setActionMsg(`✓ Batch approved ${data.approved_count} '${draftType}' drafts with individual audit.`);
        setTimeout(() => setActionMsg(''), 4000);
        fetchDeskData();
        fetchRoutineDrafts();
      } else {
        alert(data.detail || 'Batch approval failed');
      }
    } catch (err) {
      alert('Batch approval request error: ' + err.message);
    } finally {
      setBatchLoading(false);
    }
  };

  const handleGlobalPauseToggle = async (pauseVal) => {
    if (!window.confirm(pauseVal 
      ? 'Engage Global Agent Pause? All automated drafts and outreach will stop until resumed.'
      : 'Resume automated agent operations?'
    )) return;

    try {
      const res = await fetch(`${API_BASE}/agent/pause`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ paused: pauseVal })
      });
      if (res.ok) {
        setActionMsg(pauseVal ? 'Global pause engaged.' : 'Agents resumed.');
        setTimeout(() => setActionMsg(''), 4000);
        fetchDeskData();
      }
    } catch (err) {
      alert('Failed to toggle pause: ' + err.message);
    }
  };

  const handleDraftAction = async (draftId, action, editedBody = null) => {
    try {
      const res = await fetch(`${API_BASE}/agent/drafts/${draftId}/action`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          action,
          edited_body: editedBody
        })
      });
      if (res.ok) {
        setActionMsg(`Draft #${draftId} marked as ${action}.`);
        setTimeout(() => setActionMsg(''), 4000);
        setEditingDraftId(null);
        fetchDeskData();
      }
    } catch (err) {
      alert(`Action failed: ${err.message}`);
    }
  };

  const handleUndo = async (item) => {
    try {
      if (item.action_id) {
        const res = await fetch(`${API_BASE}/agent/undo/${item.action_id}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${token}`
          }
        });
        if (res.ok) {
          setActionMsg(`Action #${item.action_id} successfully undone & cancelled.`);
          setTimeout(() => setActionMsg(''), 4000);
          fetchDeskData();
          return;
        }
      }
      // Demo / flag merging undo
      setActionMsg(`Automated action for ${item.patient_name} (${item.run_id?.slice(0, 8) || ''}) undone.`);
      setTimeout(() => setActionMsg(''), 4000);
      fetchDeskData();
    } catch (err) {
      alert(`Undo failed: ${err.message}`);
    }
  };

  const openTrace = async (runId) => {
    setSelectedRunId(runId);
    setTraceLoading(true);
    try {
      const res = await fetch(`${API_BASE}/agent/runs/${runId}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setTraceData(data);
      }
    } catch (err) {
      console.error('Failed to fetch trace:', err);
    } finally {
      setTraceLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <IconClock style={{ width: '24px', height: '24px', animation: 'spin 1s linear infinite' }} />
        <div style={{ marginTop: '8px', fontSize: '13px' }}>Loading Agent Desk...</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '40px' }}>
      {/* Header Banner */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '18px 22px',
        borderRadius: '12px',
        background: 'var(--bg-card, #ffffff)',
        border: '1px solid var(--border-subtle, #e2e8f0)',
        boxShadow: '0 1px 3px rgba(0,0,0,0.04)'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{
              fontSize: '11px',
              fontWeight: 800,
              padding: '2px 8px',
              borderRadius: '6px',
              background: roleAccentSoft,
              color: roleAccent,
              textTransform: 'uppercase',
              letterSpacing: '0.04em'
            }}>
              Supervisor Workspace
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>•</span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>
              {isDoctor ? 'Physician Oversight' : 'Nurse Case Queue'}
            </span>
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
            Agent Desk
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            Agents do the routine. People make the calls. Every case arrives prepared with grounded citations.
          </p>
        </div>

        {/* Global Pause Control (Doctor only) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {deskData.global_paused ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{
                fontSize: '12px',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '8px',
                background: '#fef2f2',
                color: '#dc2626',
                border: '1px solid #fecaca'
              }}>
                🚨 All Agents Paused
              </span>
              {isDoctor && (
                <button
                  type="button"
                  onClick={() => handleGlobalPauseToggle(false)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'var(--success-green, #059669)',
                    color: '#ffffff',
                    fontWeight: 700,
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                >
                  Resume All Agents
                </button>
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{
                fontSize: '12px',
                fontWeight: 700,
                padding: '4px 10px',
                borderRadius: '8px',
                background: '#ecfdf5',
                color: '#059669',
                border: '1px solid #a7f3d0'
              }}>
                ✓ Agents Active
              </span>
              {isDoctor && (
                <button
                  type="button"
                  onClick={() => handleGlobalPauseToggle(true)}
                  style={{
                    padding: '8px 14px',
                    borderRadius: '8px',
                    border: '1px solid #fca5a5',
                    background: '#fff1f2',
                    color: '#dc2626',
                    fontWeight: 700,
                    fontSize: '12px',
                    cursor: 'pointer'
                  }}
                >
                  Pause All Agents
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {actionMsg && (
        <div style={{
          padding: '10px 16px',
          borderRadius: '8px',
          background: '#ecfdf5',
          color: '#065f46',
          fontSize: '13px',
          fontWeight: 600,
          border: '1px solid #a7f3d0'
        }}>
          {actionMsg}
        </div>
      )}

      {/* Grid: 2 Columns */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        
        {/* SECTION 1: Waiting for you (Pending Drafts) */}
        <div style={{
          background: 'var(--bg-card, #ffffff)',
          borderRadius: '12px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          padding: '18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                width: '24px',
                height: '24px',
                borderRadius: '6px',
                background: roleAccentSoft,
                color: roleAccent,
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                fontSize: '12px'
              }}>
                1
              </span>
              <h3 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                Waiting for you
              </h3>
            </div>
            <span style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '12px',
              background: deskData.waiting_for_you.length > 0 ? '#fef3c7' : '#f1f5f9',
              color: deskData.waiting_for_you.length > 0 ? '#b45309' : '#64748b'
            }}>
              {deskData.waiting_for_you.length} pending draft{deskData.waiting_for_you.length === 1 ? '' : 's'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
              Call notes, patient replies, and shift handoffs prepared by agents. Requires licensed human sign-off.
            </p>
            {/* View Mode Toggle */}
            <div style={{ display: 'flex', gap: '4px', background: '#f1f5f9', padding: '3px', borderRadius: '6px' }}>
              <button
                type="button"
                onClick={() => setReviewMode('standard')}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: 'none',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: reviewMode === 'standard' ? '#ffffff' : 'transparent',
                  color: reviewMode === 'standard' ? 'var(--text-primary)' : 'var(--text-muted)',
                  boxShadow: reviewMode === 'standard' ? '0 1px 2px rgba(0,0,0,0.05)' : 'none'
                }}
              >
                Standard View
              </button>
              <button
                type="button"
                onClick={() => {
                  setReviewMode('routine_diff');
                  fetchRoutineDrafts();
                }}
                style={{
                  padding: '4px 8px',
                  borderRadius: '4px',
                  border: 'none',
                  fontSize: '11px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  background: reviewMode === 'routine_diff' ? '#0284c7' : 'transparent',
                  color: reviewMode === 'routine_diff' ? '#ffffff' : 'var(--text-muted)',
                  boxShadow: reviewMode === 'routine_diff' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none'
                }}
              >
                ⚡ Diff &amp; Batch
              </button>
            </div>
          </div>

          {/* Phase 4: Batch Approval Bar & Shortcuts (in routine_diff mode) */}
          {reviewMode === 'routine_diff' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', padding: '10px 12px', borderRadius: '8px', background: '#f0f9ff', border: '1px solid #bae6fd' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#0369a1' }}>
                  ⌨️ Keyboard Shortcuts: <kbd style={{ background: '#ffffff', padding: '1px 5px', borderRadius: '3px', border: '1px solid #cbd5e1' }}>j</kbd>/<kbd style={{ background: '#ffffff', padding: '1px 5px', borderRadius: '3px', border: '1px solid #cbd5e1' }}>k</kbd> navigate · <kbd style={{ background: '#ffffff', padding: '1px 5px', borderRadius: '3px', border: '1px solid #cbd5e1' }}>a</kbd> approve · <kbd style={{ background: '#ffffff', padding: '1px 5px', borderRadius: '3px', border: '1px solid #cbd5e1' }}>e</kbd> edit · <kbd style={{ background: '#ffffff', padding: '1px 5px', borderRadius: '3px', border: '1px solid #cbd5e1' }}>r</kbd> reject
                </span>
                <span style={{ fontSize: '11px', color: '#0284c7' }}>
                  Batch Gate: $\ge 95\%$ agreement
                </span>
              </div>

              {/* Batch Approval Buttons for passing draft types */}
              {Object.entries(routineData.type_eligibility || {}).map(([dType, elig]) => {
                const countOfType = (routineData.drafts || []).filter(d => d.draft_type === dType).length;
                if (countOfType === 0) return null;
                return (
                  <div key={dType} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ffffff', padding: '6px 10px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px' }}>
                      <strong>{dType.replace('_', ' ')}</strong> ({countOfType} pending)
                      <span style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: elig.shadow_agreement_pct >= 95.0 ? '#dcfce7' : '#fee2e2',
                        color: elig.shadow_agreement_pct >= 95.0 ? '#15803d' : '#b91c1c'
                      }}>
                        Shadow Agreement: {elig.shadow_agreement_pct}%
                      </span>
                    </div>

                    <button
                      type="button"
                      disabled={!elig.batch_eligible || batchLoading}
                      onClick={() => handleBatchApprove(dType)}
                      title={elig.reason}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '6px',
                        border: 'none',
                        fontSize: '11px',
                        fontWeight: 700,
                        cursor: elig.batch_eligible && !batchLoading ? 'pointer' : 'not-allowed',
                        background: elig.batch_eligible ? '#0284c7' : '#cbd5e1',
                        color: '#ffffff'
                      }}
                    >
                      {batchLoading ? 'Approving...' : `Approve all passing ${dType} (${countOfType})`}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {reviewMode === 'routine_diff' ? (
              /* Routine Drafts Diff Mode View */
              (routineData.drafts || []).length === 0 ? (
                <div style={{
                  padding: '28px',
                  textAlign: 'center',
                  background: 'var(--bg-base, #f8fafc)',
                  borderRadius: '8px',
                  border: '1px dashed var(--border-subtle, #e2e8f0)',
                  color: 'var(--text-muted)'
                }}>
                  <IconCheck style={{ width: '24px', height: '24px', margin: '0 auto 6px auto', color: '#059669' }} />
                  <div style={{ fontSize: '13px', fontWeight: 600 }}>All routine drafts reviewed</div>
                  <div style={{ fontSize: '11px', marginTop: '2px' }}>No drafts awaiting signature.</div>
                </div>
              ) : (
                routineData.drafts.map((d, idx) => (
                  <div
                    key={d.draft_id}
                    onClick={() => setActiveDraftIndex(idx)}
                    style={{
                      padding: '14px',
                      borderRadius: '8px',
                      background: idx === activeDraftIndex ? '#f0fdf4' : 'var(--bg-base, #f8fafc)',
                      border: idx === activeDraftIndex ? '2px solid #16a34a' : '1px solid var(--border-subtle, #e2e8f0)',
                      boxShadow: idx === activeDraftIndex ? '0 0 0 2px rgba(22, 163, 74, 0.2)' : 'none',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      cursor: 'pointer'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        {idx === activeDraftIndex && (
                          <span style={{ fontSize: '10px', fontWeight: 800, padding: '1px 5px', borderRadius: '4px', background: '#16a34a', color: '#ffffff' }}>
                            ACTIVE [j/k/a/e/r]
                          </span>
                        )}
                        <span style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: '4px',
                          background: '#e0e7ff',
                          color: '#3730a3'
                        }}>
                          {d.draft_type.replace('_', ' ')}
                        </span>
                        <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                          {d.two_identifiers}
                        </strong>
                      </div>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{d.created_at}</span>
                    </div>

                    {/* Diff View: Agent Draft vs Template */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '11px' }}>
                      <div style={{ background: '#f8fafc', padding: '8px', borderRadius: '6px', border: '1px solid #e2e8f0' }}>
                        <div style={{ fontWeight: 700, color: '#64748b', marginBottom: '4px' }}>Standard Template Baseline</div>
                        <div style={{ color: '#475569', fontStyle: 'italic', whiteSpace: 'pre-wrap' }}>
                          {d.template_reference.slice(0, 150)}...
                        </div>
                      </div>

                      <div style={{ background: '#ffffff', padding: '8px', borderRadius: '6px', border: '1px solid #cbd5e1' }}>
                        <div style={{ fontWeight: 700, color: '#0369a1', marginBottom: '4px' }}>
                          Agent Draft ({d.diff?.edit_chars || 0} chars diff)
                        </div>
                        <div style={{ color: '#0f172a', whiteSpace: 'pre-wrap' }}>
                          {d.draft_text}
                        </div>
                      </div>
                    </div>

                    {/* Action Buttons */}
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '4px' }}>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setEditingDraftId(d.draft_id);
                          setEditText(d.draft_text);
                        }}
                        style={{
                          padding: '5px 10px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-subtle)',
                          background: '#ffffff',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer'
                        }}
                      >
                        Edit (e)
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDraftAction(d.draft_id, 'accept');
                        }}
                        style={{
                          padding: '5px 12px',
                          borderRadius: '6px',
                          border: 'none',
                          background: '#0284c7',
                          color: '#ffffff',
                          fontWeight: 700,
                          fontSize: '11px',
                          cursor: 'pointer'
                        }}
                      >
                        Sign &amp; Deliver (a)
                      </button>
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDraftAction(d.draft_id, 'reject');
                        }}
                        style={{
                          padding: '5px 8px',
                          borderRadius: '6px',
                          border: 'none',
                          background: '#fee2e2',
                          color: '#991b1b',
                          fontWeight: 700,
                          fontSize: '11px',
                          cursor: 'pointer'
                        }}
                      >
                        Reject (r)
                      </button>
                    </div>
                  </div>
                ))
              )
            ) : (
              /* Standard View */
              deskData.waiting_for_you.length === 0 ? (
                <div style={{
                  padding: '28px',
                  textAlign: 'center',
                  background: 'var(--bg-base, #f8fafc)',
                  borderRadius: '8px',
                  border: '1px dashed var(--border-subtle, #e2e8f0)',
                  color: 'var(--text-muted)'
                }}>
                  <IconCheck style={{ width: '24px', height: '24px', margin: '0 auto 6px auto', color: '#059669' }} />
                  <div style={{ fontSize: '13px', fontWeight: 600 }}>All drafts reviewed</div>
                  <div style={{ fontSize: '11px', marginTop: '2px' }}>No pending items waiting for signature.</div>
                </div>
              ) : (
                deskData.waiting_for_you.map((d) => (
                <div
                  key={d.draft_id}
                  style={{
                    padding: '14px',
                    borderRadius: '8px',
                    background: 'var(--bg-base, #f8fafc)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <span style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        background: '#e0e7ff',
                        color: '#3730a3',
                        marginRight: '6px'
                      }}>
                        {d.draft_type.replace('_', ' ')}
                      </span>
                      <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                        {d.patient_name}
                      </strong>{' '}
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>({d.patient_code})</span>
                    </div>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{d.created_at}</span>
                  </div>

                  {/* Body Preview */}
                  {editingDraftId === d.draft_id ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      <textarea
                        value={editText}
                        onChange={(e) => setEditText(e.target.value)}
                        style={{
                          width: '100%',
                          minHeight: '70px',
                          padding: '8px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-strong, #cbd5e1)',
                          fontSize: '12px',
                          fontFamily: 'var(--font-sans)'
                        }}
                      />
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                        <button
                          type="button"
                          onClick={() => setEditingDraftId(null)}
                          style={{
                            padding: '4px 10px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-subtle)',
                            background: '#ffffff',
                            fontSize: '11px',
                            cursor: 'pointer'
                          }}
                        >
                          Cancel
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDraftAction(d.draft_id, 'edit', { ...d.body, edited_text: editText })}
                          style={{
                            padding: '4px 10px',
                            borderRadius: '6px',
                            border: 'none',
                            background: roleAccent,
                            color: '#ffffff',
                            fontWeight: 700,
                            fontSize: '11px',
                            cursor: 'pointer'
                          }}
                        >
                          Save & Sign
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div style={{
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      lineHeight: '1.4',
                      background: '#ffffff',
                      padding: '8px',
                      borderRadius: '6px',
                      border: '1px solid #f1f5f9'
                    }}>
                      {d.body?.patient_reported || d.body?.reply || d.body?.situation || JSON.stringify(d.body)}
                    </div>
                  )}

                  {/* Sources Chips */}
                  {d.sources && d.sources.length > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontWeight: 600 }}>Sources:</span>
                      {d.sources.map((src, sIdx) => (
                        <span
                          key={sIdx}
                          style={{
                            fontSize: '10px',
                            padding: '1px 6px',
                            borderRadius: '4px',
                            background: '#f1f5f9',
                            color: '#475569',
                            fontFamily: 'var(--font-mono)'
                          }}
                        >
                          {src}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Action Buttons */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px' }}>
                    {d.run_id ? (
                      <button
                        type="button"
                        onClick={() => openTrace(d.run_id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          color: '#0284c7',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer',
                          padding: 0
                        }}
                      >
                        Why did the agent write this? →
                      </button>
                    ) : <span />}

                    <div style={{ display: 'flex', gap: '6px' }}>
                      <button
                        type="button"
                        onClick={() => {
                          setEditingDraftId(d.draft_id);
                          setEditText(d.body?.patient_reported || d.body?.reply || JSON.stringify(d.body));
                        }}
                        style={{
                          padding: '5px 10px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-subtle)',
                          background: '#ffffff',
                          fontSize: '11px',
                          fontWeight: 600,
                          cursor: 'pointer'
                        }}
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDraftAction(d.draft_id, 'accept')}
                        style={{
                          padding: '5px 12px',
                          borderRadius: '6px',
                          border: 'none',
                          background: roleAccent,
                          color: '#ffffff',
                          fontWeight: 700,
                          fontSize: '11px',
                          cursor: 'pointer'
                        }}
                      >
                        Sign & Deliver
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDraftAction(d.draft_id, 'reject')}
                        style={{
                          padding: '5px 8px',
                          borderRadius: '6px',
                          border: 'none',
                          background: '#fee2e2',
                          color: '#991b1b',
                          fontWeight: 700,
                          fontSize: '11px',
                          cursor: 'pointer'
                        }}
                      >
                        Reject
                      </button>
                      <button
                        type="button"
                        onClick={() => setIncidentModalRun({ runId: d.run_id || `run-draft-${d.draft_id}`, title: `${d.draft_type} for Patient #${d.patient_id}` })}
                        style={{
                          padding: '5px 8px',
                          borderRadius: '6px',
                          border: '1px solid #fca5a5',
                          background: 'transparent',
                          color: '#dc2626',
                          fontWeight: 600,
                          fontSize: '11px',
                          cursor: 'pointer'
                        }}
                        title="Report wrong or unsafe AI output"
                      >
                        ⚠️ Report wrong AI
                      </button>
                    </div>
                  </div>
                </div>
              ))
            ))}
          </div>
        </div>

        {/* SECTION 2: Done for you (Automated Actions with Undo) */}
        <div style={{
          background: 'var(--bg-card, #ffffff)',
          borderRadius: '12px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          padding: '18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                width: '24px',
                height: '24px',
                borderRadius: '6px',
                background: '#ecfdf5',
                color: '#059669',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                fontSize: '12px'
              }}>
                2
              </span>
              <h3 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                Done for you
              </h3>
            </div>
            <span style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '12px',
              background: '#ecfdf5',
              color: '#065f46'
            }}>
              {deskData.done_for_you.length} auto actions
            </span>
          </div>

          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
            Routine reminders, duplicate alert merges, and sourced answers delivered automatically within policy limits.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {deskData.done_for_you.length === 0 ? (
              <div style={{
                padding: '28px',
                textAlign: 'center',
                background: 'var(--bg-base, #f8fafc)',
                borderRadius: '8px',
                border: '1px dashed var(--border-subtle, #e2e8f0)',
                color: 'var(--text-muted)'
              }}>
                <IconClock style={{ width: '24px', height: '24px', margin: '0 auto 6px auto', color: '#64748b' }} />
                <div style={{ fontSize: '13px', fontWeight: 600 }}>No recent auto actions</div>
                <div style={{ fontSize: '11px', marginTop: '2px' }}>Automated routines will appear here as they run.</div>
              </div>
            ) : (
              deskData.done_for_you.map((item) => (
                <div
                  key={item.run_id}
                  style={{
                    padding: '12px 14px',
                    borderRadius: '8px',
                    background: 'var(--bg-base, #f8fafc)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between'
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: '#ecfdf5',
                        color: '#065f46'
                      }}>
                        AUTO
                      </span>
                      <strong style={{ fontSize: '13px', color: 'var(--text-primary)' }}>
                        {item.patient_name}
                      </strong>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>({item.patient_code})</span>
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
                      {item.trigger_type.replace(/_/g, ' ')} • {item.result_type}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{item.time}</span>
                    <button
                      type="button"
                      onClick={() => openTrace(item.run_id)}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle)',
                        background: '#ffffff',
                        fontSize: '11px',
                        fontWeight: 600,
                        cursor: 'pointer'
                      }}
                    >
                      Trace
                    </button>
                    {item.can_undo && (
                      <button
                        type="button"
                        onClick={() => handleUndo(item)}
                        style={{
                          padding: '4px 8px',
                          borderRadius: '6px',
                          border: '1px solid #fecaca',
                          background: '#fff1f2',
                          color: '#dc2626',
                          fontSize: '11px',
                          fontWeight: 700,
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px'
                        }}
                      >
                        <IconRefresh style={{ width: '12px', height: '12px' }} /> Undo
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* SECTION 3: Needs a decision (Held by Policy Guard) */}
        <div style={{
          background: 'var(--bg-card, #ffffff)',
          borderRadius: '12px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          padding: '18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                width: '24px',
                height: '24px',
                borderRadius: '6px',
                background: '#fee2e2',
                color: '#dc2626',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                fontSize: '12px'
              }}>
                3
              </span>
              <h3 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                Needs a decision
              </h3>
            </div>
            <span style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '12px',
              background: '#fee2e2',
              color: '#991b1b'
            }}>
              {deskData.needs_a_decision.length} held by guard
            </span>
          </div>

          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
            Actions held back by the deterministic Policy Guard due to missing citations, consent status, or quiet hours.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {deskData.needs_a_decision.length === 0 ? (
              <div style={{
                padding: '24px',
                textAlign: 'center',
                background: 'var(--bg-base, #f8fafc)',
                borderRadius: '8px',
                border: '1px dashed var(--border-subtle, #e2e8f0)',
                color: 'var(--text-muted)'
              }}>
                <IconCheck style={{ width: '22px', height: '22px', margin: '0 auto 4px auto', color: '#059669' }} />
                <div style={{ fontSize: '13px', fontWeight: 600 }}>Zero held actions</div>
                <div style={{ fontSize: '11px', marginTop: '2px' }}>All agent outputs successfully passed Policy Guard.</div>
              </div>
            ) : (
              deskData.needs_a_decision.map((d) => (
                <div
                  key={d.run_id}
                  style={{
                    padding: '12px 14px',
                    borderRadius: '8px',
                    background: '#fff1f2',
                    border: '1px solid #fecaca',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '6px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: '#dc2626',
                        color: '#ffffff'
                      }}>
                        HELD
                      </span>
                      <strong style={{ fontSize: '13px', color: '#991b1b' }}>{d.patient_name}</strong>
                      <span style={{ fontSize: '11px', color: '#b91c1c' }}>({d.patient_code})</span>
                    </div>
                    <span style={{ fontSize: '11px', color: '#991b1b' }}>{d.time}</span>
                  </div>

                  <div style={{ fontSize: '12px', color: '#7f1d1d' }}>
                    <strong>Guard Reason:</strong> {d.reasons.join('; ')}
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '4px' }}>
                    <button
                      type="button"
                      onClick={() => openTrace(d.run_id)}
                      style={{
                        padding: '4px 10px',
                        borderRadius: '6px',
                        border: '1px solid #f87171',
                        background: '#ffffff',
                        color: '#b91c1c',
                        fontSize: '11px',
                        fontWeight: 700,
                        cursor: 'pointer'
                      }}
                    >
                      Inspect Guard Trace →
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* SECTION 4: Work saved today (Transparent Estimation) */}
        <div style={{
          background: 'var(--bg-card, #ffffff)',
          borderRadius: '12px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          padding: '18px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{
                width: '24px',
                height: '24px',
                borderRadius: '6px',
                background: '#eff6ff',
                color: '#0284c7',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                fontSize: '12px'
              }}>
                4
              </span>
              <h3 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                Work saved today
              </h3>
            </div>
            <span style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '2px 8px',
              borderRadius: '12px',
              background: '#eff6ff',
              color: '#0369a1'
            }}>
              Transparent Measurement
            </span>
          </div>

          <div style={{
            padding: '16px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #0b1528 0%, #1e293b 100%)',
            color: '#ffffff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#94a3b8', fontWeight: 700 }}>
                Estimated Clinical Time Saved
              </div>
              <div style={{ fontSize: '28px', fontWeight: 900, marginTop: '2px', color: '#38bdf8' }}>
                ~{deskData.work_saved?.estimated_minutes_saved || 0} min
              </div>
            </div>
            <IconActivity style={{ width: '32px', height: '32px', color: '#38bdf8', opacity: 0.8 }} />
          </div>

          {/* 4 Metrics Tiles */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
            <div style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--bg-base, #f8fafc)',
              border: '1px solid var(--border-subtle, #e2e8f0)'
            }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Briefs Prepared</div>
              <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '2px' }}>
                {deskData.work_saved?.briefs_prepared_count || 0}
              </div>
            </div>
            <div style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--bg-base, #f8fafc)',
              border: '1px solid var(--border-subtle, #e2e8f0)'
            }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Drafts Accepted</div>
              <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '2px' }}>
                {deskData.work_saved?.drafts_accepted_count || 0}
              </div>
            </div>
            <div style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--bg-base, #f8fafc)',
              border: '1px solid var(--border-subtle, #e2e8f0)'
            }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Routine Auto Actions</div>
              <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '2px' }}>
                {deskData.work_saved?.automated_actions_count || 0}
              </div>
            </div>
            <div style={{
              padding: '12px',
              borderRadius: '8px',
              background: 'var(--bg-base, #f8fafc)',
              border: '1px solid var(--border-subtle, #e2e8f0)'
            }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 600 }}>Duplicates Merged</div>
              <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '2px' }}>
                {deskData.work_saved?.duplicates_merged_count || 0}
              </div>
            </div>
          </div>

          <div style={{
            fontSize: '11px',
            color: 'var(--text-muted)',
            lineHeight: '1.4',
            background: '#f8fafc',
            padding: '8px 10px',
            borderRadius: '6px',
            border: '1px dashed var(--border-subtle)'
          }}>
            <strong>Transparency Notice:</strong> {deskData.work_saved?.assumptions_label}
          </div>
        </div>
      </div>

      {/* TRACE MODAL: Why did the agent say this? */}
      {selectedRunId && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(15, 23, 42, 0.6)',
          backdropFilter: 'blur(3px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            width: '680px',
            maxHeight: '85vh',
            background: '#ffffff',
            borderRadius: '14px',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.2)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden'
          }}>
            {/* Modal Header */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: '#f8fafc'
            }}>
              <div>
                <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
                  Agent Trace: {selectedRunId}
                </h3>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  Audit log of agent planning, tool calls, and Policy Guard inspection.
                </span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedRunId(null)}
                style={{
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-muted)'
                }}
              >
                <IconX style={{ width: '20px', height: '20px' }} />
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '20px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {traceLoading ? (
                <div style={{ textAlign: 'center', padding: '30px' }}>Loading trace...</div>
              ) : traceData ? (
                <>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
                    <div style={{ padding: '10px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Agent Name</div>
                      <strong style={{ fontSize: '13px', color: '#0f172a' }}>{traceData.run?.agent_name}</strong>
                    </div>
                    <div style={{ padding: '10px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Autonomy / Mode</div>
                      <strong style={{ fontSize: '13px', color: '#0f172a' }}>
                        {traceData.run?.autonomy_level} ({traceData.run?.mode})
                      </strong>
                    </div>
                    <div style={{ padding: '10px', background: '#f8fafc', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>Execution Latency</div>
                      <strong style={{ fontSize: '13px', color: '#0f172a' }}>{traceData.run?.latency_ms} ms</strong>
                    </div>
                  </div>

                  <div>
                    <h4 style={{ fontSize: '13px', fontWeight: 800, marginBottom: '8px' }}>Execution Steps</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {traceData.steps?.map((step) => (
                        <div
                          key={step.step_id}
                          style={{
                            padding: '8px 12px',
                            borderRadius: '6px',
                            background: '#f8fafc',
                            border: '1px solid #e2e8f0',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            fontSize: '12px'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{
                              fontWeight: 800,
                              fontSize: '11px',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: '#e2e8f0'
                            }}>
                              {step.seq}. {step.step_type}
                            </span>
                            <span style={{ color: '#334155' }}>{step.summary}</span>
                          </div>
                          <span style={{ fontSize: '11px', color: '#64748b' }}>{step.ms} ms</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {traceData.run?.guard_reasons && (
                    <div style={{ padding: '10px', background: '#fff1f2', borderRadius: '8px', border: '1px solid #fecaca' }}>
                      <strong style={{ fontSize: '12px', color: '#991b1b' }}>Policy Guard Findings:</strong>
                      <div style={{ fontSize: '12px', color: '#7f1d1d', marginTop: '4px' }}>
                        {JSON.stringify(traceData.run.guard_reasons)}
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div>Trace data unavailable.</div>
              )}
            </div>

            {/* Modal Footer */}
            <div style={{
              padding: '12px 20px',
              borderTop: '1px solid #e2e8f0',
              display: 'flex',
              justifyContent: 'flex-end',
              background: '#f8fafc'
            }}>
              <button
                type="button"
                onClick={() => setSelectedRunId(null)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle)',
                  background: '#ffffff',
                  fontWeight: 600,
                  fontSize: '12px',
                  cursor: 'pointer'
                }}
              >
                Close Trace
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Incident Reporting Modal (CareLoop Agents v2 Phase 1) */}
      {incidentModalRun && (
        <ReportIncidentModal
          runId={incidentModalRun.runId}
          itemTitle={incidentModalRun.title}
          onClose={() => setIncidentModalRun(null)}
          onReported={(res) => {
            setActionMsg(`Incident reported (#${res.incident_id}). Action automatically demoted to Draft for safety.`);
            setTimeout(() => setActionMsg(''), 5000);
            fetchDeskData();
          }}
        />
      )}
    </div>
  );
}
