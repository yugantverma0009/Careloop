import React, { useState, useEffect } from 'react';
import {
  getPatientDetail,
  breakGlassAccess,
  getPatientMedicines,
  getPatientRules,
  getPatientTimeline,
} from '../services/api';
import PatientIdentity from './PatientIdentity';
import {
  IconAlertTriangle,
  IconActivity,
  IconShieldCheck,
  IconPill,
  IconClock,
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
 * 7. Upgraded timeline with day grouping, filter chips, event collapse, and telemetry chart
 */
export default function PatientOverviewTab({
  patientId,
  onBackToDirectory,
  onOpenFlagDrawer,
  user,
}) {
  const [subTab, setSubTab] = useState('overview'); // 'overview', 'medicines', 'rules', 'timeline'
  const [loading, setLoading] = useState(true);
  const [detailData, setDetailData] = useState(null);
  const [medicinesData, setMedicinesData] = useState(null);
  const [rulesData, setRulesData] = useState([]);
  const [timelineData, setTimelineData] = useState(null);

  // Break-glass modal state
  const [breakGlassReason, setBreakGlassReason] = useState('');
  const [breakGlassSubmitting, setBreakGlassSubmitting] = useState(false);
  const [breakGlassError, setBreakGlassError] = useState('');

  // Timeline subtab filters
  const [timelineType, setTimelineType] = useState('All');
  const [timelineRange, setTimelineRange] = useState('all');

  const fetchOverview = async () => {
    setLoading(true);
    try {
      const data = await getPatientDetail(patientId);
      setDetailData(data);
    } catch (err) {
      console.error('Failed to load patient detail:', err);
    } finally {
      setLoading(false);
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

  useEffect(() => {
    fetchOverview();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [patientId]);

  useEffect(() => {
    if (detailData && !detailData.requires_break_glass) {
      if (subTab === 'medicines') fetchMedicines();
      else if (subTab === 'rules') fetchRules();
      else if (subTab === 'timeline') fetchTimeline();
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
            { id: 'overview', label: 'Clinical Overview', Icon: IconActivity },
            { id: 'medicines', label: 'Prescriptions & Adherence', Icon: IconPill },
            { id: 'rules', label: 'Trigger Rules & Limits', Icon: IconShieldCheck },
            { id: 'timeline', label: 'Upgraded Timeline', Icon: IconClock },
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
            This patient is assigned to another clinician's care roster. To view their chart, discharge records, and sensor telemetry, you must declare a valid clinical reason under clinical audit guidelines.
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
                  <div style={{ fontSize: '13px', fontWeight: 800, color: 'var(--text-primary, #0f172a)' }}>
                    Latest Vitals Telemetry
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
                </div>
              </div>

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

              {/* Card 4: Open Flags & Drawer Launcher */}
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
                            {fl.severity.replace('_', ' ')}
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
              <h3 style={{ fontSize: '14px', fontWeight: 800, color: 'var(--text-primary, #0f172a)', margin: '0 0 14px 0' }}>
                Clinician-Approved Trigger Rules (D-05 Rules Tab)
              </h3>
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
                    </tr>
                  </thead>
                  <tbody>
                    {rulesData.map((r) => (
                      <tr key={r.rule_id} style={{ borderBottom: '1px solid var(--border-subtle, #e2e8f0)' }}>
                        <td style={{ padding: '12px', fontSize: '12px', fontWeight: 700, color: 'var(--text-primary, #0f172a)' }}>
                          {r.rule_type.replace(/_/g, ' ')}
                        </td>
                        <td style={{ padding: '12px', fontSize: '12px', color: 'var(--text-secondary, #475569)' }}>
                          {r.threshold_value} {r.measurement_type || ''} {r.window_hours ? `(${r.window_hours}h)` : ''}
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
                            {r.severity.replace('_', ' ')}
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

              {/* Telemetry Chart with Approved Limit Dashed Lines (D-06) */}
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
                      Heart Rate & Telemetry Trend with Approved Rule Limits
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
                {(timelineData?.day_groups || []).map((grp) => (
                  <div
                    key={grp.date}
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
                        justifyContent: 'space-between',
                      }}
                    >
                      <span>{grp.display_date}</span>
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
                ))}
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
