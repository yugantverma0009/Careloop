import React, { useState, useEffect } from 'react';
import { getAuditLog, exportAuditLogAudit } from '../services/api';
import {
  IconShieldCheck,
  IconSearch,
} from './Icons';

/**
 * AuditLogViewer Component (Feature D-17)
 * 
 * Provides a tamper-evident, read-only audit log viewer.
 * Supports filtering by patient, staff, action type, and date.
 * Strictly logs export operations.
 */
export default function AuditLogViewer() {
  const [logs, setLogs] = useState([]);
  const [actionsList, setActionsList] = useState([]);
  const [staffList, setStaffList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Filters (Hidden by default per Phase 3)
  const [showFilters, setShowFilters] = useState(false);
  const [selectedAction, setSelectedAction] = useState('');
  const [selectedStaff, setSelectedStaff] = useState('');
  const [patientQuery, setPatientQuery] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  // Expanded row details
  const [expandedLogIds, setExpandedLogIds] = useState(new Set());

  const fetchLogs = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getAuditLog({
        action: selectedAction || undefined,
        staff_id: selectedStaff || undefined,
        patient_id: patientQuery ? parseInt(patientQuery, 10) || undefined : undefined,
        start_date: startDate || undefined,
        end_date: endDate || undefined,
        limit: 20,
      });
      setLogs(data.logs || []);
      if (data.actions && !actionsList.length) setActionsList(data.actions);
      if (data.staff && !staffList.length) setStaffList(data.staff);
    } catch (err) {
      console.error('Failed to load audit logs:', err);
      setError(err.message || 'Failed to load audit logs.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedAction, selectedStaff, startDate, endDate]);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    fetchLogs();
  };

  const toggleExpand = (logId) => {
    const next = new Set(expandedLogIds);
    if (next.has(logId)) next.delete(logId);
    else next.add(logId);
    setExpandedLogIds(next);
  };

  const handleExportCSV = async () => {
    if (!logs.length) {
      alert('No audit logs to export.');
      return;
    }

    try {
      await exportAuditLogAudit(logs.length, {
        action: selectedAction,
        staff_id: selectedStaff,
        patient_id: patientQuery,
        start_date: startDate,
        end_date: endDate,
      });

      const headers = ['Log ID', 'Timestamp', 'Actor Type', 'Actor ID', 'Actor Name', 'Action', 'Entity Type', 'Entity ID', 'Patient Code', 'Patient Name', 'Details'];
      const rows = logs.map((l) => [
        l.log_id,
        l.created_at,
        l.actor_type,
        `"${(l.actor_id || '').replace(/"/g, '""')}"`,
        `"${(l.staff_name || '').replace(/"/g, '""')}"`,
        l.action,
        l.entity_type || '',
        l.entity_id || '',
        l.patient_code || '',
        `"${(l.patient_name || '').replace(/"/g, '""')}"`,
        `"${(typeof l.details === 'object' ? JSON.stringify(l.details) : l.details || '').replace(/"/g, '""')}"`,
      ]);

      const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `careloop_audit_log_${new Date().toISOString().slice(0, 10)}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('Failed to log audit export:', err);
      alert('Export failed to record in compliance log.');
    }
  };

  const getActionBadgeStyle = (action) => {
    if (action.includes('BREAK_GLASS')) {
      return { background: '#fee2e2', color: '#b91c1c', border: '1px solid #f87171' };
    }
    if (action.includes('APPROVE') || action.includes('RESOLVE')) {
      return { background: '#ecfdf5', color: '#047857', border: '1px solid #a7f3d0' };
    }
    if (action.includes('REJECT') || action.includes('DISMISS')) {
      return { background: '#fef3c7', color: '#b45309', border: '1px solid #fde68a' };
    }
    if (action.includes('ACKNOWLEDGE') || action.includes('CLAIM')) {
      return { background: '#eff6ff', color: '#1d4ed8', border: '1px solid #bfdbfe' };
    }
    if (action.includes('NOTE') || action.includes('CONTACT')) {
      return { background: '#f5f3ff', color: '#6d28d9', border: '1px solid #ddd6fe' };
    }
    return { background: 'var(--bg-base, #f1f5f9)', color: 'var(--text-secondary, #475569)', border: '1px solid var(--border-subtle, #cbd5e1)' };
  };

  const breakGlassCount = logs.filter((l) => (l.action || '').includes('BREAK_GLASS')).length;
  const noteCount = logs.filter((l) => (l.action || '').includes('NOTE')).length;
  const approvalCount = logs.filter((l) => (l.action || '').includes('APPROVE')).length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Header Bar */}
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
            <IconShieldCheck width={22} height={22} style={{ color: 'var(--accent-teal, #0d9488)' }} />
            <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
              Compliance & Security Audit Log
            </h2>
          </div>
          <p style={{ margin: 0, fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
            Tamper-evident system activity record for DPDP compliance and clinical governance.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            type="button"
            onClick={() => setShowFilters(!showFilters)}
            style={{
              padding: '8px 14px',
              borderRadius: '8px',
              background: showFilters ? 'var(--role-doctor-soft, #f5f3ff)' : 'var(--bg-base, #f1f5f9)',
              border: `1px solid ${showFilters ? 'var(--role-doctor, #7c3aed)' : 'var(--border-subtle, #cbd5e1)'}`,
              color: showFilters ? 'var(--role-doctor, #7c3aed)' : 'var(--text-primary, #0f172a)',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <span>🔍 {showFilters ? 'Hide filters' : 'Filter events'}</span>
          </button>

          <button
            type="button"
            onClick={handleExportCSV}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              background: 'var(--bg-base, #f1f5f9)',
              border: '1px solid var(--border-subtle, #cbd5e1)',
              color: 'var(--text-primary, #0f172a)',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <span>📥 Export CSV (Audited)</span>
          </button>
        </div>
      </div>

      {/* 2. Key Metrics Bar */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '14px' }}>
        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '14px 18px', borderRadius: '10px', border: '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>Logged Events (Showing 20)</div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginTop: '4px' }}>{logs.length}</div>
        </div>

        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '14px 18px', borderRadius: '10px', border: breakGlassCount > 0 ? '1px solid #fca5a5' : '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: breakGlassCount > 0 ? '#b91c1c' : 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>Break-Glass Views</div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: breakGlassCount > 0 ? '#b91c1c' : 'var(--text-primary, #0f172a)', marginTop: '4px' }}>{breakGlassCount}</div>
        </div>

        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '14px 18px', borderRadius: '10px', border: '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>Doctor Approvals</div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: '#047857', marginTop: '4px' }}>{approvalCount}</div>
        </div>

        <div style={{ background: 'var(--bg-surface, #ffffff)', padding: '14px 18px', borderRadius: '10px', border: '1px solid var(--border-subtle, #e2e8f0)', boxShadow: 'var(--shadow-card)' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', letterSpacing: '0.05em' }}>Clinical Notes</div>
          <div style={{ fontSize: '22px', fontWeight: 800, color: '#6d28d9', marginTop: '4px' }}>{noteCount}</div>
        </div>
      </div>

      {/* 3. Filter Controls (Collapsible, default hidden per Phase 3) */}
      {showFilters && (
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '12px',
            padding: '16px 20px',
            display: 'flex',
            flexWrap: 'wrap',
            gap: '14px',
            alignItems: 'center',
          }}
        >
      >
        <form onSubmit={handleSearchSubmit} style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '180px' }}>
          <div style={{ position: 'relative', width: '100%' }}>
            <input
              type="text"
              placeholder="Patient ID #..."
              value={patientQuery}
              onChange={(e) => setPatientQuery(e.target.value)}
              style={{
                width: '100%',
                padding: '7px 10px 7px 32px',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle, #cbd5e1)',
                background: 'var(--bg-base, #f8fafc)',
                color: 'var(--text-primary, #0f172a)',
                fontSize: '13px',
              }}
            />
            <IconSearch width={14} height={14} style={{ position: 'absolute', left: '10px', top: '10px', color: 'var(--text-muted, #94a3b8)' }} />
          </div>
        </form>

        <select
          value={selectedAction}
          onChange={(e) => setSelectedAction(e.target.value)}
          style={{
            padding: '7px 12px',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle, #cbd5e1)',
            background: 'var(--bg-base, #f8fafc)',
            color: 'var(--text-primary, #0f172a)',
            fontSize: '13px',
          }}
        >
          <option value="">All Actions ({actionsList.length})</option>
          {actionsList.map((act) => (
            <option key={act} value={act}>{act}</option>
          ))}
        </select>

        <select
          value={selectedStaff}
          onChange={(e) => setSelectedStaff(e.target.value)}
          style={{
            padding: '7px 12px',
            borderRadius: '8px',
            border: '1px solid var(--border-subtle, #cbd5e1)',
            background: 'var(--bg-base, #f8fafc)',
            color: 'var(--text-primary, #0f172a)',
            fontSize: '13px',
          }}
        >
          <option value="">All Staff Members</option>
          {staffList.map((s) => (
            <option key={s.staff_id} value={s.staff_id}>
              {s.full_name} ({s.staff_role})
            </option>
          ))}
        </select>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>From:</span>
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            style={{
              padding: '6px 8px',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle, #cbd5e1)',
              background: 'var(--bg-base, #f8fafc)',
              color: 'var(--text-primary, #0f172a)',
              fontSize: '12px',
            }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>To:</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            style={{
              padding: '6px 8px',
              borderRadius: '6px',
              border: '1px solid var(--border-subtle, #cbd5e1)',
              background: 'var(--bg-base, #f8fafc)',
              color: 'var(--text-primary, #0f172a)',
              fontSize: '12px',
            }}
          />
        </div>

        {(selectedAction || selectedStaff || patientQuery || startDate || endDate) && (
          <button
            type="button"
            onClick={() => {
              setSelectedAction('');
              setSelectedStaff('');
              setPatientQuery('');
              setStartDate('');
              setEndDate('');
            }}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: 'none',
              background: 'transparent',
              color: 'var(--accent-teal, #0d9488)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            Reset Filters
          </button>
        )}
      </div>
      )}

      {error && (
        <div style={{ padding: '12px 16px', borderRadius: '8px', background: '#fee2e2', color: '#b91c1c', fontSize: '13px' }}>
          {error}
        </div>
      )}

      {/* 4. Audit Log Table */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          boxShadow: 'var(--shadow-card)',
          overflow: 'hidden',
        }}
      >
        {loading ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '14px' }}>
            Loading audit records...
          </div>
        ) : logs.length === 0 ? (
          <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '14px' }}>
            No audit records found matching selected criteria.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
              <thead>
                <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)', width: '60px' }}>ID</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)', width: '150px' }}>Timestamp</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)', width: '160px' }}>Actor</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)', width: '170px' }}>Action</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)', width: '180px' }}>Subject / Patient</th>
                  <th style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-secondary, #475569)' }}>Details</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => {
                  const isExpanded = expandedLogIds.has(log.log_id);
                  const isBreakGlass = (log.action || '').includes('BREAK_GLASS');
                  const badgeStyle = getActionBadgeStyle(log.action);

                  return (
                    <React.Fragment key={log.log_id}>
                      <tr
                        style={{
                          borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
                          background: isBreakGlass ? '#fff7ed' : 'transparent',
                        }}
                      >
                        <td style={{ padding: '12px 16px', fontFamily: 'monospace', fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
                          #{log.log_id}
                        </td>
                        <td style={{ padding: '12px 16px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                          {log.created_at ? log.created_at.replace('T', ' ').slice(0, 19) : '—'}
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <span style={{ fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                              {log.staff_name || log.actor_id || log.actor_type}
                            </span>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                              {log.staff_role ? `${log.staff_role} · ` : ''}{log.actor_type}
                            </span>
                          </div>
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <span
                            style={{
                              display: 'inline-block',
                              padding: '3px 8px',
                              borderRadius: '6px',
                              fontSize: '11px',
                              fontWeight: 700,
                              fontFamily: 'monospace',
                              ...badgeStyle,
                            }}
                          >
                            {log.action}
                          </span>
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          {log.patient_name ? (
                            <div>
                              <div style={{ fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>{log.patient_name}</div>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>PID: {log.patient_code}</div>
                            </div>
                          ) : log.entity_type ? (
                            <span style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                              {log.entity_type} {log.entity_id ? `#${log.entity_id}` : ''}
                            </span>
                          ) : (
                            <span style={{ color: 'var(--text-muted, #94a3b8)', fontSize: '12px' }}>—</span>
                          )}
                        </td>
                        <td style={{ padding: '12px 16px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                            <span
                              style={{
                                fontSize: '12px',
                                color: 'var(--text-secondary, #334155)',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: isExpanded ? 'normal' : 'nowrap',
                                maxWidth: '380px',
                              }}
                            >
                              {typeof log.details === 'object'
                                ? (log.details.reason || log.details.summary || log.details.resolution_code || JSON.stringify(log.details))
                                : log.details || '—'}
                            </span>
                            {log.details && (
                              <button
                                type="button"
                                onClick={() => toggleExpand(log.log_id)}
                                style={{
                                  border: 'none',
                                  background: 'transparent',
                                  color: 'var(--accent-teal, #0d9488)',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                  flexShrink: 0,
                                }}
                              >
                                {isExpanded ? 'Less' : 'Inspect'}
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                      {isExpanded && log.details && (
                        <tr style={{ background: 'var(--bg-base, #f8fafc)', borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                          <td colSpan={6} style={{ padding: '12px 20px' }}>
                            <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', marginBottom: '4px' }}>RAW DETAILS:</div>
                            <pre
                              style={{
                                margin: 0,
                                padding: '10px 14px',
                                borderRadius: '6px',
                                background: '#1e293b',
                                color: '#e2e8f0',
                                fontSize: '11px',
                                fontFamily: 'monospace',
                                overflowX: 'auto',
                              }}
                            >
                              {JSON.stringify(log.details, null, 2)}
                            </pre>
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
