import React, { useState, useEffect } from 'react';
import { API_BASE } from '../services/api';
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

export default function AgentSettingsView({ currentUser }) {
  const isDoctor = currentUser?.account_role === 'Doctor';
  const roleAccent = isDoctor ? 'var(--navy-deep, #0b1528)' : 'var(--accent-teal, #0d9488)';
  const roleAccentSoft = isDoctor ? '#e0f2fe' : 'var(--accent-teal-soft, #ecfdf5)';

  const [loading, setLoading] = useState(true);
  const [settings, setSettings] = useState({
    global_paused: false,
    daily_llm_budget_per_patient: 20,
    autonomy_matrix: [],
    shadow_agreement_stats: [],
    auto_close_enabled: false,
    auto_close_catalog: []
  });
  const [actionMsg, setActionMsg] = useState('');
  const [updatingAction, setUpdatingAction] = useState(null);

  const token = localStorage.getItem('careloop_token');

  const fetchSettings = async () => {
    try {
      setLoading(true);
      const res = await fetch(`${API_BASE}/agent/settings`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSettings(data);
      }
    } catch (err) {
      console.error('Failed to load Agent Settings:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSettings();
  }, []);

  const handlePauseToggle = async (pauseVal) => {
    if (!window.confirm(pauseVal 
      ? 'Engage Global Agent Pause? All automated agents will stop operations until resumed.'
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
        setActionMsg(pauseVal ? 'Global agent pause engaged.' : 'Agents resumed.');
        setTimeout(() => setActionMsg(''), 4000);
        fetchSettings();
      }
    } catch (err) {
      alert('Failed to toggle pause: ' + err.message);
    }
  };

  const handleAutonomyChange = async (actionType, newLevel, newMode) => {
    try {
      setUpdatingAction(actionType);
      const res = await fetch(`${API_BASE}/agent/settings`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          action_type: actionType,
          level: newLevel,
          mode: newMode
        })
      });
      if (res.ok) {
        setActionMsg(`Autonomy updated for ${actionType.replace(/_/g, ' ')} (${newMode} mode).`);
        setTimeout(() => setActionMsg(''), 4000);
        fetchSettings();
      } else {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || 'Failed to update autonomy.');
      }
    } catch (err) {
      alert('Network error: ' + err.message);
    } finally {
      setUpdatingAction(null);
    }
  };

  const handleAutoCloseToggle = async (enabledVal) => {
    try {
      const res = await fetch(`${API_BASE}/agent/settings/auto-close`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ enabled: enabledVal })
      });
      if (res.ok) {
        setActionMsg(enabledVal ? 'Approved low-risk auto-close rules enabled.' : 'Auto-close rules disabled.');
        setTimeout(() => setActionMsg(''), 4000);
        fetchSettings();
      }
    } catch (err) {
      alert('Failed to toggle auto-close: ' + err.message);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <IconClock style={{ width: '24px', height: '24px', animation: 'spin 1s linear infinite' }} />
        <div style={{ marginTop: '8px', fontSize: '13px' }}>Loading Agent Settings &amp; Autonomy Matrix...</div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', paddingBottom: '50px' }}>
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
              Physician Governance
            </span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>•</span>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>
              Section 5 Autonomy &amp; Shadow Controls
            </span>
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
            Agent Settings &amp; Governance
          </h2>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
            "Autonomy is earned: shadow mode first." Doctors control which routines promote to Live or remain in Shadow.
          </p>
        </div>

        {/* Global Kill Switch */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {settings.global_paused ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{
                fontSize: '12px',
                fontWeight: 700,
                padding: '5px 12px',
                borderRadius: '8px',
                background: '#fef2f2',
                color: '#dc2626',
                border: '1px solid #fecaca'
              }}>
                🚨 All Agents Paused
              </span>
              <button
                type="button"
                onClick={() => handlePauseToggle(false)}
                style={{
                  padding: '8px 16px',
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
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <span style={{
                fontSize: '12px',
                fontWeight: 700,
                padding: '5px 12px',
                borderRadius: '8px',
                background: '#ecfdf5',
                color: '#059669',
                border: '1px solid #a7f3d0'
              }}>
                ✓ All Agents Active
              </span>
              <button
                type="button"
                onClick={() => handlePauseToggle(true)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '8px',
                  border: '1px solid #fca5a5',
                  background: '#fff1f2',
                  color: '#dc2626',
                  fontWeight: 700,
                  fontSize: '12px',
                  cursor: 'pointer'
                }}
              >
                Pause All Agents (Kill Switch)
              </button>
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
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 0.8fr', gap: '20px' }}>
        
        {/* COLUMN 1: Autonomy Matrix */}
        <div style={{
          background: 'var(--bg-card, #ffffff)',
          borderRadius: '12px',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          padding: '20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '14px'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
              Action Autonomy Matrix (Section 5.2)
            </h3>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              {settings.autonomy_matrix.length} Registered Actions
            </span>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
            Every action type defaults to policy tiers: <strong>Auto</strong> (runs inside limits), <strong>Draft</strong> (requires human sign-off), or <strong>Suggest</strong> (idea only). Doctors can promote actions between Shadow and Live.
          </p>

          <div style={{ overflowX: 'auto', border: '1px solid var(--border-subtle, #e2e8f0)', borderRadius: '8px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: 'var(--text-secondary)' }}>Action Type</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: 'var(--text-secondary)' }}>Autonomy Level</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: 'var(--text-secondary)' }}>Mode</th>
                  <th style={{ padding: '10px 14px', fontWeight: 700, color: 'var(--text-secondary)' }}>Control</th>
                </tr>
              </thead>
              <tbody>
                {settings.autonomy_matrix.map((row) => {
                  const isUpdating = updatingAction === row.action_type;
                  const isLive = row.mode === 'Live';
                  return (
                    <tr key={row.action_type} style={{ borderBottom: '1px solid #f1f5f9' }}>
                      <td style={{ padding: '10px 14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                        {row.action_type.replace(/_/g, ' ')}
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: row.level === 'Auto' ? '#ecfdf5' : (row.level === 'Draft' ? '#fef3c7' : '#f1f5f9'),
                          color: row.level === 'Auto' ? '#065f46' : (row.level === 'Draft' ? '#b45309' : '#475569')
                        }}>
                          {row.level}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        <span style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '6px',
                          background: isLive ? '#e0e7ff' : '#f1f5f9',
                          color: isLive ? '#3730a3' : '#64748b'
                        }}>
                          {row.mode}
                        </span>
                      </td>
                      <td style={{ padding: '10px 14px' }}>
                        {isDoctor ? (
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              type="button"
                              disabled={isUpdating}
                              onClick={() => handleAutonomyChange(row.action_type, row.level, isLive ? 'Shadow' : 'Live')}
                              style={{
                                padding: '4px 10px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-subtle)',
                                background: isLive ? '#fff1f2' : '#ecfdf5',
                                color: isLive ? '#dc2626' : '#059669',
                                fontSize: '11px',
                                fontWeight: 700,
                                cursor: 'pointer'
                              }}
                            >
                              {isLive ? 'Demote to Shadow' : 'Promote to Live'}
                            </button>
                          </div>
                        ) : (
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Doctor sign-off only</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* COLUMN 2: Shadow Mode Agreement & Auto-Close Rules */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          
          {/* Shadow Agreement Card */}
          <div style={{
            background: 'var(--bg-card, #ffffff)',
            borderRadius: '12px',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <h3 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
              Shadow Mode Agreement (Section 5.3)
            </h3>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
              Before an action is promoted to Live, the agent shadows human clinicians to measure agreement without acting.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {settings.shadow_agreement_stats.length === 0 ? (
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', padding: '12px', textAlign: 'center' }}>
                  No shadow cases recorded yet.
                </div>
              ) : (
                settings.shadow_agreement_stats.map((stat) => (
                  <div
                    key={stat.action_type}
                    style={{
                      padding: '12px',
                      borderRadius: '8px',
                      background: 'var(--bg-base, #f8fafc)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between'
                    }}
                  >
                    <div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                        {stat.action_type.replace(/_/g, ' ')}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {stat.agreed_cases} of {stat.total_cases} decisions agreed
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: '16px', fontWeight: 800, color: stat.agreement_pct >= 90 ? '#059669' : '#b45309' }}>
                        {stat.agreement_pct}%
                      </div>
                      <span style={{
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '1px 6px',
                        borderRadius: '4px',
                        background: stat.agreement_pct >= 90 ? '#ecfdf5' : '#fef3c7',
                        color: stat.agreement_pct >= 90 ? '#065f46' : '#92400e'
                      }}>
                        {stat.agreement_pct >= 90 ? 'Ready for Live' : 'Monitoring'}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Approved Auto-Close Rules Card (Section 5.4) */}
          <div style={{
            background: 'var(--bg-card, #ffffff)',
            borderRadius: '12px',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            padding: '20px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <h3 style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-primary)', margin: 0 }}>
                Approved Auto-Close Rules (Section 5.4)
              </h3>
              <span style={{
                fontSize: '11px',
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: '8px',
                background: settings.auto_close_enabled ? '#ecfdf5' : '#f1f5f9',
                color: settings.auto_close_enabled ? '#065f46' : '#64748b'
              }}>
                {settings.auto_close_enabled ? 'Active (Live)' : 'Off by default'}
              </span>
            </div>

            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', margin: 0 }}>
              Doctor-enabled for low-risk routine alerts only. <span style={{ color: '#dc2626', fontWeight: 700 }}>STRICT SAFETY GUARD:</span> Emergency, SOS, Urgent, and Symptom flags are never auto-closed.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {(settings.auto_close_catalog || []).map((rule) => (
                <div
                  key={rule.rule_type}
                  style={{
                    padding: '10px 12px',
                    borderRadius: '8px',
                    background: '#f8fafc',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <strong style={{ fontSize: '12px', color: 'var(--text-primary)' }}>{rule.name}</strong>
                    <span style={{ fontSize: '10px', fontWeight: 700, padding: '1px 5px', borderRadius: '4px', background: '#ecfdf5', color: '#065f46' }}>
                      Low Risk
                    </span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                    Condition: {rule.condition}
                  </div>
                  <div style={{ fontSize: '10px', color: '#b91c1c', fontWeight: 600 }}>
                    Blocked on: {rule.refuses}
                  </div>
                </div>
              ))}
            </div>

            {isDoctor && (
              <div style={{ paddingTop: '8px', borderTop: '1px solid #f1f5f9', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  onClick={() => handleAutoCloseToggle(!settings.auto_close_enabled)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '6px',
                    border: 'none',
                    background: settings.auto_close_enabled ? '#fee2e2' : 'var(--navy-deep, #0b1528)',
                    color: settings.auto_close_enabled ? '#991b1b' : '#ffffff',
                    fontWeight: 700,
                    fontSize: '11px',
                    cursor: 'pointer'
                  }}
                >
                  {settings.auto_close_enabled ? 'Disable Auto-Close Rules' : 'Enable Approved Auto-Close Rules'}
                </button>
              </div>
            )}
          </div>

          {/* Daily Budgets Card */}
          <div style={{
            background: 'var(--bg-card, #ffffff)',
            borderRadius: '12px',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            padding: '16px 20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Daily LLM Budget Limit
              </div>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Max proactive LLM calls per patient per 24 hours
              </div>
            </div>
            <span style={{
              fontSize: '14px',
              fontWeight: 800,
              padding: '4px 12px',
              borderRadius: '8px',
              background: '#f1f5f9',
              color: 'var(--text-primary)',
              fontFamily: 'var(--font-mono)'
            }}>
              {settings.daily_llm_budget_per_patient} calls / day
            </span>
          </div>

        </div>
      </div>
    </div>
  );
}

