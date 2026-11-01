import React, { useState, useEffect } from 'react';
import { getOperationalInsights, exportInsightsAudit } from '../services/api';
import { IconActivity } from './Icons';

/**
 * OperationalInsights Component (Feature D-14)
 * 
 * Provides operational transparency into triage SLA compliance,
 * false alarm rates, self-reported adherence, and device uptime.
 * Strictly avoids outcome claims (readmission rate, recovery rate).
 */
export default function OperationalInsights() {
  const [dateRange, setDateRange] = useState('30d'); // '7d', '30d', '90d'
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [exporting, setExporting] = useState(false);

  const fetchInsights = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getOperationalInsights(dateRange);
      setData(res);
    } catch (err) {
      console.error('Failed to load operational insights:', err);
      setError(err.message || 'Failed to load operational metrics.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dateRange]);

  const handleExportCSV = async () => {
    if (!data || !data.metrics) return;
    setExporting(true);
    try {
      await exportInsightsAudit(dateRange);

      const m = data.metrics;
      const rows = [
        ['Metric', 'Value', 'Definition'],
        ['Date Range Window', dateRange, 'Selected historical window'],
        ['Median Acknowledge Time (Immediate)', `${m.median_time_to_acknowledge_minutes?.Immediate ?? 0} min`, data.definitions?.median_time_to_acknowledge],
        ['Median Acknowledge Time (Urgent)', `${m.median_time_to_acknowledge_minutes?.Urgent ?? 0} min`, data.definitions?.median_time_to_acknowledge],
        ['Median Acknowledge Time (Review Soon)', `${m.median_time_to_acknowledge_minutes?.Review_Soon ?? 0} min`, data.definitions?.median_time_to_acknowledge],
        ['Within SLA Target %', `${m.within_target_pct}%`, data.definitions?.within_target],
        ['Alerts Per Patient Per Day', m.alerts_per_patient_per_day, data.definitions?.alerts_per_patient_per_day],
        ['Duplicate Rate %', `${m.duplicate_rate_pct}%`, data.definitions?.duplicate_rate],
        ['Self-Reported Dose Confirmation %', `${m.self_reported_dose_confirmation_pct}%`, data.definitions?.self_reported_dose_confirmation],
        ['Continuous Telemetry Uptime %', `${m.device_uptime_pct}%`, data.definitions?.device_uptime],
        ['Overdue Tasks Count', m.overdue_tasks_count, data.definitions?.overdue_tasks],
      ];

      const csvContent = rows.map((r) => r.map((c) => `"${(c + '').replace(/"/g, '""')}"`).join(',')).join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `careloop_operational_insights_${dateRange}_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('Export failed:', err);
      alert('Failed to log insights export.');
    } finally {
      setExporting(false);
    }
  };

  if (loading && !data) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '14px' }}>
        Calculating clinical operations metrics...
      </div>
    );
  }

  const m = data?.metrics || {};
  const defs = data?.definitions || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 1. Header & Controls */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '20px 24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '4px' }}>
            <IconActivity width={22} height={22} style={{ color: 'var(--accent-teal, #0d9488)' }} />
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
              Clinical Operations & SLA Insights
            </h2>
          </div>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
            Transparent workflow telemetry and trigger quality. (Strictly non-outcome metrics).
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Date Range Chips */}
          <div style={{ display: 'flex', background: 'var(--bg-base, #f1f5f9)', padding: '3px', borderRadius: '8px' }}>
            {[
              { id: '7d', label: '7 Days' },
              { id: '30d', label: '30 Days' },
              { id: '90d', label: '90 Days' },
            ].map((rng) => (
              <button
                key={rng.id}
                type="button"
                onClick={() => setDateRange(rng.id)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  border: 'none',
                  background: dateRange === rng.id ? 'var(--bg-surface, #ffffff)' : 'transparent',
                  color: dateRange === rng.id ? 'var(--text-primary, #0f172a)' : 'var(--text-secondary, #64748b)',
                  fontWeight: dateRange === rng.id ? 700 : 500,
                  fontSize: '12px',
                  cursor: 'pointer',
                  boxShadow: dateRange === rng.id ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                }}
              >
                {rng.label}
              </button>
            ))}
          </div>

          <button
            type="button"
            disabled={exporting}
            onClick={handleExportCSV}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              background: 'var(--bg-base, #f1f5f9)',
              border: '1px solid var(--border-subtle, #cbd5e1)',
              color: 'var(--text-primary, #0f172a)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            {exporting ? 'Exporting...' : '📥 Export CSV (Audited)'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: '8px', background: '#fee2e2', color: '#b91c1c', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* 2. Primary KPI Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        {/* Within Target % */}
        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '18px 20px', borderRadius: '12px', border: '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>
            Within SLA Target
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: m.within_target_pct >= 90 ? '#059669' : '#d97706', marginTop: '6px' }}>
            {m.within_target_pct ?? 0}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '4px' }}>
            Immediate &lt; 15m, Urgent &lt; 2h
          </div>
        </div>

        {/* Alerts per Patient Day */}
        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '18px 20px', borderRadius: '12px', border: '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>
            Alerts / Patient / Day
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginTop: '6px' }}>
            {m.alerts_per_patient_per_day ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '4px' }}>
            Flag density in window
          </div>
        </div>

        {/* Duplicate Rate */}
        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '18px 20px', borderRadius: '12px', border: '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>
            Duplicate Rate
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: m.duplicate_rate_pct > 20 ? '#dc2626' : '#0f172a', marginTop: '6px' }}>
            {m.duplicate_rate_pct ?? 0}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '4px' }}>
            Deduplicated repeats
          </div>
        </div>

        {/* Dose Confirmation */}
        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '18px 20px', borderRadius: '12px', border: '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>
            Self-Reported Adherence
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: '#0284c7', marginTop: '6px' }}>
            {m.self_reported_dose_confirmation_pct ?? 0}%
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '4px' }}>
            Confirmed scheduled doses
          </div>
        </div>

        {/* Overdue Tasks */}
        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '18px 20px', borderRadius: '12px', border: m.overdue_tasks_count > 0 ? '1px solid #fca5a5' : '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: m.overdue_tasks_count > 0 ? '#b91c1c' : 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>
            Overdue Follow-ups
          </div>
          <div style={{ fontSize: '26px', fontWeight: 800, color: m.overdue_tasks_count > 0 ? '#b91c1c' : '#059669', marginTop: '6px' }}>
            {m.overdue_tasks_count ?? 0}
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '4px' }}>
            Tasks past due_at
          </div>
        </div>
      </div>

      {/* 3. Median Response Time & Open Flags Age Distribution */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Median Response Time */}
        <div style={{ background: 'var(--bg-surface, #ffffff)', border: '1px solid var(--border-subtle, #e2e8f0)', borderRadius: '12px', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
            Median Time to Acknowledge
          </h3>
          <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
            Time from flag generation until clinician acknowledgment.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {[
              { tier: 'Immediate Review', key: 'Immediate', target: '< 15 min', val: m.median_time_to_acknowledge_minutes?.Immediate, color: '#dc2626', bg: '#fef2f2' },
              { tier: 'Urgent Review', key: 'Urgent', target: '< 2 hours', val: m.median_time_to_acknowledge_minutes?.Urgent, color: '#d97706', bg: '#fffbeb' },
              { tier: 'Review Soon', key: 'Review_Soon', target: '< 24 hours', val: m.median_time_to_acknowledge_minutes?.Review_Soon, color: '#0284c7', bg: '#eff6ff' },
              { tier: 'Routine Review', key: 'Routine', target: '< 72 hours', val: m.median_time_to_acknowledge_minutes?.Routine, color: '#475569', bg: '#f1f5f9' },
            ].map((t) => (
              <div key={t.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 14px', borderRadius: '8px', background: t.bg }}>
                <div>
                  <span style={{ fontWeight: 700, color: t.color, fontSize: '13px' }}>{t.tier}</span>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginLeft: '8px' }}>Target: {t.target}</span>
                </div>
                <div style={{ fontWeight: 800, fontSize: '15px', color: t.color }}>
                  {t.val !== undefined ? `${t.val} min` : '—'}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Open Flags by Age */}
        <div style={{ background: 'var(--bg-surface, #ffffff)', border: '1px solid var(--border-subtle, #e2e8f0)', borderRadius: '12px', padding: '20px', boxShadow: 'var(--shadow-card)' }}>
          <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
            Active Flags by Age Buckets
          </h3>
          <p style={{ margin: '0 0 16px 0', fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
            Age of currently active unresolved flags on clinician worklists.
          </p>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px' }}>
            {[
              { label: '< 1 hour', val: m.open_flags_by_age?.under_1h ?? 0, color: '#059669', bg: '#f0fdf4' },
              { label: '1 - 4 hours', val: m.open_flags_by_age?.from_1_to_4h ?? 0, color: '#0284c7', bg: '#eff6ff' },
              { label: '4 - 24 hours', val: m.open_flags_by_age?.from_4_to_24h ?? 0, color: '#d97706', bg: '#fffbeb' },
              { label: '> 24 hours', val: m.open_flags_by_age?.over_24h ?? 0, color: '#dc2626', bg: '#fef2f2' },
            ].map((b) => (
              <div key={b.label} style={{ padding: '14px 10px', borderRadius: '8px', background: b.bg, textAlign: 'center' }}>
                <div style={{ fontSize: '22px', fontWeight: 800, color: b.color }}>{b.val}</div>
                <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginTop: '4px' }}>{b.label}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 4. False-Alarm Dismissals by Rule Table */}
      <div style={{ background: 'var(--bg-surface, #ffffff)', border: '1px solid var(--border-subtle, #e2e8f0)', borderRadius: '12px', boxShadow: 'var(--shadow-card)', overflow: 'hidden' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
          <h3 style={{ margin: '0 0 2px 0', fontSize: '15px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
            False-Alarm Dismissals by Rule
          </h3>
          <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
            Feeds rule-tuning workflows. High false-alarm rates indicate a candidate for threshold adjustment.
          </p>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
            <thead>
              <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)' }}>Rule ID</th>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)' }}>Rule Type</th>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)' }}>Measurement</th>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)' }}>Total Closed</th>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)' }}>False Alarms</th>
                <th style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)' }}>False Alarm Rate</th>
              </tr>
            </thead>
            <tbody>
              {(m.false_alarms_by_rule || []).length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted, #64748b)' }}>
                    No closed rule alerts in this window.
                  </td>
                </tr>
              ) : (
                m.false_alarms_by_rule.map((r) => (
                  <tr key={r.rule_id} style={{ borderBottom: '1px solid var(--border-subtle, #f1f5f9)' }}>
                    <td style={{ padding: '10px 16px', fontFamily: 'monospace', color: 'var(--text-muted, #64748b)' }}>#{r.rule_id}</td>
                    <td style={{ padding: '10px 16px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>{r.rule_type}</td>
                    <td style={{ padding: '10px 16px', color: 'var(--text-secondary, #475569)' }}>{r.measurement_type || '—'}</td>
                    <td style={{ padding: '10px 16px' }}>{r.total_closed}</td>
                    <td style={{ padding: '10px 16px', color: r.false_alarm_count > 0 ? '#b45309' : '#059669', fontWeight: 600 }}>
                      {r.false_alarm_count}
                    </td>
                    <td style={{ padding: '10px 16px' }}>
                      <span
                        style={{
                          padding: '2px 8px',
                          borderRadius: '10px',
                          fontSize: '11px',
                          fontWeight: 700,
                          background: r.false_alarm_pct > 25 ? '#fee2e2' : '#f0fdf4',
                          color: r.false_alarm_pct > 25 ? '#b91c1c' : '#047857',
                        }}
                      >
                        {r.false_alarm_pct}%
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 5. Metrics Definitions Footnote */}
      <div style={{ background: 'var(--bg-base, #f8fafc)', border: '1px solid var(--border-subtle, #e2e8f0)', borderRadius: '10px', padding: '16px 20px', fontSize: '11px', color: 'var(--text-muted, #64748b)', lineHeight: '1.6' }}>
        <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginBottom: '6px' }}>
          Clinical Governance & Definition Lineage (D-14)
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '8px', marginBottom: '8px' }}>
          {Object.entries(defs).map(([k, desc]) => (
            <div key={k}>
              <strong style={{ color: 'var(--text-secondary, #475569)' }}>{k.replace(/_/g, ' ')}:</strong> {desc}
            </div>
          ))}
        </div>
        <div>
          In strict adherence to D-14, all metrics reflect internal response workflows and hardware connectivity. No predictive recovery rates or external hospital benchmarks are calculated.
        </div>
      </div>
    </div>
  );
}
