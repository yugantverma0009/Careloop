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
  getStaffNotifications,
  globalStaffSearch,
  getDoctorDecisions,
  getNurseCallList,
  simulateInboundSms,
  logout,
  API_BASE,
} from '../services/api';
import PatientIdentity from './PatientIdentity';
import FlagDrawer from './FlagDrawer';
import PatientDirectory from './PatientDirectory';
import PatientOverviewTab from './PatientOverviewTab';
import TaskQueue from './TaskQueue';
import ClinicalSummaries from './ClinicalSummaries';
import ShiftHandoff from './ShiftHandoff';
import AuditLogViewer from './AuditLogViewer';
import OperationalInsights from './OperationalInsights';
import DoctorLimitsView from './DoctorLimitsView';
import DoctorFhirExportView from './DoctorFhirExportView';
import NurseCallListView from './NurseCallListView';
import RoundsView from './RoundsView';
import AdmitPatientWizard from './AdmitPatientWizard';
import AgentDesk from './AgentDesk';
import AgentSettingsView from './AgentSettingsView';
import AgentHealthView from './AgentHealthView';
import WorkSavedPanel from './WorkSavedPanel';
import AgentTraceModal from './AgentTraceModal';
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
  IconBell,
  IconExternalLink,
} from './Icons';

function RestrictedNurseView({ pageName }) {
  return (
    <div
      style={{
        background: 'var(--bg-surface, #ffffff)',
        border: '1px solid #fecaca',
        borderRadius: '12px',
        padding: '40px 24px',
        textAlign: 'center',
        boxShadow: 'var(--shadow-card)',
        maxWidth: '560px',
        margin: '40px auto',
      }}
    >
      <div style={{ fontSize: '36px', marginBottom: '12px' }}>🔒</div>
      <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#dc2626', margin: '0 0 8px 0' }}>
        Access Restricted to Attending Physicians
      </h2>
      <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', lineHeight: '1.5', margin: '0 auto 18px auto' }}>
        Clinical Governance Policy: {pageName} is reserved exclusively for Dr. Ananya Sharma. Nurses may propose limit adjustments via the call list or patient chart.
      </p>
      <button
        type="button"
        onClick={() => { window.location.href = '/nurse'; }}
        style={{
          display: 'inline-block',
          padding: '8px 18px',
          borderRadius: '8px',
          border: 'none',
          background: '#0284c7',
          color: '#ffffff',
          fontSize: '12px',
          fontWeight: 700,
          cursor: 'pointer',
        }}
      >
        ← Return to My Call List
      </button>
    </div>
  );
}

export default function CareLoopStaffPortal({ user, defaultRole }) {
  const effectiveRole = user?.role || user?.account_role || defaultRole || 'Doctor';
  const isDoctor = effectiveRole === 'Doctor';
  const isNurse = effectiveRole === 'Nurse';

  const roleAccent = isDoctor ? 'var(--role-doctor, #7c3aed)' : 'var(--role-nurse, #0284c7)';
  const roleAccentSoft = isDoctor ? 'var(--role-doctor-soft, #f5f3ff)' : 'var(--role-nurse-soft, #eff6ff)';
  const roleAccentText = isDoctor ? 'var(--role-doctor-text, #6d28d9)' : 'var(--role-nurse-text, #0369a1)';
  const roleSubtitle = isDoctor ? 'Doctor desk' : 'Nurse desk';
  const roleSectionKicker = isDoctor ? 'DOCTOR DESK' : 'NURSE DESK';
  const roleFirstScreenTitle = isDoctor ? 'Needs my decision' : 'My call list';

  const [activeNav, setActiveNav] = useState('triage');
  const [worklistData, setWorklistData] = useState({ summary: {}, patients: [] });
  const [staffMembers, setStaffMembers] = useState([]);
  const [expandedPatientIds, setExpandedPatientIds] = useState(new Set());
  const [scopeFilter, setScopeFilter] = useState('mine'); // Defaults to 'mine' per D-12
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
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationsData, setNotificationsData] = useState({ count: 0, notifications: [] });

  // Doctor Decision Desk State (Phase 3)
  const [doctorDecisions, setDoctorDecisions] = useState({
    cards: { needs_decision_now: 0, summaries_to_approve: 0, limit_change_requests: 0, patients_in_followup: 5 },
    items: [],
    quiet_patients: { count: 0, patients: [], message: '' },
  });
  const [doctorTraceRunId, setDoctorTraceRunId] = useState(null);

  const handleDoctorCaseDecide = async (caseId, actionKey, note = '') => {
    try {
      const token = localStorage.getItem('careloop_token');
      const res = await fetch(`${API_BASE}/cases/${caseId}/decide`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ action: actionKey, note: note || `Physician selected ${actionKey}` })
      });
      if (res.ok) {
        setActionMsg(`✓ Action '${actionKey}' recorded.`);
        setTimeout(() => setActionMsg(''), 4000);
        loadData();
      }
    } catch (err) {
      console.error('Failed to decide case', err);
    }
  };

  // Nurse Call List State (Phase 4)
  const [nurseCallCount, setNurseCallCount] = useState(3);

  // D-21 Command Palette & Shortcuts State
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [commandQuery, setCommandQuery] = useState('');
  const [commandResults, setCommandResults] = useState({ patients: [], flags: [], tasks: [], notes: [] });
  const [commandLoading, setCommandLoading] = useState(false);
  const [shortcutsModalOpen, setShortcutsModalOpen] = useState(false);
  const [highlightedRowIndex, setHighlightedRowIndex] = useState(0);

  // Phase 2 Feature F3: SMS Patient Simulator State
  const [smsSimOpen, setSmsSimOpen] = useState(false);
  const [smsSimPhone, setSmsSimPhone] = useState('+91-98765-00001');
  const [smsSimBody, setSmsSimBody] = useState('1');
  const [smsSimLoading, setSmsSimLoading] = useState(false);
  const [smsSimResult, setSmsSimResult] = useState(null);
  const [smsSimError, setSmsSimError] = useState(null);

  const handleSimulateSms = async (overrideBody = null) => {
    const textToSend = overrideBody !== null ? overrideBody : smsSimBody;
    if (!textToSend || !textToSend.trim()) return;
    setSmsSimLoading(true);
    setSmsSimError(null);
    setSmsSimResult(null);
    try {
      const res = await simulateInboundSms(smsSimPhone, textToSend.trim());
      setSmsSimResult(res);
      loadData();
    } catch (err) {
      setSmsSimError(err.message || 'SMS simulation failed');
    } finally {
      setSmsSimLoading(false);
    }
  };

  // D-12 Idle Timeout (15 minutes)
  useEffect(() => {
    let timeoutId;
    const IDLE_LIMIT_MS = 15 * 60 * 1000; // 15 minutes

    const resetTimer = () => {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => {
        alert('Your session has timed out due to 15 minutes of inactivity for DPDP security compliance.');
        logout();
        window.location.href = '/login?reason=idle_timeout';
      }, IDLE_LIMIT_MS);
    };

    const events = ['mousedown', 'mousemove', 'keydown', 'scroll', 'touchstart'];
    events.forEach((ev) => window.addEventListener(ev, resetTimer));
    resetTimer();

    return () => {
      clearTimeout(timeoutId);
      events.forEach((ev) => window.removeEventListener(ev, resetTimer));
    };
  }, []);

  // D-21 Global Keyboard Shortcuts (Ctrl+K, ?, j, k, o, Esc)
  useEffect(() => {
    const handleKeyDown = (e) => {
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      const isInput = activeTag === 'input' || activeTag === 'textarea' || activeTag === 'select';

      // 1. Ctrl+K or Cmd+K: Open Command Palette
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(true);
        return;
      }

      // 2. Escape key
      if (e.key === 'Escape') {
        if (commandPaletteOpen) {
          setCommandPaletteOpen(false);
          return;
        }
        if (shortcutsModalOpen) {
          setShortcutsModalOpen(false);
          return;
        }
        if (notificationsOpen) {
          setNotificationsOpen(false);
          return;
        }
        if (selectedFlag) {
          setSelectedFlag(null);
          return;
        }
      }

      // 3. ? key opens Shortcuts Cheat Sheet (when not typing)
      if (e.key === '?' && !isInput) {
        e.preventDefault();
        setShortcutsModalOpen((prev) => !prev);
        return;
      }

      // 4. Worklist j / k row navigation (when on triage and not typing)
      if (!isInput && activeNav === 'triage') {
        const patients = worklistData.patients || [];
        if (!patients.length) return;

        if (e.key === 'j') {
          e.preventDefault();
          setHighlightedRowIndex((prev) => Math.min(prev + 1, patients.length - 1));
        } else if (e.key === 'k') {
          e.preventDefault();
          setHighlightedRowIndex((prev) => Math.max(prev - 1, 0));
        } else if (e.key === 'o') {
          e.preventDefault();
          const targetPatient = patients[highlightedRowIndex];
          if (targetPatient) {
            setSelectedPatientId(targetPatient.patient_id);
            setActiveNav('patient_chart');
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, shortcutsModalOpen, notificationsOpen, selectedFlag, activeNav, worklistData, highlightedRowIndex]);

  // Search execution for Command Palette (D-21)
  useEffect(() => {
    if (!commandPaletteOpen || !commandQuery.trim() || commandQuery.trim().length < 2) {
      setCommandResults({ patients: [], flags: [], tasks: [], notes: [] });
      return;
    }
    const timer = setTimeout(async () => {
      setCommandLoading(true);
      try {
        const data = await globalStaffSearch(commandQuery.trim());
        setCommandResults(data || { patients: [], flags: [], tasks: [], notes: [] });
      } catch (err) {
        console.error('Command search failed:', err);
      } finally {
        setCommandLoading(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [commandPaletteOpen, commandQuery]);

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
      const [wl, staff, fu, sm, notifs] = await Promise.all([
        getStaffWorklist({
          scope: scopeFilter,
          status_filter: statusFilter,
          severity_filter: severityFilter,
          search: searchQuery,
        }).catch(() => ({ summary: {}, patients: [] })),
        getStaffMembers().catch(() => []),
        getFollowUps().catch(() => []),
        getPendingSummaries().catch(() => []),
        getStaffNotifications().catch(() => ({ count: 0, notifications: [] })),
      ]);
      setWorklistData(wl || { summary: {}, patients: [] });
      setStaffMembers(staff || []);
      setFollowUps(fu || []);
      setSummaries(sm || []);
      setNotificationsData(notifs || { count: 0, notifications: [] });

      // Fetch Doctor Decision Desk items if Doctor
      if (isDoctor) {
        const dd = await getDoctorDecisions().catch(() => null);
        if (dd) setDoctorDecisions(dd);
      } else if (isNurse) {
        const ncl = await getNurseCallList().catch(() => null);
        if (ncl) setNurseCallCount(ncl.cards?.calls_to_make || 0);
      }
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
                Care<span style={{ color: roleAccent }}>Loop</span>
              </div>
              <div style={{ fontSize: '11px', color: roleAccent, fontWeight: 700 }}>
                {roleSubtitle}
              </div>
            </div>
          </div>

          {/* Navigation Links */}
          <div style={{ padding: '20px 14px' }}>
            <div
              style={{
                fontSize: '10px',
                fontWeight: 800,
                color: 'var(--text-muted, #94a3b8)',
                letterSpacing: '0.06em',
                textTransform: 'uppercase',
                padding: '0 10px',
                marginBottom: '10px',
              }}
            >
              {roleSectionKicker}
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '3px', marginBottom: '22px' }}>
              {(isDoctor
                ? [
                    { id: 'triage', label: 'Needs my decision', Icon: IconAlertTriangle, badge: doctorDecisions.cards?.needs_decision_now || 0 },
                    { id: 'agent_desk', label: 'Agent desk', Icon: IconActivity },
                    { id: 'work_saved', label: 'Work saved', Icon: IconActivity },
                    { id: 'agent_settings', label: 'Agent settings', Icon: IconShieldCheck },
                    { id: 'agent_health', label: 'Agent health', Icon: IconActivity },
                    { id: 'patients', label: 'Patients', Icon: IconPatient },
                    { id: 'admit', label: 'Admit patient', Icon: IconPatient },
                    { id: 'rounds', label: 'Rounds', Icon: IconClock },
                    { id: 'summaries', label: 'Approvals', Icon: IconFileText, badge: (doctorDecisions.cards?.summaries_to_approve || 0) + (doctorDecisions.cards?.limit_change_requests || 0) + (doctorDecisions.cards?.plans_to_approve || 0) },
                    { id: 'limits', label: 'Patient limits', Icon: IconShieldCheck },
                    { id: 'handoff', label: 'Shift handoff', Icon: IconActivity },
                    { id: 'audit', label: 'Audit log viewer', Icon: IconShieldCheck },
                    { id: 'fhir', label: 'Export FHIR bundle', Icon: IconExternalLink },
                  ]
                : [
                    { id: 'triage', label: 'My call list', Icon: IconAlertTriangle, badge: nurseCallCount },
                    { id: 'agent_desk', label: 'Agent desk', Icon: IconActivity },
                    { id: 'work_saved', label: 'Work saved', Icon: IconActivity },
                    { id: 'agent_settings', label: 'Agent settings', Icon: IconShieldCheck },
                    { id: 'agent_health', label: 'Agent health', Icon: IconActivity },
                    { id: 'patients', label: 'Patients', Icon: IconPatient },
                    { id: 'admit', label: 'Admit patient', Icon: IconPatient },
                    { id: 'rounds', label: 'Rounds', Icon: IconClock },
                    { id: 'handoff', label: 'Shift handoff', Icon: IconActivity },
                  ]
              ).map((item) => {
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
                      background: isActive ? roleAccentSoft : 'transparent',
                      color: isActive ? roleAccent : 'var(--text-secondary, #475569)',
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
                          background: isActive ? roleAccent : '#e2e8f0',
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
            <div style={{ fontSize: '10px', color: roleAccent, fontWeight: 800, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
              {roleSectionKicker}
            </div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
              {activeNav === 'triage' ? roleFirstScreenTitle : activeNav.toUpperCase()}
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
            {/* Notification Bell (D-11) */}
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                style={{
                  position: 'relative',
                  width: '36px',
                  height: '36px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-strong, #cbd5e1)',
                  background: 'var(--bg-base, #ffffff)',
                  color: 'var(--text-primary, #0f172a)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                }}
                title="Actionable Notifications"
              >
                <IconBell width={18} height={18} />
                {notificationsData.count > 0 && (
                  <span
                    style={{
                      position: 'absolute',
                      top: '-4px',
                      right: '-4px',
                      background: '#ef4444',
                      color: '#ffffff',
                      fontSize: '10px',
                      fontWeight: 800,
                      borderRadius: '10px',
                      padding: '1px 5px',
                      minWidth: '16px',
                      textAlign: 'center',
                    }}
                  >
                    {notificationsData.count}
                  </span>
                )}
              </button>

              {/* Dropdown panel */}
              {notificationsOpen && (
                <div
                  style={{
                    position: 'absolute',
                    top: '44px',
                    right: 0,
                    width: '360px',
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    boxShadow: 'var(--shadow-lg)',
                    padding: '16px',
                    zIndex: 50,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                    maxHeight: '420px',
                    overflowY: 'auto',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid var(--border-subtle, #e2e8f0)', paddingBottom: '8px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                      Actionable Alerts ({notificationsData.count})
                    </div>
                    <button
                      type="button"
                      onClick={() => setNotificationsOpen(false)}
                      style={{ border: 'none', background: 'transparent', fontSize: '12px', color: '#94a3b8', cursor: 'pointer' }}
                    >
                      ✕
                    </button>
                  </div>

                  {notificationsData.notifications?.length === 0 ? (
                    <div style={{ padding: '20px', textAlign: 'center', color: '#94a3b8', fontSize: '12px' }}>
                      No action items requiring attention.
                    </div>
                  ) : (
                    notificationsData.notifications.map((n) => (
                      <div
                        key={n.id}
                        onClick={() => {
                          setNotificationsOpen(false);
                          if (n.entity_type === 'flag') {
                            handleOpenFlagDrawer(n.entity_id);
                          } else if (n.entity_type === 'task') {
                            setActiveNav('tasks');
                          }
                        }}
                        style={{
                          padding: '10px 12px',
                          borderRadius: '8px',
                          background: n.tier === 'Immediate' || n.tier === 'Urgent' ? '#fef2f2' : 'var(--bg-base, #f8fafc)',
                          border: `1px solid ${n.tier === 'Immediate' || n.tier === 'Urgent' ? '#fecaca' : 'var(--border-subtle, #e2e8f0)'}`,
                          cursor: 'pointer',
                        }}
                      >
                        <div style={{ fontSize: '12px', fontWeight: 700, color: n.tier === 'Immediate' || n.tier === 'Urgent' ? '#b91c1c' : 'var(--text-primary, #0f172a)' }}>
                          {n.title}
                        </div>
                        <div style={{ fontSize: '11px', color: '#64748b', marginTop: '3px', lineHeight: '1.4' }}>
                          {n.description}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '6px', fontSize: '10px', color: '#94a3b8' }}>
                          <span>{n.created_at?.slice(0, 16).replace('T', ' ')}</span>
                          {n.can_snooze ? (
                            <span style={{ color: '#0284c7', fontWeight: 600 }}>Snooze allowed</span>
                          ) : (
                            <span style={{ color: '#ef4444', fontWeight: 700 }}>Priority action required</span>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>

            {/* Role Chip (Phase 2 & Section 2.5) */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '5px 12px',
                borderRadius: '20px',
                backgroundColor: roleAccentSoft,
                border: `1px solid ${roleAccent}`,
                color: roleAccentText,
                fontSize: '12px',
                fontWeight: 700,
              }}
            >
              <span>{isDoctor ? 'Doctor' : 'Nurse'}</span>
            </div>

            <SwitchDemoWorkspace currentUser={user} />

            <button
              type="button"
              onClick={() => { setSmsSimOpen(true); setSmsSimResult(null); setSmsSimError(null); }}
              title="Simulate inbound patient SMS (Feature F3)"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 11px',
                borderRadius: '8px',
                border: '1px solid var(--border-subtle, #cbd5e1)',
                background: 'var(--bg-base, #ffffff)',
                color: 'var(--text-primary, #0f172a)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: 'pointer',
              }}
            >
              <span>📱 SMS Sim</span>
            </button>

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

          {/* TAB 1: CLINICIAN DESK (DOCTOR DECISIONS / NURSE CALL LIST) */}
          {activeNav === 'triage' && (
            isDoctor ? (
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
                        color: roleAccent,
                        letterSpacing: '0.06em',
                        textTransform: 'uppercase',
                        marginBottom: '6px',
                      }}
                    >
                      <IconShieldCheck width={14} height={14} />
                      <span>DOCTOR DESK</span>
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
                      Needs my decision
                    </h1>
                    <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', margin: 0 }}>
                      High-priority clinical items awaiting physician review, sign-off, or protocol decisions.
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

                {/* DOCTOR DECISION DESK (Phase 3 Task 1) */}
                <div>
                  {/* 4 Decision Cards */}
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(4, 1fr)',
                      gap: '18px',
                      marginBottom: '24px',
                    }}
                  >
                    {/* Card 1: Needs Decision Now */}
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
                          background: 'var(--role-doctor-soft, #f5f3ff)',
                          border: '1px solid #ddd6fe',
                          color: 'var(--role-doctor, #7c3aed)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <IconAlertTriangle width={18} height={18} />
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                        Needs decision now
                      </div>
                      <div
                        style={{
                          fontSize: '28px',
                          fontWeight: 800,
                          color: (doctorDecisions.cards?.needs_decision_now || 0) > 0 ? 'var(--role-doctor, #7c3aed)' : 'var(--text-primary, #0f172a)',
                          margin: '6px 0 2px',
                        }}
                      >
                        {doctorDecisions.cards?.needs_decision_now ?? 0}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                        Immediate flags, drafts &amp; proposals
                      </div>
                    </div>

                    {/* Card 2: Summaries to Approve */}
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
                        <IconFileText width={18} height={18} />
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                        Summaries to approve
                      </div>
                      <div
                        style={{
                          fontSize: '28px',
                          fontWeight: 800,
                          color: 'var(--text-primary, #0f172a)',
                          margin: '6px 0 2px',
                        }}
                      >
                        {doctorDecisions.cards?.summaries_to_approve ?? 0}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                        AI discharge drafts awaiting sign-off
                      </div>
                    </div>

                    {/* Card 3: Limit Change Requests */}
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
                        <IconShieldCheck width={18} height={18} />
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                        Limit change requests
                      </div>
                      <div
                        style={{
                          fontSize: '28px',
                          fontWeight: 800,
                          color: 'var(--text-primary, #0f172a)',
                          margin: '6px 0 2px',
                        }}
                      >
                        {doctorDecisions.cards?.limit_change_requests ?? 0}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                        Nurse-proposed limit modifications
                      </div>
                    </div>

                    {/* Card 4: Patients in Follow-Up */}
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
                          background: '#f0fdfa',
                          border: '1px solid #99f6e4',
                          color: '#0f766e',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                        }}
                      >
                        <IconPatient width={18} height={18} />
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                        Patients in follow-up
                      </div>
                      <div
                        style={{
                          fontSize: '28px',
                          fontWeight: 800,
                          color: 'var(--text-primary, #0f172a)',
                          margin: '6px 0 2px',
                        }}
                      >
                        {doctorDecisions.cards?.patients_in_followup ?? 5}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                        Active post-op &amp; convalescence cohort
                      </div>
                    </div>
                  </div>

                  {/* Decision Items Queue */}
                  <div
                    style={{
                      background: 'var(--bg-surface, #ffffff)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      borderRadius: '12px',
                      padding: '22px 24px',
                      boxShadow: 'var(--shadow-card)',
                      marginBottom: '20px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                      <div>
                        <h3 style={{ margin: '0 0 4px 0', fontSize: '15px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                          Decision Items Awaiting Physician Action ({doctorDecisions.items?.length || 0})
                        </h3>
                        <p style={{ margin: 0, fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                          Routine telemetry and task checklists are handled by Nurse Priya. Only items requiring physician authority appear here.
                        </p>
                      </div>
                    </div>

                    {(!doctorDecisions.items || doctorDecisions.items.length === 0) ? (
                      <div style={{ padding: '36px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                        ✓ All decision items cleared. No open flags or unsigned summaries requiring doctor action.
                      </div>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {doctorDecisions.items.map((item) => (
                          <div
                            key={`${item.type}-${item.id}`}
                            style={{
                              border: '1px solid var(--border-subtle, #e2e8f0)',
                              borderLeft: item.tier === 'Immediate' ? '4px solid #ef4444' : item.type === 'summary' ? '4px solid #0284c7' : '4px solid #d97706',
                              borderRadius: '8px',
                              padding: '16px 18px',
                              background: 'var(--bg-surface, #ffffff)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              gap: '16px',
                            }}
                          >
                            <div style={{ flex: 1 }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                                  {item.patient_name}
                                </span>
                                <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                                  {item.patient_age} y · {item.patient_code}
                                </span>
                                <span style={{ fontSize: '11px', padding: '1px 7px', borderRadius: '4px', background: 'var(--bg-base, #f1f5f9)', color: 'var(--text-secondary, #475569)', fontWeight: 600 }}>
                                  {item.condition}
                                </span>
                                <span
                                  style={{
                                    fontSize: '10px',
                                    fontWeight: 700,
                                    padding: '2px 8px',
                                    borderRadius: '12px',
                                    textTransform: 'uppercase',
                                    background: item.tier === 'Immediate' ? '#fef2f2' : item.type === 'flag' ? '#fef3c7' : item.type === 'summary' ? '#eff6ff' : '#fffbeb',
                                    color: item.tier === 'Immediate' ? '#dc2626' : item.type === 'flag' ? '#b45309' : item.type === 'summary' ? '#0284c7' : '#d97706',
                                  }}
                                >
                                  {item.tier === 'Immediate' ? 'Immediate Flag' : item.type === 'flag' ? 'Urgent Flag' : item.type === 'summary' ? 'AI Summary Draft' : 'Limit Proposal'}
                                </span>
                                <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600, marginLeft: 'auto' }}>
                                  {item.waited_text}
                                </span>
                              </div>

                              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary, #0f172a)', lineHeight: '1.4' }}>
                                {item.title}
                              </div>

                              {item.escalated_kicker && (
                                <div style={{ marginTop: '4px', fontSize: '11px', color: '#b45309', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                                  ⚡ {item.escalated_kicker}
                                </div>
                              )}

                              {/* Phase 3 Doctor Decision Card Brief, Pre-drafted note, and One-click options */}
                              {item.brief && (
                                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px 12px', marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                    <span style={{ fontSize: '10px', fontWeight: 800, textTransform: 'uppercase', color: '#7c3aed', background: '#f5f3ff', padding: '2px 8px', borderRadius: '10px', border: '1px solid #ddd6fe' }}>
                                      ✨ Case Brief Ready
                                    </span>
                                    {item.agent_run_id && (
                                      <button
                                        type="button"
                                        onClick={() => setDoctorTraceRunId(item.agent_run_id)}
                                        style={{ background: 'none', border: 'none', color: '#7c3aed', fontSize: '11px', fontWeight: 700, cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                                      >
                                        <span>⚡ Agent trace</span>
                                      </button>
                                    )}
                                  </div>

                                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '2px' }}>
                                    {(item.brief.what_happened || []).slice(0, 2).concat((item.brief.context || []).slice(0, 3)).map((f, idx) => (
                                      <span key={idx} style={{ fontSize: '11px', color: '#334155', background: '#ffffff', border: '1px solid #e2e8f0', padding: '2px 6px', borderRadius: '4px' }}>
                                        {f.fact} <strong style={{ color: '#64748b', fontSize: '9px' }}>[{f.source}]</strong>
                                      </span>
                                    ))}
                                  </div>

                                  {item.prefilled_note && (
                                    <div style={{ fontSize: '12px', color: '#475569', background: '#ffffff', border: '1px dashed #cbd5e1', padding: '6px 10px', borderRadius: '6px', marginTop: '4px' }}>
                                      <strong style={{ color: '#0f172a' }}>Pre-drafted note:</strong> {item.prefilled_note}
                                    </div>
                                  )}

                                  {/* 2 to 3 one-click doctor options */}
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px' }}>
                                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#64748b' }}>One-click action:</span>
                                    <button
                                      type="button"
                                      onClick={() => handleDoctorCaseDecide(item.case_id, 'call_now')}
                                      style={{ padding: '4px 10px', borderRadius: '4px', border: '1px solid #0284c7', background: '#eff6ff', color: '#0284c7', fontSize: '11px', fontWeight: 700, cursor: 'pointer' }}
                                    >
                                      Call now
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleDoctorCaseDecide(item.case_id, 'ask_doctor')}
                                      style={{ padding: '4px 10px', borderRadius: '4px', border: '1px solid #7c3aed', background: '#f5f3ff', color: '#6d28d9', fontSize: '11px', fontWeight: 700, cursor: 'pointer' }}
                                    >
                                      Consult team
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleDoctorCaseDecide(item.case_id, 'recheck_at')}
                                      style={{ padding: '4px 10px', borderRadius: '4px', border: '1px solid #64748b', background: '#f8fafc', color: '#334155', fontSize: '11px', fontWeight: 700, cursor: 'pointer' }}
                                    >
                                      Re-check at 2h
                                    </button>
                                  </div>
                                </div>
                              )}
                            </div>

                            <div style={{ display: 'flex', gap: '8px', flexShrink: 0 }}>
                              <button
                                type="button"
                                onClick={() => {
                                  if (item.type === 'flag') handleOpenFlagDrawer(item.flag_id);
                                  else if (item.type === 'summary') setActiveNav('summaries');
                                  else if (item.type === 'limit_proposal') setActiveNav('summaries');
                                }}
                                style={{
                                  padding: '8px 16px',
                                  borderRadius: '6px',
                                  border: 'none',
                                  background: 'var(--role-doctor, #7c3aed)',
                                  color: '#ffffff',
                                  fontSize: '12px',
                                  fontWeight: 700,
                                  cursor: 'pointer',
                                }}
                              >
                                Decide
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedPatientId(item.patient_id);
                                  setActiveNav('patient_chart');
                                }}
                                style={{
                                  padding: '8px 14px',
                                  borderRadius: '6px',
                                  border: '1px solid var(--border-strong, #cbd5e1)',
                                  background: 'transparent',
                                  color: 'var(--text-primary, #0f172a)',
                                  fontSize: '12px',
                                  fontWeight: 600,
                                  cursor: 'pointer',
                                }}
                              >
                                Open patient
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Quiet Patients Reassuring Row (Phase 3 Task 1) */}
                  <div
                    style={{
                      background: 'var(--bg-surface, #ffffff)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      borderLeft: '4px solid #10b981',
                      borderRadius: '10px',
                      padding: '16px 20px',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      boxShadow: 'var(--shadow-card)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                      <div style={{ width: '28px', height: '28px', borderRadius: '50%', background: '#ecfdf5', color: '#059669', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '13px' }}>
                        ✓
                      </div>
                      <div>
                        <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                          {doctorDecisions.quiet_patients?.message || 'Quiet patients: 1. Nothing open.'}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
                          {doctorDecisions.quiet_patients?.patients && doctorDecisions.quiet_patients.patients.length > 0
                            ? doctorDecisions.quiet_patients.patients.map(p => `${p.full_name} (${p.patient_code} · ${p.condition_summary || 'Recovery'})`).join(' · ')
                            : 'All active patients currently have open reviews or tasks.'}
                        </div>
                      </div>
                    </div>
                    <span style={{ fontSize: '11px', fontWeight: 700, padding: '3px 10px', borderRadius: '12px', background: '#ecfdf5', color: '#059669' }}>
                      Telemetry On Track
                    </span>
                  </div>
                </div>
              </>
            ) : (
              <NurseCallListView
                onSelectPatient={(pid) => {
                  setSelectedPatientId(pid);
                  setActiveNav('patient_chart');
                }}
              />
            )
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

          {/* TAB: ADMIT PATIENT (Phase 4 Feature F6) */}
          {activeNav === 'admit' && (
            <AdmitPatientWizard
              onComplete={(res) => {
                setActionMsg(`Patient ${res.full_name} (${res.patient_code}) admitted successfully.`);
                setTimeout(() => setActionMsg(''), 4000);
                setSelectedPatientId(res.patient_id);
                setActiveNav('patient_chart');
              }}
              onCancel={() => setActiveNav('triage')}
            />
          )}

          {/* TAB: ROUNDS (Feature F1: Scheduled Automation) */}
          {activeNav === 'rounds' && (
            <RoundsView currentUser={user} />
          )}

          {/* TAB: AGENT DESK (CareLoop Care Agents Phase 1) */}
          {activeNav === 'agent_desk' && (
            <AgentDesk
              currentUser={user}
              onSelectPatient={(pid) => {
                setSelectedPatientId(pid);
                setActiveNav('patient_chart');
              }}
            />
          )}

          {/* TAB: AGENT SETTINGS (CareLoop Care Agents Phase 5) */}
          {activeNav === 'agent_settings' && (
            <AgentSettingsView currentUser={user} />
          )}

          {/* TAB: AGENT HEALTH & TELEMETRY (CareLoop Agents v2 Phase 1) */}
          {activeNav === 'agent_health' && (
            <AgentHealthView user={user} />
          )}

          {/* TAB: WORK SAVED & PERFORMANCE (CareLoop Care Agents Phase 6) */}
          {activeNav === 'work_saved' && (
            <WorkSavedPanel currentUser={user} />
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

          {/* TAB 3: TASKS (Feature D-07) */}
          {activeNav === 'tasks' && (
            <TaskQueue
              staffMembers={staffMembers}
              user={user}
              onSelectPatient={(pid) => {
                setSelectedPatientId(pid);
                setActiveNav('patient_chart');
              }}
            />
          )}

          {/* TAB 4: SUMMARIES & APPROVALS (DOCTOR ONLY) */}
          {activeNav === 'summaries' && (
            isDoctor ? (
              <ClinicalSummaries
                user={user}
                onSelectPatient={(pid) => {
                  setSelectedPatientId(pid);
                  setActiveNav('patient_chart');
                }}
              />
            ) : (
              <RestrictedNurseView pageName="Approvals & Summaries" />
            )
          )}

          {/* TAB 5: SHIFT HANDOFF (Feature D-09) */}
          {activeNav === 'handoff' && (
            <ShiftHandoff
              user={user}
              onSelectPatient={(pid) => {
                setSelectedPatientId(pid);
                setActiveNav('patient_chart');
              }}
            />
          )}

          {/* TAB 6: OPERATIONAL INSIGHTS (Feature D-14) */}
          {activeNav === 'insights' && (
            isDoctor ? <OperationalInsights /> : <RestrictedNurseView pageName="Operational Insights" />
          )}

          {/* TAB 7: AUDIT LOG VIEWER (Feature D-17) */}
          {activeNav === 'audit' && (
            isDoctor ? <AuditLogViewer /> : <RestrictedNurseView pageName="Audit Log Viewer" />
          )}

          {/* TAB 8: PATIENT APPROVED LIMITS (Phase 3 Task 4) */}
          {activeNav === 'limits' && (
            isDoctor ? <DoctorLimitsView user={user} /> : <RestrictedNurseView pageName="Patient Limits Management" />
          )}

          {/* TAB 9: FHIR R4 EXPORT (Phase 3 Task 6) */}
          {activeNav === 'fhir' && (
            isDoctor ? <DoctorFhirExportView user={user} /> : <RestrictedNurseView pageName="FHIR R4 Bundle Export" />
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

      {/* D-21: Command Palette Modal (Ctrl+K / Cmd+K) */}
      {commandPaletteOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'center',
            paddingTop: '100px',
            zIndex: 1100,
          }}
          onClick={() => setCommandPaletteOpen(false)}
        >
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              border: '1px solid var(--border-subtle, #cbd5e1)',
              borderRadius: '12px',
              width: '90%',
              maxWidth: '620px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.25), 0 10px 10px -5px rgba(0, 0, 0, 0.15)',
              overflow: 'hidden',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Search Input Bar */}
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '14px 18px',
                borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                gap: '12px',
              }}
            >
              <IconSearch width={18} height={18} style={{ color: 'var(--text-muted, #94a3b8)' }} />
              <input
                autoFocus
                type="text"
                placeholder="Search patients, active flags, tasks, clinical notes... (Esc to close)"
                value={commandQuery}
                onChange={(e) => setCommandQuery(e.target.value)}
                style={{
                  flex: 1,
                  border: 'none',
                  outline: 'none',
                  background: 'transparent',
                  fontSize: '15px',
                  color: 'var(--text-primary, #0f172a)',
                }}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted, #94a3b8)', border: '1px solid #e2e8f0', borderRadius: '4px', padding: '2px 6px' }}>
                ESC
              </span>
            </div>

            {/* Results Area */}
            <div style={{ maxHeight: '420px', overflowY: 'auto', padding: '12px 16px' }}>
              {commandLoading ? (
                <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                  Searching clinical directory...
                </div>
              ) : !commandQuery.trim() || commandQuery.trim().length < 2 ? (
                <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                  Type at least 2 characters to search across patients, active flags, follow-up tasks, and notes.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {/* Patients */}
                  {commandResults.patients?.length > 0 && (
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', marginBottom: '6px' }}>
                        Patients ({commandResults.patients.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {commandResults.patients.map((pt) => (
                          <div
                            key={pt.patient_id}
                            onClick={() => {
                              setSelectedPatientId(pt.patient_id);
                              setActiveNav('patient_chart');
                              setCommandPaletteOpen(false);
                            }}
                            style={{
                              padding: '8px 12px',
                              borderRadius: '6px',
                              background: 'var(--bg-base, #f8fafc)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              cursor: 'pointer',
                            }}
                          >
                            <div>
                              <span style={{ fontWeight: 600, color: 'var(--text-primary, #0f172a)', fontSize: '13px' }}>{pt.full_name}</span>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginLeft: '8px' }}>PID: {pt.patient_code}</span>
                            </div>
                            <span style={{ fontSize: '11px', color: '#0284c7', fontWeight: 600 }}>Open Chart →</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Flags */}
                  {commandResults.flags?.length > 0 && (
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', marginBottom: '6px' }}>
                        Active Flags ({commandResults.flags.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {commandResults.flags.map((fl) => (
                          <div
                            key={fl.flag_id}
                            onClick={() => {
                              setSelectedFlag(fl);
                              setCommandPaletteOpen(false);
                            }}
                            style={{
                              padding: '8px 12px',
                              borderRadius: '6px',
                              background: 'var(--bg-base, #f8fafc)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              cursor: 'pointer',
                            }}
                          >
                            <div>
                              <span style={{ fontWeight: 600, color: '#b91c1c', fontSize: '12px' }}>
                                [{fl.severity === 'Review_Soon' ? 'Review soon' : fl.severity === 'Urgent_Review' ? 'Urgent' : fl.severity}]
                              </span>
                              <span style={{ fontSize: '13px', color: 'var(--text-primary, #0f172a)', marginLeft: '6px' }}>{fl.reason}</span>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginLeft: '8px' }}>({fl.full_name})</span>
                            </div>
                            <span style={{ fontSize: '11px', color: '#0284c7', fontWeight: 600 }}>Review Flag →</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Tasks */}
                  {commandResults.tasks?.length > 0 && (
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', marginBottom: '6px' }}>
                        Follow-Up Tasks ({commandResults.tasks.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {commandResults.tasks.map((tk) => (
                          <div
                            key={tk.task_id}
                            onClick={() => {
                              setActiveNav('tasks');
                              setCommandPaletteOpen(false);
                            }}
                            style={{
                              padding: '8px 12px',
                              borderRadius: '6px',
                              background: 'var(--bg-base, #f8fafc)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              cursor: 'pointer',
                            }}
                          >
                            <div>
                              <span style={{ fontWeight: 600, color: 'var(--text-primary, #0f172a)', fontSize: '13px' }}>{tk.task_description}</span>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginLeft: '8px' }}>({tk.full_name})</span>
                            </div>
                            <span style={{ fontSize: '11px', color: '#0284c7', fontWeight: 600 }}>Task Queue →</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Notes */}
                  {commandResults.notes?.length > 0 && (
                    <div>
                      <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted, #64748b)', marginBottom: '6px' }}>
                        Clinician Notes ({commandResults.notes.length})
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {commandResults.notes.map((nt) => (
                          <div
                            key={nt.note_id}
                            onClick={() => {
                              setSelectedPatientId(nt.patient_id);
                              setActiveNav('patient_chart');
                              setCommandPaletteOpen(false);
                            }}
                            style={{
                              padding: '8px 12px',
                              borderRadius: '6px',
                              background: 'var(--bg-base, #f8fafc)',
                              display: 'flex',
                              justifyContent: 'space-between',
                              alignItems: 'center',
                              cursor: 'pointer',
                            }}
                          >
                            <div>
                              <span style={{ fontWeight: 600, color: '#6d28d9', fontSize: '12px' }}>[{nt.note_type}]</span>
                              <span style={{ fontSize: '13px', color: 'var(--text-primary, #0f172a)', marginLeft: '6px' }}>{nt.note_text.slice(0, 60)}...</span>
                              <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginLeft: '8px' }}>({nt.full_name})</span>
                            </div>
                            <span style={{ fontSize: '11px', color: '#0284c7', fontWeight: 600 }}>View Note →</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {commandResults.patients?.length === 0 &&
                    commandResults.flags?.length === 0 &&
                    commandResults.tasks?.length === 0 &&
                    commandResults.notes?.length === 0 && (
                      <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                        No results found for &ldquo;{commandQuery}&rdquo;.
                      </div>
                    )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* D-21: Keyboard Shortcuts Cheat Sheet Modal (?) */}
      {shortcutsModalOpen && (
        <div
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1100,
          }}
          onClick={() => setShortcutsModalOpen(false)}
        >
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              border: '1px solid var(--border-subtle, #cbd5e1)',
              borderRadius: '12px',
              width: '90%',
              maxWidth: '480px',
              padding: '24px',
              boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.25)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                Clinician Keyboard Shortcuts
              </h3>
              <button
                type="button"
                onClick={() => setShortcutsModalOpen(false)}
                style={{ border: 'none', background: 'transparent', fontSize: '18px', cursor: 'pointer', color: 'var(--text-muted, #64748b)' }}
              >
                ×
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '13px' }}>
              {[
                { key: 'Ctrl + K  /  ⌘ + K', desc: 'Open global command palette & search' },
                { key: 'j', desc: 'Select next patient row in worklist' },
                { key: 'k', desc: 'Select previous patient row in worklist' },
                { key: 'o', desc: 'Open patient clinical chart for selected row' },
                { key: '?', desc: 'Toggle keyboard shortcuts cheat sheet' },
                { key: 'Esc', desc: 'Close modals, command palette, and drawers' },
              ].map((sc) => (
                <div
                  key={sc.key}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'var(--bg-base, #f8fafc)',
                  }}
                >
                  <kbd
                    style={{
                      fontFamily: 'monospace',
                      fontWeight: 700,
                      background: 'var(--bg-surface, #ffffff)',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      borderRadius: '4px',
                      padding: '2px 8px',
                      fontSize: '12px',
                      color: 'var(--text-primary, #0f172a)',
                    }}
                  >
                    {sc.key}
                  </kbd>
                  <span style={{ color: 'var(--text-secondary, #475569)', fontSize: '12px' }}>{sc.desc}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Phase 2 Feature F3: SMS Patient Simulator Modal */}
      {smsSimOpen && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(15, 23, 42, 0.65)',
            backdropFilter: 'blur(3px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 9999,
            padding: '20px',
          }}
          onClick={() => setSmsSimOpen(false)}
        >
          <div
            style={{
              background: 'var(--bg-surface, #ffffff)',
              borderRadius: '14px',
              padding: '24px',
              maxWidth: '520px',
              width: '100%',
              boxShadow: 'var(--shadow-xl, 0 20px 25px -5px rgba(0,0,0,0.1))',
              border: '1px solid var(--border-subtle, #e2e8f0)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '20px' }}>📱</span>
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                  Two-Way SMS Patient Simulator
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSmsSimOpen(false)}
                style={{ border: 'none', background: 'transparent', fontSize: '18px', cursor: 'pointer', color: '#94a3b8' }}
              >
                ×
              </button>
            </div>

            <p style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', margin: '0 0 16px 0', lineHeight: 1.4 }}>
              Simulates inbound SMS messages sent to Twilio. The deterministic rule engine confirms doses, schedules nurse callbacks, toggles DPDP opt-outs, or raises emergency escalations.
            </p>

            {/* Patient phone selector */}
            <div style={{ marginBottom: '12px' }}>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#64748b', marginBottom: '4px', textTransform: 'uppercase' }}>
                Patient Phone Number
              </label>
              <select
                value={smsSimPhone}
                onChange={(e) => setSmsSimPhone(e.target.value)}
                style={{
                  width: '100%',
                  padding: '8px 10px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  background: 'var(--bg-base, #ffffff)',
                  color: 'var(--text-primary, #0f172a)',
                  fontSize: '13px',
                }}
              >
                <option value="+91-98765-00001">Aarav Patel (+91-98765-00001)</option>
                <option value="+91-98765-00002">Meera Sharma (+91-98765-00002)</option>
                <option value="+91-98765-00003">Rajesh Verma (+91-98765-00003)</option>
                <option value="+91-98765-00004">Kabir Mehta (+91-98765-00004)</option>
                <option value="+91-98765-00005">Sunita Rao (+91-98765-00005)</option>
                <option value="+91-99999-99999">Unknown Number (+91-99999-99999)</option>
              </select>
            </div>

            {/* Preset quick command buttons */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#64748b', marginBottom: '6px', textTransform: 'uppercase' }}>
                Quick Inbound Commands
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                {[
                  { label: '1 (Dose Taken)', val: '1' },
                  { label: '2 (Dose Skipped)', val: '2' },
                  { label: '3 (Nurse Callback)', val: '3' },
                  { label: 'STOP (Opt-Out)', val: 'STOP' },
                  { label: 'START (Opt-In)', val: 'START' },
                  { label: 'Chest pain & dizzy', val: 'Chest pain and feeling dizzy' },
                ].map((chip) => (
                  <button
                    key={chip.val}
                    type="button"
                    onClick={() => {
                      setSmsSimBody(chip.val);
                      handleSimulateSms(chip.val);
                    }}
                    style={{
                      padding: '4px 9px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'var(--bg-base, #f8fafc)',
                      color: 'var(--text-primary, #0f172a)',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Message input */}
            <div style={{ marginBottom: '14px' }}>
              <label style={{ display: 'block', fontSize: '11px', fontWeight: 700, color: '#64748b', marginBottom: '4px', textTransform: 'uppercase' }}>
                SMS Text Body
              </label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="text"
                  value={smsSimBody}
                  onChange={(e) => setSmsSimBody(e.target.value)}
                  placeholder="Type '1', 'HELP', or custom text..."
                  style={{
                    flex: 1,
                    padding: '8px 10px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle, #cbd5e1)',
                    background: 'var(--bg-base, #ffffff)',
                    color: 'var(--text-primary, #0f172a)',
                    fontSize: '13px',
                  }}
                />
                <button
                  type="button"
                  disabled={smsSimLoading || !smsSimBody.trim()}
                  onClick={() => handleSimulateSms()}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '6px',
                    border: 'none',
                    background: '#0284c7',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 700,
                    cursor: smsSimLoading ? 'not-allowed' : 'pointer',
                    opacity: smsSimLoading ? 0.7 : 1,
                  }}
                >
                  {smsSimLoading ? 'Simulating...' : 'Send SMS'}
                </button>
              </div>
            </div>

            {/* Result feedback */}
            {smsSimError && (
              <div style={{ padding: '10px 12px', borderRadius: '6px', background: '#fef2f2', border: '1px solid #fecaca', color: '#b91c1c', fontSize: '12px', marginBottom: '12px' }}>
                ❌ {smsSimError}
              </div>
            )}

            {smsSimResult && (
              <div style={{ padding: '12px 14px', borderRadius: '8px', background: 'var(--bg-base, #f0fdf4)', border: '1px solid #bbf7d0', marginBottom: '12px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', color: '#166534' }}>
                    Engine Action: <code>{smsSimResult.action}</code>
                  </span>
                  <span style={{ fontSize: '11px', padding: '1px 6px', borderRadius: '4px', background: '#dcfce7', color: '#15803d', fontWeight: 700 }}>
                    ✓ Processed
                  </span>
                </div>
                <div style={{ fontSize: '12px', color: '#1e293b', marginBottom: '4px' }}>
                  <strong>Outbound Reply Body:</strong>
                </div>
                <div style={{ fontSize: '12px', color: '#334155', background: '#ffffff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #cbd5e1', fontStyle: 'italic' }}>
                  &ldquo;{smsSimResult.reply_body}&rdquo;
                </div>
                {smsSimResult.action === 'help_callback_created' && (
                  <div style={{ marginTop: '6px', fontSize: '11px', color: '#b45309', fontWeight: 600 }}>
                    ⚡ High-priority callback task has been dispatched to the Nurse queue.
                  </div>
                )}
                {smsSimResult.action === 'emergency_alert_escalated' && (
                  <div style={{ marginTop: '6px', fontSize: '11px', color: '#dc2626', fontWeight: 700 }}>
                    🚨 Emergency flag raised on patient chart; dial 112 guidance dispatched.
                  </div>
                )}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                type="button"
                onClick={() => setSmsSimOpen(false)}
                style={{
                  padding: '6px 14px',
                  borderRadius: '6px',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  background: 'transparent',
                  color: 'var(--text-secondary, #475569)',
                  fontSize: '12px',
                  cursor: 'pointer',
                }}
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Phase 3 Doctor Desk Agent Execution Trace Modal */}
      <AgentTraceModal
        runId={doctorTraceRunId}
        isOpen={!!doctorTraceRunId}
        onClose={() => setDoctorTraceRunId(null)}
      />
    </div>
  );
}
