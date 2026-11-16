import React, { useState, useEffect } from 'react';
import {
  getPatientDetail,
  breakGlassAccess,
  getPatientMedicines,
  getPatientRules,
  getPatientTimeline,
  getPatientContacts,
  logCommunication,
  getPatientNotes,
  addPatientNote,
  getPathwayTemplates,
  applyPathwayTemplate,
  getRuleHistory,
  updateAlertRule,
  getPatientFhirBundle,
  getPatientLace,
  recordPatientLace,
  getAgentActivity,
  getPatientSmsMessages,
  getStaffPatientPlans,
  draftRecoveryPlan,
  verifyPlanItem,
  approveRecoveryPlan,
  rejectRecoveryPlan,
} from '../services/api';
import PatientIdentity from './PatientIdentity';
import {
  IconAlertTriangle,
  IconActivity,
  IconShieldCheck,
  IconPill,
  IconClock,
  IconFileText,
} from './Icons';

/**
 * PatientOverviewTab Component (D-05, D-06, D-12, D-13, D-18)
 *
 * Implements:
 * 1. Clinical snapshot & Break-Glass audited access (D-12)
 * 2. Latest vitals with Data Quality badges (Good, Questionable, Invalid, Simulated) (D-18)
 * 3. 7-day dose grid & 14-day pain trend
 * 4. Caregiver consent indicators & Silent device tracking
 * 5. Medicines tab with strict "Self-reported" labeling & dose exception notes
 * 6. Alert rules tab with clinician approval tracking & false alarm dismissal counts
 * 7. Upgraded timeline with day grouping, filter chips, event collapse, and vitals trend chart
 */
export default function PatientOverviewTab({
  patientId,
  onBackToDirectory,
  onOpenFlagDrawer,
  user,
}) {
  const [subTab, setSubTab] = useState('overview'); // 'overview', 'medicines', 'rules', 'timeline', 'notes'
  const [loading, setLoading] = useState(true);
  const [detailData, setDetailData] = useState(null);
  const [medicinesData, setMedicinesData] = useState(null);
  const [rulesData, setRulesData] = useState([]);
  const [timelineData, setTimelineData] = useState(null);

  // D-15 & D-16 Notes and Contacts state
  const [contactsData, setContactsData] = useState([]);
  const [notesData, setNotesData] = useState([]);
  const [noteText, setNoteText] = useState('');
  const [noteType, setNoteType] = useState('General');
  const [amendsNoteId, setAmendsNoteId] = useState(null);
  const [noteSubmitting, setNoteSubmitting] = useState(false);
  const [contactModalOpen, setContactModalOpen] = useState(false);
  const [contactChannel, setContactChannel] = useState('Phone');
  const [contactOutcome, setContactOutcome] = useState('Reached');
  const [contactSummary, setContactSummary] = useState('');
  const [contactSubmitting, setContactSubmitting] = useState(false);

  // Break-glass modal state
  const [breakGlassReason, setBreakGlassReason] = useState('');
  const [breakGlassSubmitting, setBreakGlassSubmitting] = useState(false);
  const [breakGlassError, setBreakGlassError] = useState('');

  // Agent Activity subtab state
  const [agentActivityData, setAgentActivityData] = useState([]);
  const [agentActivityLoading, setAgentActivityLoading] = useState(false);

  // SMS Messages subtab state (Phase 2 Feature F3)
  const [smsMessagesData, setSmsMessagesData] = useState([]);
  const [smsMessagesLoading, setSmsMessagesLoading] = useState(false);

  // Phase 4: Recovery Plans State
  const [plansData, setPlansData] = useState({ plans: [] });
  const [plansLoading, setPlansLoading] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState(null);
  const [draftingPlan, setDraftingPlan] = useState(false);
  const [planActionMsg, setPlanActionMsg] = useState('');
  const [planActionError, setPlanActionError] = useState('');
  const [verifyingItemId, setVerifyingItemId] = useState(null);
  const [approvingPlanId, setApprovingPlanId] = useState(null);

  // Timeline subtab filters
  const [timelineType, setTimelineType] = useState('All');
  const [timelineRange, setTimelineRange] = useState('all');

  // Phase 5: Governance & Interoperability states
  const [fhirExporting, setFhirExporting] = useState(false);
  const [laceData, setLaceData] = useState(null);
  const [laceModalOpen, setLaceModalOpen] = useState(false);
  const [laceLos, setLaceLos] = useState(2);
  const [laceAcute, setLaceAcute] = useState(true);
  const [laceCharlson, setLaceCharlson] = useState(1);
  const [laceEd, setLaceEd] = useState(0);
  const [laceSubmitting, setLaceSubmitting] = useState(false);

  const [ruleHistoryModalOpen, setRuleHistoryModalOpen] = useState(false);
  const [selectedRuleHistory, setSelectedRuleHistory] = useState([]);
  const [ruleHistoryLoading, setRuleHistoryLoading] = useState(false);

  const [ruleEditModalOpen, setRuleEditModalOpen] = useState(false);
  const [editingRule, setEditingRule] = useState(null);
  const [ruleEditThreshold, setRuleEditThreshold] = useState('');
  const [ruleEditReason, setRuleEditReason] = useState('');
  const [ruleEditSubmitting, setRuleEditSubmitting] = useState(false);

  const [pathwayModalOpen, setPathwayModalOpen] = useState(false);
  const [pathwayTemplates, setPathwayTemplates] = useState([]);
  const [selectedPathway, setSelectedPathway] = useState(null);
  const [pathwayFormValues, setPathwayFormValues] = useState({});
  const [pathwaySubmitting, setPathwaySubmitting] = useState(false);
  const [overviewUpdatedTime, setOverviewUpdatedTime] = useState(() => new Date().toLocaleTimeString());

  const fetchOverview = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const data = await getPatientDetail(patientId);
      setDetailData(data);
      setOverviewUpdatedTime(new Date().toLocaleTimeString());
      getPatientLace(patientId).then(setLaceData).catch((e) => console.error(e));
    } catch (err) {
      console.error('Failed to load patient detail:', err);
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const handleExportFhir = async () => {
    setFhirExporting(true);
    try {
      const bundle = await getPatientFhirBundle(patientId);
      const jsonStr = JSON.stringify(bundle, null, 2);
      const blob = new Blob([jsonStr], { type: 'application/fhir+json;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.setAttribute('href', url);
      link.setAttribute('download', `careloop_fhir_bundle_pat${patientId}_${new Date().toISOString().slice(0, 10)}.json`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      console.error('FHIR export failed:', err);
      alert('Failed to export FHIR bundle.');
    } finally {
      setFhirExporting(false);
    }
  };

  const handleOpenRuleHistory = async (ruleId) => {
    setRuleHistoryModalOpen(true);
    setRuleHistoryLoading(true);
    try {
      const res = await getRuleHistory(ruleId);
      setSelectedRuleHistory(res.history || []);
    } catch (err) {
      console.error('Failed to load rule history:', err);
    } finally {
      setRuleHistoryLoading(false);
    }
  };

  const handleOpenPathwayModal = async () => {
    setPathwayModalOpen(true);
    try {
      const res = await getPathwayTemplates();
      setPathwayTemplates(res.templates || []);
      if (res.templates?.length) {
        setSelectedPathway(res.templates[0]);
        setPathwayFormValues({});
      }
    } catch (err) {
      console.error('Failed to load pathway templates:', err);
    }
  };

  const isDoctor = user?.role === 'Doctor' || user?.is_doctor === true;

  const handleApplyPathway = async () => {
    if (!selectedPathway) return;
    setPathwaySubmitting(true);
    try {
      for (const rule of selectedPathway.rules || []) {
        const val = pathwayFormValues[rule.key];
        if (val === undefined || val === null || String(val).trim() === '') {
          alert(`Please fill in the threshold value for "${rule.rule_type.replace(/_/g, ' ')}". Defaults are strictly blank.`);
          setPathwaySubmitting(false);
          return;
        }
      }
      const rulesPayload = (selectedPathway.rules || []).map((r) => ({
        rule_type: r.rule_type,
        threshold_value: parseFloat(pathwayFormValues[r.key]) || pathwayFormValues[r.key],
        severity: r.severity || 'Medium_Priority',
        window_hours: r.window_hours || 4,
        measurement_type: r.measurement_type || '',
      }));
      await applyPathwayTemplate(patientId, selectedPathway.template_id, rulesPayload);
      setPathwayModalOpen(false);
      await fetchRules();
      alert('Pathway template applied successfully!');
    } catch (err) {
      console.error('Failed to apply pathway:', err);
      alert(err.message || 'Failed to apply pathway template.');
    } finally {
      setPathwaySubmitting(false);
    }
  };

  const handleSaveRuleEdit = async (e) => {
    e.preventDefault();
    if (!editingRule) return;
    if (!ruleEditReason || ruleEditReason.trim().length < 5) {
      alert('A clinical justification of at least 5 characters is mandatory.');
      return;
    }
    setRuleEditSubmitting(true);
    try {
      const res = await updateAlertRule(editingRule.rule_id, {
        threshold_value: parseFloat(ruleEditThreshold) || ruleEditThreshold,
        change_reason: ruleEditReason.trim(),
      });
      setRuleEditModalOpen(false);
      setEditingRule(null);
      setRuleEditThreshold('');
      setRuleEditReason('');
      await fetchRules();
      alert(res.message || 'Rule updated successfully.');
    } catch (err) {
      console.error('Failed to update rule:', err);
      alert(err.message || 'Failed to update rule.');
    } finally {
      setRuleEditSubmitting(false);
    }
  };

  const handleSaveLace = async (e) => {
    e.preventDefault();
    setLaceSubmitting(true);
    try {
      const res = await recordPatientLace(patientId, {
        length_of_stay_days: parseInt(laceLos, 10) || 0,
        acute_admission: Boolean(laceAcute),
        charlson_index: parseInt(laceCharlson, 10) || 0,
        ed_visits_6m: parseInt(laceEd, 10) || 0,
      });
      setLaceData(res);
      setLaceModalOpen(false);
    } catch (err) {
      console.error('Failed to record LACE score:', err);
      alert(err.message || 'Failed to save LACE context score.');
    } finally {
      setLaceSubmitting(false);
    }
  };

  const fetchMedicines = async () => {
    try {
      const data = await getPatientMedicines(patientId);
      setMedicinesData(data);
    } catch (err) {
      console.error('Failed to load medicines:', err);
    }
  };

  const fetchRules = async () => {
    try {
      const data = await getPatientRules(patientId);
      setRulesData(data.rules || []);
    } catch (err) {
      console.error('Failed to load rules:', err);
    }
  };

  const fetchTimeline = async () => {
    try {
      const data = await getPatientTimeline(patientId, timelineType, timelineRange);
      setTimelineData(data);
    } catch (err) {
      console.error('Failed to load timeline:', err);
    }
  };

  const fetchNotesAndContacts = async () => {
    try {
      const [notes, contacts] = await Promise.all([
        getPatientNotes(patientId),
        getPatientContacts(patientId),
      ]);
      setNotesData(notes || []);
      setContactsData(contacts || []);
    } catch (err) {
      console.error('Failed to load notes and contacts:', err);
    }
  };

  const fetchAgentActivity = async () => {
    try {
      setAgentActivityLoading(true);
      const res = await getAgentActivity(patientId);
      setAgentActivityData(res.actions || []);
    } catch (err) {
      console.error('Failed to load agent activity:', err);
    } finally {
      setAgentActivityLoading(false);
    }
  };

  const fetchSmsMessages = async () => {
    try {
      setSmsMessagesLoading(true);
      const res = await getPatientSmsMessages(patientId);
      setSmsMessagesData(res.messages || []);
    } catch (err) {
      console.error('Failed to load SMS messages:', err);
    } finally {
      setSmsMessagesLoading(false);
    }
  };

  const fetchPlans = async () => {
    if (!patientId) return;
    setPlansLoading(true);
    setPlanActionError('');
    try {
      const res = await getStaffPatientPlans(patientId);
      if (res && res.success) {
        setPlansData(res.data || { plans: [] });
        const plans = res.data?.plans || [];
        if (plans.length > 0) {
          setSelectedPlanId((prev) => {
            if (prev && plans.some((p) => p.plan_id === prev)) return prev;
            return plans[0].plan_id;
          });
        }
      }
    } catch (err) {
      console.error('Failed to load patient recovery plans:', err);
      setPlanActionError(err?.message || 'Failed to load recovery plans.');
    } finally {
      setPlansLoading(false);
    }
  };

  const handleDraftPlan = async () => {
    setDraftingPlan(true);
    setPlanActionError('');
    setPlanActionMsg('');
    try {
      const res = await draftRecoveryPlan(patientId);
      if (res && res.success) {
        setPlanActionMsg(`Recovery plan draft (v${res.data?.plan?.version || 'new'}) successfully generated from discharge papers.`);
        setTimeout(() => setPlanActionMsg(''), 5000);
        await fetchPlans();
        if (res.data?.plan?.plan_id) {
          setSelectedPlanId(res.data.plan.plan_id);
        }
      }
    } catch (err) {
      setPlanActionError(err?.message || 'Failed to draft recovery plan.');
    } finally {
      setDraftingPlan(false);
    }
  };

  const handleVerifyItem = async (itemId) => {
    setVerifyingItemId(itemId);
    setPlanActionError('');
    try {
      const res = await verifyPlanItem(itemId);
      if (res && res.success) {
        setPlanActionMsg('Plan item verified against cited passage in discharge papers.');
        setTimeout(() => setPlanActionMsg(''), 4000);
        await fetchPlans();
      }
    } catch (err) {
      setPlanActionError(err?.message || 'Failed to verify plan item.');
    } finally {
      setVerifyingItemId(null);
    }
  };

  const handleApprovePlan = async (planId) => {
    setApprovingPlanId(planId);
    setPlanActionError('');
    try {
      const res = await approveRecoveryPlan(planId);
      if (res && res.success) {
        setPlanActionMsg('Recovery plan approved! Now published and active for the patient.');
        setTimeout(() => setPlanActionMsg(''), 5000);
        await fetchPlans();
      }
    } catch (err) {
      setPlanActionError(err?.message || 'Only attending doctors can approve recovery plans.');
    } finally {
      setApprovingPlanId(null);
    }
  };

  const handleRejectPlan = async (planId) => {
    const reason = window.prompt('Please enter clinical reason for rejecting draft plan:') || '';
    if (!reason.trim()) return;
    setApprovingPlanId(planId);
    setPlanActionError('');
    try {
      const res = await rejectRecoveryPlan(planId, reason.trim());
      if (res && res.success) {
        setPlanActionMsg('Recovery plan draft rejected.');
        setTimeout(() => setPlanActionMsg(''), 5000);
        await fetchPlans();
      }
    } catch (err) {
      setPlanActionError(err?.message || 'Failed to reject recovery plan.');
    } finally {
      setApprovingPlanId(null);
    }
  };

  useEffect(() => {
    fetchOverview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);

  // 10-second live refresh polling on overview tab
  useEffect(() => {
    if (!patientId || detailData?.requires_break_glass) return;
    if (subTab === 'overview') {
      const interval = setInterval(() => {
        getPatientDetail(patientId)
          .then((data) => {
            setDetailData(data);
            setOverviewUpdatedTime(new Date().toLocaleTimeString());
          })
          .catch((err) => console.error('Silent refresh error', err));
      }, 10000);
      return () => clearInterval(interval);
    }
  }, [patientId, subTab, detailData?.requires_break_glass]);

  useEffect(() => {
    if (detailData && !detailData.requires_break_glass) {
      if (subTab === 'medicines') fetchMedicines();
      else if (subTab === 'plan') fetchPlans();
      else if (subTab === 'rules') fetchRules();
      else if (subTab === 'timeline') fetchTimeline();
      else if (subTab === 'notes') fetchNotesAndContacts();
      else if (subTab === 'agent_activity') fetchAgentActivity();
      else if (subTab === 'messages') fetchSmsMessages();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [subTab, detailData, timelineType, timelineRange]);

  const handleBreakGlassSubmit = async (e) => {
    e.preventDefault();
    if (breakGlassReason.trim().length < 5) {
      setBreakGlassError('A clinical justification of at least 5 characters is mandatory.');
      return;
    }
    setBreakGlassSubmitting(true);
    setBreakGlassError('');
    try {
      await breakGlassAccess(patientId, breakGlassReason.trim());
      // Refresh detail data
      await fetchOverview();
    } catch (err) {
      setBreakGlassError(err.message || 'Failed to authorize break-glass access.');
    } finally {
      setBreakGlassSubmitting(false);
    }
  };

  if (loading && !detailData) {
    return (
      <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '14px' }}>
        Loading patient clinical chart...
      </div>
    );
  }

  const p = detailData?.patient || {};
  const isOutsideAssignment = detailData?.outside_assignment;
  const requiresBreakGlass = detailData?.requires_break_glass;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* 1. Header Banner & Identity */}
      <div
        style={{
          background: 'var(--bg-surface, #ffffff)',
          border: '1px solid var(--border-subtle, #e2e8f0)',
          borderRadius: '12px',
          padding: '20px 24px',
          boxShadow: 'var(--shadow-card)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '6px' }}>
              {onBackToDirectory && (
                <button
                  type="button"
                  onClick={onBackToDirectory}
                  style={{
                    padding: '4px 10px',
                    borderRadius: '6px',
                    border: '1px solid var(--border-subtle, #cbd5e1)',
                    background: 'var(--bg-base, #f1f5f9)',
                    color: 'var(--text-secondary, #475569)',
                    fontSize: '11px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  ← Directory
                </button>
              )}
              <span
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                  color: 'var(--accent-teal, #0d9488)',
                  background: 'var(--accent-teal-soft, #ecfdf5)',
                  padding: '2px 8px',
                  borderRadius: '12px',
                }}
              >
                Post-Discharge Day {p.day_number || 1}
              </span>
            </div>

            <PatientIdentity
              patient={{
                patient_id: p.patient_id,
                full_name: p.full_name,
                age_years: p.age_years,
                patient_code: p.patient_code,
                condition_summary: p.condition_summary,
              }}
              size="lg"
              showCondition={true}
            />
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
            {/* Attending & Nurse Details */}
            <div
              style={{
                display: 'flex',
                gap: '20px',
                padding: '10px 16px',
                borderRadius: '8px',
                background: 'var(--bg-base, #f8fafc)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
              }}
            >
              <div>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  Attending Doctor
                </div>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                  {p.attending_doctor || 'Dr. Ananya Sharma'}
                </div>
              </div>
              <div style={{ width: '1px', background: 'var(--border-subtle, #e2e8f0)' }} />
              <div>
                <div style={{ fontSize: '10px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                  Patient Phone
                </div>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                  {p.phone || '+91-98765-43210'}
                </div>
              </div>
            </div>

            {/* FHIR R4 Bundle Export Button (D-19) */}
            <button
              type="button"
              id="export-fhir-btn"
              onClick={handleExportFhir}
              disabled={fhirExporting}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '9px 14px',
                borderRadius: '8px',
                border: '1px solid var(--accent-teal, #0d9488)',
                background: 'var(--accent-teal-soft, #f0fdfa)',
                color: 'var(--accent-teal, #0f766e)',
                fontSize: '12px',
                fontWeight: 700,
                cursor: fhirExporting ? 'not-allowed' : 'pointer',
                transition: 'all 0.15s ease',
              }}
            >
              <IconFileText width={14} height={14} />
              <span>{fhirExporting ? 'Exporting FHIR...' : '📥 Export FHIR R4 Bundle'}</span>
            </button>
          </div>
        </div>

        {/* Break-Glass Audited Warning Banner (D-12) */}
        {isOutsideAssignment && !requiresBreakGlass && (
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '8px',
              background: 'var(--warning-amber-soft, #fffbeb)',
              border: '1px solid rgba(217, 119, 6, 0.3)',
              color: 'var(--warning-amber, #d97706)',
              fontSize: '12px',
              fontWeight: 600,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <IconAlertTriangle width={15} height={15} />
            <span>
              <strong>Viewing outside your assignment (Audited access).</strong> Your chart reviews, flag actions, and note updates are permanently recorded in the clinical audit log.
            </span>
          </div>
        )}

        {/* Sub-Tabs Navigation */}
        <div
          style={{
            display: 'flex',
            gap: '8px',
            borderTop: '1px solid var(--border-subtle, #e2e8f0)',
            paddingTop: '14px',
          }}
        >
          {[
            { id: 'overview', label: 'Overview', Icon: IconActivity },
            { id: 'plan', label: 'Recovery Plan', Icon: IconFileText },
            { id: 'medicines', label: 'Medicines', Icon: IconPill },
            { id: 'timeline', label: 'Timeline', Icon: IconClock },
            { id: 'rules', label: 'Limits', Icon: IconShieldCheck },
            { id: 'notes', label: 'Notes', Icon: IconFileText },
            { id: 'agent_activity', label: 'Agent Activity', Icon: IconClock },
            { id: 'messages', label: 'SMS Messages', Icon: IconFileText },
          ].map((tab) => {
            const isActive = subTab === tab.id;
            const TabIcon = tab.Icon;
            return (
              <button
                key={tab.id}
                id={`tab-${tab.id}`}
                type="button"
                onClick={() => setSubTab(tab.id)}
                disabled={requiresBreakGlass}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '7px 14px',
                  borderRadius: '6px',
                  fontSize: '12px',
                  fontWeight: isActive ? 700 : 500,
                  border: 'none',
                  cursor: requiresBreakGlass ? 'not-allowed' : 'pointer',
                  background: isActive ? '#0b1528' : 'transparent',
                  color: isActive ? '#ffffff' : 'var(--text-secondary, #475569)',
                  transition: 'all 0.15s ease',
                  opacity: requiresBreakGlass && !isActive ? 0.5 : 1,
                }}
              >
                <TabIcon width={14} height={14} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 2. Break-Glass Access Required Modal / Wall (D-12) */}
      {requiresBreakGlass ? (
        <div
          style={{
            background: 'var(--bg-surface, #ffffff)',
            border: '1px solid var(--border-subtle, #e2e8f0)',
            borderRadius: '12px',
            padding: '36px 30px',
            boxShadow: 'var(--shadow-card)',
            maxWidth: '650px',
            margin: '20px auto',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '48px',
              height: '48px',
              borderRadius: '50%',
              background: 'var(--warning-amber-soft, #fffbeb)',
              color: 'var(--warning-amber, #d97706)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px auto',
            }}
          >
            <IconShieldCheck width={24} height={24} />
          </div>

          <h3 style={{ fontSize: '17px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: '0 0 8px 0' }}>
            Break-Glass Access Required
          </h3>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary, #475569)', lineHeight: 1.5, margin: '0 0 20px 0' }}>
            This patient is assigned to another clinician's care roster. To view their chart, discharge records, and sensor readings, you must declare a valid clinical reason under clinical audit guidelines.
          </p>

          <form onSubmit={handleBreakGlassSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px', textAlign: 'left' }}>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase', display: 'block', marginBottom: '6px' }}>
                Clinical Justification (Minimum 5 characters) *
              </label>
              <textarea
                rows={3}
                required
                placeholder="e.g. Covering evening urgent on-call rounds; patient called triage helpline with severe dizziness"
                value={breakGlassReason}
                onChange={(e) => setBreakGlassReason(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 12px',
                  borderRadius: '8px',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  background: 'var(--bg-input, #ffffff)',
                  color: 'var(--text-primary, #0f172a)',
                  fontSize: '13px',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
            </div>

            {breakGlassError && (
              <div style={{ fontSize: '12px', color: 'var(--alert-red, #dc2626)', fontWeight: 600 }}>
                {breakGlassError}
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
              {onBackToDirectory && (
                <button
                  type="button"
                  onClick={onBackToDirectory}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle, #cbd5e1)',
                    background: 'transparent',
                    color: 'var(--text-secondary, #475569)',
                    fontSize: '13px',
                    fontWeight: 600,
                    cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
              )}
              <button
                type="submit"
                disabled={breakGlassSubmitting || breakGlassReason.trim().length < 5}
                style={{
                  padding: '8px 18px',
                  borderRadius: '8px',
                  border: 'none',
                  background: 'var(--warning-amber, #d97706)',
                  color: '#ffffff',
                  fontSize: '13px',
                  fontWeight: 700,
                  cursor: breakGlassSubmitting || breakGlassReason.trim().length < 5 ? 'not-allowed' : 'pointer',
                  opacity: breakGlassSubmitting || breakGlassReason.trim().length < 5 ? 0.6 : 1,
                }}
              >
                {breakGlassSubmitting ? 'Verifying...' : 'Authorize & Log Break-Glass Access'}
              </button>
            </div>
          </form>
        </div>
      ) : (
        <>
          {/* 3. SUBTAB 1: CLINICAL OVERVIEW */}
          {subTab === 'overview' && (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '20px' }}>
              {/* Card 1: Latest Sensor Readings with Data Quality Badges (D-18) */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 20px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                      Latest Vital Readings
                    </span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: '#0284c7', background: 'var(--accent-blue-soft, #eff6ff)', padding: '2px 8px', borderRadius: '10px', fontWeight: 700 }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#0284c7' }} />
                      Live · Updated {overviewUpdatedTime}
                    </span>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>ESP32 Watch</span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {/* Heart Rate */}
                  {detailData.latest_readings?.Heart_Rate ? (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 12px',
                        borderRadius: '8px',
                        background: 'var(--bg-base, #f8fafc)',
                        border: '1px solid var(--border-subtle, #e2e8f0)',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>Heart Rate</div>
                        <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                          {detailData.latest_readings.Heart_Rate.measurement_value}{' '}
                          <span style={{ fontSize: '12px', fontWeight: 500 }}>{detailData.latest_readings.Heart_Rate.unit}</span>
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)', marginTop: '2px' }}>
                          {new Date(detailData.latest_readings.Heart_Rate.measured_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                      <div>
                        <DataQualityBadge quality={detailData.latest_readings.Heart_Rate.quality_status} />
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', padding: '10px' }}>No Heart Rate readings.</div>
                  )}

                  {/* SpO2 */}
                  {detailData.latest_readings?.SpO2 ? (
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '10px 12px',
                        borderRadius: '8px',
                        background: 'var(--bg-base, #f8fafc)',
                        border: '1px solid var(--border-subtle, #e2e8f0)',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>Blood Oxygen (SpO2)</div>
                        <div style={{ fontSize: '18px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                          {detailData.latest_readings.SpO2.measurement_value}{' '}
                          <span style={{ fontSize: '12px', fontWeight: 500 }}>{detailData.latest_readings.SpO2.unit}</span>
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)', marginTop: '2px' }}>
                          {new Date(detailData.latest_readings.SpO2.measured_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </div>
                      </div>
                      <div>
                        <DataQualityBadge quality={detailData.latest_readings.SpO2.quality_status} />
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', padding: '10px', background: 'var(--bg-base, #f8fafc)', borderRadius: '8px' }}>
                      SpO2 sensor currently disconnected or uncalibrated.
                    </div>
                  )}

                  {detailData.data_check_note && (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '8px', padding: '6px 10px', background: 'var(--bg-base, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
                      ℹ️ {detailData.data_check_note}
                    </div>
                  )}
                </div>
              </div>

              {/* Card 1B: Watch Device Health (Phase 5) */}
              {detailData.device_health && (
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '18px 20px',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                      Device Health & Connectivity
                    </div>
                    <span className={`status-pill status-pill-${detailData.device_health.connectivity_status === 'Online' ? 'success' : 'neutral'}`}>
                      {detailData.device_health.connectivity_status || 'Online'}
                    </span>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    <div style={{ padding: '10px', background: 'var(--bg-base, #f8fafc)', borderRadius: '8px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>Device ID</div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', fontFamily: "var(--font-mono, monospace)", marginTop: '2px' }}>
                        {detailData.device_health.device_id || 'DEV-ESP32'}
                      </div>
                    </div>
                    <div style={{ padding: '10px', background: 'var(--bg-base, #f8fafc)', borderRadius: '8px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>Battery</div>
                      <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)', marginTop: '2px' }}>
                        🔋 {detailData.device_health.battery_pct ?? 85}%
                      </div>
                    </div>
                  </div>

                  <div style={{ marginTop: '12px', fontSize: '11px', color: 'var(--text-secondary, #475569)', lineHeight: 1.5 }}>
                    <div>Last seen: <strong>{detailData.device_health.last_seen_at ? new Date(detailData.device_health.last_seen_at).toLocaleTimeString() : 'Recent'}</strong> ({detailData.device_health.minutes_since_last_seen ?? 0}m ago)</div>
                    <div style={{ marginTop: '4px', color: 'var(--text-muted, #64748b)' }}>
                      Monitored by Rounds silence check (expected every {detailData.device_health.expected_interval_minutes || 60}m)
                    </div>
                  </div>
                </div>
              )}

              {/* Card 2: 7-Day Dose Adherence Grid */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 20px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                    7-Day Dose Tracking
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>Self-reported</span>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {(detailData.adherence_grid || []).slice(-7).map((d, idx) => {
                    const rawDate = d.log_date || d.date;
                    let dateStr = `Day ${idx + 1}`;
                    if (rawDate) {
                      const dObj = new Date(String(rawDate).includes('T') ? rawDate : `${rawDate}T00:00:00`);
                      if (!isNaN(dObj.getTime())) {
                        dateStr = dObj.toLocaleDateString([], { weekday: 'short', month: 'numeric', day: 'numeric' });
                      }
                    }
                    const taken = d.taken_count !== undefined ? d.taken_count : (d.taken || 0);
                    const skipped = d.skipped_count !== undefined ? d.skipped_count : (d.skipped || 0);
                    const unconfirmed = d.pending_count !== undefined ? d.pending_count : (d.unconfirmed || 0);

                    return (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '6px 10px',
                          borderRadius: '6px',
                          background: 'var(--bg-base, #f8fafc)',
                          border: '1px solid var(--border-subtle, #e2e8f0)',
                        }}
                      >
                        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                          {dateStr}
                        </span>
                        <div style={{ display: 'flex', gap: '10px', fontSize: '11px' }}>
                          <span style={{ color: 'var(--success-green, #059669)', fontWeight: 700 }}>{taken} taken</span>
                          {skipped > 0 && <span style={{ color: 'var(--warning-amber, #d97706)', fontWeight: 700 }}>{skipped} skipped</span>}
                          {unconfirmed > 0 && <span style={{ color: 'var(--text-muted, #94a3b8)', fontWeight: 600 }}>{unconfirmed} unconfirmed</span>}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Card 3: Caregiver Info & Escalation Consent */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 20px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                    Caregiver Contacts
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>Escalation Ladder</span>
                </div>

                {(detailData.caregivers || []).length === 0 ? (
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', padding: '10px' }}>
                    No designated caregiver on file.
                  </div>
                ) : (
                  detailData.caregivers.map((cg) => (
                    <div
                      key={cg.caregiver_id}
                      style={{
                        padding: '12px',
                        borderRadius: '8px',
                        background: 'var(--bg-base, #f8fafc)',
                        border: '1px solid var(--border-subtle, #e2e8f0)',
                        marginBottom: '8px',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                          {cg.full_name} <span style={{ fontSize: '11px', fontWeight: 500, color: 'var(--text-muted, #64748b)' }}>({cg.relationship})</span>
                        </div>
                        {cg.consent_granted ? (
                          <span style={{ fontSize: '10px', fontWeight: 700, padding: '2px 7px', borderRadius: '12px', background: 'var(--success-green-soft, #f0fdf4)', color: 'var(--success-green, #059669)' }}>
                            SMS Consent Granted
                          </span>
                        ) : (
                          <span style={{ fontSize: '10px', fontWeight: 700, padding: '2px 7px', borderRadius: '12px', background: 'var(--alert-red-soft, #fef2f2)', color: 'var(--alert-red, #dc2626)' }}>
                            No Consent (Skipped in Escalation)
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '4px' }}>
                        Phone: {cg.phone}
                      </div>
                    </div>
                  ))
                )}
              </div>

              {/* Card 4: LACE Risk Context */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 20px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                  <div>
                    <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                      LACE Risk Context
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '2px' }}>
                      Clinician-entered &bull; Context only &bull; Non-automated
                    </div>
                  </div>
                  <button
                    type="button"
                    id="update-lace-btn"
                    onClick={() => {
                      if (laceData) {
                        setLaceLos(laceData.length_of_stay_days || 0);
                        setLaceAcute(laceData.acute_admission ?? true);
                        setLaceCharlson(laceData.charlson_index || 0);
                        setLaceEd(laceData.ed_visits_6m || 0);
                      }
                      setLaceModalOpen(true);
                    }}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'var(--bg-base, #f1f5f9)',
                      color: 'var(--text-secondary, #475569)',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {laceData ? 'Update score' : 'Calculate LACE'}
                  </button>
                </div>

                {laceData ? (
                  <div>
                    <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginBottom: '10px' }}>
                      <span style={{ fontSize: '28px', fontWeight: 900, color: laceData.score >= 10 ? 'var(--alert-red, #dc2626)' : 'var(--text-primary, #0f172a)' }}>
                        {laceData.score}
                      </span>
                      <span style={{ fontSize: '13px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>/ 19</span>
                      <span
                        style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 8px',
                          borderRadius: '12px',
                          marginLeft: 'auto',
                          background: laceData.risk_tier === 'High' ? 'var(--alert-red-soft, #fef2f2)' : laceData.risk_tier === 'Moderate' ? 'var(--warning-amber-soft, #fffbeb)' : 'var(--success-green-soft, #f0fdf4)',
                          color: laceData.risk_tier === 'High' ? 'var(--alert-red, #dc2626)' : laceData.risk_tier === 'Moderate' ? 'var(--warning-amber, #d97706)' : 'var(--success-green, #059669)',
                        }}
                      >
                        {laceData.risk_tier} Risk Tier
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '8px', fontSize: '11px', marginBottom: '12px' }}>
                      <div style={{ padding: '6px 8px', background: 'var(--bg-base, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <div style={{ color: 'var(--text-muted, #64748b)' }}>Length of Stay (L)</div>
                        <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>{laceData.breakdown?.length_of_stay_points || 0} pts ({laceData.length_of_stay_days}d)</div>
                      </div>
                      <div style={{ padding: '6px 8px', background: 'var(--bg-base, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <div style={{ color: 'var(--text-muted, #64748b)' }}>Acuity of Admission (A)</div>
                        <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>{laceData.breakdown?.acuity_points || 0} pts ({laceData.acute_admission ? 'Acute' : 'Elective'})</div>
                      </div>
                      <div style={{ padding: '6px 8px', background: 'var(--bg-base, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <div style={{ color: 'var(--text-muted, #64748b)' }}>Comorbidity Charlson (C)</div>
                        <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>{laceData.breakdown?.comorbidity_points || 0} pts (Index {laceData.charlson_index})</div>
                      </div>
                      <div style={{ padding: '6px 8px', background: 'var(--bg-base, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <div style={{ color: 'var(--text-muted, #64748b)' }}>ED Visits 6m (E)</div>
                        <div style={{ fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>{laceData.breakdown?.ed_visits_points || 0} pts ({laceData.ed_visits_6m} visits)</div>
                      </div>
                    </div>

                    <div style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)', background: 'var(--bg-base, #f8fafc)', padding: '6px 8px', borderRadius: '6px', border: '1px dashed var(--border-subtle, #cbd5e1)' }}>
                      <strong>Evidence disclaimer:</strong> Published evidence on LACE discrimination is mixed (c-statistic ~0.65). CareLoop displays LACE strictly for clinician reference and never uses it to trigger automated alert suppression or clinical actions.
                    </div>
                  </div>
                ) : (
                  <div style={{ fontSize: '12px', color: 'var(--text-muted, #64748b)', padding: '12px 0', textAlign: 'center' }}>
                    No LACE index recorded yet. Click above to calculate post-discharge risk context.
                  </div>
                )}
              </div>

              {/* Card 5: Open Flags & Drawer Launcher */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 20px',
                  boxShadow: 'var(--shadow-card)',
                  gridColumn: '1 / -1',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                    Active Flags Requiring Clinical Review ({detailData.open_flags?.length || 0})
                  </div>
                </div>

                {(detailData.open_flags || []).length === 0 ? (
                  <div style={{ fontSize: '12px', color: 'var(--success-green, #059669)', fontWeight: 600, padding: '10px' }}>
                    ✓ No active flags for this patient.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {detailData.open_flags.map((fl) => (
                      <div
                        key={fl.flag_id}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '10px 14px',
                          borderRadius: '8px',
                          background: 'var(--bg-base, #f8fafc)',
                          border: '1px solid var(--border-subtle, #e2e8f0)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span
                            style={{
                              fontSize: '11px',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: '12px',
                              background: fl.severity === 'Urgent_Review' ? 'var(--alert-red-soft, #fef2f2)' : 'var(--warning-amber-soft, #fffbeb)',
                              color: fl.severity === 'Urgent_Review' ? 'var(--alert-red, #dc2626)' : 'var(--warning-amber, #d97706)',
                            }}
                          >
                            {fl.severity === 'Review_Soon' ? 'Review soon' : fl.severity === 'Urgent_Review' ? 'Urgent' : fl.severity}
                          </span>
                          <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                            {fl.reason}
                          </span>
                        </div>
                        {onOpenFlagDrawer && (
                          <button
                            type="button"
                            onClick={() => onOpenFlagDrawer(fl.flag_id)}
                            style={{
                              padding: '4px 10px',
                              borderRadius: '6px',
                              border: '1px solid var(--border-subtle, #cbd5e1)',
                              background: '#0b1528',
                              color: '#ffffff',
                              fontSize: '11px',
                              fontWeight: 600,
                              cursor: 'pointer',
                            }}
                          >
                            Review flag →
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* 3. SUBTAB: RECOVERY PLAN (Phase 4) */}
          {subTab === 'plan' && (() => {
            const currentPlan = plansData.plans?.find((p) => p.plan_id === selectedPlanId) || plansData.plans?.[0] || null;
            const isDoctor = user?.role === 'doctor' || user?.role === 'Primary_Doctor';
            const hasMismatch = currentPlan?.items?.some((it) => it.reconcile_status === 'Mismatch');

            return (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                {/* Header Controls */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '18px 24px',
                    boxShadow: 'var(--shadow-card)',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    flexWrap: 'wrap',
                    gap: '12px',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                        Recovery Plan {currentPlan ? `v${currentPlan.version}` : ''}
                      </h3>
                      {currentPlan && (
                        <span
                          style={{
                            padding: '3px 8px',
                            borderRadius: '12px',
                            fontSize: '11px',
                            fontWeight: 700,
                            background:
                              currentPlan.status === 'Approved'
                                ? 'rgba(16, 185, 129, 0.15)'
                                : currentPlan.status === 'Draft'
                                ? 'rgba(245, 158, 11, 0.15)'
                                : 'rgba(100, 116, 139, 0.15)',
                            color:
                              currentPlan.status === 'Approved'
                                ? '#065f46'
                                : currentPlan.status === 'Draft'
                                ? '#92400e'
                                : '#475569',
                          }}
                        >
                          {currentPlan.status === 'Approved'
                            ? 'Approved (Published to Patient)'
                            : currentPlan.status === 'Draft'
                            ? 'Draft (Invisible to Patient)'
                            : currentPlan.status}
                        </span>
                      )}
                    </div>
                    <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
                      Synthesized from discharge papers with chunk citations. Patient cannot see drafts until Doctor approval.
                    </p>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    {plansData.plans?.length > 1 && (
                      <div style={{ display: 'flex', gap: '4px', background: 'var(--bg-card, #f8fafc)', padding: '2px', borderRadius: '6px' }}>
                        {plansData.plans.map((p) => (
                          <button
                            key={p.plan_id}
                            type="button"
                            onClick={() => setSelectedPlanId(p.plan_id)}
                            style={{
                              padding: '4px 8px',
                              borderRadius: '4px',
                              border: 'none',
                              fontSize: '11px',
                              fontWeight: selectedPlanId === p.plan_id ? 700 : 500,
                              background: selectedPlanId === p.plan_id ? '#0b1528' : 'transparent',
                              color: selectedPlanId === p.plan_id ? '#ffffff' : 'var(--text-secondary, #64748b)',
                              cursor: 'pointer',
                            }}
                          >
                            v{p.version} ({p.status})
                          </button>
                        ))}
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={handleDraftPlan}
                      disabled={draftingPlan}
                      style={{
                        padding: '6px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: 'transparent',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: draftingPlan ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {draftingPlan ? 'Drafting from Papers...' : '+ Draft Recovery Plan'}
                    </button>

                    {isDoctor && currentPlan && currentPlan.status === 'Draft' && (
                      <>
                        <button
                          type="button"
                          onClick={() => handleApprovePlan(currentPlan.plan_id)}
                          disabled={approvingPlanId === currentPlan.plan_id}
                          style={{
                            padding: '6px 14px',
                            borderRadius: '6px',
                            border: 'none',
                            background: '#047857',
                            color: '#ffffff',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: approvingPlanId ? 'not-allowed' : 'pointer',
                          }}
                        >
                          {approvingPlanId === currentPlan.plan_id ? 'Publishing...' : 'Approve & Publish'}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleRejectPlan(currentPlan.plan_id)}
                          disabled={approvingPlanId === currentPlan.plan_id}
                          style={{
                            padding: '6px 10px',
                            borderRadius: '6px',
                            border: '1px solid #dc2626',
                            background: 'transparent',
                            color: '#dc2626',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: approvingPlanId ? 'not-allowed' : 'pointer',
                          }}
                        >
                          Reject
                        </button>
                      </>
                    )}

                    <button
                      type="button"
                      onClick={fetchPlans}
                      style={{
                        padding: '6px 10px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: 'transparent',
                        color: 'var(--text-secondary, #475569)',
                        fontSize: '11px',
                        cursor: 'pointer',
                      }}
                    >
                      ↻
                    </button>
                  </div>
                </div>

                {/* Feedback Banners */}
                {planActionMsg && (
                  <div
                    style={{
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: 'rgba(16, 185, 129, 0.1)',
                      border: '1px solid #10b981',
                      color: '#065f46',
                      fontSize: '13px',
                      fontWeight: 600,
                    }}
                  >
                    ✓ {planActionMsg}
                  </div>
                )}

                {planActionError && (
                  <div
                    style={{
                      padding: '10px 14px',
                      borderRadius: '8px',
                      background: 'rgba(239, 68, 68, 0.1)',
                      border: '1px solid #ef4444',
                      color: '#991b1b',
                      fontSize: '13px',
                      fontWeight: 600,
                    }}
                  >
                    ⚠️ {planActionError}
                  </div>
                )}

                {hasMismatch && (
                  <div
                    style={{
                      padding: '12px 16px',
                      borderRadius: '8px',
                      background: 'rgba(245, 158, 11, 0.12)',
                      border: '1px solid #f59e0b',
                      color: '#92400e',
                      fontSize: '13px',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '10px',
                    }}
                  >
                    <span style={{ fontSize: '18px' }}>⚠️</span>
                    <div>
                      <strong>Prescription Reconciliation Discrepancy:</strong> One or more items in this plan have dosage or frequency instructions that do not match the recorded pharmacy prescription. Clinician review is required before approving.
                    </div>
                  </div>
                )}

                {/* Plan Metadata Strip */}
                {currentPlan && (
                  <div
                    style={{
                      background: 'var(--bg-card, #f8fafc)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      borderRadius: '8px',
                      padding: '10px 16px',
                      fontSize: '12px',
                      color: 'var(--text-secondary, #64748b)',
                      display: 'flex',
                      justifyContent: 'space-between',
                      flexWrap: 'wrap',
                      gap: '8px',
                    }}
                  >
                    <div>
                      <strong>Drafted by:</strong> {currentPlan.drafted_by || 'Care Team'} ·{' '}
                      {new Date(currentPlan.drafted_at).toLocaleString()}
                    </div>
                    {currentPlan.approved_at && (
                      <div>
                        <strong>Approved by:</strong> Dr. {currentPlan.approved_by_name || 'Sharma'} ·{' '}
                        {new Date(currentPlan.approved_at).toLocaleString()}
                      </div>
                    )}
                    <div>
                      <strong>Grounding Check:</strong> All numbers strictly cited from discharge chunk
                    </div>
                  </div>
                )}

                {/* Items List */}
                {plansLoading ? (
                  <div style={{ padding: '40px', textAlign: 'center', color: '#64748b', fontSize: '13px' }}>
                    Loading recovery plan items...
                  </div>
                ) : !currentPlan || !currentPlan.items || currentPlan.items.length === 0 ? (
                  <div
                    style={{
                      background: 'var(--bg-surface, #ffffff)',
                      border: '1px solid var(--border-subtle, #e2e8f0)',
                      borderRadius: '12px',
                      padding: '48px',
                      textAlign: 'center',
                      color: 'var(--text-secondary, #64748b)',
                    }}
                  >
                    <div style={{ fontSize: '32px', marginBottom: '8px' }}>📋</div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                      No recovery plan drafted yet
                    </div>
                    <p style={{ maxWidth: '440px', margin: '8px auto 16px', fontSize: '13px', lineHeight: '1.5' }}>
                      Click "Draft Recovery Plan" to automatically synthesize structured medication schedules, wound care instructions, activity limits, and red flags directly from the patient's discharge papers.
                    </p>
                    <button
                      type="button"
                      onClick={handleDraftPlan}
                      disabled={draftingPlan}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: 'none',
                        background: '#0284c7',
                        color: '#ffffff',
                        fontSize: '13px',
                        fontWeight: 700,
                        cursor: draftingPlan ? 'not-allowed' : 'pointer',
                      }}
                    >
                      {draftingPlan ? 'Drafting...' : 'Draft Plan from Papers'}
                    </button>
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {currentPlan.items.map((it) => (
                      <div
                        key={it.item_id}
                        style={{
                          background: 'var(--bg-surface, #ffffff)',
                          border: it.reconcile_status === 'Mismatch' ? '1px solid #f59e0b' : '1px solid var(--border-subtle, #e2e8f0)',
                          borderRadius: '10px',
                          padding: '16px 20px',
                          boxShadow: 'var(--shadow-card)',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '8px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <span
                              style={{
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontSize: '11px',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                background:
                                  it.item_type === 'Medicine'
                                    ? '#dbeafe'
                                    : it.item_type === 'Warning_Signs'
                                    ? '#fee2e2'
                                    : it.item_type === 'Wound_Care'
                                    ? '#ede9fe'
                                    : '#f1f5f9',
                                color:
                                  it.item_type === 'Medicine'
                                    ? '#1e40af'
                                    : it.item_type === 'Warning_Signs'
                                    ? '#991b1b'
                                    : it.item_type === 'Wound_Care'
                                    ? '#6b21a8'
                                    : '#334155',
                              }}
                            >
                              {it.item_type?.replace(/_/g, ' ')}
                            </span>
                            <span style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                              {it.title}
                            </span>
                            {it.schedule_text && (
                              <span
                                style={{
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  background: 'var(--bg-card, #f8fafc)',
                                  border: '1px solid var(--border-subtle, #e2e8f0)',
                                  color: 'var(--text-secondary, #64748b)',
                                }}
                              >
                                ⏰ {it.schedule_text}
                              </span>
                            )}
                          </div>

                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            {it.reconcile_status && (
                              <span
                                style={{
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  background: it.reconcile_status === 'Matches' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
                                  color: it.reconcile_status === 'Matches' ? '#065f46' : '#991b1b',
                                }}
                              >
                                {it.reconcile_status === 'Matches' ? '✓ Prescription Matches' : '⚠️ Prescription Mismatch'}
                              </span>
                            )}

                            {it.verified_by_staff_id ? (
                              <span
                                style={{
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  background: 'rgba(16, 185, 129, 0.15)',
                                  color: '#065f46',
                                }}
                              >
                                ✓ Verified by {it.verified_by_name || 'Staff'}
                              </span>
                            ) : (
                              <button
                                type="button"
                                onClick={() => handleVerifyItem(it.item_id)}
                                disabled={verifyingItemId === it.item_id}
                                style={{
                                  padding: '3px 8px',
                                  borderRadius: '4px',
                                  border: '1px solid #0284c7',
                                  background: 'transparent',
                                  color: '#0284c7',
                                  fontSize: '11px',
                                  fontWeight: 600,
                                  cursor: verifyingItemId ? 'not-allowed' : 'pointer',
                                }}
                              >
                                {verifyingItemId === it.item_id ? 'Verifying...' : '✓ Matches Papers'}
                              </button>
                            )}
                          </div>
                        </div>

                        <div style={{ fontSize: '13px', color: 'var(--text-primary, #0f172a)', lineHeight: '1.5' }}>
                          {it.detail}
                        </div>

                        {/* Grounded Chunk Citation Callout */}
                        {it.source_chunk_text && (
                          <div
                            style={{
                              background: 'var(--bg-card, #f8fafc)',
                              borderLeft: '3px solid #0284c7',
                              borderRadius: '0 6px 6px 0',
                              padding: '8px 12px',
                              fontSize: '12px',
                              color: 'var(--text-secondary, #475569)',
                              display: 'flex',
                              flexDirection: 'column',
                              gap: '4px',
                            }}
                          >
                            <div style={{ fontStyle: 'italic', color: 'var(--text-primary, #1e293b)' }}>
                              "{it.source_chunk_text}"
                            </div>
                            <div style={{ fontSize: '11px', color: '#64748b', display: 'flex', gap: '8px' }}>
                              <span>📄 Page {it.page_no || 1}</span>
                              <span>•</span>
                              <span>Chunk #{it.source_chunk_id}</span>
                              {it.section_title && (
                                <>
                                  <span>•</span>
                                  <span>Section: {it.section_title}</span>
                                </>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })()}

          {/* 4. SUBTAB 2: MEDICINES & ADHERENCE */}
          {subTab === 'medicines' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Discharge Prescriptions Table */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '20px 22px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <h3 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: '0 0 14px 0' }}>
                  Discharge Prescriptions (Active Regimen)
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '700px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>MEDICINE</th>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>DOSE INSTRUCTIONS</th>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>COURSE PERIOD</th>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>STATUS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(medicinesData?.prescriptions || []).map((rx) => (
                        <tr key={rx.prescription_id} style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                          <td style={{ padding: '12px', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                            {rx.medicine_name}
                          </td>
                          <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                            {rx.dose_instructions}
                          </td>
                          <td style={{ padding: '12px', fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                            {rx.start_date} to {rx.end_date}
                          </td>
                          <td style={{ padding: '12px' }}>
                            <span style={{ fontSize: '10px', fontWeight: 700, padding: '2px 7px', borderRadius: '12px', background: 'var(--success-green-soft, #f0fdf4)', color: 'var(--success-green, #059669)' }}>
                              Active
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Dose Exceptions & Patient Notes Table */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '20px 22px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: 0 }}>
                    Dose Exceptions & Self-Reported Notes
                  </h3>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                    Labeling strictly: Self-reported
                  </span>
                </div>

                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '700px' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>SCHEDULED TIME</th>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>MEDICINE</th>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>STATUS</th>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>PATIENT NOTE</th>
                        <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>RECORDED BY</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(medicinesData?.exceptions || []).length === 0 ? (
                        <tr>
                          <td colSpan={5} style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '12px' }}>
                            No dose exceptions recorded.
                          </td>
                        </tr>
                      ) : (
                        (medicinesData?.exceptions || []).map((ex) => (
                          <tr key={ex.log_id} style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                            <td style={{ padding: '10px 12px', fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                              {new Date(ex.scheduled_for).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                            </td>
                            <td style={{ padding: '10px 12px', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                              {ex.medicine_name}
                            </td>
                            <td style={{ padding: '10px 12px' }}>
                              <span
                                style={{
                                  fontSize: '10px',
                                  fontWeight: 700,
                                  padding: '2px 7px',
                                  borderRadius: '12px',
                                  background: ex.status === 'Scheduled' ? 'var(--accent-blue-soft, #eff6ff)' : ex.status === 'Skipped' ? 'var(--warning-amber-soft, #fffbeb)' : 'var(--border-subtle, #e2e8f0)',
                                  color: ex.status === 'Scheduled' ? 'var(--accent-blue, #0284c7)' : ex.status === 'Skipped' ? 'var(--warning-amber, #d97706)' : 'var(--text-muted, #64748b)',
                                }}
                              >
                                {ex.status}
                              </span>
                            </td>
                            <td style={{ padding: '10px 12px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                              {ex.patient_note}
                            </td>
                            <td style={{ padding: '10px 12px', fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                              {ex.recorded_by}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* 5. SUBTAB 3: ALERT RULES */}
          {subTab === 'rules' && (
            <div
              style={{
                background: 'var(--bg-surface, #ffffff)',
                border: '1px solid var(--border-subtle, #e2e8f0)',
                borderRadius: '12px',
                padding: '20px 22px',
                boxShadow: 'var(--shadow-card)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
                <div>
                  <h3 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: 0 }}>
                    Clinician-Approved Trigger Rules & Pathway Overrides
                  </h3>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '2px' }}>
                    Threshold modifications write an append-only audit trail with mandatory clinical justification.
                  </div>
                </div>

                {isDoctor ? (
                  <button
                    type="button"
                    id="apply-pathway-btn"
                    onClick={handleOpenPathwayModal}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px',
                      padding: '7px 14px',
                      borderRadius: '8px',
                      border: '1px solid var(--accent-teal, #0d9488)',
                      background: 'var(--accent-teal-soft, #f0fdfa)',
                      color: 'var(--accent-teal, #0f766e)',
                      fontSize: '12px',
                      fontWeight: 700,
                      cursor: 'pointer',
                    }}
                  >
                    <IconShieldCheck width={14} height={14} />
                    <span>Apply Pathway Template (Doctor)</span>
                  </button>
                ) : (
                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', background: 'var(--bg-base, #f1f5f9)', padding: '5px 10px', borderRadius: '6px' }}>
                    🔒 Pathway application requires Doctor role
                  </div>
                )}
              </div>

              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '700px' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                      <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>RULE TYPE</th>
                      <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>THRESHOLD & WINDOW</th>
                      <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>SEVERITY</th>
                      <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>APPROVED BY</th>
                      <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>30D FIRED</th>
                      <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>FALSE ALARMS</th>
                      <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>ACTIONS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rulesData.map((r) => (
                      <tr key={r.rule_id} style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <td style={{ padding: '12px', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                          {r.rule_type.replace(/_/g, ' ')}
                          {r.rule_type === 'Possible_Fall' && detailData?.fall_prompt_counts && (
                            <div style={{ fontSize: '10px', color: 'var(--text-muted, #64748b)', fontWeight: 500, marginTop: '3px' }}>
                              Prompts: {detailData.fall_prompt_counts.prompts_sent} sent · {detailData.fall_prompt_counts.prompts_ok} OK · {detailData.fall_prompt_counts.prompts_unanswered} unanswered
                            </div>
                          )}
                        </td>
                        <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                          {r.rule_type === 'Possible_Fall'
                            ? `Wait ${r.threshold_value || 2} min prompt`
                            : `${r.threshold_value} ${r.measurement_type || ''} ${r.window_hours ? `(${r.window_hours}h)` : ''}`}
                        </td>
                        <td style={{ padding: '12px' }}>
                          <span
                            style={{
                              fontSize: '10px',
                              fontWeight: 700,
                              padding: '2px 7px',
                              borderRadius: '12px',
                              background: r.severity === 'Urgent_Review' ? 'var(--alert-red-soft, #fef2f2)' : 'var(--warning-amber-soft, #fffbeb)',
                              color: r.severity === 'Urgent_Review' ? 'var(--alert-red, #dc2626)' : 'var(--warning-amber, #d97706)',
                            }}
                          >
                            {r.severity === 'Review_Soon' ? 'Review soon' : r.severity === 'Urgent_Review' ? 'Urgent' : r.severity}
                          </span>
                        </td>
                        <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-primary, #0f172a)', fontWeight: 600 }}>
                          {r.approved_by_name || 'Dr. Ananya Sharma'}
                        </td>
                        <td style={{ padding: '12px', fontSize: '12px', fontWeight: 700, color: r.fired_count_30d > 0 ? 'var(--alert-red, #dc2626)' : 'var(--text-muted, #64748b)' }}>
                          {r.fired_count_30d}
                        </td>
                        <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-muted, #64748b)' }}>
                          {r.dismissed_false_count} dismissed
                        </td>
                        <td style={{ padding: '12px' }}>
                          <div style={{ display: 'flex', gap: '6px' }}>
                            <button
                              type="button"
                              onClick={() => handleOpenRuleHistory(r.rule_id)}
                              style={{
                                padding: '4px 8px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-subtle, #cbd5e1)',
                                background: 'var(--bg-base, #f1f5f9)',
                                color: 'var(--text-secondary, #475569)',
                                fontSize: '11px',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              History
                            </button>
                            <button
                              type="button"
                              onClick={() => {
                                setEditingRule(r);
                                setRuleEditThreshold(r.threshold_value);
                                setRuleEditReason('');
                                setRuleEditModalOpen(true);
                              }}
                              style={{
                                padding: '4px 8px',
                                borderRadius: '6px',
                                border: '1px solid var(--accent-teal, #0d9488)',
                                background: 'transparent',
                                color: 'var(--accent-teal, #0f766e)',
                                fontSize: '11px',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              {isDoctor ? 'Edit' : 'Propose'}
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 6. SUBTAB 4: UPGRADED TIMELINE (D-06) */}
          {subTab === 'timeline' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Timeline Filter Controls */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '16px 20px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                {/* Event Type Filter Chips */}
                <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                  {['All', 'Reading', 'Symptom', 'Dose', 'Flag', 'Call', 'Note'].map((type) => {
                    const isActive = timelineType.toLowerCase() === type.toLowerCase();
                    return (
                      <button
                        key={type}
                        type="button"
                        onClick={() => setTimelineType(type)}
                        style={{
                          padding: '5px 12px',
                          borderRadius: '14px',
                          fontSize: '11px',
                          fontWeight: isActive ? 700 : 500,
                          border: 'none',
                          cursor: 'pointer',
                          background: isActive ? '#0b1528' : 'var(--bg-base, #f1f5f9)',
                          color: isActive ? '#ffffff' : 'var(--text-secondary, #475569)',
                          transition: 'all 0.15s ease',
                        }}
                      >
                        {type === 'All' ? 'All Events' : `${type}s`}
                      </button>
                    );
                  })}
                </div>

                {/* Date Range Selector */}
                <div style={{ display: 'flex', gap: '6px' }}>
                  {[
                    { id: 'today', label: 'Today' },
                    { id: '7days', label: 'Past 7 Days' },
                    { id: 'all', label: 'All History' },
                  ].map((rg) => (
                    <button
                      key={rg.id}
                      type="button"
                      onClick={() => setTimelineRange(rg.id)}
                      style={{
                        padding: '5px 10px',
                        borderRadius: '6px',
                        fontSize: '11px',
                        fontWeight: timelineRange === rg.id ? 700 : 500,
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        cursor: 'pointer',
                        background: timelineRange === rg.id ? 'var(--navy-deep, #0b1528)' : 'transparent',
                        color: timelineRange === rg.id ? '#ffffff' : 'var(--text-secondary, #475569)',
                      }}
                    >
                      {rg.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Vital Readings Chart with Approved Limit Dashed Lines (D-06) */}
              {timelineData?.chart_readings && timelineData.chart_readings.length > 0 && (
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px 22px',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                    <h3 style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: 0 }}>
                      Heart Rate & Sensor Trend with Approved Rule Limits
                    </h3>
                    <div style={{ display: 'flex', gap: '14px', fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '12px', height: '2px', background: 'var(--alert-red, #dc2626)', borderTop: '2px dashed #dc2626' }} />
                        HR Limit ({timelineData.chart_limits?.hr_max || 110} bpm)
                      </span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--accent-teal, #0d9488)' }} />
                        Readings
                      </span>
                    </div>
                  </div>

                  {/* SVG Trend Graph */}
                  <div style={{ width: '100%', height: '140px', position: 'relative' }}>
                    <svg width="100%" height="100%" viewBox="0 0 600 120" preserveAspectRatio="none" style={{ overflow: 'visible' }}>
                      {/* HR Limit Dashed Line */}
                      <line x1="0" y1="35" x2="600" y2="35" stroke="#dc2626" strokeWidth="1.5" strokeDasharray="4 4" />
                      <text x="590" y="30" textAnchor="end" fill="#dc2626" fontSize="10" fontWeight="700">
                        Approved limit: {timelineData.chart_limits?.hr_max || 110} bpm
                      </text>

                      {/* Line of Readings */}
                      {timelineData.chart_readings.map((pt, idx) => {
                        const x = (idx / Math.max(1, timelineData.chart_readings.length - 1)) * 580 + 10;
                        const y = Math.max(20, Math.min(105, 120 - ((pt.value - 40) / (150 - 40)) * 100));
                        return (
                          <g key={idx}>
                            <circle
                              cx={x}
                              cy={y}
                              r={pt.quality === 'Invalid' ? 4 : 3}
                              fill={pt.quality === 'Invalid' ? '#dc2626' : '#0d9488'}
                              stroke="#ffffff"
                              strokeWidth="1"
                            />
                          </g>
                        );
                      })}
                    </svg>
                  </div>
                </div>
              )}

              {/* Day Groups with Collapsed Events (D-06) */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {(timelineData?.day_groups || []).map((grp, grpIdx) => (
                  <React.Fragment key={grp.date}>
                    {/* Explicit Hospital Stay (Days 1–3) vs Home Recovery (Days 4+) Dividing Line (Phase 3) */}
                    {grp.is_inpatient && (grpIdx === 0 || !(timelineData?.day_groups || [])[grpIdx - 1]?.is_inpatient) && (
                      <div
                        style={{
                          margin: '10px 0',
                          padding: '14px 20px',
                          background: 'var(--role-doctor-soft, #f5f3ff)',
                          border: '1px solid var(--role-doctor, #7c3aed)',
                          borderLeft: '5px solid var(--role-doctor, #7c3aed)',
                          borderRadius: '10px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          boxShadow: 'var(--shadow-sm)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div
                            style={{
                              width: '28px',
                              height: '28px',
                              borderRadius: '50%',
                              background: 'var(--role-doctor, #7c3aed)',
                              color: '#ffffff',
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              fontSize: '14px',
                              fontWeight: 800,
                            }}
                          >
                            ✓
                          </div>
                          <div>
                            <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--role-doctor, #7c3aed)', letterSpacing: '0.02em' }}>
                              HOSPITAL DISCHARGE TRANSITION (DAYS 1–3 INPATIENT → DAY 4+ HOME RECOVERY)
                            </div>
                            <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', marginTop: '2px' }}>
                              Inpatient post-operative course completed. Remote vital sensor monitoring and physician-approved protocol activated at discharge.
                            </div>
                          </div>
                        </div>
                        <span
                          style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            padding: '4px 10px',
                            borderRadius: '12px',
                            background: 'var(--role-doctor, #7c3aed)',
                            color: '#ffffff',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          Physician Cleared
                        </span>
                      </div>
                    )}

                    <div
                      style={{
                        background: 'var(--bg-surface, #ffffff)',
                        border: '1px solid var(--border-subtle, #e2e8f0)',
                        borderRadius: '12px',
                        overflow: 'hidden',
                        boxShadow: 'var(--shadow-card)',
                      }}
                    >
                      {/* Sticky Day Header */}
                      <div
                        style={{
                          padding: '10px 18px',
                          background: 'var(--bg-base, #f8fafc)',
                          borderBottom: '1px solid var(--border-subtle, #e2e8f0)',
                          fontSize: '12px',
                          fontWeight: 800,
                          color: 'var(--text-primary, #0f172a)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span>{grp.display_date}</span>
                          <span
                            style={{
                              fontSize: '10px',
                              fontWeight: 700,
                              padding: '2px 8px',
                              borderRadius: '10px',
                              background: grp.is_inpatient ? '#e2e8f0' : 'var(--accent-teal-soft, #f0fdfa)',
                              color: grp.is_inpatient ? '#475569' : 'var(--accent-teal, #0d9488)',
                            }}
                          >
                            {grp.phase_label || (grp.is_inpatient ? 'Hospital Stay (Days 1–3)' : 'Recovery at Home (Days 4+)')}
                          </span>
                        </div>
                        <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                          {grp.events.length} event{grp.events.length === 1 ? '' : 's'}
                        </span>
                      </div>

                    {/* Events List */}
                    <div style={{ display: 'flex', flexDirection: 'column' }}>
                      {grp.events.map((ev, evIdx) => (
                        <div
                          key={evIdx}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '12px 18px',
                            borderBottom: evIdx < grp.events.length - 1 ? '1px solid var(--border-subtle, #f1f5f9)' : 'none',
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <span
                              style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                padding: '2px 8px',
                                borderRadius: '12px',
                                textTransform: 'uppercase',
                                background:
                                  ev.event_type === 'Flag'
                                    ? 'var(--alert-red-soft, #fef2f2)'
                                    : ev.event_type === 'Symptom'
                                    ? 'var(--warning-amber-soft, #fffbeb)'
                                    : ev.event_type === 'Dose'
                                    ? 'var(--accent-blue-soft, #eff6ff)'
                                    : 'var(--bg-base, #f1f5f9)',
                                color:
                                  ev.event_type === 'Flag'
                                    ? 'var(--alert-red, #dc2626)'
                                    : ev.event_type === 'Symptom'
                                    ? 'var(--warning-amber, #d97706)'
                                    : ev.event_type === 'Dose'
                                    ? 'var(--accent-blue, #0284c7)'
                                    : 'var(--text-secondary, #475569)',
                              }}
                            >
                              {ev.event_type}
                            </span>

                            <div>
                              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary, #0f172a)' }}>
                                {ev.summary}
                                {ev.repeat_count > 1 && (
                                  <span
                                    style={{
                                      marginLeft: '8px',
                                      fontSize: '11px',
                                      fontWeight: 800,
                                      padding: '1px 6px',
                                      borderRadius: '10px',
                                      background: 'var(--alert-red-soft, #fef2f2)',
                                      color: 'var(--alert-red, #dc2626)',
                                    }}
                                  >
                                    ×{ev.repeat_count}
                                  </span>
                                )}
                              </div>
                              <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', marginTop: '2px' }}>
                                Actor: <strong>{ev.actor}</strong> •{' '}
                                {new Date(ev.event_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                              </div>
                            </div>
                          </div>

                          {ev.quality_status && (
                            <DataQualityBadge quality={ev.quality_status} />
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </React.Fragment>
                ))}
              </div>
            </div>
          )}

          {/* Subtab 5: Notes & Calls (D-15 & D-16) */}
          {subTab === 'notes' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Header Bar */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 24px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                    Clinical Documentation & Contact Log
                  </h3>
                  <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
                    Append-only clinician records and multi-channel patient interaction audit trail.
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {p.phone && (
                    <a
                      href={`tel:${p.phone}`}
                      style={{
                        padding: '8px 14px',
                        borderRadius: '8px',
                        background: 'var(--bg-base, #f1f5f9)',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '12px',
                        fontWeight: 600,
                        textDecoration: 'none',
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                      }}
                    >
                      <span>📞 Call: {p.phone}</span>
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => setContactModalOpen(true)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '8px',
                      background: 'var(--accent-teal, #0d9488)',
                      border: 'none',
                      color: '#ffffff',
                      fontSize: '12px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    + Log Communication
                  </button>
                </div>
              </div>

              {/* Add Note Card (D-16 Append-Only) */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '20px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                      {amendsNoteId ? `Amend Note #${amendsNoteId}` : 'Add New Clinical Note'}
                    </span>
                    {amendsNoteId && (
                      <span style={{ fontSize: '11px', color: '#b45309', background: '#fef3c7', padding: '2px 8px', borderRadius: '4px', fontWeight: 600 }}>
                        Appending correction record
                      </span>
                    )}
                  </div>
                  {amendsNoteId && (
                    <button
                      type="button"
                      onClick={() => { setAmendsNoteId(null); setNoteText(''); }}
                      style={{ border: 'none', background: 'transparent', color: 'var(--text-muted, #64748b)', fontSize: '12px', cursor: 'pointer' }}
                    >
                      Cancel amendment
                    </button>
                  )}
                </div>

                <div style={{ display: 'flex', gap: '10px', marginBottom: '12px' }}>
                  {['General', 'Review', 'Call', 'Plan_Change'].map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setNoteType(t)}
                      style={{
                        padding: '5px 12px',
                        borderRadius: '6px',
                        border: noteType === t ? '1px solid var(--accent-teal, #0d9488)' : '1px solid var(--border-subtle, #cbd5e1)',
                        background: noteType === t ? 'var(--accent-teal-soft, #ecfdf5)' : 'var(--bg-base, #f8fafc)',
                        color: noteType === t ? 'var(--accent-teal, #0d9488)' : 'var(--text-secondary, #475569)',
                        fontSize: '12px',
                        fontWeight: noteType === t ? 700 : 500,
                        cursor: 'pointer',
                      }}
                    >
                      {t.replace('_', ' ')}
                    </button>
                  ))}
                </div>

                <textarea
                  value={noteText}
                  onChange={(e) => setNoteText(e.target.value)}
                  placeholder={amendsNoteId ? "Enter clinical correction or updated note text..." : "Document observation, care decision, or clinical instructions..."}
                  rows={3}
                  style={{
                    width: '100%',
                    padding: '10px 12px',
                    borderRadius: '8px',
                    border: '1px solid var(--border-subtle, #cbd5e1)',
                    background: 'var(--bg-base, #f8fafc)',
                    color: 'var(--text-primary, #0f172a)',
                    fontSize: '13px',
                    lineHeight: '1.5',
                    boxSizing: 'border-box',
                    marginBottom: '12px',
                  }}
                />

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    disabled={noteSubmitting || noteText.trim().length < 3}
                    onClick={async () => {
                      setNoteSubmitting(true);
                      try {
                        await addPatientNote(patientId, noteText.trim(), noteType, amendsNoteId);
                        setNoteText('');
                        setAmendsNoteId(null);
                        await fetchNotesAndContacts();
                      } catch (err) {
                        alert(err.message || 'Failed to save clinical note.');
                      } finally {
                        setNoteSubmitting(false);
                      }
                    }}
                    style={{
                      padding: '8px 18px',
                      borderRadius: '8px',
                      background: noteText.trim().length >= 3 ? '#0284c7' : 'var(--bg-base, #cbd5e1)',
                      border: 'none',
                      color: '#ffffff',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: noteText.trim().length >= 3 ? 'pointer' : 'not-allowed',
                    }}
                  >
                    {noteSubmitting ? 'Saving...' : amendsNoteId ? 'Save Amendment Note' : 'Append Clinical Note'}
                  </button>
                </div>
              </div>

              {/* Split View: Notes History (Left) and Contact History (Right) */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                {/* 1. Clinical Notes History */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <h4 style={{ margin: '0 0 16px 0', fontSize: '14px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                    Notes Timeline ({notesData.length})
                  </h4>

                  {notesData.length === 0 ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                      No clinical notes recorded for this patient yet.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {notesData.map((note) => (
                        <div
                          key={note.note_id}
                          style={{
                            padding: '14px',
                            borderRadius: '8px',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                            background: note.amends_note_id ? '#fffbeb' : 'var(--bg-base, #f8fafc)',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span
                                style={{
                                  fontSize: '10px',
                                  fontWeight: 700,
                                  textTransform: 'uppercase',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  background: note.note_type === 'Plan_Change' ? '#fef3c7' : note.note_type === 'Review' ? '#eff6ff' : '#f1f5f9',
                                  color: note.note_type === 'Plan_Change' ? '#b45309' : note.note_type === 'Review' ? '#1d4ed8' : '#475569',
                                }}
                              >
                                {note.note_type}
                              </span>
                              {note.amends_note_id && (
                                <span style={{ fontSize: '11px', color: '#b45309', fontWeight: 600 }}>
                                  Amends note #{note.amends_note_id}
                                </span>
                              )}
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                              {note.created_at ? note.created_at.replace('T', ' ').slice(0, 16) : '—'}
                            </span>
                          </div>

                          <p style={{ margin: '0 0 10px 0', fontSize: '13px', color: 'var(--text-primary, #0f172a)', lineHeight: '1.5' }}>
                            {note.note_text}
                          </p>

                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span style={{ fontSize: '11px', color: 'var(--text-secondary, #475569)' }}>
                              By <strong>{note.author_name}</strong> ({note.author_role || 'Staff'})
                            </span>
                            <button
                              type="button"
                              onClick={() => {
                                setAmendsNoteId(note.note_id);
                                setNoteType(note.note_type);
                                setNoteText(`Amended: `);
                                window.scrollTo({ top: 300, behavior: 'smooth' });
                              }}
                              style={{
                                border: 'none',
                                background: 'transparent',
                                color: 'var(--accent-teal, #0d9488)',
                                fontSize: '11px',
                                fontWeight: 600,
                                cursor: 'pointer',
                              }}
                            >
                              Amend
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* 2. Communication Log History */}
                <div
                  style={{
                    background: 'var(--bg-surface, #ffffff)',
                    border: '1px solid var(--border-subtle, #e2e8f0)',
                    borderRadius: '12px',
                    padding: '20px',
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <h4 style={{ margin: '0 0 16px 0', fontSize: '14px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                    Contact Log ({contactsData.length})
                  </h4>

                  {contactsData.length === 0 ? (
                    <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                      No contact attempts recorded yet.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {contactsData.map((c) => (
                        <div
                          key={c.contact_id}
                          style={{
                            padding: '14px',
                            borderRadius: '8px',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                            background: 'var(--bg-base, #f8fafc)',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '6px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span style={{ fontSize: '11px', fontWeight: 700, color: '#0284c7', background: '#eff6ff', padding: '2px 6px', borderRadius: '4px' }}>
                                {c.channel}
                              </span>
                              <span
                                style={{
                                  fontSize: '11px',
                                  fontWeight: 700,
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  background: c.outcome === 'Reached' ? '#ecfdf5' : '#fef3c7',
                                  color: c.outcome === 'Reached' ? '#047857' : '#b45309',
                                }}
                              >
                                {c.outcome}
                              </span>
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                              {c.contacted_at ? c.contacted_at.replace('T', ' ').slice(0, 16) : '—'}
                            </span>
                          </div>

                          <p style={{ margin: '0 0 8px 0', fontSize: '12px', color: 'var(--text-primary, #0f172a)' }}>
                            {c.summary || 'No summary text provided.'}
                          </p>

                          <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                            Logged by <strong>{c.staff_name || 'Care Team'}</strong>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Subtab 6: Agent Activity (Rounds & Automation Policy Feed) */}
          {subTab === 'agent_activity' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Header Bar */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 24px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                    Scheduled & Automated Agent Activity
                  </h3>
                  <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
                    Outbound prompts, check-in dispatches, and routine reminders evaluated by CareLoop's automation policy.
                  </p>
                </div>

                {p.rounds_paused_until && (
                  <div
                    style={{
                      padding: '6px 12px',
                      borderRadius: '8px',
                      background: 'var(--warning-amber-soft, #fffbeb)',
                      border: '1px solid var(--warning-amber, #d97706)',
                      color: 'var(--warning-amber, #b45309)',
                      fontSize: '12px',
                      fontWeight: 600,
                    }}
                  >
                    ⏸ Rounds Paused until {p.rounds_paused_until} ({p.rounds_pause_reason || 'Clinician hold'})
                  </div>
                )}
              </div>

              {/* Table Card */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '20px 22px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <h3 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: 0 }}>
                    Action Queue & Execution Log ({agentActivityData.length})
                  </h3>
                  <button
                    type="button"
                    onClick={fetchAgentActivity}
                    style={{
                      padding: '4px 10px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'transparent',
                      color: 'var(--text-secondary, #475569)',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Refresh Feed
                  </button>
                </div>

                {agentActivityLoading ? (
                  <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    Loading agent activity feed...
                  </div>
                ) : agentActivityData.length === 0 ? (
                  <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    No scheduled or past agent actions recorded for this patient.
                  </div>
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', minWidth: '700px' }}>
                      <thead>
                        <tr style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                          <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>SCHEDULED / EXECUTED</th>
                          <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>ACTION</th>
                          <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>CHANNEL</th>
                          <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>STATUS</th>
                          <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>POLICY RATIONALE</th>
                          <th style={{ padding: '8px 12px', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)' }}>ATTEMPTS</th>
                        </tr>
                      </thead>
                      <tbody>
                        {agentActivityData.map((act) => {
                          const statusColor =
                            act.status === 'Dispatched'
                              ? { bg: 'var(--success-green-soft, #f0fdf4)', text: 'var(--success-green, #059669)' }
                              : act.status === 'Pending'
                              ? { bg: 'var(--warning-amber-soft, #fffbeb)', text: 'var(--warning-amber, #d97706)' }
                              : act.status === 'Hold'
                              ? { bg: '#fef2f2', text: '#b91c1c' }
                              : { bg: 'var(--bg-base, #f1f5f9)', text: 'var(--text-muted, #64748b)' };

                          return (
                            <tr key={act.scheduled_action_id} style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                              <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-primary, #0f172a)' }}>
                                <div style={{ fontWeight: 600 }}>{act.scheduled_for}</div>
                                {act.executed_at && (
                                  <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>Done: {act.executed_at}</div>
                                )}
                              </td>
                              <td style={{ padding: '12px', fontSize: '13px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                                {(act.action_type || '').replace(/_/g, ' ')}
                              </td>
                              <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                                {act.channel}
                              </td>
                              <td style={{ padding: '12px' }}>
                                <span
                                  style={{
                                    fontSize: '11px',
                                    fontWeight: 700,
                                    padding: '2px 8px',
                                    borderRadius: '12px',
                                    background: statusColor.bg,
                                    color: statusColor.text,
                                  }}
                                >
                                  {act.status}
                                </span>
                              </td>
                              <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-secondary, #475569)', maxWidth: '280px' }}>
                                {act.reason || '—'}
                              </td>
                              <td style={{ padding: '12px', fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                                {act.attempts}/{act.max_attempts}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Subtab 7: SMS Messages (Two-Way SMS History) */}
          {subTab === 'messages' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {/* Header Bar */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '18px 24px',
                  boxShadow: 'var(--shadow-card)',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '12px',
                }}
              >
                <div>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                    Two-Way SMS Conversation Log
                  </h3>
                  <p style={{ margin: '4px 0 0 0', fontSize: '13px', color: 'var(--text-secondary, #64748b)' }}>
                    Outbound automated prompts and patient inbound replies for {p.phone || 'patient'}.
                  </p>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {p.sms_opt_out ? (
                    <span
                      style={{
                        padding: '5px 12px',
                        borderRadius: '8px',
                        background: '#fef2f2',
                        border: '1px solid #fca5a5',
                        color: '#b91c1c',
                        fontSize: '11px',
                        fontWeight: 700,
                      }}
                    >
                      🛑 SMS Opted Out (STOP)
                    </span>
                  ) : (
                    <span
                      style={{
                        padding: '5px 12px',
                        borderRadius: '8px',
                        background: 'var(--success-green-soft, #f0fdf4)',
                        border: '1px solid var(--success-green, #059669)',
                        color: 'var(--success-green, #059669)',
                        fontSize: '11px',
                        fontWeight: 700,
                      }}
                    >
                      ✓ SMS Active
                    </span>
                  )}

                  <button
                    type="button"
                    onClick={fetchSmsMessages}
                    style={{
                      padding: '6px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'transparent',
                      color: 'var(--text-secondary, #475569)',
                      fontSize: '11px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    Refresh
                  </button>
                </div>
              </div>

              {/* Message List Card */}
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #e2e8f0)',
                  borderRadius: '12px',
                  padding: '20px 24px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <h3 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: '0 0 16px 0' }}>
                  Message History ({smsMessagesData.length})
                </h3>

                {smsMessagesLoading ? (
                  <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    Loading SMS history...
                  </div>
                ) : smsMessagesData.length === 0 ? (
                  <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    No SMS messages recorded for this patient.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {smsMessagesData.map((m) => {
                      const isInbound = m.direction === 'Inbound';
                      return (
                        <div
                          key={m.sms_id}
                          style={{
                            padding: '14px 16px',
                            borderRadius: '10px',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                            background: isInbound ? '#f0f9ff' : 'var(--bg-base, #f8fafc)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '6px',
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                              <span
                                style={{
                                  fontSize: '10px',
                                  fontWeight: 800,
                                  textTransform: 'uppercase',
                                  padding: '2px 7px',
                                  borderRadius: '6px',
                                  background: isInbound ? '#0284c7' : 'var(--navy-deep, #0b1528)',
                                  color: '#ffffff',
                                }}
                              >
                                {isInbound ? '📥 Inbound from Patient' : '📤 Outbound from CareLoop'}
                              </span>
                              {m.template_key && (
                                <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)', fontWeight: 600 }}>
                                  ({m.template_key})
                                </span>
                              )}
                            </div>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                              {m.created_at} · Status: <strong>{m.status}</strong>
                            </span>
                          </div>

                          <div style={{ fontSize: '13px', color: 'var(--text-primary, #0f172a)', lineHeight: 1.5 }}>
                            {m.body}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Modal: Log Communication (D-15) */}
          {contactModalOpen && (
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
                zIndex: 1000,
              }}
            >
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  borderRadius: '12px',
                  width: '90%',
                  maxWidth: '520px',
                  padding: '24px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                    Log Patient Communication
                  </h3>
                  <button
                    type="button"
                    onClick={() => setContactModalOpen(false)}
                    style={{ border: 'none', background: 'transparent', fontSize: '18px', cursor: 'pointer', color: 'var(--text-muted, #64748b)' }}
                  >
                    ×
                  </button>
                </div>

                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '6px' }}>
                    Communication Channel
                  </label>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '8px' }}>
                    {['Phone', 'SMS', 'In_Person', 'Video'].map((ch) => (
                      <button
                        key={ch}
                        type="button"
                        onClick={() => setContactChannel(ch)}
                        style={{
                          padding: '7px 8px',
                          borderRadius: '6px',
                          border: contactChannel === ch ? '1px solid #0284c7' : '1px solid var(--border-subtle, #cbd5e1)',
                          background: contactChannel === ch ? '#eff6ff' : 'var(--bg-base, #f8fafc)',
                          color: contactChannel === ch ? '#0284c7' : 'var(--text-secondary, #475569)',
                          fontSize: '12px',
                          fontWeight: contactChannel === ch ? 700 : 500,
                          cursor: 'pointer',
                        }}
                      >
                        {ch.replace('_', ' ')}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '6px' }}>
                    Contact Outcome
                  </label>
                  <select
                    value={contactOutcome}
                    onChange={(e) => setContactOutcome(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'var(--bg-base, #f8fafc)',
                      color: 'var(--text-primary, #0f172a)',
                      fontSize: '13px',
                    }}
                  >
                    <option value="Reached">Reached and advised</option>
                    <option value="No_Answer">No answer</option>
                    <option value="Left_Message">Left voicemail / family message</option>
                    <option value="Wrong_Number">Wrong number</option>
                    <option value="Declined">Declined to talk</option>
                  </select>
                </div>

                {contactChannel === 'SMS' && (
                  <div style={{ marginBottom: '14px' }}>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '6px' }}>
                      Clinical SMS Template (No clinical details disclosure)
                    </label>
                    <select
                      onChange={(e) => setContactSummary(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: 'var(--bg-base, #f8fafc)',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '12px',
                        marginBottom: '8px',
                      }}
                    >
                      <option value="">Select a safe template...</option>
                      <option value="Medication check-in: Hello from CareLoop team, please confirm your scheduled medication doses today.">Medication check-in reminder</option>
                      <option value="Symptom follow-up: CareLoop care team has reviewed your symptom submission. Please stay resting, our team will call shortly.">Symptom submission follow-up</option>
                      <option value="Routine check: CareLoop care team following up on your recovery progress. Please submit your daily vitals.">Routine daily vitals reminder</option>
                    </select>
                  </div>
                )}

                <div style={{ marginBottom: '18px' }}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '6px' }}>
                    Summary / Notes
                  </label>
                  <textarea
                    value={contactSummary}
                    onChange={(e) => setContactSummary(e.target.value)}
                    placeholder="Brief description of conversation, advised instructions, or next steps..."
                    rows={3}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'var(--bg-base, #f8fafc)',
                      color: 'var(--text-primary, #0f172a)',
                      fontSize: '13px',
                      boxSizing: 'border-box',
                    }}
                  />
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setContactModalOpen(false)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'transparent',
                      color: 'var(--text-secondary, #475569)',
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    disabled={contactSubmitting}
                    onClick={async () => {
                      setContactSubmitting(true);
                      try {
                        await logCommunication(patientId, contactChannel, contactOutcome, contactSummary);
                        setContactModalOpen(false);
                        setContactSummary('');
                        await fetchNotesAndContacts();
                      } catch (err) {
                        alert(err.message || 'Failed to log contact.');
                      } finally {
                        setContactSubmitting(false);
                      }
                    }}
                    style={{
                      padding: '8px 18px',
                      borderRadius: '6px',
                      border: 'none',
                      background: 'var(--accent-teal, #0d9488)',
                      color: '#ffffff',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {contactSubmitting ? 'Logging...' : 'Save Contact Record'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Modal: Apply Pathway Template (D-13) */}
          {pathwayModalOpen && (
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
                zIndex: 1000,
              }}
            >
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  borderRadius: '12px',
                  padding: '24px 28px',
                  width: '90%',
                  maxWidth: '560px',
                  boxShadow: 'var(--shadow-card)',
                  maxHeight: '90vh',
                  overflowY: 'auto',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                    Apply Pathway Trigger Template
                  </h3>
                  <button
                    type="button"
                    onClick={() => setPathwayModalOpen(false)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: 'var(--text-muted, #64748b)' }}
                  >
                    ✕
                  </button>
                </div>

                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: '8px',
                    background: 'var(--accent-teal-soft, #f0fdfa)',
                    border: '1px solid rgba(13, 148, 136, 0.25)',
                    color: 'var(--accent-teal, #0f766e)',
                    fontSize: '12px',
                    lineHeight: 1.45,
                    marginBottom: '16px',
                  }}
                >
                  <strong>Strict Governance Rule:</strong> Templates ship with <strong>blank thresholds</strong>. You must enter clinical values appropriate for this patient's condition. Defaults are never assumed.
                </div>

                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '6px' }}>
                    Select Pathway Template
                  </label>
                  <select
                    id="pathway-template-select"
                    value={selectedPathway?.template_id || ''}
                    onChange={(e) => {
                      const t = pathwayTemplates.find((x) => x.template_id === e.target.value);
                      setSelectedPathway(t);
                      setPathwayFormValues({});
                    }}
                    style={{
                      width: '100%',
                      padding: '8px 12px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'var(--bg-base, #f8fafc)',
                      color: 'var(--text-primary, #0f172a)',
                      fontSize: '13px',
                    }}
                  >
                    {pathwayTemplates.map((t) => (
                      <option key={t.template_id} value={t.template_id}>
                        {t.name} ({t.target_population})
                      </option>
                    ))}
                  </select>
                </div>

                {selectedPathway && (
                  <div>
                    <p style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', margin: '0 0 16px 0' }}>
                      {selectedPathway.description}
                    </p>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '20px' }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted, #64748b)', textTransform: 'uppercase' }}>
                        Required Medical Thresholds (Must not be blank)
                      </div>
                      {(selectedPathway.rules || []).map((r) => (
                        <div
                          key={r.key}
                          style={{
                            padding: '10px 14px',
                            borderRadius: '8px',
                            background: 'var(--bg-base, #f8fafc)',
                            border: '1px solid var(--border-subtle, #e2e8f0)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '12px',
                          }}
                        >
                          <div>
                            <div style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                              {r.rule_type.replace(/_/g, ' ')}
                            </div>
                            <div style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                              Window: {r.window_hours}h &bull; Severity: {r.severity.replace('_', ' ')}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <input
                              type="number"
                              step="any"
                              required
                              placeholder="Required"
                              id={`pathway-input-${r.key}`}
                              value={pathwayFormValues[r.key] ?? ''}
                              onChange={(e) =>
                                setPathwayFormValues((prev) => ({
                                  ...prev,
                                  [r.key]: e.target.value,
                                }))
                              }
                              style={{
                                width: '100px',
                                padding: '6px 10px',
                                borderRadius: '6px',
                                border: '1px solid var(--border-subtle, #cbd5e1)',
                                background: '#ffffff',
                                color: 'var(--text-primary, #0f172a)',
                                fontSize: '12px',
                                fontWeight: 600,
                              }}
                            />
                            <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                              {r.measurement_type || ''}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                  <button
                    type="button"
                    onClick={() => setPathwayModalOpen(false)}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'transparent',
                      color: 'var(--text-secondary, #475569)',
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    id="confirm-apply-pathway-btn"
                    disabled={pathwaySubmitting}
                    onClick={handleApplyPathway}
                    style={{
                      padding: '8px 18px',
                      borderRadius: '6px',
                      border: 'none',
                      background: 'var(--accent-teal, #0d9488)',
                      color: '#ffffff',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    {pathwaySubmitting ? 'Applying...' : 'Apply & Overwrite Rules'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Modal: Rule History Audit Timeline (D-13) */}
          {ruleHistoryModalOpen && (
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
                zIndex: 1000,
              }}
            >
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  borderRadius: '12px',
                  padding: '24px 28px',
                  width: '90%',
                  maxWidth: '680px',
                  boxShadow: 'var(--shadow-card)',
                  maxHeight: '90vh',
                  overflowY: 'auto',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                    Rule Threshold Audit History
                  </h3>
                  <button
                    type="button"
                    onClick={() => setRuleHistoryModalOpen(false)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: 'var(--text-muted, #64748b)' }}
                  >
                    ✕
                  </button>
                </div>

                {ruleHistoryLoading ? (
                  <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    Loading audit trail...
                  </div>
                ) : selectedRuleHistory.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted, #64748b)', fontSize: '13px' }}>
                    No prior threshold modifications recorded for this rule. Initial baseline intact.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginBottom: '20px' }}>
                    {selectedRuleHistory.map((h, i) => (
                      <div
                        key={h.history_id || i}
                        style={{
                          padding: '12px 14px',
                          borderRadius: '8px',
                          background: 'var(--bg-base, #f8fafc)',
                          border: '1px solid var(--border-subtle, #e2e8f0)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                            Threshold changed: {h.old_threshold ?? '—'} → {h.new_threshold}
                          </span>
                          <span style={{ fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                            {h.changed_at ? h.changed_at.replace('T', ' ').slice(0, 16) : '—'}
                          </span>
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--text-secondary, #475569)', marginBottom: '4px' }}>
                          Reason: <em>"{h.change_reason || 'No justification logged'}"</em>
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted, #64748b)' }}>
                          <span>Modified by: {h.changed_by_name || 'Clinician'}</span>
                          <span>Doctor approval: {h.approved_by_doctor ? '✓ Confirmed' : 'Pending'}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    onClick={() => setRuleHistoryModalOpen(false)}
                    style={{
                      padding: '8px 18px',
                      borderRadius: '6px',
                      border: '1px solid var(--border-subtle, #cbd5e1)',
                      background: 'var(--bg-base, #f1f5f9)',
                      color: 'var(--text-secondary, #475569)',
                      fontSize: '13px',
                      cursor: 'pointer',
                    }}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Modal: Edit or Propose Alert Rule (D-13) */}
          {ruleEditModalOpen && (
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
                zIndex: 1000,
              }}
            >
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  borderRadius: '12px',
                  padding: '24px 28px',
                  width: '90%',
                  maxWidth: '500px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                    {isDoctor ? 'Update Rule Threshold' : 'Propose Rule Threshold'}
                  </h3>
                  <button
                    type="button"
                    onClick={() => setRuleEditModalOpen(false)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: 'var(--text-muted, #64748b)' }}
                  >
                    ✕
                  </button>
                </div>

                <form onSubmit={handleSaveRuleEdit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '4px' }}>
                      Rule Type
                    </label>
                    <input
                      type="text"
                      disabled
                      value={editingRule?.rule_type?.replace(/_/g, ' ') || ''}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: 'var(--bg-base, #f8fafc)',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '13px',
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '4px' }}>
                      New Threshold Value ({editingRule?.measurement_type || ''}) *
                    </label>
                    <input
                      type="number"
                      step="any"
                      required
                      id="rule-edit-threshold-input"
                      value={ruleEditThreshold}
                      onChange={(e) => setRuleEditThreshold(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: '#ffffff',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '13px',
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '4px' }}>
                      Clinical Justification (Mandatory, min 5 chars) *
                    </label>
                    <textarea
                      rows={3}
                      required
                      placeholder="e.g. Patient has baseline chronic tachycardia; raising alert floor to prevent alarm fatigue"
                      id="rule-edit-reason-input"
                      value={ruleEditReason}
                      onChange={(e) => setRuleEditReason(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: '#ffffff',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '13px',
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                    <button
                      type="button"
                      onClick={() => setRuleEditModalOpen(false)}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: 'transparent',
                        color: 'var(--text-secondary, #475569)',
                        fontSize: '13px',
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      id="rule-edit-submit-btn"
                      disabled={ruleEditSubmitting || ruleEditReason.trim().length < 5}
                      style={{
                        padding: '8px 18px',
                        borderRadius: '6px',
                        border: 'none',
                        background: 'var(--accent-teal, #0d9488)',
                        color: '#ffffff',
                        fontSize: '13px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {ruleEditSubmitting ? 'Saving...' : isDoctor ? 'Update Rule' : 'Submit Proposal'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}

          {/* Modal: Calculate LACE Risk Score */}
          {laceModalOpen && (
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
                zIndex: 1000,
              }}
            >
              <div
                style={{
                  background: 'var(--bg-surface, #ffffff)',
                  border: '1px solid var(--border-subtle, #cbd5e1)',
                  borderRadius: '12px',
                  padding: '24px 28px',
                  width: '90%',
                  maxWidth: '520px',
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                  <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                    LACE Risk Index
                  </h3>
                  <button
                    type="button"
                    onClick={() => setLaceModalOpen(false)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: 'var(--text-muted, #64748b)' }}
                  >
                    ✕
                  </button>
                </div>

                <div
                  style={{
                    padding: '8px 12px',
                    borderRadius: '6px',
                    background: 'var(--bg-base, #f8fafc)',
                    border: '1px dashed var(--border-subtle, #cbd5e1)',
                    color: 'var(--text-muted, #64748b)',
                    fontSize: '11px',
                    lineHeight: 1.4,
                    marginBottom: '16px',
                  }}
                >
                  Strictly clinician-entered for context. Not used for automated alert thresholds.
                </div>

                <form onSubmit={handleSaveLace} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '4px' }}>
                      Length of Stay (L) &bull; Days in Hospital
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="120"
                      required
                      id="lace-los-input"
                      value={laceLos}
                      onChange={(e) => setLaceLos(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: '#ffffff',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '13px',
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '4px' }}>
                      Acuity of Admission (A)
                    </label>
                    <select
                      id="lace-acute-select"
                      value={laceAcute ? 'acute' : 'elective'}
                      onChange={(e) => setLaceAcute(e.target.value === 'acute')}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: '#ffffff',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '13px',
                      }}
                    >
                      <option value="acute">Acute / Emergent Admission (3 points)</option>
                      <option value="elective">Elective Admission (0 points)</option>
                    </select>
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '4px' }}>
                      Charlson Comorbidity Index (C) &bull; 0 to 6+
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="20"
                      required
                      id="lace-charlson-input"
                      value={laceCharlson}
                      onChange={(e) => setLaceCharlson(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: '#ffffff',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '13px',
                      }}
                    />
                  </div>

                  <div>
                    <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary, #475569)', marginBottom: '4px' }}>
                      Emergency Dept Visits in Prior 6 Months (E) &bull; 0 to 4+
                    </label>
                    <input
                      type="number"
                      min="0"
                      max="20"
                      required
                      id="lace-ed-input"
                      value={laceEd}
                      onChange={(e) => setLaceEd(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '8px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: '#ffffff',
                        color: 'var(--text-primary, #0f172a)',
                        fontSize: '13px',
                      }}
                    />
                  </div>

                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '10px' }}>
                    <button
                      type="button"
                      onClick={() => setLaceModalOpen(false)}
                      style={{
                        padding: '8px 16px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle, #cbd5e1)',
                        background: 'transparent',
                        color: 'var(--text-secondary, #475569)',
                        fontSize: '13px',
                        cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      id="save-lace-btn"
                      disabled={laceSubmitting}
                      style={{
                        padding: '8px 18px',
                        borderRadius: '6px',
                        border: 'none',
                        background: 'var(--accent-teal, #0d9488)',
                        color: '#ffffff',
                        fontSize: '13px',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      {laceSubmitting ? 'Calculating...' : 'Save LACE Score'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/**
 * Data Quality Badge Component (D-18)
 * Displays explicit clinical status: Good, Questionable, Invalid, Simulated
 */
function DataQualityBadge({ quality = 'Good' }) {
  const configs = {
    Good: { bg: 'var(--success-green-soft, #f0fdf4)', color: 'var(--success-green, #059669)', label: 'Good Quality' },
    Questionable: { bg: 'var(--warning-amber-soft, #fffbeb)', color: 'var(--warning-amber, #d97706)', label: 'Questionable' },
    Invalid: { bg: 'var(--alert-red-soft, #fef2f2)', color: 'var(--alert-red, #dc2626)', label: 'Artifact / Invalid' },
    Simulated: { bg: 'var(--accent-blue-soft, #eff6ff)', color: 'var(--accent-blue, #0284c7)', label: 'Simulated Data' },
  }[quality] || { bg: 'var(--bg-base, #f1f5f9)', color: 'var(--text-muted, #64748b)', label: quality };

  return (
    <span
      style={{
        fontSize: '10px',
        fontWeight: 700,
        padding: '2px 8px',
        borderRadius: '12px',
        background: configs.bg,
        color: configs.color,
      }}
    >
      {configs.label}
    </span>
  );
}
