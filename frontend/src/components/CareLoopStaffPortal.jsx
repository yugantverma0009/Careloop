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
import ThemeToggle from './ThemeToggle';
import {
  IconLogo,
  IconAlertTriangle,
  IconActivity,
  IconCheck,
  IconFileText,
  IconLogOut,
  IconShieldCheck,
  IconClock,
  IconSearch,
} from './Icons';

export default function CareLoopStaffPortal({ user }) {
  const [activeNav, setActiveNav] = useState('triage');
  const [triageItems, setTriageItems] = useState([]);
  const [followUps, setFollowUps] = useState([]);
  const [summaries, setSummaries] = useState([]);
  const [timelinePatientId, setTimelinePatientId] = useState(1);
  const [summaryPatientId, setSummaryPatientId] = useState(1);

  const handleExportCSV = () => {
    if (!triageItems || triageItems.length === 0) {
      alert('No flags to export.');
      return;
    }
    const headers = ['Flag ID', 'Patient ID', 'Patient Name', 'Severity', 'Source', 'Reason', 'Risk Score', 'Status', 'Flagged At'];
    const rows = triageItems.map((item) => [
      item.flag_id,
      item.patient_id,
      `"${(item.patient_name || '').replace(/"/g, '""')}"`,
      item.severity,
      item.source_type || 'Clinical',
      `"${(item.reason || '').replace(/"/g, '""')}"`,
      item.risk_score ?? '',
      item.status,
      item.flagged_at || '',
    ]);
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `careloop_triage_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [actionMsg, setActionMsg] = useState('');
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');

  const loadData = async () => {
    try {
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
    if (activeNav === 'timeline') {
      loadTimeline(timelinePatientId);
    }
  }, [activeNav, timelinePatientId]);

  const handleAcknowledge = async (flagId) => {
    try {
      await acknowledgeFlag(flagId, 'Acknowledged by care team');
      setActionMsg(`Flag #${flagId} acknowledged.`);
      setTimeout(() => setActionMsg(''), 4000);
      await loadData();
    } catch (err) {
      alert(`Acknowledge failed: ${err.message}`);
    }
  };

  const handleGenerateSummary = async (pid) => {
    try {
      const res = await generateSummary(pid);
      setActionMsg(`Draft #${res.summary_id} created for Patient #${pid}.`);
      setTimeout(() => setActionMsg(''), 4000);
      await loadData();
    } catch (err) {
      alert(`Summary generation failed: ${err.message}`);
    }
  };

  const handleReviewSummary = async (summaryId, action) => {
    try {
      await reviewSummary(summaryId, action, 'Reviewed by care team');
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

  const immediateCount = triageItems.filter((i) => i.severity === 'Immediate_Review').length;
  const urgentCount = triageItems.filter((i) => i.severity === 'Urgent_Review').length;

  return (
    <div
      style={{
        display: 'flex',
        minHeight: '100vh',
        background: 'var(--bg-base, #f8fafc)',
        color: 'var(--text-primary, #0f172a)',
        fontFamily: "'Plus Jakarta Sans', sans-serif",
      }}
    >
      {/* 1. LEFT VERTICAL SIDEBAR */}
      <aside
        style={{
          width: '240px',
          background: 'var(--sidebar-bg, #ffffff)',
          borderRight: '1px solid var(--sidebar-border, #e2e8f0)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          height: '100vh',
          flexShrink: 0,
          zIndex: 40,
        }}
      >
        <div>
          {/* Logo Brand Header */}
          <div
            style={{
              padding: '20px 22px 18px',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
            }}
          >
            <IconLogo size={34} />
            <div>
              <div
                style={{
                  fontSize: '17px',
                  fontWeight: 800,
                  letterSpacing: '-0.02em',
                  color: 'var(--text-primary, #0f172a)',
                }}
              >
                Care<span style={{ color: '#0d9488' }}>Loop</span>
              </div>
              <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 600 }}>
                Care team hub
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <div style={{ padding: '20px 14px' }}>
            <div
              style={{
                fontSize: '10px',
                fontWeight: 800,
                color: '#94a3b8',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                padding: '0 10px',
                marginBottom: '10px',
              }}
            >
              CARE TEAM
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '22px' }}>
              {[
                { id: 'triage', label: 'Who needs attention', Icon: IconAlertTriangle, badge: triageItems.length },
                { id: 'timeline', label: 'Patient timeline', Icon: IconActivity },
                { id: 'tasks', label: 'Follow-up tasks', Icon: IconCheck, badge: followUps.length },
                { id: 'summaries', label: 'Draft summaries', Icon: IconFileText, badge: summaries.length },
              ].map((item) => {
                const isActive = activeNav === item.id;
                const ItemIcon = item.Icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveNav(item.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      width: '100%',
                      padding: '9px 12px',
                      borderRadius: '8px',
                      border: 'none',
                      background: isActive ? '#eff6ff' : 'transparent',
                      color: isActive ? '#0284c7' : 'var(--text-secondary, #475569)',
                      fontWeight: isActive ? 700 : 500,
                      fontSize: '13px',
                      cursor: 'pointer',
                      textAlign: 'left',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <ItemIcon width={16} height={16} />
                      <span>{item.label}</span>
                    </div>
                    {item.badge !== undefined && item.badge > 0 && (
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 7px',
                          borderRadius: '12px',
                          background: isActive ? '#0284c7' : '#e2e8f0',
                          color: isActive ? '#ffffff' : '#475569',
                        }}
                      >
                        {item.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Sidebar Footer */}
        <div
          style={{
            padding: '16px 14px',
            borderTop: '1px solid var(--sidebar-border, #e2e8f0)',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0 6px' }}>
            <span style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 600 }}>Theme</span>
            <ThemeToggle />
          </div>

          <button
            type="button"
            onClick={logout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '8px 10px',
              borderRadius: '8px',
              border: 'none',
              background: 'transparent',
              color: 'var(--text-secondary, #475569)',
              fontSize: '12px',
              fontWeight: 600,
              cursor: 'pointer',
            }}
          >
            <IconLogOut width={14} height={14} />
            <span>Sign Out</span>
          </button>
        </div>
      </aside>

      {/* 2. MAIN APPLICATION CONTENT AREA */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minWidth: 0 }}>
        {/* Top Breadcrumb & Search Header */}
        <header
          style={{
            height: '64px',
            background: 'var(--header-bg, #ffffff)',
            borderBottom: '1px solid var(--header-border, #e2e8f0)',
            padding: '0 32px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            position: 'sticky',
            top: 0,
            zIndex: 30,
          }}
        >
          <div>
            <div style={{ fontSize: '10px', color: '#94a3b8', fontWeight: 800, letterSpacing: '0.06em' }}>
              WHO NEEDS ATTENTION
            </div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
              Care team
            </div>
          </div>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              background: 'var(--bg-base, #f8fafc)',
              border: '1px solid var(--border-strong, #cbd5e1)',
              borderRadius: '8px',
              padding: '6px 14px',
              width: '360px',
              gap: '8px',
            }}
          >
            <IconSearch width={14} height={14} style={{ color: '#94a3b8' }} />
            <input
              type="text"
              placeholder="Search patients, flags, records..."
              style={{
                border: 'none',
                background: 'transparent',
                width: '100%',
                fontSize: '12px',
                color: 'var(--text-primary, #0f172a)',
              }}
            />
            <span
              style={{
                fontSize: '10px',
                fontWeight: 700,
                color: '#94a3b8',
                background: 'var(--border-subtle, #e2e8f0)',
                padding: '2px 5px',
                borderRadius: '4px',
              }}
            >
              Ctrl+K
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
            <SwitchDemoWorkspace currentUser={user} />

            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  background: '#0f172a',
                  color: '#ffffff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '11px',
                  fontWeight: 800,
                }}
              >
                {user.role === 'Doctor' ? 'DR' : 'PN'}
              </div>
              <div style={{ textAlign: 'left', lineHeight: 1.2 }}>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                  {user.name}
                </div>
                <div style={{ fontSize: '10px', color: '#94a3b8' }}>{user.role} · Care team</div>
              </div>
            </div>
          </div>
        </header>

        {/* Dashboard Main Container */}
        <main style={{ padding: '32px 36px', maxWidth: '1400px', width: '100%', margin: '0 auto' }}>
          {actionMsg && (
            <div
              style={{
                background: '#f0fdf4',
                color: '#166534',
                padding: '12px 18px',
                borderRadius: '8px',
                fontSize: '13px',
                fontWeight: 600,
                marginBottom: '20px',
                border: '1px solid #bbf7d0',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <IconCheck width={15} height={15} />
              <span>{actionMsg}</span>
            </div>
          )}

          {/* Title */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              marginBottom: '26px',
            }}
          >
            <div>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontSize: '11px',
                  fontWeight: 800,
                  color: '#0284c7',
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  marginBottom: '6px',
                }}
              >
                <IconShieldCheck width={14} height={14} />
                <span>WHO NEEDS ATTENTION FIRST</span>
              </div>
              <h1
                style={{
                  fontSize: '26px',
                  fontWeight: 800,
                  color: 'var(--text-primary, #0f172a)',
                  letterSpacing: '-0.025em',
                  marginBottom: '4px',
                }}
              >
                Who needs attention first
              </h1>
              <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', margin: 0 }}>
                Every flag shows why it was raised. Open flags are listed by severity.
              </p>
            </div>

            <button
              type="button"
              onClick={handleExportCSV}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                padding: '8px 14px',
                borderRadius: '8px',
                border: '1px solid var(--border-strong, #cbd5e1)',
                background: 'var(--bg-surface, #ffffff)',
                color: 'var(--text-primary, #0f172a)',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <span>Export flags (CSV)</span>
            </button>
          </div>

          {/* TAB 1: TRIAGE BOARD */}
          {activeNav === 'triage' && (
            <>
              {/* 4 KPI Stat Cards */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '18px',
                  marginBottom: '24px',
                }}
              >
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#eff6ff',
                      border: '1px solid #bfdbfe',
                      color: '#1d4ed8',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconAlertTriangle width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Open flags
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {triageItems.length}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    All monitored patients
                  </div>
                </div>

                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#fff7ed',
                      border: '1px solid #fed7aa',
                      color: '#c2410c',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconActivity width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Immediate review
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: immediateCount > 0 ? '#dc2626' : 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {immediateCount}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    Target: under 15 minutes
                  </div>
                </div>

                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#faf5ff',
                      border: '1px solid #e9d5ff',
                      color: '#7e22ce',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconClock width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Urgent review
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {urgentCount}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    Target: under 2 hours
                  </div>
                </div>

                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    position: 'relative',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div
                    style={{
                      position: 'absolute',
                      top: '18px',
                      right: '18px',
                      width: '36px',
                      height: '36px',
                      borderRadius: '10px',
                      background: '#f0fdf4',
                      border: '1px solid #bbf7d0',
                      color: '#15803d',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconFileText width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Drafts to review
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {summaries.length}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    Waiting for a clinician. AI draft, not reviewed.
                  </div>
                </div>
              </div>

              {/* Triage Register Table */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '22px 24px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '18px',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                      Open flags
                    </div>
                    <div style={{ fontSize: '12px', color: '#94a3b8' }}>
                      Sorted by severity. Each row says why it was raised.
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {[
                      { key: 'ALL', label: 'All' },
                      { key: 'Immediate_Review', label: 'Urgent now' },
                      { key: 'Urgent_Review', label: 'Review soon' },
                      { key: 'Routine_Review', label: 'Routine' },
                    ].map(({ key, label }) => (
                      <button
                        key={key}
                        type="button"
                        onClick={() => setSelectedSeverity(key)}
                        style={{
                          padding: '4px 10px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-subtle, #e2e8f0)',
                          background: selectedSeverity === key ? '#0f172a' : 'var(--bg-base, #f8fafc)',
                          color: selectedSeverity === key ? '#ffffff' : 'var(--text-secondary, #475569)',
                          fontSize: '11px',
                          fontWeight: 700,
                          cursor: 'pointer',
                        }}
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          SCORE
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          PATIENT
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          SEVERITY
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          WHY IT WAS RAISED
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase' }}>
                          RAISED AT
                        </th>
                        <th style={{ padding: '10px 12px', fontSize: '11px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', textAlign: 'right' }}>
                          ACTION
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredTriage.length === 0 ? (
                        <tr>
                          <td colSpan="6" style={{ padding: '36px', textAlign: 'center', color: '#94a3b8', fontSize: '13px' }}>
                            No open flags in this view.
                          </td>
                        </tr>
                      ) : (
                        filteredTriage.map((item) => (
                          <tr
                            key={item.flag_id}
                            style={{
                              borderBottom: '1px solid var(--border-subtle, #f1f5f9)',
                              transition: 'background 0.15s ease',
                            }}
                            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--bg-card-hover, #f8fafc)')}
                            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                          >
                            <td style={{ padding: '12px' }}>
                              <span
                                style={{
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  justifyContent: 'center',
                                  minWidth: '32px',
                                  height: '32px',
                                  padding: '0 8px',
                                  borderRadius: '8px',
                                  background: '#f1f5f9',
                                  color: '#0f172a',
                                  fontWeight: 800,
                                  fontSize: '12px',
                                  fontFamily: "'JetBrains Mono', monospace",
                                }}
                              >
                                {item.risk_score ?? item.priority_score ?? '-'}
                              </span>
                            </td>
                            <td style={{ padding: '12px', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                              <div>{item.patient_name || `Patient #${item.patient_id}`}</div>
                              <div style={{ fontSize: '11px', color: '#94a3b8', fontWeight: 500 }}>PID #{item.patient_id}</div>
                            </td>
                            <td style={{ padding: '12px' }}>
                              {item.severity === 'Immediate_Review' ? (
                                <span className="status-pill status-pill-red">Immediate</span>
                              ) : item.severity === 'Urgent_Review' ? (
                                <span className="status-pill status-pill-amber">Urgent</span>
                              ) : (
                                <span className="status-pill status-pill-blue">Routine</span>
                              )}
                            </td>
                            <td style={{ padding: '12px', fontSize: '13px', color: 'var(--text-secondary, #475569)', maxWidth: '420px' }}>
                              <div>{item.reason || item.flag_reason || 'Clinical alert flagged for review'}</div>
                              <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
                                Source: {item.source_type || item.source_table || 'Clinical Rules'} · Status: {item.status || 'Open'}
                              </div>
                            </td>
                            <td style={{ padding: '12px', fontSize: '12px', color: '#64748b', fontFamily: "'JetBrains Mono', monospace" }}>
                              {(item.flagged_at || item.created_at)?.slice(11, 19) || '14:22:06'}
                            </td>
                            <td style={{ padding: '12px', textAlign: 'right' }}>
                              <button
                                type="button"
                                onClick={() => handleAcknowledge(item.flag_id)}
                                style={{
                                  padding: '5px 12px',
                                  borderRadius: '6px',
                                  border: 'none',
                                  background: '#0f172a',
                                  color: '#ffffff',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                }}
                              >
                                Acknowledge
                              </button>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* TAB 2: TIMELINE */}
          {activeNav === 'timeline' && (
            <div
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '12px',
                padding: '24px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 4px 0' }}>Patient event timeline</h2>
                  <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>Recorded events in chronological order</p>
                </div>
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', maxWidth: '680px' }}>
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((pid) => (
                    <button
                      key={pid}
                      type="button"
                      onClick={() => setTimelinePatientId(pid)}
                      style={{
                        padding: '5px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-strong, #cbd5e1)',
                        background: timelinePatientId === pid ? '#0f172a' : '#ffffff',
                        color: timelinePatientId === pid ? '#ffffff' : '#0f172a',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      Patient #{pid}
                    </button>
                  ))}
                </div>
              </div>

              {timelineEvents.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '30px', color: '#94a3b8', fontSize: '13px' }}>
                  No recorded events for Patient #{timelinePatientId}.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                  {timelineEvents.map((evt, idx) => {
                    const eventType = evt.event_type || evt.type || 'Clinical Event';
                    const summary = evt.summary || evt.description || evt.title || 'Verified event entry';
                    const time = evt.event_time || evt.timestamp || '';
                    const timeStr = time ? time.slice(0, 19).replace('T', ' ') : 'Logged';

                    let badgeClass = 'status-pill-blue';
                    if (eventType === 'Flag') badgeClass = 'status-pill-red';
                    else if (eventType === 'Dose') badgeClass = 'status-pill-green';
                    else if (eventType === 'Symptom') badgeClass = 'status-pill-amber';

                    return (
                      <div
                        key={idx}
                        style={{
                          padding: '12px 16px',
                          borderRadius: '8px',
                          background: 'var(--bg-base, #f8fafc)',
                          border: '1px solid var(--border-subtle, #e2e8f0)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          gap: '14px',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flex: 1, minWidth: 0 }}>
                          <span className={`status-pill ${badgeClass}`} style={{ fontSize: '10px', minWidth: '65px', textAlign: 'center', flexShrink: 0 }}>
                            {eventType}
                          </span>
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', wordBreak: 'break-word' }}>
                              {summary}
                            </div>
                            <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '2px' }}>
                              Patient #{evt.patient_id || timelinePatientId} · Event log
                            </div>
                          </div>
                        </div>
                        <span style={{ fontSize: '11px', color: '#94a3b8', fontFamily: "'JetBrains Mono', monospace", flexShrink: 0 }}>
                          {timeStr}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: TASKS */}
          {activeNav === 'tasks' && (
            <div
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '12px',
                padding: '24px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <div style={{ marginBottom: '18px' }}>
                <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 4px 0' }}>Care team follow-up tasks</h2>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>Tasks created from alerts waiting for review</p>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {followUps.map((t, idx) => (
                  <div
                    key={t.followup_id || t.task_id || idx}
                    style={{
                      padding: '14px 18px',
                      borderRadius: '8px',
                      background: 'var(--bg-base, #f8fafc)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: '12px',
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                        {t.reason || t.task_title || t.title || 'Clinical Follow-up Task'}
                      </div>
                      <div style={{ fontSize: '12px', color: '#94a3b8', marginTop: '2px' }}>
                        Patient: {t.patient_name || (`#${t.patient_id}`)} · Assigned: {t.assigned_to || 'Staff'} · {t.hours_pending != null ? `Pending: ${t.hours_pending}h` : `Created: ${t.created_at?.slice(0, 16) || 'Today'}`}
                      </div>
                    </div>
                    <span className={`status-pill ${t.priority === 'Urgent_Review' || t.priority === 'High' ? 'status-pill-red' : 'status-pill-amber'}`}>
                      {t.priority}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: SUMMARIES */}
          {activeNav === 'summaries' && (
            <div
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '12px',
                padding: '24px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '18px' }}>
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 4px 0' }}>Draft summaries to review</h2>
                  <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>Review and approve drafts. AI draft, not reviewed.</p>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <select
                    value={summaryPatientId}
                    onChange={(e) => setSummaryPatientId(Number(e.target.value))}
                    style={{
                      padding: '7px 10px',
                      borderRadius: '8px',
                      border: '1px solid var(--border-strong, #cbd5e1)',
                      background: 'var(--bg-base, #ffffff)',
                      color: 'var(--text-primary, #0f172a)',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((pid) => (
                      <option key={pid} value={pid}>Patient #{pid}</option>
                    ))}
                  </select>
                  <button
                    type="button"
                    onClick={() => handleGenerateSummary(summaryPatientId)}
                    style={{
                      padding: '8px 14px',
                      borderRadius: '8px',
                      border: 'none',
                      background: '#0f172a',
                      color: '#ffffff',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    Create draft summary
                  </button>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {summaries.map((s) => (
                  <div
                    key={s.summary_id}
                    style={{
                      padding: '18px',
                      borderRadius: '8px',
                      background: 'var(--bg-base, #f8fafc)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                      <div>
                        <span style={{ fontSize: '14px', fontWeight: 800 }}>Draft Summary #{s.summary_id}</span>
                        <span style={{ fontSize: '12px', color: '#64748b', marginLeft: '10px' }}>
                          Patient: {s.patient_name || (`#${s.patient_id}`)} · Model: {s.model_name || 'LLM'} · Generated: {s.generated_at?.slice(0, 16).replace('T', ' ')}
                        </span>
                      </div>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          type="button"
                          onClick={() => handleReviewSummary(s.summary_id, 'Approve')}
                          style={{
                            padding: '5px 12px',
                            borderRadius: '6px',
                            border: 'none',
                            background: '#059669',
                            color: '#ffffff',
                            fontSize: '11px',
                            fontWeight: 700,
                            cursor: 'pointer',
                          }}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReviewSummary(s.summary_id, 'Reject')}
                          style={{
                            padding: '5px 12px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-strong, #cbd5e1)',
                            background: '#ffffff',
                            color: '#dc2626',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Reject
                        </button>
                      </div>
                    </div>
                    <div style={{ fontSize: '13px', color: '#475569', lineHeight: 1.55 }}>{s.summary_text}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
