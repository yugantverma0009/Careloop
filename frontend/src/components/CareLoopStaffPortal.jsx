import React, { useState, useEffect } from 'react';
import {
  getTriageBoard,
  acknowledgeFlag,
  getFollowUps,
  getPatientTimeline,
  getPendingSummaries,
  generateSummary,
  reviewSummary,
  logout,
} from '../services/api';
import SwitchDemoWorkspace from './SwitchDemoWorkspace';

export default function CareLoopStaffPortal({ user }) {
  const [activeTab, setActiveTab] = useState('triage');
  const [triageItems, setTriageItems] = useState([]);
  const [followUps, setFollowUps] = useState([]);
  const [summaries, setSummaries] = useState([]);
  const [timelinePatientId, setTimelinePatientId] = useState(1);
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');

  const loadData = async () => {
    try {
      setLoading(true);
      const [tr, fu, sm] = await Promise.all([
        getTriageBoard().catch(() => []),
        getFollowUps().catch(() => []),
        getPendingSummaries().catch(() => []),
      ]);
      setTriageItems(tr || []);
      setFollowUps(fu || []);
      setSummaries(sm || []);
    } catch (err) {
      console.error('Error fetching clinical data', err);
    } finally {
      setLoading(false);
    }
  };

  const loadTimeline = async (pid) => {
    try {
      const data = await getPatientTimeline(pid);
      setTimelineEvents(data || []);
    } catch (err) {
      console.error('Error fetching timeline', err);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 12000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (activeTab === 'timeline') {
      loadTimeline(timelinePatientId);
    }
  }, [activeTab, timelinePatientId]);

  const handleAcknowledge = async (flagId) => {
    try {
      await acknowledgeFlag(flagId, 'Acknowledged by clinician in Triage Portal');
      setActionMsg(`Flag #${flagId} acknowledged.`);
      setTimeout(() => setActionMsg(''), 4000);
      await loadData();
    } catch (err) {
      alert(`Acknowledge failed: ${err.message}`);
    }
  };

  const handleGenerateSummary = async (pid) => {
    try {
      setLoading(true);
      const res = await generateSummary(pid);
      setActionMsg(`Summary draft #${res.summary_id} generated for Patient #${pid}.`);
      setTimeout(() => setActionMsg(''), 4000);
      await loadData();
    } catch (err) {
      alert(`Summary generation failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleReviewSummary = async (summaryId, action) => {
    try {
      await reviewSummary(summaryId, action, 'Clinically validated');
      setActionMsg(`Summary #${summaryId} ${action}ed.`);
      setTimeout(() => setActionMsg(''), 4000);
      await loadData();
    } catch (err) {
      alert(`Review failed: ${err.message}`);
    }
  };

  const filteredTriage = triageItems.filter((item) => {
    if (selectedSeverity === 'ALL') return true;
    return item.severity === selectedSeverity;
  });

  return (
    <div style={{
      minHeight: '100vh',
      background: '#090d16',
      color: '#f8fafc',
      fontFamily: "'Inter', sans-serif",
      paddingBottom: '40px',
    }}>
      {/* Top Navbar */}
      <header style={{
        background: 'rgba(15, 23, 42, 0.9)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid #1e293b',
        padding: '16px 28px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <img
            src="/careloop_logo.jpg"
            alt="CareLoop"
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '10px',
              objectFit: 'cover',
              boxShadow: '0 4px 14px rgba(14, 165, 233, 0.35)',
              border: '1px solid rgba(56, 189, 248, 0.4)',
            }}
          />
          <div>
            <div style={{ fontWeight: 800, fontSize: '18px', color: '#f8fafc', letterSpacing: '-0.02em' }}>
              Care<span style={{ color: '#2dd4bf' }}>Loop</span> Clinical Hub
            </div>
            <div style={{ fontSize: '11px', color: '#94a3b8' }}>
              "The LLM talks. Rules decide. Humans act."
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Switch Demo Workspace Component */}
          <SwitchDemoWorkspace currentUser={user} />

          <button
            onClick={logout}
            style={{
              padding: '7px 12px',
              borderRadius: '8px',
              border: '1px solid #475569',
              background: '#1e293b',
              color: '#94a3b8',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
            }}
            title="Sign Out"
          >
            <span>🚪</span> Sign Out
          </button>
        </div>
      </header>

      {/* Main Container */}
      <main style={{ maxWidth: '1340px', margin: '24px auto', padding: '0 24px' }}>
        {actionMsg && (
          <div style={{
            background: '#065f46',
            color: '#34d399',
            padding: '12px 18px',
            borderRadius: '10px',
            fontSize: '13px',
            fontWeight: 600,
            marginBottom: '20px',
            border: '1px solid #059669',
          }}>
            ✓ {actionMsg}
          </div>
        )}

        {/* Tab Switcher */}
        <div style={{
          display: 'flex',
          gap: '8px',
          borderBottom: '1px solid #1e293b',
          marginBottom: '24px',
          paddingBottom: '2px',
        }}>
          {[
            { id: 'triage', label: `🚨 Triage Board (${triageItems.length})` },
            { id: 'timeline', label: '📈 Patient Timeline' },
            { id: 'tasks', label: `📋 Follow-up Tasks (${followUps.length})` },
            { id: 'summaries', label: `📑 AI Draft Summaries (${summaries.length})` },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                padding: '10px 18px',
                borderRadius: '8px 8px 0 0',
                border: 'none',
                background: activeTab === tab.id ? '#1e293b' : 'transparent',
                color: activeTab === tab.id ? '#2dd4bf' : '#94a3b8',
                fontWeight: activeTab === tab.id ? 700 : 500,
                fontSize: '14px',
                cursor: 'pointer',
                borderBottom: activeTab === tab.id ? '2px solid #2dd4bf' : 'none',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* TAB 1: TRIAGE BOARD */}
        {activeTab === 'triage' && (
          <div style={{ background: '#131b2e', borderRadius: '16px', border: '1px solid #1e293b', padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 4px 0', color: '#f8fafc' }}>
                  Live Clinical Triage Board
                </h2>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                  Single source of truth: <code>v_triage_board</code> view with priority scoring & transparent reasons
                </p>
              </div>

              {/* Severity filter */}
              <div style={{ display: 'flex', gap: '8px' }}>
                {['ALL', 'Urgent_Review', 'Review_Soon'].map((sev) => (
                  <button
                    key={sev}
                    onClick={() => setSelectedSeverity(sev)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #334155',
                      background: selectedSeverity === sev ? '#0d9488' : '#0f172a',
                      color: '#f8fafc',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {sev === 'ALL' ? 'All Alerts' : sev.replace('_', ' ')}
                  </button>
                ))}
              </div>
            </div>

            {filteredTriage.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8', fontSize: '14px' }}>
                No active clinical alerts matching criteria.
              </div>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #334155', color: '#94a3b8', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      <th style={{ padding: '12px 14px' }}>Severity</th>
                      <th style={{ padding: '12px 14px' }}>Score</th>
                      <th style={{ padding: '12px 14px' }}>Patient</th>
                      <th style={{ padding: '12px 14px' }}>Reason (Rule-based)</th>
                      <th style={{ padding: '12px 14px' }}>Status</th>
                      <th style={{ padding: '12px 14px' }}>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredTriage.map((item) => (
                      <tr key={item.flag_id} style={{ borderBottom: '1px solid #1e293b' }}>
                        <td style={{ padding: '14px' }}>
                          <span style={{
                            padding: '4px 8px',
                            borderRadius: '4px',
                            fontSize: '11px',
                            fontWeight: 700,
                            background: item.severity === 'Urgent_Review' ? 'rgba(239, 68, 68, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                            color: item.severity === 'Urgent_Review' ? '#f87171' : '#fbbf24',
                            border: item.severity === 'Urgent_Review' ? '1px solid rgba(239, 68, 68, 0.4)' : '1px solid rgba(245, 158, 11, 0.4)',
                          }}>
                            {item.severity.replace('_', ' ')}
                          </span>
                        </td>
                        <td style={{ padding: '14px', fontWeight: 800, color: '#38bdf8' }}>
                          {item.priority_score}
                        </td>
                        <td style={{ padding: '14px', fontWeight: 600, color: '#f1f5f9' }}>
                          {item.patient_name} <span style={{ color: '#64748b', fontSize: '11px' }}>(#{item.patient_id})</span>
                        </td>
                        <td style={{ padding: '14px', color: '#cbd5e1', maxWidth: '400px' }}>
                          {item.reason}
                        </td>
                        <td style={{ padding: '14px' }}>
                          <span style={{
                            fontSize: '11px',
                            fontWeight: 600,
                            color: item.flag_status === 'Open' ? '#f87171' : '#34d399',
                          }}>
                            ● {item.flag_status}
                          </span>
                        </td>
                        <td style={{ padding: '14px' }}>
                          {item.flag_status === 'Open' ? (
                            <button
                              onClick={() => handleAcknowledge(item.flag_id)}
                              style={{
                                padding: '6px 12px',
                                borderRadius: '6px',
                                border: 'none',
                                background: '#0d9488',
                                color: '#fff',
                                fontWeight: 700,
                                fontSize: '11px',
                                cursor: 'pointer',
                              }}
                            >
                              ✓ Acknowledge
                            </button>
                          ) : (
                            <span style={{ color: '#64748b', fontSize: '11px' }}>Acknowledged</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: PATIENT TIMELINE */}
        {activeTab === 'timeline' && (
          <div style={{ background: '#131b2e', borderRadius: '16px', border: '1px solid #1e293b', padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 4px 0', color: '#f8fafc' }}>
                  Unified Clinical Timeline
                </h2>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                  Chronological integration from <code>v_patient_timeline</code> view
                </p>
              </div>

              {/* Patient Selector */}
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <span style={{ fontSize: '12px', color: '#94a3b8' }}>Patient:</span>
                {[
                  { id: 1, name: 'Aarav (#1)' },
                  { id: 2, name: 'Meera (#2)' },
                  { id: 3, name: 'Kabir (#3)' },
                ].map((p) => (
                  <button
                    key={p.id}
                    onClick={() => setTimelinePatientId(p.id)}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid #334155',
                      background: timelinePatientId === p.id ? '#0d9488' : '#0f172a',
                      color: '#f8fafc',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {p.name}
                  </button>
                ))}
              </div>
            </div>

            {timelineEvents.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
                No timeline events found for this patient.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {timelineEvents.map((ev, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: '14px',
                      background: '#0f172a',
                      padding: '12px 16px',
                      borderRadius: '10px',
                      border: '1px solid #1e293b',
                    }}
                  >
                    <span style={{
                      padding: '4px 8px',
                      borderRadius: '4px',
                      fontSize: '10px',
                      fontWeight: 700,
                      background:
                        ev.event_type === 'Flag' ? 'rgba(239, 68, 68, 0.2)' :
                        ev.event_type === 'Reading' ? 'rgba(56, 189, 248, 0.2)' :
                        ev.event_type === 'Symptom' ? 'rgba(251, 191, 36, 0.2)' : 'rgba(52, 211, 153, 0.2)',
                      color:
                        ev.event_type === 'Flag' ? '#f87171' :
                        ev.event_type === 'Reading' ? '#38bdf8' :
                        ev.event_type === 'Symptom' ? '#fbbf24' : '#34d399',
                    }}>
                      {ev.event_type}
                    </span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '13px', color: '#f1f5f9' }}>{ev.summary}</div>
                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                        {new Date(ev.event_time).toLocaleString()}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: FOLLOW-UP TASKS */}
        {activeTab === 'tasks' && (
          <div style={{ background: '#131b2e', borderRadius: '16px', border: '1px solid #1e293b', padding: '24px' }}>
            <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 16px 0', color: '#f8fafc' }}>
              Pending Follow-up Tasks (<code>v_pending_followups</code>)
            </h2>

            {followUps.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
                No pending follow-up tasks.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {followUps.map((t) => (
                  <div
                    key={t.followup_id}
                    style={{
                      background: '#0f172a',
                      borderRadius: '12px',
                      padding: '16px',
                      border: '1px solid #1e293b',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                    }}
                  >
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '14px', color: '#f8fafc' }}>
                        Task #{t.followup_id} • Patient: {t.patient_name} <span style={{ color: '#64748b' }}>(#{t.patient_id})</span>
                      </div>
                      <div style={{ fontSize: '13px', color: '#cbd5e1', marginTop: '4px' }}>
                        {t.reason}
                      </div>
                      <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '6px' }}>
                        Assigned to: <strong>{t.assigned_to}</strong> • Created: {new Date(t.created_at).toLocaleDateString()}
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
                      <span style={{
                        padding: '3px 8px',
                        borderRadius: '4px',
                        fontSize: '11px',
                        fontWeight: 700,
                        background: t.priority === 'Urgent_Review' ? '#991b1b' : '#1e3a8a',
                        color: t.priority === 'Urgent_Review' ? '#fca5a5' : '#93c5fd',
                      }}>
                        {t.priority}
                      </span>
                      <span style={{ fontSize: '11px', color: '#fbbf24', fontWeight: 600 }}>
                        ⏳ {t.hours_pending}h pending
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* TAB 4: AI DRAFT SUMMARIES */}
        {activeTab === 'summaries' && (
          <div style={{ background: '#131b2e', borderRadius: '16px', border: '1px solid #1e293b', padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <div>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 4px 0', color: '#f8fafc' }}>
                  AI Draft Summaries (Awaiting Clinician Review)
                </h2>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                  Generated from <code>sp_daily_report</code> • Factual note only, no interpretation or advice
                </p>
              </div>

              {/* Generate Draft Button */}
              <button
                onClick={() => handleGenerateSummary(2)}
                disabled={loading}
                style={{
                  padding: '9px 16px',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'linear-gradient(135deg, #0d9488, #0284c7)',
                  color: '#fff',
                  fontSize: '12px',
                  fontWeight: 700,
                  cursor: loading ? 'not-allowed' : 'pointer',
                }}
              >
                + Draft Summary for Meera (#2)
              </button>
            </div>

            {summaries.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px 0', color: '#94a3b8' }}>
                No draft summaries waiting for clinician review.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {summaries.map((s) => (
                  <div
                    key={s.summary_id}
                    style={{
                      background: '#0f172a',
                      borderRadius: '12px',
                      padding: '20px',
                      border: '1px solid #334155',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                      <div style={{ fontWeight: 800, fontSize: '15px', color: '#f8fafc' }}>
                        Draft #{s.summary_id} • Patient: {s.patient_name} <span style={{ color: '#64748b' }}>(#{s.patient_id})</span>
                      </div>
                      <span style={{
                        background: '#eab308',
                        color: '#000',
                        fontSize: '11px',
                        fontWeight: 800,
                        padding: '3px 10px',
                        borderRadius: '6px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.05em',
                      }}>
                        AI draft, not reviewed
                      </span>
                    </div>

                    <div style={{
                      background: '#1e293b',
                      borderRadius: '8px',
                      padding: '14px',
                      fontSize: '13px',
                      lineHeight: '1.6',
                      color: '#cbd5e1',
                      borderLeft: '4px solid #38bdf8',
                      marginBottom: '14px',
                    }}>
                      {s.summary_text}
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ fontSize: '11px', color: '#64748b' }}>
                        Model: {s.model_name || 'Gemini'} • Period: {s.period_start?.slice(0, 10)}
                      </div>

                      <div style={{ display: 'flex', gap: '10px' }}>
                        <button
                          onClick={() => handleReviewSummary(s.summary_id, 'Approve')}
                          style={{
                            padding: '8px 16px',
                            borderRadius: '8px',
                            border: 'none',
                            background: '#0d9488',
                            color: '#fff',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          ✓ Approve Summary
                        </button>
                        <button
                          onClick={() => handleReviewSummary(s.summary_id, 'Reject')}
                          style={{
                            padding: '8px 16px',
                            borderRadius: '8px',
                            border: '1px solid #ef4444',
                            background: 'transparent',
                            color: '#ef4444',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
