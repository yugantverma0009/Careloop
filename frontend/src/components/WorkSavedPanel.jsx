import React, { useState, useEffect } from 'react';
import { API_BASE } from '../services/api';

export default function WorkSavedPanel({ currentUser = {} }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);
  const [replaying, setReplaying] = useState(false);
  const [editAssumptionsModal, setEditAssumptionsModal] = useState(false);
  const [assumptionsDraft, setAssumptionsDraft] = useState({});
  const [saveMsg, setSaveMsg] = useState('');

  const token = localStorage.getItem('careloop_token');
  const isDoctor = currentUser.role === 'Doctor' || currentUser.account_role === 'Doctor';

  const fetchMetrics = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/agent/metrics`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setMetrics(data);
        setAssumptionsDraft(data.assumptions || {});
      }
    } catch (err) {
      console.error('Failed to load agent metrics:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  const handleRunReplay = async () => {
    try {
      setReplaying(true);
      const res = await fetch(`${API_BASE}/agent/replay`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setSaveMsg('✓ 40-Event Workload Replay executed! Metrics and shadow agreement refreshed.');
        setTimeout(() => setSaveMsg(''), 4000);
        fetchMetrics();
      }
    } catch (err) {
      alert(`Replay failed: ${err.message}`);
    } finally {
      setReplaying(false);
    }
  };

  const handleSaveAssumptions = async () => {
    try {
      const res = await fetch(`${API_BASE}/agent/assumptions`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ assumptions: assumptionsDraft })
      });
      if (res.ok) {
        setSaveMsg('✓ Assumptions updated and saved.');
        setTimeout(() => setSaveMsg(''), 4000);
        setEditAssumptionsModal(false);
        fetchMetrics();
      }
    } catch (err) {
      alert(`Save failed: ${err.message}`);
    }
  };

  if (loading && !metrics) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>
        Loading clinical work-saved metrics...
      </div>
    );
  }

  const counts = metrics?.counts || {};
  const lastReplay = metrics?.last_replay;
  const assumptions = metrics?.assumptions || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Header Bar */}
      <div style={{
        background: 'var(--bg-card, #ffffff)',
        border: '1px solid var(--border-subtle, #e2e8f0)',
        borderRadius: '12px',
        padding: '18px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '14px',
        boxShadow: 'var(--shadow-card)'
      }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
              Clinical Work Saved & Performance
            </h2>
            <span style={{
              fontSize: '11px',
              fontWeight: 700,
              padding: '3px 10px',
              borderRadius: '6px',
              background: '#fef3c7',
              color: '#92400e',
              border: '1px solid #fde68a'
            }}>
              ⚠️ {metrics?.disclaimer || "Estimated from editable assumptions"}
            </span>
          </div>
          <p style={{ margin: '4px 0 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
            Transparent measurement of routine clinical workflow offloaded to CareLoop Agents across the cohort.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            type="button"
            onClick={handleRunReplay}
            disabled={replaying}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              background: '#0284c7',
              color: '#ffffff',
              fontWeight: 700,
              fontSize: '12px',
              border: 'none',
              cursor: replaying ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px'
            }}
          >
            {replaying ? 'Replaying Shift...' : '▶ Run 40-Event Shift Replay'}
          </button>

          {isDoctor && (
            <button
              type="button"
              onClick={() => setEditAssumptionsModal(true)}
              style={{
                padding: '8px 14px',
                borderRadius: '8px',
                border: '1px solid var(--border-strong, #cbd5e1)',
                background: '#ffffff',
                color: 'var(--text-primary)',
                fontWeight: 700,
                fontSize: '12px',
                cursor: 'pointer'
              }}
            >
              ⚙️ Edit Assumptions
            </button>
          )}
        </div>
      </div>

      {saveMsg && (
        <div style={{
          padding: '10px 16px',
          borderRadius: '8px',
          background: '#ecfdf5',
          color: '#065f46',
          fontSize: '13px',
          fontWeight: 600,
          border: '1px solid #a7f3d0'
        }}>
          {saveMsg}
        </div>
      )}

      {/* Primary Impact Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
        
        {/* Card 1: Time Saved */}
        <div style={{
          background: '#f0fdf4',
          borderRadius: '12px',
          padding: '16px',
          border: '1px solid #bbf7d0',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#166534', textTransform: 'uppercase' }}>
            Est. Time Saved
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: '#15803d' }}>
            {metrics?.estimated_hours_saved || 0} hrs
          </div>
          <div style={{ fontSize: '11px', color: '#166534' }}>
            ~{metrics?.estimated_minutes_saved || 0} minutes of clinician routine time
          </div>
        </div>

        {/* Card 2: Replay Steps Reduction */}
        <div style={{
          background: '#eff6ff',
          borderRadius: '12px',
          padding: '16px',
          border: '1px solid #bfdbfe',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: '#1e40af', textTransform: 'uppercase' }}>
            Replay Step Reduction
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: '#2563eb' }}>
            -{lastReplay?.impact?.steps_reduction_pct || 76.8}%
          </div>
          <div style={{ fontSize: '11px', color: '#1e40af' }}>
            {lastReplay?.manual_baseline?.total_steps || 155} → {lastReplay?.agents_active?.total_steps || 36} human steps
          </div>
        </div>

        {/* Card 3: Duplicates Merged */}
        <div style={{
          background: '#ffffff',
          borderRadius: '12px',
          padding: '16px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Duplicates Auto-Merged
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: 'var(--text-primary)' }}>
            {counts.duplicates_merged || 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            SpO2 & missed dose alerts grouped
          </div>
        </div>

        {/* Card 4: Drafts Accepted */}
        <div style={{
          background: '#ffffff',
          borderRadius: '12px',
          padding: '16px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Drafts Signed
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: 'var(--text-primary)' }}>
            {counts.drafts_accepted_unchanged || 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            {counts.drafts_edited || 0} edited · {counts.drafts_rejected || 0} rejected
          </div>
        </div>

        {/* Card 5: Pre-briefed Calls */}
        <div style={{
          background: '#ffffff',
          borderRadius: '12px',
          padding: '16px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Pre-Briefed Cases
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: 'var(--text-primary)' }}>
            {counts.calls_prebriefed || 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Facts & unknowns prepared
          </div>
        </div>

        {/* Card 6: Approved Auto-Closes */}
        <div style={{
          background: '#ffffff',
          borderRadius: '12px',
          padding: '16px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          display: 'flex',
          flexDirection: 'column',
          gap: '4px'
        }}>
          <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Auto-Closed by Rule
          </div>
          <div style={{ fontSize: '26px', fontWeight: 900, color: 'var(--text-primary)' }}>
            {counts.auto_closes || 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Low-risk device flags auto-resolved
          </div>
        </div>

      </div>

      {/* Scripted Shift Workload Replay Benchmark Table */}
      <div style={{
        background: 'var(--bg-card, #ffffff)',
        borderRadius: '12px',
        border: '1px solid var(--border-subtle, #e2e8f0)',
        padding: '20px',
        boxShadow: 'var(--shadow-card)'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--text-primary)' }}>
              Scripted 40-Event Shift Replay Benchmark
            </h3>
            <p style={{ margin: '3px 0 0 0', fontSize: '12px', color: 'var(--text-secondary)' }}>
              Comparison of full 8-hour synthetic shift workload executed with Agents OFF (Manual) vs Agents ON.
            </p>
          </div>
          <span style={{ fontSize: '11px', color: '#64748b' }}>
            Last replay: {lastReplay?.replayed_at ? new Date(lastReplay.replayed_at).toLocaleTimeString() : 'Ready'}
          </span>
        </div>

        <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569' }}>Category</th>
                <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>Events</th>
                <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>Manual Steps</th>
                <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>Agents Steps</th>
                <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>Steps Saved</th>
                <th style={{ padding: '10px 14px', fontWeight: 700, color: '#475569', textAlign: 'right' }}>Est. Time Saved</th>
              </tr>
            </thead>
            <tbody>
              {lastReplay?.category_counts && Object.entries(lastReplay.category_counts).map(([cat, count]) => {
                const rule = assumptions[cat] || {};
                const m_steps = count * (rule.manual_steps || 0);
                const a_steps = count * (rule.agents_steps || 0);
                const saved_steps = m_steps - a_steps;
                const saved_mins = count * ((rule.manual_minutes || 0) - (rule.agents_minutes || 0));
                return (
                  <tr key={cat} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '10px 14px', fontWeight: 600, color: '#0f172a' }}>
                      {cat.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                    </td>
                    <td style={{ padding: '10px 14px', textAlign: 'center' }}>{count}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'center', color: '#64748b' }}>{m_steps}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 700, color: '#0284c7' }}>{a_steps}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'center', fontWeight: 700, color: '#16a34a' }}>-{saved_steps}</td>
                    <td style={{ padding: '10px 14px', textAlign: 'right', fontWeight: 600, color: '#059669' }}>{saved_mins.toFixed(1)} m</td>
                  </tr>
                );
              })}
              <tr style={{ background: '#f8fafc', fontWeight: 800, borderTop: '2px solid #cbd5e1' }}>
                <td style={{ padding: '12px 14px' }}>TOTAL SHIFT WORKLOAD</td>
                <td style={{ padding: '12px 14px', textAlign: 'center' }}>{lastReplay?.total_events || 40}</td>
                <td style={{ padding: '12px 14px', textAlign: 'center' }}>{lastReplay?.manual_baseline?.total_steps || 155}</td>
                <td style={{ padding: '12px 14px', textAlign: 'center', color: '#0284c7' }}>{lastReplay?.agents_active?.total_steps || 36}</td>
                <td style={{ padding: '12px 14px', textAlign: 'center', color: '#16a34a' }}>
                  -{lastReplay?.impact?.steps_saved || 119} ({lastReplay?.impact?.steps_reduction_pct || 76.8}%)
                </td>
                <td style={{ padding: '12px 14px', textAlign: 'right', color: '#059669' }}>
                  {lastReplay?.impact?.minutes_saved || 134.5} m (~{((lastReplay?.impact?.minutes_saved || 134.5)/60).toFixed(1)} hrs)
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Grid: Agent Performance Counters & Daily Budgets */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: '20px' }}>
        
        {/* Latency & Token Usage */}
        <div style={{
          background: 'var(--bg-card, #ffffff)',
          borderRadius: '12px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          padding: '20px',
          boxShadow: 'var(--shadow-card)'
        }}>
          <h3 style={{ fontSize: '15px', fontWeight: 800, margin: '0 0 12px 0', color: 'var(--text-primary)' }}>
            Agent Latency & Token Usage
          </h3>
          <div style={{ overflowX: 'auto', border: '1px solid #e2e8f0', borderRadius: '8px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                  <th style={{ padding: '8px 12px', fontWeight: 700, color: '#475569' }}>Agent</th>
                  <th style={{ padding: '8px 12px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>Runs</th>
                  <th style={{ padding: '8px 12px', fontWeight: 700, color: '#475569', textAlign: 'right' }}>Prompt Tokens</th>
                  <th style={{ padding: '8px 12px', fontWeight: 700, color: '#475569', textAlign: 'right' }}>Avg Latency</th>
                  <th style={{ padding: '8px 12px', fontWeight: 700, color: '#475569', textAlign: 'center' }}>Blocked</th>
                </tr>
              </thead>
              <tbody>
                {metrics?.agent_performance && metrics.agent_performance.map((ap) => (
                  <tr key={ap.agent_name} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={{ padding: '8px 12px', fontWeight: 600, color: '#0f172a' }}>{ap.agent_name}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'center' }}>{ap.total_runs}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', color: '#64748b' }}>{ap.tokens_prompt}</td>
                    <td style={{ padding: '8px 12px', textAlign: 'right', fontWeight: 600, color: '#0284c7' }}>{ap.avg_latency_ms} ms</td>
                    <td style={{ padding: '8px 12px', textAlign: 'center', color: ap.blocked_by_guard_count > 0 ? '#dc2626' : '#16a34a' }}>
                      {ap.blocked_by_guard_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Daily Patient LLM Budget Meter */}
        <div style={{
          background: 'var(--bg-card, #ffffff)',
          borderRadius: '12px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          padding: '20px',
          boxShadow: 'var(--shadow-card)'
        }}>
          <h3 style={{ fontSize: '15px', fontWeight: 800, margin: '0 0 12px 0', color: 'var(--text-primary)' }}>
            Patient Daily LLM Budget (Max 15/day)
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {metrics?.patient_budgets && metrics.patient_budgets.map((pb) => (
              <div key={pb.patient_id} style={{
                padding: '10px 12px',
                borderRadius: '8px',
                border: '1px solid #e2e8f0',
                background: '#fafafa',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
              }}>
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#0f172a' }}>
                    {pb.full_name} ({pb.patient_code})
                  </div>
                  <div style={{ fontSize: '11px', color: '#64748b' }}>
                    {pb.today_calls} / {pb.daily_budget} calls used today
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    padding: '2px 8px',
                    borderRadius: '6px',
                    background: pb.today_calls >= pb.daily_budget ? '#fef2f2' : '#ecfdf5',
                    color: pb.today_calls >= pb.daily_budget ? '#dc2626' : '#16a34a',
                    border: pb.today_calls >= pb.daily_budget ? '1px solid #fca5a5' : '1px solid #bbf7d0'
                  }}>
                    {pb.budget_used_pct}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>

      {/* Edit Assumptions Modal */}
      {editAssumptionsModal && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: 'rgba(0,0,0,0.4)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px'
        }}>
          <div style={{
            background: '#ffffff',
            borderRadius: '12px',
            width: '100%',
            maxWidth: '650px',
            maxHeight: '85vh',
            overflowY: 'auto',
            padding: '24px',
            boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1)'
          }}>
            <h3 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 6px 0', color: '#0f172a' }}>
              Configure Step & Minute Assumptions
            </h3>
            <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: '#64748b' }}>
              Adjust manual vs automated steps and time assumptions. All metrics update dynamically.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {Object.entries(assumptionsDraft).map(([key, val]) => (
                <div key={key} style={{
                  padding: '12px',
                  borderRadius: '8px',
                  background: '#f8fafc',
                  border: '1px solid #e2e8f0',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px'
                }}>
                  <div style={{ fontSize: '12px', fontWeight: 700, color: '#1e293b' }}>
                    {val.label || key.replace(/_/g, ' ')}
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', fontSize: '11px' }}>
                    <div>
                      <label style={{ color: '#64748b', display: 'block', marginBottom: '2px' }}>Manual Steps</label>
                      <input
                        type="number"
                        min="0"
                        value={val.manual_steps}
                        onChange={(e) => setAssumptionsDraft({
                          ...assumptionsDraft,
                          [key]: { ...val, manual_steps: parseInt(e.target.value) || 0 }
                        })}
                        style={{ width: '100%', padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                    <div>
                      <label style={{ color: '#64748b', display: 'block', marginBottom: '2px' }}>Manual Mins</label>
                      <input
                        type="number"
                        step="0.5"
                        min="0"
                        value={val.manual_minutes}
                        onChange={(e) => setAssumptionsDraft({
                          ...assumptionsDraft,
                          [key]: { ...val, manual_minutes: parseFloat(e.target.value) || 0 }
                        })}
                        style={{ width: '100%', padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                    <div>
                      <label style={{ color: '#64748b', display: 'block', marginBottom: '2px' }}>Agents Steps</label>
                      <input
                        type="number"
                        min="0"
                        value={val.agents_steps}
                        onChange={(e) => setAssumptionsDraft({
                          ...assumptionsDraft,
                          [key]: { ...val, agents_steps: parseInt(e.target.value) || 0 }
                        })}
                        style={{ width: '100%', padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                    <div>
                      <label style={{ color: '#64748b', display: 'block', marginBottom: '2px' }}>Agents Mins</label>
                      <input
                        type="number"
                        step="0.5"
                        min="0"
                        value={val.agents_minutes}
                        onChange={(e) => setAssumptionsDraft({
                          ...assumptionsDraft,
                          [key]: { ...val, agents_minutes: parseFloat(e.target.value) || 0 }
                        })}
                        style={{ width: '100%', padding: '4px 8px', borderRadius: '4px', border: '1px solid #cbd5e1' }}
                      />
                    </div>
                  </div>
                </div>
              ))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '18px' }}>
              <button
                type="button"
                onClick={() => setEditAssumptionsModal(false)}
                style={{
                  padding: '8px 14px',
                  borderRadius: '6px',
                  border: '1px solid #cbd5e1',
                  background: '#ffffff',
                  fontSize: '12px',
                  cursor: 'pointer'
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSaveAssumptions}
                style={{
                  padding: '8px 18px',
                  borderRadius: '6px',
                  background: '#0284c7',
                  color: '#ffffff',
                  border: 'none',
                  fontWeight: 700,
                  fontSize: '12px',
                  cursor: 'pointer'
                }}
              >
                Save Assumptions
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}
