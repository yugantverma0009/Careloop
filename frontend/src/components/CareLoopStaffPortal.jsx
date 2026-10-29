import React, { useState, useEffect, useRef } from 'react';
import {
  getStaffWorklist,
  getFlagDetail,
  getStaffMembers,
  acknowledgeFlag,
  getFollowUps,
  getPatientTimeline,
  getPendingSummaries,
  generateSummary,
  reviewSummary,
  logout,
} from '../services/api';
import PatientIdentity from './PatientIdentity';
import FlagDrawer from './FlagDrawer';
import PatientDirectory from './PatientDirectory';
import PatientOverviewTab from './PatientOverviewTab';
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
  IconPatient,
} from './Icons';

export default function CareLoopStaffPortal({ user }) {
  const [activeNav, setActiveNav] = useState('triage');
  const [worklistData, setWorklistData] = useState({ summary: {}, patients: [] });
  const [staffMembers, setStaffMembers] = useState([]);
  const [expandedPatientIds, setExpandedPatientIds] = useState(new Set());
  const [scopeFilter, setScopeFilter] = useState('all'); // 'all', 'mine', 'unassigned'
  const [statusFilter, setStatusFilter] = useState('open'); // 'open', 'seen', 'all'
  const [severityFilter, setSeverityFilter] = useState('all'); // 'all', 'immediate', 'urgent', 'review_soon', 'routine'
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFlag, setSelectedFlag] = useState(null);
  const [selectedPatientId, setSelectedPatientId] = useState(1);
  const [hoveredScorePid, setHoveredScorePid] = useState(null);
  const searchInputRef = useRef(null);

  const [followUps, setFollowUps] = useState([]);
  const [summaries, setSummaries] = useState([]);
  const [timelinePatientId, setTimelinePatientId] = useState(1);
  const [summaryPatientId, setSummaryPatientId] = useState(1);
  const [timelineEvents, setTimelineEvents] = useState([]);
  const [actionMsg, setActionMsg] = useState('');

  // Keyboard shortcut Ctrl+K / Cmd+K for search
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        searchInputRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleExportCSV = () => {
    const patients = worklistData.patients || [];
    if (!patients.length) {
      alert('No worklist records to export.');
      return;
    }
    const headers = ['Patient Code', 'Patient Name', 'Age', 'Condition', 'Attending Doctor', 'SLA Tier', 'Score', 'Open Flags', 'Distinct Reasons', 'Overdue'];
    const rows = patients.map((p) => [
      p.patient_code,
      `"${(p.full_name || '').replace(/"/g, '""')}"`,
      p.age_years || '',
      `"${(p.condition || '').replace(/"/g, '""')}"`,
      `"${(p.attending_doctor || '').replace(/"/g, '""')}"`,
      p.tier,
      p.attention_score,
      p.open_flag_count,
      p.distinct_reasons,
      p.is_overdue ? 'YES' : 'NO',
    ]);
    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `careloop_worklist_export_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const loadData = async () => {
    try {
      const [wl, staff, fu, sm] = await Promise.all([
        getStaffWorklist({
          scope: scopeFilter,
          status_filter: statusFilter,
          severity_filter: severityFilter,
          search: searchQuery,
        }).catch(() => ({ summary: {}, patients: [] })),
        getStaffMembers().catch(() => []),
        getFollowUps().catch(() => []),
        getPendingSummaries().catch(() => []),
      ]);
      setWorklistData(wl || { summary: {}, patients: [] });
      setStaffMembers(staff || []);
      setFollowUps(fu || []);
      setSummaries(sm || []);
      // Auto expand first patient if none expanded
      if (wl?.patients?.length > 0 && expandedPatientIds.size === 0) {
        setExpandedPatientIds(new Set([wl.patients[0].patient_id]));
      }
    } catch (err) {
      console.error('Error fetching clinical data', err);
    }
  };

  const togglePatientExpand = (pid) => {
    setExpandedPatientIds((prev) => {
      const next = new Set(prev);
      if (next.has(pid)) next.delete(pid);
      else next.add(pid);
      return next;
    });
  };

  const handleOpenFlagDrawer = async (flagId) => {
    try {
      const detail = await getFlagDetail(flagId);
      setSelectedFlag(detail);
    } catch (err) {
      alert(`Could not load flag details: ${err.message}`);
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
    const interval = setInterval(loadData, 15000);
    return () => clearInterval(interval);
  }, [scopeFilter, statusFilter, severityFilter, searchQuery]);

  useEffect(() => {
    if (activeNav === 'timeline') {
      loadTimeline(timelinePatientId);
    }
  }, [activeNav, timelinePatientId]);

  const handleQuickAcknowledge = async (flagId, e) => {
    e?.stopPropagation();
    try {
      await acknowledgeFlag(flagId, 'Acknowledged via worklist table');
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
                { id: 'triage', label: 'Who needs attention', Icon: IconAlertTriangle, badge: worklistData.patients?.length || 0 },
                { id: 'patients', label: 'Patient directory', Icon: IconPatient },
                { id: 'timeline', label: 'Patient timeline', Icon: IconActivity },
                { id: 'tasks', label: 'Follow-up tasks', Icon: IconCheck, badge: followUps.length },
                { id: 'summaries', label: 'Draft summaries', Icon: IconFileText, badge: summaries.length },
              ].map((item) => {
                const isActive = activeNav === item.id || (item.id === 'patients' && activeNav === 'patient_chart');
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

          {/* TAB 1: GROUPED CLINICIAN WORKLIST (D-02, D-03, D-04) */}
          {activeNav === 'triage' && (
            <>
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
              {/* 4 KPI Summary Cards */}
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: 'repeat(4, 1fr)',
                  gap: '18px',
                  marginBottom: '24px',
                }}
              >
                {/* Card 1: Cohort Patients with Flags */}
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
                    Patients needing attention
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {worklistData.summary?.total_patients ?? 0}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    {worklistData.summary?.total_open_flags ?? 0} open flags across cohort
                  </div>
                </div>

                {/* Card 2: Immediate Review Target */}
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
                      background: '#fef2f2',
                      border: '1px solid #fecaca',
                      color: '#dc2626',
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
                      color: (worklistData.summary?.immediate_count || 0) > 0 ? '#dc2626' : 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                    }}
                  >
                    {worklistData.summary?.immediate_count ?? 0}
                    {(worklistData.summary?.immediate_count || 0) > 0 && (
                      <span
                        style={{
                          width: '10px',
                          height: '10px',
                          borderRadius: '50%',
                          background: '#ef4444',
                          display: 'inline-block',
                          boxShadow: '0 0 0 4px rgba(239, 68, 68, 0.2)',
                        }}
                      />
                    )}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    Target: under 15 minutes
                  </div>
                </div>

                {/* Card 3: Urgent Review Target */}
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
                      background: '#fffbeb',
                      border: '1px solid #fde68a',
                      color: '#b45309',
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
                    {worklistData.summary?.urgent_count ?? 0}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    Target: under 2 hours
                  </div>
                </div>

                {/* Card 4: Overdue SLAs */}
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
                      background: (worklistData.summary?.overdue_count || 0) > 0 ? '#fef2f2' : '#f0fdf4',
                      border: `1px solid ${(worklistData.summary?.overdue_count || 0) > 0 ? '#fecaca' : '#bbf7d0'}`,
                      color: (worklistData.summary?.overdue_count || 0) > 0 ? '#dc2626' : '#15803d',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    <IconShieldCheck width={18} height={18} />
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Overdue targets
                  </div>
                  <div
                    style={{
                      fontSize: '28px',
                      fontWeight: 800,
                      color: (worklistData.summary?.overdue_count || 0) > 0 ? '#dc2626' : 'var(--text-primary, #0f172a)',
                      margin: '6px 0 2px',
                    }}
                  >
                    {worklistData.summary?.overdue_count ?? 0}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                    {worklistData.summary?.not_yet_seen_count ?? 0} flags not yet seen
                  </div>
                </div>
              </div>

              {/* Worklist Container */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '22px 24px',
                  boxShadow: 'var(--shadow-card)',
                  marginBottom: '24px',
                }}
              >
                {/* Toolbar: Search & Multi-Filters */}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '16px',
                    marginBottom: '20px',
                    paddingBottom: '16px',
                    borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                  }}
                >
                  {/* Top Row: Search & Scope Filter */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
                    {/* Search Input (Ctrl+K) */}
                    <div style={{ position: 'relative', flex: '1', minWidth: '280px', maxWidth: '440px' }}>
                      <input
                        ref={searchInputRef}
                        type="text"
                        placeholder="Search patient, code (CL-00001), condition, or reason... (Ctrl+K)"
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        style={{
                          width: '100%',
                          padding: '9px 14px 9px 36px',
                          borderRadius: '8px',
                          border: '1px solid var(--border-subtle, #cbd5e1)',
                          background: 'var(--bg-base, #f8fafc)',
                          fontSize: '13px',
                          color: 'var(--text-primary, #0f172a)',
                          outline: 'none',
                          boxSizing: 'border-box',
                        }}
                      />
                      <div style={{ position: 'absolute', left: '12px', top: '10px', color: '#94a3b8' }}>
                        <IconSearch width={16} height={16} />
                      </div>
                      {searchQuery && (
                        <button
                          type="button"
                          onClick={() => setSearchQuery('')}
                          style={{
                            position: 'absolute',
                            right: '10px',
                            top: '8px',
                            background: 'transparent',
                            border: 'none',
                            color: '#94a3b8',
                            cursor: 'pointer',
                            fontSize: '12px',
                          }}
                        >
                          ✕
                        </button>
                      )}
                    </div>

                    {/* Scope Filter Chips */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', marginRight: '4px' }}>
                        Scope:
                      </span>
                      {[
                        { key: 'all', label: 'All Patients' },
                        { key: 'mine', label: 'My Assigned' },
                        { key: 'unassigned', label: 'Unassigned' },
                      ].map(({ key, label }) => (
                        <button
                          key={key}
                          type="button"
                          onClick={() => setScopeFilter(key)}
                          style={{
                            padding: '5px 12px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                            background: scopeFilter === key ? '#0f172a' : 'var(--bg-base, #f8fafc)',
                            color: scopeFilter === key ? '#ffffff' : 'var(--text-secondary, #475569)',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Bottom Row: Status & Severity Filters */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '16px', flexWrap: 'wrap' }}>
                    {/* Status Filter */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', marginRight: '4px' }}>
                        Status:
                      </span>
                      {[
                        { key: 'all', label: 'All Flags' },
                        { key: 'open', label: 'Not yet seen (Open)' },
                        { key: 'seen', label: 'Seen (Acknowledged)' },
                      ].map(({ key, label }) => (
                        <button
                          key={key}
                          type="button"
                          onClick={() => setStatusFilter(key)}
                          style={{
                            padding: '4px 10px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                            background: statusFilter === key ? '#0f172a' : 'var(--bg-base, #f8fafc)',
                            color: statusFilter === key ? '#ffffff' : 'var(--text-secondary, #475569)',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          {label}
                        </button>
                      ))}
                    </div>

                    {/* Severity Filter */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: '#64748b', marginRight: '4px' }}>
                        Severity Tier:
                      </span>
                      {[
                        { key: 'all', label: 'All Tiers' },
                        { key: 'immediate', label: 'Immediate (<15m)' },
                        { key: 'urgent', label: 'Urgent (<2h)' },
                        { key: 'review_soon', label: 'Review soon' },
                        { key: 'routine', label: 'Routine' },
                      ].map(({ key, label }) => (
                        <button
                          key={key}
                          type="button"
                          onClick={() => setSeverityFilter(key)}
                          style={{
                            padding: '4px 10px',
                            borderRadius: '6px',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                            background: severityFilter === key ? '#0f172a' : 'var(--bg-base, #f8fafc)',
                            color: severityFilter === key ? '#ffffff' : 'var(--text-secondary, #475569)',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Worklist Patient Cards List */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {worklistData.patients.length === 0 ? (
                    <div
                      style={{
                        padding: '48px 24px',
                        textAlign: 'center',
                        color: 'var(--text-muted, #94a3b8)',
                        fontSize: '13px',
                      }}
                    >
                      <div>No patient flags match the selected filters.</div>
                      {(scopeFilter !== 'all' || statusFilter !== 'all' || severityFilter !== 'all' || searchQuery) && (
                        <button
                          type="button"
                          onClick={() => {
                            setScopeFilter('all');
                            setStatusFilter('all');
                            setSeverityFilter('all');
                            setSearchQuery('');
                          }}
                          style={{
                            marginTop: '12px',
                            padding: '6px 14px',
                            borderRadius: '6px',
                            border: '1px solid #cbd5e1',
                            background: '#ffffff',
                            color: '#0f172a',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          Reset Filters
                        </button>
                      )}
                    </div>
                  ) : (
                    worklistData.patients.map((patient) => {
                      const isExpanded = expandedPatientIds.has(patient.patient_id);
                      const isImmediate = patient.tier === 'Immediate';
                      const isUrgent = patient.tier === 'Urgent';

                      return (
                        <div
                          key={patient.patient_id}
                          style={{
                            borderRadius: '10px',
                            border: `1px solid ${isImmediate ? '#fca5a5' : isUrgent ? '#fde68a' : 'var(--border-subtle, #e2e8f0)'}`,
                            background: 'var(--bg-surface, #ffffff)',
                            overflow: 'visible',
                            transition: 'all 0.15s ease',
                            boxShadow: isExpanded ? '0 4px 12px rgba(0,0,0,0.04)' : 'none',
                          }}
                        >
                          {/* Collapsed Patient Header Row */}
                          <div
                            onClick={() => togglePatientExpand(patient.patient_id)}
                            style={{
                              padding: '16px 20px',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              cursor: 'pointer',
                              background: isImmediate ? 'rgba(254, 242, 242, 0.4)' : 'transparent',
                              gap: '16px',
                              flexWrap: 'wrap',
                            }}
                          >
                            {/* Left: Chevron, Attention Score, PatientIdentity */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '14px', minWidth: '320px' }}>
                              {/* Chevron */}
                              <span
                                style={{
                                  fontSize: '12px',
                                  color: '#94a3b8',
                                  transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                                  transition: 'transform 0.15s ease',
                                  userSelect: 'none',
                                }}
                              >
                                ▶
                              </span>

                              {/* Explainable Attention Score Pill with hover breakdown */}
                              <div
                                style={{ position: 'relative' }}
                                onMouseEnter={() => setHoveredScorePid(patient.patient_id)}
                                onMouseLeave={() => setHoveredScorePid(null)}
                              >
                                <span
                                  style={{
                                    display: 'inline-flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    minWidth: '40px',
                                    padding: '4px 6px',
                                    borderRadius: '8px',
                                    background: isImmediate ? '#fee2e2' : isUrgent ? '#fef3c7' : '#f1f5f9',
                                    color: isImmediate ? '#991b1b' : isUrgent ? '#92400e' : '#334155',
                                    fontWeight: 800,
                                    fontSize: '13px',
                                    fontFamily: "'JetBrains Mono', monospace",
                                    border: `1px solid ${isImmediate ? '#fecaca' : isUrgent ? '#fde68a' : '#e2e8f0'}`,
                                  }}
                                  title="Clinical Attention Score (Click/hover for breakdown)"
                                >
                                  {patient.attention_score}
                                  <span style={{ fontSize: '9px', fontWeight: 600, color: '#64748b', textTransform: 'uppercase' }}>
                                    SCORE
                                  </span>
                                </span>

                                {/* Attention Factors Tooltip */}
                                {hoveredScorePid === patient.patient_id && (
                                  <div
                                    style={{
                                      position: 'absolute',
                                      top: '100%',
                                      left: '0',
                                      marginTop: '8px',
                                      width: '260px',
                                      padding: '12px 14px',
                                      borderRadius: '8px',
                                      background: '#0f172a',
                                      color: '#ffffff',
                                      fontSize: '12px',
                                      zIndex: 100,
                                      boxShadow: '0 8px 24px rgba(0,0,0,0.25)',
                                      lineHeight: '1.4',
                                      pointerEvents: 'none',
                                    }}
                                  >
                                    <div style={{ fontWeight: 700, marginBottom: '6px', borderBottom: '1px solid #334155', paddingBottom: '4px' }}>
                                      Attention Score: {patient.attention_score}/100
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                      {patient.attention_factors?.map((f, i) => (
                                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', color: '#cbd5e1' }}>
                                          <span>{f.label}</span>
                                          <span style={{ fontWeight: 700, color: '#38bdf8' }}>+{f.points}</span>
                                        </div>
                                      ))}
                                    </div>
                                    <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '6px', fontStyle: 'italic' }}>
                                      Weights are configurable and capped to prevent saturation.
                                    </div>
                                  </div>
                                )}
                              </div>

                              {/* PatientIdentity upholding 2-identifier clinical safety */}
                              <PatientIdentity patient={patient} size="md" showCondition={true} />
                            </div>

                            {/* Middle: SLA Tier Chip & Overdue badge */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                              <span
                                style={{
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  padding: '4px 10px',
                                  borderRadius: '6px',
                                  background: isImmediate ? '#fef2f2' : isUrgent ? '#fffbeb' : '#eff6ff',
                                  color: isImmediate ? '#dc2626' : isUrgent ? '#b45309' : '#1d4ed8',
                                  border: `1px solid ${isImmediate ? '#fecaca' : isUrgent ? '#fde68a' : '#bfdbfe'}`,
                                  display: 'inline-flex',
                                  alignItems: 'center',
                                  gap: '6px',
                                }}
                              >
                                {isImmediate && (
                                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#dc2626' }} />
                                )}
                                {patient.tier} (Target: {patient.sla_target})
                              </span>

                              {patient.is_overdue && (
                                <span
                                  style={{
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    padding: '4px 8px',
                                    borderRadius: '6px',
                                    background: '#fef2f2',
                                    color: '#b91c1c',
                                    border: '1px solid #fca5a5',
                                  }}
                                >
                                  ⚠️ {patient.overdue_display || 'Overdue SLA'}
                                </span>
                              )}
                            </div>

                            {/* Right: Flag Counts & Timestamps */}
                            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                              <div style={{ textAlign: 'right', fontSize: '12px' }}>
                                <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                                  {patient.open_flag_count} open flags · {patient.distinct_reasons} distinct reasons
                                </div>
                                <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                                  {patient.not_yet_seen > 0 && (
                                    <span style={{ color: '#dc2626', fontWeight: 700, marginRight: '6px' }}>
                                      {patient.not_yet_seen} not seen ·
                                    </span>
                                  )}
                                  First: {patient.first_flag_at ? new Date(patient.first_flag_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'} · Latest: {patient.latest_flag_at ? new Date(patient.latest_flag_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '-'}
                                </div>
                              </div>

                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  togglePatientExpand(patient.patient_id);
                                }}
                                style={{
                                  padding: '6px 14px',
                                  borderRadius: '6px',
                                  border: '1px solid var(--border-subtle, #cbd5e1)',
                                  background: 'var(--bg-base, #f8fafc)',
                                  color: 'var(--text-primary, #0f172a)',
                                  fontSize: '12px',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                }}
                              >
                                {isExpanded ? 'Collapse' : `View Flags (${patient.open_flag_count})`}
                              </button>

                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setSelectedPatientId(patient.patient_id);
                                  setActiveNav('patient_chart');
                                }}
                                style={{
                                  padding: '6px 12px',
                                  borderRadius: '6px',
                                  border: 'none',
                                  background: '#0b1528',
                                  color: '#ffffff',
                                  fontSize: '12px',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                }}
                              >
                                Open Chart →
                              </button>
                            </div>
                          </div>

                          {/* Expanded Nested Flags Table */}
                          {isExpanded && (
                            <div
                              style={{
                                borderTop: '1px solid var(--border-subtle, #e2e8f0)',
                                background: 'var(--bg-base, #f8fafc)',
                                padding: '16px 20px',
                              }}
                            >
                              <div style={{ fontSize: '12px', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '10px' }}>
                                Individual Flags for {patient.full_name} ({patient.patient_code})
                              </div>

                              <div style={{ overflowX: 'auto' }}>
                                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '12px' }}>
                                  <thead>
                                    <tr style={{ borderBottom: '1px solid #cbd5e1', color: '#64748b' }}>
                                      <th style={{ padding: '8px 10px', fontWeight: 700 }}>SEVERITY</th>
                                      <th style={{ padding: '8px 10px', fontWeight: 700 }}>SOURCE</th>
                                      <th style={{ padding: '8px 10px', fontWeight: 700 }}>REASON</th>
                                      <th style={{ padding: '8px 10px', fontWeight: 700 }}>FLAGGED AT</th>
                                      <th style={{ padding: '8px 10px', fontWeight: 700 }}>STATUS</th>
                                      <th style={{ padding: '8px 10px', fontWeight: 700, textAlign: 'right' }}>ACTIONS</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {patient.flags.map((flag) => {
                                      const isFlagOpen = flag.status === 'Open';
                                      const isFlagAck = flag.status === 'Acknowledged';

                                      return (
                                        <tr
                                          key={flag.flag_id}
                                          style={{
                                            borderBottom: '1px solid #e2e8f0',
                                            background: '#ffffff',
                                            transition: 'background 0.15s ease',
                                          }}
                                          onMouseEnter={(e) => (e.currentTarget.style.background = '#f8fafc')}
                                          onMouseLeave={(e) => (e.currentTarget.style.background = '#ffffff')}
                                        >
                                          {/* Severity */}
                                          <td style={{ padding: '10px' }}>
                                            {flag.severity === 'Urgent_Review' ? (
                                              <span className="status-pill status-pill-red">Urgent</span>
                                            ) : flag.severity === 'Review_Soon' ? (
                                              <span className="status-pill status-pill-amber">Review Soon</span>
                                            ) : (
                                              <span className="status-pill status-pill-blue">Routine</span>
                                            )}
                                          </td>

                                          {/* Source */}
                                          <td style={{ padding: '10px', color: '#475569', fontWeight: 600 }}>
                                            {flag.source_type}
                                          </td>

                                          {/* Reason (with deduplicated count if repeated D-04) */}
                                          <td style={{ padding: '10px', color: '#0f172a', maxWidth: '380px' }}>
                                            <div style={{ fontWeight: 600 }}>
                                              {flag.reason}
                                              {flag.occurrence_count > 1 && (
                                                <span
                                                  style={{
                                                    marginLeft: '6px',
                                                    padding: '1px 6px',
                                                    borderRadius: '4px',
                                                    background: '#fee2e2',
                                                    color: '#b91c1c',
                                                    fontWeight: 700,
                                                    fontSize: '11px',
                                                  }}
                                                >
                                                  ×{flag.occurrence_count} reports
                                                </span>
                                              )}
                                            </div>
                                            {flag.occurrence_count > 1 && (
                                              <div style={{ fontSize: '10px', color: '#94a3b8', marginTop: '2px' }}>
                                                First: {new Date(flag.first_created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · Last: {new Date(flag.last_created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                              </div>
                                            )}
                                          </td>

                                          {/* Flagged At */}
                                          <td style={{ padding: '10px', color: '#64748b', fontFamily: "'JetBrains Mono', monospace" }}>
                                            {new Date(flag.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                                            <div style={{ fontSize: '10px', color: '#94a3b8' }}>
                                              {flag.hours_open}h open
                                            </div>
                                          </td>

                                          {/* Status */}
                                          <td style={{ padding: '10px' }}>
                                            <span
                                              style={{
                                                fontSize: '11px',
                                                fontWeight: 700,
                                                padding: '2px 8px',
                                                borderRadius: '4px',
                                                background: isFlagOpen ? '#fef2f2' : isFlagAck ? '#f0fdf4' : '#f1f5f9',
                                                color: isFlagOpen ? '#dc2626' : isFlagAck ? '#16a34a' : '#64748b',
                                              }}
                                            >
                                              {flag.status}
                                            </span>
                                            {flag.acknowledged_by_name && (
                                              <div style={{ fontSize: '10px', color: '#64748b', marginTop: '2px' }}>
                                                by {flag.acknowledged_by_name}
                                              </div>
                                            )}
                                          </td>

                                          {/* Actions */}
                                          <td style={{ padding: '10px', textAlign: 'right' }}>
                                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                                              {isFlagOpen && (
                                                <button
                                                  type="button"
                                                  onClick={(e) => handleQuickAcknowledge(flag.flag_id, e)}
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
                                              )}

                                              <button
                                                type="button"
                                                onClick={() => handleOpenFlagDrawer(flag.flag_id)}
                                                style={{
                                                  padding: '5px 10px',
                                                  borderRadius: '6px',
                                                  border: '1px solid #cbd5e1',
                                                  background: isFlagAck ? '#f0fdf4' : '#ffffff',
                                                  color: isFlagAck ? '#166534' : '#0f172a',
                                                  fontSize: '11px',
                                                  fontWeight: 600,
                                                  cursor: 'pointer',
                                                }}
                                              >
                                                {isFlagAck ? 'Resolve Flag...' : 'Detail Drawer'}
                                              </button>
                                            </div>
                                          </td>
                                        </tr>
                                      );
                                    })}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </>
          )}

          {/* TAB: PATIENT DIRECTORY (Phase 2, D-05) */}
          {activeNav === 'patients' && (
            <PatientDirectory
              onSelectPatient={(pid) => {
                setSelectedPatientId(pid);
                setActiveNav('patient_chart');
              }}
              currentStaffId={user?.staff_id}
            />
          )}

          {/* TAB: PATIENT CLINICAL CHART (Phase 2, D-05, D-06, D-12, D-18) */}
          {activeNav === 'patient_chart' && (
            <PatientOverviewTab
              patientId={selectedPatientId || 1}
              onBackToDirectory={() => setActiveNav('patients')}
              onOpenFlagDrawer={handleOpenFlagDrawer}
              user={user}
            />
          )}

          {/* TAB 2: UPGRADED TIMELINE (Phase 2, D-06) */}
          {activeNav === 'timeline' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '16px 20px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <h2 style={{ fontSize: '18px', fontWeight: 800, margin: '0 0 4px 0' }}>Patient Telemetry & Event Timeline</h2>
                  <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>Select a post-discharge patient to inspect chronological telemetry, symptoms, and self-reported doses</p>
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
                        background: timelinePatientId === pid ? '#0b1528' : 'var(--bg-surface, #ffffff)',
                        color: timelinePatientId === pid ? '#ffffff' : 'var(--text-primary, #0f172a)',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      CL-0000{pid}
                    </button>
                  ))}
                </div>
              </div>

              <PatientOverviewTab
                patientId={timelinePatientId || 1}
                onOpenFlagDrawer={handleOpenFlagDrawer}
                user={user}
              />
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

      {/* Flag Detail Drawer (D-03, D-10, D-18) */}
      {selectedFlag && (
        <FlagDrawer
          flag={selectedFlag}
          staffMembers={staffMembers}
          currentStaffId={user?.staff_id}
          onClose={() => setSelectedFlag(null)}
          onActionSuccess={(msg) => {
            setActionMsg(msg);
            setTimeout(() => setActionMsg(''), 4000);
            loadData();
          }}
        />
      )}
    </div>
  );
}
