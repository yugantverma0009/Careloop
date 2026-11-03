import React, { useState, useEffect } from 'react';
import {
  getAgentHealth,
  getCandidateTests,
  approveCandidateTest,
  rejectCandidateTest,
  getCircuitBreakerDemotions,
} from '../services/api';
import {
  IconActivity,
  IconShieldCheck,
  IconAlertTriangle,
  IconClock,
  IconFileText,
} from './Icons';

export default function AgentHealthView({ user }) {
  const [windowTime, setWindowTime] = useState('24h');
  const [healthData, setHealthData] = useState(null);
  const [candidateTests, setCandidateTests] = useState([]);
  const [demotions, setDemotions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState('');

  const isDoctor = user?.role === 'Doctor';

  const loadHealthData = async () => {
    setLoading(true);
    try {
      const [h, c, d] = await Promise.all([
        getAgentHealth(windowTime).catch(() => null),
        isDoctor ? getCandidateTests().catch(() => []) : Promise.resolve([]),
        getCircuitBreakerDemotions().catch(() => []),
      ]);
      setHealthData(h);
      setCandidateTests(c || []);
      setDemotions(d || []);
    } catch (err) {
      console.error('Failed to load agent health data', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealthData();
  }, [windowTime]);

  const handleReviewCandidate = async (candidateId, approve) => {
    try {
      if (approve) {
        await approveCandidateTest(candidateId);
        setActionMsg(`Candidate test #${candidateId} approved into regression suite.`);
      } else {
        await rejectCandidateTest(candidateId);
        setActionMsg(`Candidate test #${candidateId} rejected.`);
      }
      setTimeout(() => setActionMsg(''), 4000);
      loadHealthData();
    } catch (err) {
      alert(`Review failed: ${err.message}`);
    }
  };

  if (loading && !healthData) {
    return (
      <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-secondary)' }}>
        Loading agent health and safety telemetry...
      </div>
    );
  }

  const summary = healthData?.summary || {};
  const nurseSummary = healthData?.nurse_summary || {};
  const byAgent = healthData?.by_agent || [];
  const byAction = healthData?.by_action || [];
  const incidents = healthData?.incidents || [];

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '24px 16px' }}>
      {/* Header & Window Toggle */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '20px',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
              Agent Health & Telemetry
            </h2>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '3px 8px',
                borderRadius: '12px',
                backgroundColor: 'rgba(13, 148, 136, 0.1)',
                color: 'var(--teal-primary, #0d9488)',
              }}
            >
              Live Health Guard
            </span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            {isDoctor
              ? 'Real-time agent safety, latency percentiles, token burn, shadow agreement, and circuit breaker telemetry.'
              : 'Read-only clinical agent system status and safety monitor summary.'}
          </p>
        </div>

        {/* 24h / 7d Time Window Toggle */}
        <div
          style={{
            display: 'flex',
            backgroundColor: 'var(--bg-card, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '8px',
            padding: '3px',
          }}
        >
          <button
            type="button"
            onClick={() => setWindowTime('24h')}
            style={{
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: windowTime === '24h' ? 700 : 500,
              borderRadius: '6px',
              border: 'none',
              backgroundColor: windowTime === '24h' ? 'var(--teal-primary, #0d9488)' : 'transparent',
              color: windowTime === '24h' ? '#ffffff' : 'var(--text-secondary)',
              cursor: 'pointer',
            }}
          >
            Last 24 Hours
          </button>
          <button
            type="button"
            onClick={() => setWindowTime('7d')}
            style={{
              padding: '6px 14px',
              fontSize: '12px',
              fontWeight: windowTime === '7d' ? 700 : 500,
              borderRadius: '6px',
              border: 'none',
              backgroundColor: windowTime === '7d' ? 'var(--teal-primary, #0d9488)' : 'transparent',
              color: windowTime === '7d' ? '#ffffff' : 'var(--text-secondary)',
              cursor: 'pointer',
            }}
          >
            Last 7 Days
          </button>
        </div>
      </div>

      {actionMsg && (
        <div
          style={{
            padding: '10px 16px',
            backgroundColor: 'rgba(13, 148, 136, 0.1)',
            border: '1px solid var(--teal-primary, #0d9488)',
            borderRadius: '8px',
            color: 'var(--teal-primary, #0d9488)',
            fontSize: '13px',
            fontWeight: 600,
            marginBottom: '16px',
          }}
        >
          ✓ {actionMsg}
        </div>
      )}

      {/* Circuit Breaker Demotions Banner */}
      {demotions.length > 0 && (
        <div
          style={{
            padding: '14px 18px',
            backgroundColor: 'rgba(220, 38, 38, 0.08)',
            border: '1px solid #dc2626',
            borderRadius: '10px',
            marginBottom: '20px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#dc2626', fontWeight: 700, fontSize: '14px' }}>
            <IconAlertTriangle width={18} height={18} />
            <span>Circuit Breaker Active: Safety Auto-Demotions Triggered</span>
          </div>
          <div style={{ marginTop: '8px', fontSize: '13px', color: 'var(--text-primary)' }}>
            {demotions.map((d, i) => (
              <div key={i} style={{ marginTop: '4px' }}>
                • <strong>{d.action_type}</strong> was automatically demoted to <strong>Draft</strong>. Reason: {d.reason} ({d.timestamp})
              </div>
            ))}
          </div>
        </div>
      )}

      {/* NURSE READ-ONLY SUMMARY (If Nurse) */}
      {!isDoctor ? (
        <div
          style={{
            backgroundColor: 'var(--bg-card, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '12px',
            padding: '24px',
            marginBottom: '24px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
            <div
              style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                backgroundColor: nurseSummary.system_status === 'Healthy' ? '#059669' : '#d97706',
              }}
            />
            <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              Nurse Operational Summary ({windowTime})
            </h3>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
            <div style={{ padding: '16px', background: 'var(--bg-base, #f8fafc)', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>System Status</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: '#059669', marginTop: '4px' }}>
                {nurseSummary.system_status || 'Healthy'}
              </div>
            </div>
            <div style={{ padding: '16px', background: 'var(--bg-base, #f8fafc)', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Total Agent Runs</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '4px' }}>
                {nurseSummary.total_runs || 0}
              </div>
            </div>
            <div style={{ padding: '16px', background: 'var(--bg-base, #f8fafc)', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Guard Safety Interventions</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--teal-primary, #0d9488)', marginTop: '4px' }}>
                {nurseSummary.blocked_by_guard || 0}
              </div>
            </div>
            <div style={{ padding: '16px', background: 'var(--bg-base, #f8fafc)', borderRadius: '8px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Open Reported Incidents</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: nurseSummary.safety_incidents_open > 0 ? '#dc2626' : '#059669', marginTop: '4px' }}>
                {nurseSummary.safety_incidents_open || 0}
              </div>
            </div>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '16px', marginBottom: 0 }}>
            Policy note: All AI outputs are governed by deterministic clinical guards. Any output requiring revision can be reported via "Report wrong AI output".
          </p>
        </div>
      ) : (
        /* DOCTOR DETAILED TELEMETRY */
        <>
          {/* Key Metric Cards */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
              gap: '14px',
              marginBottom: '24px',
            }}
          >
            <div
              style={{
                backgroundColor: 'var(--bg-card, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '10px',
                padding: '16px',
              }}
            >
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Total Runs</div>
              <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '4px' }}>
                {summary.total_runs || 0}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Window: {windowTime}
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-card, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '10px',
                padding: '16px',
              }}
            >
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Latency (p50 / p95)</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '4px', fontFamily: "'JetBrains Mono', monospace" }}>
                {summary.overall_p50_ms || 0} / {summary.overall_p95_ms || 0} ms
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Deterministic + LLM
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-card, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '10px',
                padding: '16px',
              }}
            >
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Token Burn & Cost</div>
              <div style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)', marginTop: '4px', fontFamily: "'JetBrains Mono', monospace" }}>
                ${(summary.estimated_cost_usd || 0).toFixed(4)}
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {(summary.total_tokens || 0).toLocaleString()} tokens
              </div>
            </div>

            <div
              style={{
                backgroundColor: 'var(--bg-card, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '10px',
                padding: '16px',
              }}
            >
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>Draft Feedback</div>
              <div style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '4px' }}>
                <span style={{ color: '#059669' }}>{summary.draft_accepted || 0} accept</span> /{' '}
                <span style={{ color: '#d97706' }}>{summary.draft_edited || 0} edit</span> /{' '}
                <span style={{ color: '#dc2626' }}>{summary.draft_rejected || 0} rej</span>
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                Avg edit: {summary.avg_edit_chars || 0} chars | 👎 {summary.thumbs_down_count || 0}
              </div>
            </div>
          </div>

          {/* Table 1: Performance by Agent */}
          <div
            style={{
              backgroundColor: 'var(--bg-card, #ffffff)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              borderRadius: '12px',
              overflow: 'hidden',
              marginBottom: '24px',
            }}
          >
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Per-Agent Performance & Telemetry ({windowTime})
              </h3>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)', color: 'var(--text-secondary)' }}>
                    <th style={{ padding: '10px 16px' }}>Agent Name</th>
                    <th style={{ padding: '10px 16px' }}>Version</th>
                    <th style={{ padding: '10px 16px' }}>Model</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>Runs</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>Success</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>Blocked</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>Failed</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>p50 (ms)</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>p95 (ms)</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>Est. Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {byAgent.map((a, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                      <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {a.agent_name}
                      </td>
                      <td style={{ padding: '12px 16px', fontFamily: "'JetBrains Mono', monospace", fontSize: '11px' }}>
                        {a.version_in_use}
                      </td>
                      <td style={{ padding: '12px 16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                        {a.model_name}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600 }}>{a.runs}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', color: '#059669', fontWeight: 600 }}>{a.success}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', color: '#d97706', fontWeight: 600 }}>{a.blocked}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', color: a.failed > 0 ? '#dc2626' : 'var(--text-muted)', fontWeight: 600 }}>{a.failed}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{a.latency_p50_ms}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>{a.latency_p95_ms}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontFamily: "'JetBrains Mono', monospace" }}>${a.estimated_cost_usd}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Table 2: Autonomy Level & Shadow Agreement Trend */}
          <div
            style={{
              backgroundColor: 'var(--bg-card, #ffffff)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              borderRadius: '12px',
              overflow: 'hidden',
              marginBottom: '24px',
            }}
          >
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Action Types: Autonomy, Mode & Shadow Agreement Trend
              </h3>
            </div>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)', color: 'var(--text-secondary)' }}>
                    <th style={{ padding: '10px 16px' }}>Action Type</th>
                    <th style={{ padding: '10px 16px' }}>Autonomy Level</th>
                    <th style={{ padding: '10px 16px' }}>Mode</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>Shadow Decisions</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>Shadow Agreement %</th>
                  </tr>
                </thead>
                <tbody>
                  {byAction.map((act, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                      <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {act.action_type}
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '3px 8px',
                            borderRadius: '10px',
                            backgroundColor: act.level === 'Auto' ? 'rgba(5, 150, 105, 0.1)' : 'rgba(217, 119, 6, 0.1)',
                            color: act.level === 'Auto' ? '#059669' : '#d97706',
                          }}
                        >
                          {act.level}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '3px 8px',
                            borderRadius: '10px',
                            backgroundColor: act.mode === 'Live' ? 'rgba(13, 148, 136, 0.1)' : 'rgba(100, 116, 139, 0.1)',
                            color: act.mode === 'Live' ? 'var(--teal-primary, #0d9488)' : 'var(--text-muted)',
                          }}
                        >
                          {act.mode}
                        </span>
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>{act.shadow_cases}</td>
                      <td style={{ padding: '12px 16px', textAlign: 'right', fontWeight: 600 }}>
                        {act.shadow_agreement_pct !== null ? `${act.shadow_agreement_pct}%` : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Candidate Regression Tests Queue (Doctor Review) */}
          <div
            style={{
              backgroundColor: 'var(--bg-card, #ffffff)',
              border: '1px solid var(--border-subtle, #e2e8f0)',
              borderRadius: '12px',
              padding: '20px',
              marginBottom: '24px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div>
                <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                  Candidate Regression Tests (Doctor Review Queue)
                </h3>
                <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                  Incidents reported by staff generate candidate tests requiring doctor approval before entering permanent evaluation sets.
                </p>
              </div>
              <span
                style={{
                  fontSize: '12px',
                  fontWeight: 700,
                  padding: '3px 10px',
                  borderRadius: '12px',
                  backgroundColor: 'rgba(124, 58, 237, 0.1)',
                  color: '#7c3aed',
                }}
              >
                {candidateTests.filter((c) => c.status === 'Pending_Review').length} Pending
              </span>
            </div>

            {candidateTests.length === 0 ? (
              <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                No candidate tests waiting for review.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {candidateTests.map((ct) => (
                  <div
                    key={ct.candidate_id}
                    style={{
                      padding: '14px',
                      background: 'var(--bg-base, #f8fafc)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      borderRadius: '8px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      gap: '16px',
                    }}
                  >
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>
                          Candidate #{ct.candidate_id}: {ct.test_type}
                        </span>
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            backgroundColor: ct.status === 'Approved' ? 'rgba(5, 150, 105, 0.1)' : 'rgba(217, 119, 6, 0.1)',
                            color: ct.status === 'Approved' ? '#059669' : '#d97706',
                            fontWeight: 600,
                          }}
                        >
                          {ct.status}
                        </span>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                          Reported by: {ct.reported_by_name || 'Staff'} ({ct.category})
                        </span>
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '4px' }}>
                        {ct.expected_behavior}
                      </div>
                    </div>

                    {ct.status === 'Pending_Review' && (
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          type="button"
                          onClick={() => handleReviewCandidate(ct.candidate_id, true)}
                          style={{
                            padding: '6px 12px',
                            backgroundColor: '#059669',
                            color: '#ffffff',
                            border: 'none',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReviewCandidate(ct.candidate_id, false)}
                          style={{
                            padding: '6px 12px',
                            backgroundColor: 'transparent',
                            color: '#dc2626',
                            border: '1px solid #dc2626',
                            borderRadius: '6px',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

